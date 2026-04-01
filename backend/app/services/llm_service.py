import os
import re
import logging
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from functools import lru_cache
from typing import Optional

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

DEFAULT_REPO_ID      = "mistralai/Mistral-7B-Instruct-v0.2"
DEFAULT_TEMPERATURE  = 0.0
DEFAULT_MAX_TOKENS   = 512
EMAIL_MAX_TOKENS     = 300
EMAIL_TEMPERATURE    = 0.2
HISTORY_WINDOW       = 3   # last N turns for answer context
REWRITE_WINDOW       = 1   # FIX: only last 1 turn for query rewriting (prevents context bleed)
MAX_PHRASE_REPEATS   = 2   # FIX: max times a phrase can repeat before cutting off stream

FALLBACK_RESPONSE    = "I do not have enough internal information to answer that."

CONTEXT_BANNED_PATTERNS = [
    "hide details",
    "note:",
    "remember",
    "incorrect answers:",
    "connect to google drive",
    "short_answer:",
    "detailed_answer:",
]

OUTPUT_REMOVE_PATTERNS = [
    r"\bNote\b",
    r"\bRemember\b",
    r"\bUnfortunately\b",
    r"\bHide Details\b",
    r"\bUser Question:\b",
]

BANNED_PHRASES = [
    "Note:",
    "(Code block",
    "[No detailed",
    "Detailed steps",
    "(Details",
    "Incorrect answers:",
    "If the documentation does not",
    "this will not work",
]

# FIX: Phrases that indicate the model is looping/hallucinating if repeated too often
REPETITION_GUARD_PHRASES = [
    "DRQUEST",
    "If the",
    "Without specific",
    "report through",
    "does not provide",
]


# ---------------------------------------------------------------------------
# MODEL FACTORY (CACHED)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def _create_chat_model_cached(
    repo_id: str,
    temperature: float,
    max_new_tokens: int,
) -> ChatHuggingFace:
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        raise EnvironmentError("HF_TOKEN is not set in environment variables.")

    logger.info(f"Initializing model: {repo_id} (temp={temperature}, max_tokens={max_new_tokens})")

    llm = HuggingFaceEndpoint(
        repo_id=repo_id,
        huggingfacehub_api_token=hf_token,
        task="conversational",
        temperature=temperature,
        max_new_tokens=max_new_tokens,
    )
    return ChatHuggingFace(llm=llm)


def create_chat_model(llm_config: Optional[dict] = None) -> ChatHuggingFace:
    cfg = llm_config or {}
    return _create_chat_model_cached(
        repo_id=cfg.get("repo_id", DEFAULT_REPO_ID),
        temperature=float(cfg.get("temperature", DEFAULT_TEMPERATURE)),
        max_new_tokens=int(cfg.get("max_new_tokens", DEFAULT_MAX_TOKENS)),
    )


# ---------------------------------------------------------------------------
# CONTEXT CLEANING
# ---------------------------------------------------------------------------

def clean_context(context: str) -> str:
    """
    Remove noise from retrieved documentation before sending to the model.
    Drops banned patterns, very short lines, and duplicates.
    """
    if not context or not context.strip():
        logger.warning("clean_context received empty context.")
        return ""

    seen = set()
    cleaned_lines = []

    for line in context.split("\n"):
        line = line.strip()

        if not line or len(line) < 3:
            continue

        if any(p in line.lower() for p in CONTEXT_BANNED_PATTERNS):
            continue

        if line in seen:
            continue

        seen.add(line)
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    logger.debug(f"clean_context: {len(context)} → {len(cleaned)} chars after cleaning.")
    return cleaned


# ---------------------------------------------------------------------------
# FINAL OUTPUT CLEANING
# ---------------------------------------------------------------------------

