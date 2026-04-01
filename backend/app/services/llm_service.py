#llm_Service.py
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

load_dotenv()

from functools import lru_cache

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "llama-3.1-8b-instant"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 1024

HISTORY_WINDOW = 3
REWRITE_WINDOW = 1

FALLBACK_RESPONSE = "I do not have enough internal information to answer that."

REPETITION_GUARD_PHRASES = [
    "If the",
    "does not provide",
    "Without specific",
]

MAX_PHRASE_REPEATS = 2

@lru_cache(maxsize=4)
def _cached_model(model: str, temperature: float, max_tokens: int):
    return ChatGroq(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=os.getenv("GROQ_API_KEY")
    )

def create_chat_model(llm_config: dict = None):
    llm_config = llm_config or {}
    return _cached_model(
        model=llm_config.get("model", DEFAULT_MODEL),
        temperature=float(llm_config.get("temperature", DEFAULT_TEMPERATURE)),
        max_tokens=int(llm_config.get("max_new_tokens", DEFAULT_MAX_TOKENS)),
    )

def clean_context(context: str) -> str:
    if not context:
        return ""
    seen = set()
    cleaned = []
    for line in context.split("\n"):
        line = line.strip()
        if not line or len(line) < 3:
            continue
        if line in seen:
            continue
        seen.add(line)
        cleaned.append(line)
    return "\n".join(cleaned)

#rewriting queryyy
def rewrite_query(user_query: str, history=None, llm_config=None) -> str:
    if not user_query or len(user_query.split()) < 3:
        return user_query

    # 🔥 Skip rewrite if no pronouns
    pronouns = {"it", "this", "that", "they", "them"}
    if not any(p in user_query.lower().split() for p in pronouns):
        return user_query

    chat_model = create_chat_model(llm_config)

    history_summary = ""
    if history:
        history_summary = "\n".join(
            [f"{m['role']}: {m['content']}" for m in history[-REWRITE_WINDOW:]]
        )

    prompt = f"""
Rewrite this into a clear standalone question.

History:
{history_summary}

Question:
{user_query}

Return ONLY rewritten question.
"""

    try:
        response = chat_model.invoke([HumanMessage(content=prompt)])
        rewritten = response.content.strip()

        if len(rewritten) > len(user_query) * 4:
            return user_query  # avoid over-rewrite

        return rewritten
    except:
        return user_query


def get_answers(history, context, user_query, llm_config=None):
    # Fix 1: Set a reasonable token limit and force temperature to 0.0.
    if llm_config is None:
        llm_config = {"max_new_tokens": 1024, "temperature": 0.0}
    else:
        llm_config["max_new_tokens"] = 1024 
        llm_config["temperature"] = 0.0 

    chat_model = create_chat_model(llm_config)

    optimized_system_prompt = """You are the Highwire Support Assistant.
- Answer ONLY using the provided documentation.
- If the information is not present in the documentation, respond ONLY with:
  I do not have enough internal information to answer that.

- Do NOT use prior knowledge.
- Do NOT guess or infer information.
- Do NOT add external examples.
- Do NOT mention things like "not mentioned in documentation".

Return the response STRICTLY in the following format:

SHORT_ANSWER:
A short 1–2 sentence answer.

DETAILED_ANSWER:
A more detailed explanation using bullet points or numbered steps if necessary.Use code blocks for commands.

Rules:
- Always start with SHORT_ANSWER:
- Then provide DETAILED_ANSWER:
- Do not add any other sections.
- Never use HTML tags like <details>, <summary>, <ul>, <li>, <code>
- Never use markdown headers like ###
- Only use - for bullet points
- Only use ``` for code blocks
- Do not repeat SHORT_ANSWER at the end.
"""
    context=clean_context(context)
    messages = [SystemMessage(content=optimized_system_prompt)]

    # Add History
    if history and isinstance(history, list):
        for msg in history:
            role = msg.get("role")
            content = msg.get("content")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    # Fix 3: Removed the conflicting formatting rules from the HumanMessage
    messages.append(
        HumanMessage(content=f"""DOCUMENTATION:
{context}

USER QUESTION:
{user_query}

INSTRUCTION: 
Apply the ### SHORT_ANSWER and <details> structure to the documentation above. Do not add any text outside this structure.""")
    )

    full_response = ""
    for chunk in chat_model.stream(messages):
        token = chunk.content
        if not token:
            continue
        full_response+=token
        if is_repeating(full_response):
            print("⚠️ Repetition detected, stopping generation")
            break
        # banned_phrases = ["Note:", "(Code block", "[No detailed", "Detailed steps", "(Details","Incorrect answers:",
        # "If the documentation does not",
        # "this will not work"]
        # if any(phrase in token for phrase in banned_phrases):
        #     break
    full_response=clean_final_output(full_response)
    full_response=enforce_format(full_response)
    yield full_response

