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

DEFAULT_REPO_ID      = "HuggingFaceH4/zephyr-7b-beta"
DEFAULT_TEMPERATURE  = 0.0
DEFAULT_MAX_TOKENS   = 512
EMAIL_MAX_TOKENS     = 300
EMAIL_TEMPERATURE    = 0.2
HISTORY_WINDOW       = 3  # last N turns to include

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
    """
    if "SHORT_ANSWER:" not in output or "DETAILED_ANSWER:" not in output:
        logger.warning("enforce_format: required format sections missing.")
        return FALLBACK_RESPONSE

    try:
        output = "SHORT_ANSWER:" + output.split("SHORT_ANSWER:")[-1]
        short_raw, detailed_raw = output.split("DETAILED_ANSWER:", 1)

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

def _build_history_messages(history: Optional[list]) -> list:
    """
    Convert raw history dicts to LangChain message objects.
    Limits to last HISTORY_WINDOW turns.
    """
    messages = []
    if not history or not isinstance(history, list):
        return messages

    for msg in history[-HISTORY_WINDOW:]:
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
    """
    if not user_query or not user_query.strip():
        logger.warning("rewrite_query: received empty query.")
        return ""

    chat_model = create_chat_model(llm_config)

    history_summary = ""
    if history and isinstance(history, list):
        history_summary = "\n".join(
            f"{m['role']}: {m['content']}" for m in history[-HISTORY_WINDOW:]
        )

    prompt = (
        "Rewrite the user query into a clear standalone technical search query "
        "for a documentation database. Remove filler words. Keep it concise.\n\n"
        f"Chat History:\n{history_summary}\n\n"
        f"User Question:\n{user_query}\n\n"
        "Search Query:"
    )

    try:
        response = chat_model.invoke([HumanMessage(content=prompt)])
        rewritten = response.content.strip().rstrip("?").strip()
        logger.info(f"rewrite_query: '{user_query}' → '{rewritten}'")
        return rewritten or user_query
    except Exception as e:
        logger.error(f"rewrite_query error: {e}")
        return user_query


# ---------------------------------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the MPS Support Assistant.

STRICT RULES:
- Answer ONLY using the provided documentation.
- Do NOT use prior knowledge.
- Do NOT guess or infer missing information.
- If this is a follow-up question, answer only the new part.
- Never truncate URLs — always include them in full.

If the answer is not in the documentation, respond ONLY with:
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
    Streams tokens using the same pattern as the original working version.
    """
    if not user_query or not user_query.strip():
        yield FALLBACK_RESPONSE
        return

    if not context or not context.strip():
        logger.warning("get_answers: empty context received.")
        yield FALLBACK_RESPONSE
        return

    config = {
        "max_new_tokens": DEFAULT_MAX_TOKENS,
        "temperature": DEFAULT_TEMPERATURE,
        **(llm_config or {}),
    }
    config["max_new_tokens"] = DEFAULT_MAX_TOKENS
    config["temperature"]    = DEFAULT_TEMPERATURE

    chat_model = create_chat_model(config)
    context    = clean_context(context)

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(_build_history_messages(history))
    messages.append(
        HumanMessage(content=f"DOCUMENTATION:\n{context}\n\nQUERY:\n{user_query}")
    )

    try:
        logger.info(f"get_answers: streaming for query='{user_query[:60]}...'")
        full_response = ""

        for chunk in chat_model.stream(messages):
            token = chunk.content
            if not token:
                continue
            if any(phrase in token for phrase in BANNED_PHRASES):
                break
            full_response += token
            yield token

        logger.info("get_answers: streaming complete.")

    except Exception as e:
        logger.error(f"get_answers error: {e}")
        yield f"Error generating response: {e}"


# ---------------------------------------------------------------------------
# TICKET INTENT DETECTION
# ---------------------------------------------------------------------------

def detect_ticket_intent(
    user_message: str,
    llm_config: Optional[dict] = None,
) -> bool:
    """
    Returns True if the user's message indicates intent to create a support ticket.
    """
    if not user_message or not user_message.strip():
        return False

    chat_model = create_chat_model(llm_config)

    prompt = (
        f'Does the following message indicate the user wants to create a support ticket?\n\n'
        f'Message: "{user_message}"\n\n'
        'Reply with exactly one word: YES or NO.'
    )

    try:
        response = chat_model.invoke([HumanMessage(content=prompt)])
        result   = response.content.strip().upper().rstrip(".").strip()
        intent   = "YES" in result
        logger.info(f"detect_ticket_intent: '{user_message[:40]}...' → {intent}")
        return intent
    except Exception as e:
        logger.error(f"detect_ticket_intent error: {e}")
        return False


# ---------------------------------------------------------------------------
# EMAIL REPLY GENERATION
# ---------------------------------------------------------------------------

EMAIL_SYSTEM_PROMPT = """You are a professional MPS Support Assistant writing customer email replies.

Guidelines:
- Start with "Hello,"
- Acknowledge the specific issue mentioned
- Show genuine empathy
- Do NOT provide troubleshooting steps
- Do NOT promise resolution timelines
- Inform the customer that the support team will review their issue
- Keep the reply to 5–6 lines maximum

End every reply with:
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

def detect_category(user_query: str, llm_config: Optional[dict] = None) -> str:
    """
    Classify the user query into a predefined support category.
    Uses a tiny token limit for fast classification.
    """
    classification_config = {"max_new_tokens": 15, "temperature": 0.0}
    if llm_config:
        classification_config.update(llm_config)

    chat_model = create_chat_model(classification_config)

    prompt = f"""Classify into exactly ONE category:
- chrome_extension
- escalation_process
- ecommerce_setup
- jcore_platform
- site_operations
- platform_overview
- general

Question: "{user_query}"
Reply with ONLY the category name."""

    try:
        response = chat_model.invoke([HumanMessage(content=prompt)])
        category = re.sub(r'[^a-z_]', '', response.content.strip().lower())

        valid = [
            "chrome_extension", "escalation_process", "ecommerce_setup",
            "jcore_platform", "site_operations", "platform_overview", "general"
        ]

        for v in valid:
            if v in category:
                return v
        return "general"
    except Exception as e:
        logger.error(f"detect_category error: {e}")
        return "general"