def clean_final_output(text: str) -> str:
    """
    Remove unwanted words/phrases from model output using word-boundary regex.
    """
    for pattern in OUTPUT_REMOVE_PATTERNS:
        text = re.sub(pattern, "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# FORMAT ENFORCEMENT
# ---------------------------------------------------------------------------

def enforce_format(output: str) -> str:
    """
    Ensure model output strictly follows SHORT_ANSWER / DETAILED_ANSWER format.
    Returns FALLBACK_RESPONSE if format is missing or malformed.

    FIX: Previously crashed with 'not enough values to unpack' when the model
         returned only SHORT_ANSWER: without DETAILED_ANSWER: (e.g. when it
         responded with the fallback sentence mid-stream and was cut off).
         Now handles each section independently so a missing DETAILED_ANSWER
         section returns FALLBACK_RESPONSE cleanly instead of raising.
    """
    output = output.strip()

    has_short    = "SHORT_ANSWER:" in output
    has_detailed = "DETAILED_ANSWER:" in output

    # If neither section present, check for plain fallback text then return
    if not has_short and not has_detailed:
        logger.warning("enforce_format: both sections missing.")
        return FALLBACK_RESPONSE

    try:
        # Anchor to first SHORT_ANSWER: occurrence
        if has_short:
            output = "SHORT_ANSWER:" + output.split("SHORT_ANSWER:")[-1]

        # FIX: split safely — if DETAILED_ANSWER: is missing, parts will have len==1
        #      Original code did: short_raw, detailed_raw = output.split(..., 1)
        #      which raises ValueError when there's only 1 element.
        parts = output.split("DETAILED_ANSWER:", 1)

        if len(parts) == 1:
            # Only SHORT_ANSWER present — extract it and return fallback
            # (model was truncated or gave a one-liner without details)
            short_part = parts[0].replace("SHORT_ANSWER:", "").strip()
            if short_part:
                logger.warning("enforce_format: DETAILED_ANSWER missing; returning short only.")
                return f"SHORT_ANSWER:\n{short_part}\n\nDETAILED_ANSWER:\n{FALLBACK_RESPONSE}"
            return FALLBACK_RESPONSE

        short_raw, detailed_raw = parts
        short_part    = short_raw.replace("SHORT_ANSWER:", "").strip()
        detailed_part = detailed_raw.strip()

        if not short_part or not detailed_part:
            logger.warning("enforce_format: empty SHORT or DETAILED section.")
            return FALLBACK_RESPONSE

        # Deduplicate lines while preserving order
        seen: set[str] = set()
        cleaned_lines = []
        for line in detailed_part.split("\n"):
            line = line.strip()
            if line and line not in seen:
                cleaned_lines.append(line)
                seen.add(line)

        return (
            "SHORT_ANSWER:\n"
            + short_part
            + "\n\nDETAILED_ANSWER:\n"
            + "\n".join(cleaned_lines)
        ).strip()

    except Exception as e:
        logger.error(f"enforce_format error: {e}")
        return FALLBACK_RESPONSE


# ---------------------------------------------------------------------------
# BUILD HISTORY MESSAGES
# ---------------------------------------------------------------------------

def _build_history_messages(history: Optional[list], window: int = HISTORY_WINDOW) -> list:
    """
    Convert raw history dicts to LangChain message objects.
    Limits to last `window` turns (default: HISTORY_WINDOW).
    FIX: accepts window param so rewrite vs answer can use different limits.
    """
    messages = []
    if not history or not isinstance(history, list):
        return messages

    for msg in history[-window:]:
        role    = msg.get("role", "").lower()
        content = msg.get("content", "").strip()

        if not content:
            continue

        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            logger.debug(f"_build_history_messages: skipping unknown role '{role}'")

    return messages



def _inject_topic_from_history(user_query: str, history: Optional[list]) -> str:
    """
    When rewrite_query fails or returns a bloated result, extract the last
    meaningful topic word from history and inject it in place of pronouns.

    Example:
      history last assistant msg: "JCore is a publishing platform..."
      user_query: "who manages it"
      result:     "who manages JCore"

    This is a cheap string operation — no LLM call needed.
    """
    if not history or not isinstance(history, list):
        return user_query

    # Find the last assistant message
    last_topic = None
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            # Extract first capitalised word that looks like a product/platform name
            # (longer than 3 chars, not a common sentence-starter)
            # Skip only generic sentence-starter words, NOT product names.
            # "jcore" and "highwire" must NOT be skipped — they are the exact
            # topics we want to inject into follow-up queries like "who manages it".
            SKIP_WORDS = {
                "the", "this", "that", "there", "their", "these", "those",
                "with", "from", "into", "also", "both", "each", "more",
                "short_answer", "detailed_answer",
            }
            words = content.split()
            for word in words:
                cleaned = word.strip(".,;:()")
                if (
                    len(cleaned) > 3
                    and cleaned[0].isupper()
                    and cleaned.lower() not in SKIP_WORDS
                ):
                    last_topic = cleaned
                    break
            # If nothing found with above heuristic, fall back to first noun-like word
            if not last_topic:
                for word in words:
                    cleaned = word.strip(".,;:()")
                    if len(cleaned) > 3 and cleaned.lower() not in SKIP_WORDS:
                        last_topic = cleaned
                        break
            if last_topic:
                logger.info(f"_inject_topic_from_history: picked topic='{last_topic}'")
                break

    if not last_topic:
        logger.warning("_inject_topic_from_history: no topic found in history, returning original query.")
        return user_query

    # Replace trailing pronouns in the query
    PRONOUN_REPLACEMENTS = {
        " it": f" {last_topic}",
        " its": f" {last_topic}'s",
        " they": f" {last_topic}",
        " them": f" {last_topic}",
        " this": f" {last_topic}",
        " that": f" {last_topic}",
    }
    result = f" {user_query.lower()}"
    for pronoun, replacement in PRONOUN_REPLACEMENTS.items():
        result = result.replace(pronoun, replacement)

    result = result.strip()
    logger.info(f"_inject_topic_from_history: '{user_query}' → '{result}' (topic: {last_topic})")
    return result


# ---------------------------------------------------------------------------
# QUERY REWRITING
# ---------------------------------------------------------------------------

def rewrite_query(
    user_query: str,
    history: Optional[list],
    llm_config: Optional[dict] = None,
) -> str:
    """
    Rewrite a user query into a standalone technical search query,
    resolving references using recent history.

    FIX 1: Uses REWRITE_WINDOW (1 turn) instead of HISTORY_WINDOW (3 turns)
            to prevent prior topic context bleeding into the rewritten query.
    FIX 2: Skip rewrite entirely if the query has no pronouns / ambiguous refs
            (e.g. "what is jcore?" is already standalone — rewriting it caused
            the model to inject previous context and produce a bloated query like
            "Could you please provide more information about what jcore is in the
            context of the given conversation..." which then retrieved wrong chunks).
    """
    if not user_query or not user_query.strip():
        logger.warning("rewrite_query: received empty query.")
        return ""

    # FIX 2: if query contains no pronouns that need resolving, skip the LLM call
    PRONOUN_TRIGGERS = {"it", "its", "they", "them", "their", "this", "that", "he", "she", "those", "these"}
    query_words = set(user_query.lower().split())
    if not query_words & PRONOUN_TRIGGERS:
        logger.info(f"rewrite_query: no pronouns detected, skipping rewrite for '{user_query}'")
        return user_query

    chat_model = create_chat_model(llm_config)

    history_summary = ""
    if history and isinstance(history, list):
        # FIX 1: was history[-HISTORY_WINDOW:] — using only last 1 turn now
        history_summary = "\n".join(
            f"{m['role']}: {m['content']}" for m in history[-REWRITE_WINDOW:]
        )

    prompt = (
        "Given the following conversation and a follow-up question, "
        "rephrase the follow-up question to be a standalone question "
        "by resolving pronouns (like 'it', 'they', 'this') to the actual subject. "
        "DO NOT add extra information or search keywords from previous answers. "
        "Output ONLY the rewritten question. No explanation. No prefix.\n\n"
        f"Chat History:\n{history_summary}\n\n"
        f"Follow-up Question: {user_query}\n\n"
        "Standalone Question:"
    )

    try:
        response  = chat_model.invoke([HumanMessage(content=prompt)])
        rewritten = response.content.strip().rstrip("?").strip()

        # Safety: if rewrite is suspiciously long (model rambled), use topic injection
        if len(rewritten) > len(user_query) * 4:
            logger.warning(f"rewrite_query: rewrite too long ({len(rewritten)} chars), injecting topic.")
            return _inject_topic_from_history(user_query, history)

        logger.info(f"rewrite_query: '{user_query}' → '{rewritten}'")
        return rewritten or user_query
    except Exception as e:
        logger.error(f"rewrite_query error: {e}")
        # FIX: on any error, still try topic injection rather than returning bare query
        return _inject_topic_from_history(user_query, history)


# ---------------------------------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the MPS Support Assistant.

STRICT RULES:
- Answer ONLY using the provided DOCUMENTATION below.
- Do NOT use prior knowledge or training data.
- Do NOT invent names, people, teams, or organisations.
- Do NOT guess or infer anything not explicitly stated in the DOCUMENTATION.
- If the DOCUMENTATION does not contain the answer, respond ONLY with the fallback.
- Never truncate URLs — always include them in full.

ANTI-HALLUCINATION RULE (critical):
If you cannot find the answer word-for-word or concept-for-concept in the
DOCUMENTATION, do NOT attempt to answer. Write the fallback sentence below.
Do NOT name any person, team, or organisation unless they appear in the DOCUMENTATION.

FALLBACK (copy exactly when answer is not in documentation):
I do not have enough internal information to answer that.

FORMAT (MANDATORY — no exceptions):

SHORT_ANSWER:
One or two sentences directly answering the question.

DETAILED_ANSWER:
1. First step or detail
2. Second step or detail
3. Continue as needed

RULES:
- Always begin with SHORT_ANSWER:
- Always follow with DETAILED_ANSWER:
- No markdown headers (###), no HTML tags, no extra sections.
- Do not repeat the question.
- Stop immediately after DETAILED_ANSWER content.
"""



# ---------------------------------------------------------------------------
# ANSWER GENERATION (WITH STREAMING)
# ---------------------------------------------------------------------------

def get_answers(
    history: Optional[list],
    context: str,
    user_query: str,
    llm_config: Optional[dict] = None,
):
    """
    Generate a structured answer from documentation context.
    Streams tokens, then yields the final cleaned + formatted response.

    FIX 1: Removed the bug where config["max_new_tokens"] and config["temperature"]
            were set from llm_config then immediately overwritten with defaults.
    FIX 2: enforce_format + clean_final_output now applied to the full response.
    FIX 3: Repetition guard added to catch looping model output mid-stream.
    FIX 4: History window uses HISTORY_WINDOW (not REWRITE_WINDOW) for answer context.
    """
    if not user_query or not user_query.strip():
        yield FALLBACK_RESPONSE
        return

    if not context or not context.strip():
        logger.warning("get_answers: empty context received.")
        yield FALLBACK_RESPONSE
        return

    # FIX 1: was overwriting llm_config values with defaults unconditionally
    config = {
        "max_new_tokens": DEFAULT_MAX_TOKENS,
        "temperature": DEFAULT_TEMPERATURE,
        **(llm_config or {}),
    }
    # REMOVED the two lines that re-set max_new_tokens and temperature after merging

    chat_model = create_chat_model(config)
    context    = clean_context(context)

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    # FIX 4: pass window explicitly so answer uses full HISTORY_WINDOW
    messages.extend(_build_history_messages(history, window=HISTORY_WINDOW))
    # FIX: Zephyr-7b frequently ignores format rules in the system prompt alone.
    # Repeating the format requirement directly in the user message forces compliance.
    FORMAT_REMINDER = (
        "\n\nCRITICAL RULES — follow exactly:\n"
        "1. Use ONLY information from the DOCUMENTATION above.\n"
        "2. Do NOT invent or assume any names, people, or organisations.\n"
        "3. If the answer is not explicitly in the DOCUMENTATION, write ONLY:\n"
        "   I do not have enough internal information to answer that.\n"
        "\n"
        "Your response MUST use this exact format:\n"
        "SHORT_ANSWER:\n<one or two sentences from the documentation>\n\n"
        "DETAILED_ANSWER:\n1. <first detail>\n2. <second detail>\n..."
    )
    messages.append(
        HumanMessage(
            content=(
                f"DOCUMENTATION:\n{context}"
                f"\n\nQUERY:\n{user_query}"
                f"{FORMAT_REMINDER}"
            )
        )
    )

    try:
        logger.info(f"get_answers: streaming for query='{user_query[:60]}...'")
        full_response = ""

        for chunk in chat_model.stream(messages):
            token = chunk.content
            if not token:
                continue

            # Existing banned phrase check
            if any(phrase in token for phrase in BANNED_PHRASES):
                logger.warning(f"get_answers: banned phrase hit, stopping stream.")
                break

            full_response += token

            # FIX 3: repetition guard — stop if any guard phrase appears too many times
            if any(
                full_response.count(phrase) > MAX_PHRASE_REPEATS
                for phrase in REPETITION_GUARD_PHRASES
            ):
                logger.warning("get_answers: repetition guard triggered, stopping stream.")
                break

        logger.info("get_answers: streaming complete, applying format enforcement.")

        # FIX 2: apply format enforcement and output cleaning on full response
        final = enforce_format(full_response)
        final = clean_final_output(final)

        yield final

    except Exception as e:
        logger.error(f"get_answers error: {e}")
        yield f"Error generating response: {e}"


# ---------------------------------------------------------------------------
# TICKET INTENT DETECTION
# ---------------------------------------------------------------------------

# Keyword-based ticket intent detection — no LLM call needed.
# This avoids burning HuggingFace quota on a simple classification task
# that a small keyword set handles reliably.
TICKET_INTENT_KEYWORDS = [
    "create a ticket", "open a ticket", "raise a ticket", "submit a ticket",
    "create ticket", "open ticket", "raise ticket", "submit ticket",
    "log a ticket", "log ticket", "file a ticket", "file ticket",
    "create a case", "open a case", "raise a case", "submit a case",
    "need help", "report an issue", "report issue", "escalate",
    "support request", "raise an issue", "raise issue",
]


def detect_ticket_intent(
    user_message: str,
    llm_config: Optional[dict] = None,
) -> bool:
    """
    Returns True if the user's message indicates intent to create a support ticket.

    FIX: Replaced LLM call with fast keyword matching.
         The original LLM call fired on EVERY message, consuming HuggingFace
         quota and causing 503 errors under load. Keyword matching is instant,
         free, and accurate enough for this binary classification task.
    """
    if not user_message or not user_message.strip():
        return False

    msg_lower = user_message.lower().strip()
    intent = any(kw in msg_lower for kw in TICKET_INTENT_KEYWORDS)
    logger.info(f"detect_ticket_intent (keyword): '{user_message[:40]}' → {intent}")
    return intent


# ---------------------------------------------------------------------------
# EMAIL REPLY GENERATION
# ---------------------------------------------------------------------------

EMAIL_SYSTEM_PROMPT = """You are a professional and helpful MPS Support Assistant.

Write a clear, human-like email reply.

RULES:
- Start with "Hello,"
- Directly answer the user's question if the answer is available
- Be concise and natural (no robotic phrases)
- Do NOT say "we will get back to you" if you already answered
- Only mention support team if answer is NOT available
- Avoid unnecessary formal phrases like "we appreciate your patience"
- Keep it within 5–6 lines

End with:
Regards,
MPS Support Team
"""

def generate_email_reply(
    email_subject: str,
    email_body: str,
    llm_config: Optional[dict] = None,
) -> str:
    """
    Generate a professional, empathetic email reply for a customer support request.
    """
    if not email_subject or not email_body:
        logger.warning("generate_email_reply: missing subject or body.")
        return "Error: email subject and body are required."

    config     = {"max_new_tokens": EMAIL_MAX_TOKENS, "temperature": EMAIL_TEMPERATURE, **(llm_config or {})}
    chat_model = create_chat_model(config)
    prompt     = f"Customer Email:\nSubject: {email_subject}\nMessage: {email_body}"

    try:
        logger.info(f"generate_email_reply: subject='{email_subject}'")
        response = chat_model.invoke([
            SystemMessage(content=EMAIL_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        return response.content.strip()
    except Exception as e:
        logger.error(f"generate_email_reply error: {e}")
        return f"Error generating email reply: {e}"


# ---------------------------------------------------------------------------
# CATEGORY DETECTION
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# CATEGORY KEYWORD MAP
# ---------------------------------------------------------------------------
# Keyword-based category detection — no LLM call needed.
# Replaces the previous LLM classifier that consumed quota on every message
# and caused 503 errors. Each entry maps a category to its trigger keywords.

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "chrome_extension": [
        "chrome", "extension", "crx", "developer mode", "load unpacked",
        "highwire extension", "browser extension", "chrome://extensions",
    ],
    "jcore_platform": [
        "jcore", "j-core", "publishing platform", "article discovery",
        "user engagement", "jcore prime", "jcore configuration",
    ],
    "ecommerce_setup": [
        "ecommerce", "e-commerce", "shop", "payment", "checkout",
        "store", "purchase", "subscription", "billing",
    ],
    "site_operations": [
        "site down", "outage", "deploy", "deployment", "server",
        "site name", "production", "staging", "environment", "hosting",
    ],
    "escalation_process": [
        "escalate", "escalation", "ticket", "support case", "drquest",
        "raise issue", "report issue", "open case",
    ],
    "platform_overview": [
        "highwire", "platform", "overview", "architecture", "maximus",
        "what is highwire", "highwire press",
    ],
}


def detect_category(user_query: str, llm_config: Optional[dict] = None) -> str:
    """
    Classify the user query into a predefined support category using keywords.

    FIX: Replaced LLM call (max_tokens=15) with keyword matching.
         The log showed 'Initializing model... max_tokens=15' on every message,
         burning HuggingFace quota for a task that simple keywords handle well.
         Falls back to 'general' if no keywords match.
    """
    if not user_query:
        return "general"

    q = user_query.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            logger.info(f"detect_category (keyword): '{user_query[:40]}' → {category}")
            return category

    logger.info(f"detect_category (keyword): '{user_query[:40]}' → general (no match)")
    return "general"