def detect_ticket_intent(user_message, llm_config=None):

    chat_model = create_chat_model(llm_config)

    prompt = f"""
Determine if the user wants to create a support ticket.

User message: "{user_message}"

Reply ONLY with YES or NO.
"""

    response = chat_model.invoke([HumanMessage(content=prompt)])

    result = response.content.strip()

    return "YES" in result.upper()


def detect_category(user_query: str, llm_config=None) -> str:
    chat_model = create_chat_model(llm_config)

    prompt = f"""Classify the following support question into exactly ONE of these categories:

- chrome_extension: Questions about installing or using the HighWire Chrome Extension
- escalation_process: Questions about escalation matrix, Salesforce cases, JIRA, support levels
- ecommerce_setup: Questions about HW Intelligent Commerce, Foxycart, Access Control, Drupal
- jcore_platform: Questions about JCore features, configuration, sites, key staff
- site_operations: Questions about H10 restarts, hwmaint servers, stopsite/startsite scripts
- platform_overview: Questions about HighWire Press, MPS, journal hosting, general platform
- general: Any question that doesn't fit the above categories

User question: "{user_query}"

Reply with ONLY the category name, nothing else. No explanation."""

    try:
        response = chat_model.invoke([HumanMessage(content=prompt)])
        category = response.content.strip().lower()
        valid = ["chrome_extension", "escalation_process", "ecommerce_setup",
                 "jcore_platform", "site_operations", "platform_overview", "general"]
        return category if category in valid else "general"
    except Exception:
        return "general"

def clean_final_output(text: str) -> str:
    if not text:
        return ""

    for phrase in ["Note:", "Remember", "Unfortunately"]:
        text = text.replace(phrase, "")

    return text.strip()

def enforce_format(output: str) -> str:
    if not output:
        return FALLBACK_RESPONSE

    if "SHORT_ANSWER:" not in output or "DETAILED_ANSWER:" not in output:
        return FALLBACK_RESPONSE

    try:
        parts = output.split("DETAILED_ANSWER:", 1)

        if len(parts) < 2:
            return FALLBACK_RESPONSE

        short = parts[0].replace("SHORT_ANSWER:", "").strip()
        detailed = parts[1].strip()

        if not short or not detailed:
            return FALLBACK_RESPONSE

        return f"SHORT_ANSWER:\n{short}\n\nDETAILED_ANSWER:\n{detailed}"

    except:
        return FALLBACK_RESPONSE 

def is_repeating(text: str) -> bool:
    return any(text.count(p) > MAX_PHRASE_REPEATS for p in REPETITION_GUARD_PHRASES)


# ---------------------------------------------------------------------------
# EMAIL REPLY GENERATION
# ---------------------------------------------------------------------------

EMAIL_MAX_TOKENS = 300
EMAIL_TEMPERATURE = 0.2

EMAIL_SYSTEM_PROMPT = """You are a professional IT Support Assistant writing email replies.

Guidelines:
- Start with "Hello,"
- Acknowledge the user's issue clearly
- Be polite and empathetic
- Do NOT hallucinate or add fake details
- Do NOT give unnecessary technical explanation
- Keep it concise (5–6 lines max)

End with:
Thank you,
IT Support Team
"""


def generate_email_reply(
    email_subject: str,
    email_body: str,
    llm_config: dict = None,
) -> str:
    """
    Generate a clean, professional email reply (NOT chatbot response).
    Completely separate from RAG.
    """

    if not email_subject or not email_body:
        return "Error: Missing email subject or body."

    config = {
        "max_new_tokens": EMAIL_MAX_TOKENS,
        "temperature": EMAIL_TEMPERATURE,
        **(llm_config or {})
    }

    chat_model = create_chat_model(config)

    prompt = f"""
Customer Email:
Subject: {email_subject}
Message: {email_body}

Write a professional support reply.
"""

    try:
        response = chat_model.invoke([
            SystemMessage(content=EMAIL_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        return response.content.strip()

    except Exception as e:
        return f"Error generating email reply: {str(e)}"