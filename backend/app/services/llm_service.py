import os
import re
import logging
from dotenv import load_dotenv
from langchain_groq import ChatGroq
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

DEFAULT_REPO_ID      = "llama-3.1-8b-instant"
DEFAULT_TEMPERATURE  = 0.0
DEFAULT_MAX_TOKENS   = 4096  # Increased for more detailed responses
EMAIL_MAX_TOKENS     = 300
EMAIL_TEMPERATURE    = 0.2
HISTORY_WINDOW       = 3
REWRITE_WINDOW       = 1
MAX_PHRASE_REPEATS   = 2

FALLBACK_RESPONSE    = "I do not have enough internal information to answer that."

# ✅ IMAGE_REF lines must NEVER be stripped from context
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

REPETITION_GUARD_PHRASES = [
    "DRQUEST",
    "If the",
    "Without specific",
    "report through",
    "does not provide",
]

TICKET_INTENT_KEYWORDS = [
    "create a ticket", "open a ticket", "raise a ticket", "submit a ticket",
    "create ticket", "open ticket", "raise ticket", "submit ticket",
    "log a ticket", "log ticket", "file a ticket", "file ticket",
    "create a case", "open a case", "raise a case", "submit a case",
    "need help", "report an issue", "report issue", "escalate",
    "support request", "raise an issue", "raise issue",
]

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
        "fragr", "restart", "semantico", "h10", "hwmaint",
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


# ---------------------------------------------------------------------------
# MODEL FACTORY (CACHED)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def _create_chat_model_cached(
    repo_id: str,
    temperature: float,
    max_new_tokens: int,
) -> ChatGroq:
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise EnvironmentError("GROQ_API_KEY is not set.")

    logger.info(f"Initializing model: {repo_id} (temp={temperature}, max_tokens={max_new_tokens})")

    return ChatGroq(
        model=repo_id,
        temperature=temperature,
        max_tokens=max_new_tokens,
        api_key=groq_key,
    )


def create_chat_model(llm_config: Optional[dict] = None) -> ChatGroq:
    cfg = llm_config or {}

    repo_id     = cfg.get("repo_id", DEFAULT_REPO_ID)
    temperature = float(cfg.get("temperature", DEFAULT_TEMPERATURE))
    max_tokens  = int(cfg.get("max_new_tokens", DEFAULT_MAX_TOKENS))

    GROQ_SUPPORTED = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"]
    if repo_id not in GROQ_SUPPORTED:
        logger.warning(f"Unsupported model '{repo_id}', overriding to {DEFAULT_REPO_ID}")
        repo_id = DEFAULT_REPO_ID

    if max_tokens < 500:
        logger.warning(f"max_tokens={max_tokens} too low, overriding to {DEFAULT_MAX_TOKENS}")
        max_tokens = DEFAULT_MAX_TOKENS

    return _create_chat_model_cached(
        repo_id=repo_id,
        temperature=temperature,
        max_new_tokens=max_tokens,
    )


# ---------------------------------------------------------------------------
# CONTEXT CLEANING
# ✅ KEY FIX: [IMAGE_REF:url] lines are ALWAYS preserved
# ---------------------------------------------------------------------------

def clean_context(context: str) -> str:
    if not context or not context.strip():
        logger.warning("clean_context received empty context.")
        return ""

    seen = set()
    cleaned_lines = []

    for line in context.split("\n"):
        line = line.strip()

        # ✅ Always keep image reference lines — never filter them
        if line.startswith("[IMAGE_REF:") and line.endswith("]"):
            if line not in seen:
                cleaned_lines.append(line)
                seen.add(line)
            continue

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
# EXTRACT IMAGE REFS FROM CONTEXT
# ---------------------------------------------------------------------------

def extract_image_refs(context: str) -> list:
    """Extract all [IMAGE_REF:url] markers from context."""
    if not context:
        return []
    
    pattern = r'\[IMAGE_REF:(https?://[^\]]+)\]'
    matches = re.findall(pattern, context)
    
    logger.info(f"extract_image_refs: found {len(matches)} image(s) in context")
    return matches


# ---------------------------------------------------------------------------
# FINAL OUTPUT CLEANING
# ---------------------------------------------------------------------------

def clean_final_output(text: str) -> str:
    for pattern in OUTPUT_REMOVE_PATTERNS:
        text = re.sub(pattern, "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# FORMAT ENFORCEMENT
# ---------------------------------------------------------------------------

def enforce_format(output: str) -> str:
    output = output.strip()

    has_short    = "SHORT_ANSWER:" in output
    has_detailed = "DETAILED_ANSWER:" in output

    if not has_short and not has_detailed:
        logger.warning("enforce_format: both sections missing.")
        return FALLBACK_RESPONSE

    try:
        if has_short:
            output = "SHORT_ANSWER:" + output.split("SHORT_ANSWER:")[-1]

        parts = output.split("DETAILED_ANSWER:", 1)

        if len(parts) == 1:
            short_part = parts[0].replace("SHORT_ANSWER:", "").strip()
            if short_part:
                logger.warning("enforce_format: DETAILED_ANSWER missing; returning short only.")
                return (
                    f"SHORT_ANSWER:\n{short_part}\n\n"
                    f"DETAILED_ANSWER:\n{FALLBACK_RESPONSE}"
                )
            return FALLBACK_RESPONSE

        short_raw, detailed_raw = parts
        short_part    = short_raw.replace("SHORT_ANSWER:", "").strip()
        detailed_part = detailed_raw.strip()

        if not has_short and not has_detailed:
            logger.warning("Format missing → using raw output")
            return (
                "SHORT_ANSWER:\n"
                + output[:200]
                + "\n\nDETAILED_ANSWER:\n"
                + output
            ).strip()

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
    messages = []

    if not history or not isinstance(history, list):
        return messages

    last_role = None

    for msg in history[-window:]:
        role    = msg.get("role", "").lower()
        content = msg.get("content", "").strip()

        if not content:
            continue
        if role not in ("user", "assistant"):
            continue
        if role == last_role:
            continue

        if role == "user":
            messages.append(HumanMessage(content=content))
            last_role = "user"
        elif role == "assistant":
            messages.append(AIMessage(content=content))
            last_role = "assistant"

    if messages and not isinstance(messages[0], HumanMessage):
        messages = messages[1:]

    return messages


# ---------------------------------------------------------------------------
# TOPIC INJECTION
# ---------------------------------------------------------------------------

def _inject_topic_from_history(user_query: str, history: Optional[list]) -> str:
    if not history or not isinstance(history, list):
        return user_query

    last_topic = None

    for msg in reversed(history):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")

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
    if not user_query or not user_query.strip():
        logger.warning("rewrite_query: received empty query.")
        return ""

    PRONOUN_TRIGGERS = {
        "it", "its", "they", "them", "their", "this", "that",
        "he", "she", "those", "these"
    }

    clean_query = re.sub(r'[^\w\s]', '', user_query.lower())
    query_words = set(clean_query.split())

    if not query_words & PRONOUN_TRIGGERS:
        logger.info(f"rewrite_query: no pronouns detected, skipping rewrite for '{user_query}'")
        return user_query

    chat_model = create_chat_model(llm_config)

    history_summary = ""
    if history and isinstance(history, list):
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

        if len(rewritten) > len(user_query) * 4:
            logger.warning(f"rewrite_query: rewrite too long ({len(rewritten)} chars), injecting topic.")
            return _inject_topic_from_history(user_query, history)

        logger.info(f"rewrite_query: '{user_query}' → '{rewritten}'")

        return rewritten or user_query

    except Exception as e:
        logger.error(f"rewrite_query error: {e}")
        return _inject_topic_from_history(user_query, history)


# ---------------------------------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the MPS Support Assistant.

STRICT RULES:
- Answer ONLY using the provided DOCUMENTATION.
- Do NOT use prior knowledge or training data.
- If the DOCUMENTATION does not contain the answer, respond ONLY with:
  "I do not have enough internal information to answer that."

🖼️ IMAGE HANDLING (CRITICAL):
- The DOCUMENTATION may contain lines like: [IMAGE_REF:https://example.com/image.png]
- These are image references that MUST be included in your response
- Copy EVERY [IMAGE_REF:...] line EXACTLY as it appears
- Place them at the END of your DETAILED_ANSWER section
- Do NOT modify, skip, or paraphrase these lines
- Include ALL image references, even if there are many

- Provide comprehensive, detailed explanations with step-by-step instructions when available.
- Include all relevant information from the documentation.

FORMAT (MANDATORY):
SHORT_ANSWER:
<2-3 sentences summarizing the key points>

DETAILED_ANSWER:
<Provide comprehensive explanation with:>
- Step-by-step instructions (numbered)
- Important details and context
- Any warnings or notes
<Then copy ALL [IMAGE_REF:...] lines from documentation here>"""


# ---------------------------------------------------------------------------
# ANSWER GENERATION (STREAMING)
# ---------------------------------------------------------------------------

def get_answers(
    history: Optional[list],
    context: str,
    user_query: str,
    llm_config: Optional[dict] = None,
):
    """
    Streams text tokens from the LLM.
    Yields plain text strings token by token.
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

    chat_model = create_chat_model(config)
    context    = clean_context(context)

    # Extract image URLs from context
    image_urls = extract_image_refs(context)

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(_build_history_messages(history, window=HISTORY_WINDOW))

    FORMAT_REMINDER = (
        "\n\n🚨 CRITICAL RULES — follow exactly:\n"
        "1. Use ONLY information from the DOCUMENTATION above.\n"
        "2. Do NOT invent or assume any names, people, or organisations.\n"
        "3. If the answer is not explicitly in the DOCUMENTATION, write ONLY:\n"
        "   I do not have enough internal information to answer that.\n"
        "\n"
        "4. 🖼️ IMAGE RULE (MANDATORY):\n"
        "   - If you see ANY lines starting with [IMAGE_REF: in the DOCUMENTATION\n"
        "   - You MUST copy them EXACTLY into your DETAILED_ANSWER section\n"
        "   - Copy the COMPLETE line including the brackets and URL\n"
        "   - Example: [IMAGE_REF:https://example.com/image.png]\n"
        "   - Place all image references at the END of your DETAILED_ANSWER\n"
        "\n"
        "Your response MUST use this exact format:\n"
        "SHORT_ANSWER:\n<2-3 sentences summarizing the key points>\n\n"
        "DETAILED_ANSWER:\n<comprehensive explanation>\n"
        "<all [IMAGE_REF:...] lines from documentation>"
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
        logger.info(f"get_answers: context contains {len(image_urls)} image(s)")
        full_response = ""

        for chunk in chat_model.stream(messages):
            token = chunk.content
            if not token:
                continue

            if any(phrase in token for phrase in BANNED_PHRASES):
                logger.warning("get_answers: banned phrase hit, stopping stream.")
                break

            full_response += token
            yield token  # Yield each token from LLM

            if any(
                full_response.count(phrase) > MAX_PHRASE_REPEATS
                for phrase in REPETITION_GUARD_PHRASES
            ):
                logger.warning("get_answers: repetition guard triggered, stopping stream.")
                break

        logger.info("get_answers: streaming complete, applying format enforcement.")
        logger.info(f"get_answers: LLM response contains {full_response.count('[IMAGE_REF:')} image reference(s)")
        
        # 🔥 FALLBACK: If LLM didn't include images but context has them, append them
        if image_urls and '[IMAGE_REF:' not in full_response:
            logger.warning(f"get_answers: LLM didn't include images, appending {len(image_urls)} image(s) automatically")
            image_block = "\n\n" + "\n".join([f"[IMAGE_REF:{url}]" for url in image_urls[:5]])  # Limit to 5 images
            yield image_block

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
    if not user_message or not user_message.strip():
        return False
    msg_lower = user_message.lower().strip()
    return any(kw in msg_lower for kw in TICKET_INTENT_KEYWORDS)


# ---------------------------------------------------------------------------
# EMAIL REPLY GENERATION
# ---------------------------------------------------------------------------

EMAIL_SYSTEM_PROMPT = """You are a professional MPS Support Engineer.

Write a clean and concise support email.

STRICT RULES:
- Answer ONLY using the provided documentation/context
- Do NOT use prior knowledge or assumptions
- Do NOT add information that is not present in the documentation
- If the answer is not available, say:
  "The requested information is not available in the current documentation."

- Start with "Hello,"
- Maximum 5–6 lines total
- If steps exist, format as numbered list (1, 2, 3)
- Each step on a new line
- Do NOT repeat information
- Do NOT include sections like "Resolution" or "Next Steps"
- Sound like a human engineer, not documentation

End with:
Regards,
MPS Support Team"""


def generate_email_reply(
    email_subject: str,
    email_body: str,
    llm_config: Optional[dict] = None,
) -> str:
    if not email_subject or not email_body:
        logger.warning("generate_email_reply: missing subject or body.")
        return "Error: email subject and body are required."

    config     = {
        "max_new_tokens": EMAIL_MAX_TOKENS,
        "temperature": EMAIL_TEMPERATURE,
        **(llm_config or {}),
    }
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
    if not user_query:
        return "general"

    q = user_query.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            logger.info(f"detect_category (keyword): '{user_query[:40]}' → {category}")
            return category

    logger.info(f"detect_category (keyword): '{user_query[:40]}' → general (no match)")
    return "general"
