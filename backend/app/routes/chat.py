from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, List, Tuple
import re
import asyncio
import random
import traceback

from app.services.auth_service import verify_jwt_token, check_rate_limit, create_jwt_token
from app.services.salesforce_service import create_salesforce_case
from app.services.retrieval_service import retrieve_chunks
from app.services.llm_service import get_answers, detect_ticket_intent, detect_category
from app.services.memory_service import (
    get_or_create_user,
    get_or_create_conversation,
    save_message,
    get_recent_messages,
    get_user_by_session,
    link_session_to_user,
)
from app.services.bot_service import get_bot_config

router = APIRouter()


# ---------------------------------------------------------------------------
# Constants — no more magic strings scattered through the code
# ---------------------------------------------------------------------------

class TicketStep:
    """Sentinel strings written into assistant messages to track ticket state."""
    ASK_ISSUE    = "please describe your issue"
    ASK_SITE     = "site name or system affected"
    ASK_DURATION = "how long has this issue"


SMALLTALK_RESPONSES: Dict[str, List[str]] = {
    "greeting": [
        "Hello! How can I assist you today?",
        "Hi there! What can I help you with?",
        "Hey! How can I help you today?",
    ],
    "closing": [
        "Goodbye! Feel free to reach out anytime.",
        "Take care! I'm here whenever you need help.",
        "Good night! Don't hesitate to come back if you need anything.",
    ],
    "gratitude": [
        "You're welcome! Let me know if you need anything else.",
        "Happy to help! Is there anything else I can assist you with?",
        "Glad I could help! Feel free to ask if you have more questions.",
    ],
    "apology": [
        "No worries at all! How can I assist you further?",
        "That's completely fine! What can I help you with?",
        "No problem at all. How can I help?",
    ],
    "casual": [
        "Got it! How can I help you next?",
        "Alright, let me know what you need.",
        "Sure! What would you like to know?",
    ],
}

EMAIL_PATTERN = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    user_question: str
    user_info: Optional[Dict] = None
    user_session_id: Optional[str] = "default_session"
    bot_id: int


# ---------------------------------------------------------------------------
# Small utility helpers
# ---------------------------------------------------------------------------

def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(email))


async def stream_text(text: str):
    """Yield one character at a time for a streaming effect."""
    for char in text:
        yield char
        await asyncio.sleep(0.003)


def _stream(text: str) -> StreamingResponse:
    """Convenience wrapper so callers stay one-liners."""
    return StreamingResponse(stream_text(text), media_type="text/plain")


def split_short_detailed(answer: str) -> Tuple[str, Optional[str]]:
    if "DETAILED ANSWER:" not in answer:
        return answer, None
    parts = answer.split("DETAILED ANSWER:", 1)
    return parts[0].replace("SHORT ANSWER:", "").strip(), parts[1].strip()


# ---------------------------------------------------------------------------
# Small-talk detection
# ---------------------------------------------------------------------------

class SmallTalkDetector:
    """
    Compiled-regex small-talk classifier.
    Building the patterns once at import time is faster than looping over
    plain strings on every request.
    """

    _PHRASES: Dict[str, List[str]] = {
        "greeting": [
            "hi", "hello", "hey", "good morning", "good afternoon",
            "good evening", "whats up", "howdy", "hiya", "hi there",
            "hello there", "hey there",
        ],
        "closing": [
            "bye", "goodbye", "see you", "good night", "goodnight",
            "lets stop", "cya", "see ya", "take care", "talk later",
        ],
        "gratitude": [
            "thanks", "thank you", "thx", "thank u", "thanks a lot",
            "many thanks", "much appreciated", "cheers",
        ],
        "apology": [
            "sorry", "my bad", "apologies", "apology", "i apologize",
            "excuse me", "pardon",
        ],
        "casual": [
            "okay", "ok", "alright", "sure", "cool", "got it", "noted",
            "i see", "makes sense", "sounds good", "fine", "understood",
        ],
    }

    # Map category → compiled pattern that matches the cleaned input
    _PATTERNS: Dict[str, re.Pattern] = {}

    @classmethod
    def _build(cls) -> None:
        for category, phrases in cls._PHRASES.items():
            # Sort longest first so "good morning" beats "good"
            sorted_phrases = sorted(phrases, key=len, reverse=True)
            escaped = [re.escape(p) for p in sorted_phrases]
            # Match at the start OR as the entire string
            cls._PATTERNS[category] = re.compile(
                r"^(?:" + "|".join(escaped) + r")(?:\s|$)"
            )

    @classmethod
    def detect(cls, query: str) -> Optional[str]:
        if not cls._PATTERNS:
            cls._build()
        cleaned = re.sub(r"[^\w\s]", "", query.lower().strip())
        for category, pattern in cls._PATTERNS.items():
            if pattern.match(cleaned):
                return category
        return None


def get_smalltalk_response(smalltalk_type: str) -> str:
    return random.choice(SMALLTALK_RESPONSES.get(smalltalk_type, ["How can I help you?"]))


# ---------------------------------------------------------------------------
# Ticket flow helpers
# ---------------------------------------------------------------------------

def _get_ticket_step(last_role: str, last_msg: str) -> Optional[str]:
    """
    Return the current ticket step based on the last assistant message,
    or None if we are not in a ticket flow.
    """
    if last_role != "assistant":
        return None
    msg = last_msg.lower()
    if TicketStep.ASK_DURATION in msg:
        return TicketStep.ASK_DURATION
    if TicketStep.ASK_SITE in msg:
        return TicketStep.ASK_SITE
    if TicketStep.ASK_ISSUE in msg:
        return TicketStep.ASK_ISSUE
    return None


def _collect_ticket_user_messages(recent: List[Tuple[str, str]], n: int = 2) -> List[str]:
    """Extract the last *n* user messages from a history slice."""
    user_msgs = [msg for role, msg in recent if role == "user"]
    return user_msgs[-n:]


async def _handle_ticket_step(
    step: str,
    request: ChatRequest,
    conversation_id: int,
    user: Dict,
    email_from_token: Optional[str],
    history_text: str,
) -> StreamingResponse:
    """
    Drive the multi-step ticket creation state machine.
    Returns a StreamingResponse for whichever step we are currently on.
    """

    # ── Step 1: user just described the issue → ask for site ──────────────
    if step == TicketStep.ASK_ISSUE:
        save_message(conversation_id, "user", request.user_question)
        reply = "Thank you. What is the site name or system affected?"
        save_message(conversation_id, "assistant", reply)
        return _stream(reply)

    # ── Step 2: user gave site name → ask for duration ────────────────────
    if step == TicketStep.ASK_SITE:
        save_message(conversation_id, "user", request.user_question)
        reply = "How long has this issue been occurring?"
        save_message(conversation_id, "assistant", reply)
        return _stream(reply)

    # ── Step 3: user gave duration → validate, then create ticket ─────────
    if step == TicketStep.ASK_DURATION:

        if not email_from_token:
            return _stream("You must be logged in to create a support ticket.")

        user_email: str = user.get("email", "")
        if user_email != email_from_token:
            return _stream("Your email does not match the authorized account.")

        try:
            check_rate_limit(user_email)
        except HTTPException as exc:
            save_message(conversation_id, "assistant", exc.detail)
            return _stream(exc.detail)

        # Pull the last 6 messages to reconstruct what was collected
        recent = get_recent_messages(conversation_id, limit=6)
        user_msgs = _collect_ticket_user_messages(recent, n=2)

        issue_desc = user_msgs[-2] if len(user_msgs) >= 2 else "N/A"
        site_name  = user_msgs[-1] if len(user_msgs) >= 2 else "N/A"
        duration   = request.user_question
        category   = detect_category(issue_desc)

        case = create_salesforce_case(
            subject="Chatbot Technical Escalation",
            description=f"Issue: {issue_desc}\nSite: {site_name}\nDuration: {duration}",
            email=user_email,
            chat_history=history_text,
        )
        case_id = case.get("id", "N/A")

        response_text = (
            "Your support ticket has been created successfully.\n\n"
            "--------------------------------\n"
            f"Case ID  : {case_id}\n"
            f"Name     : {user.get('name')}\n"
            f"Email    : {user_email}\n"
            f"User ID  : {user.get('id')}\n"
            f"Issue    : {issue_desc}\n"
            f"Site     : {site_name}\n"
            f"Duration : {duration}\n"
            f"Category : {category}\n"
            "--------------------------------"
        )

        save_message(conversation_id, "user", request.user_question)
        save_message(conversation_id, "assistant", response_text)
        return _stream(response_text)

    # Should never reach here
    return _stream("Something went wrong with the ticket flow. Please try again.")


# ---------------------------------------------------------------------------
# Main chat endpoint
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):
    try:

        # ── Bot config ────────────────────────────────────────────────────
        bot_config = get_bot_config(request.bot_id)
        if not bot_config:
            return _stream("Invalid bot configuration.")

        require_registration: bool = bot_config.get("require_registration", True)

        existing_user = get_user_by_session(request.bot_id, request.user_session_id)

        # Prevent session/email mismatch (e.g. same browser, different account)
        if existing_user and request.user_info:
            incoming_email = request.user_info.get("email")
            if incoming_email and incoming_email != existing_user.get("email"):
                existing_user = None

        # ── Registration gate ─────────────────────────────────────────────
        if require_registration and not existing_user:
            name, email = None, None

            if request.user_info:
                name  = request.user_info.get("name")
                email = request.user_info.get("email")
            elif "," in request.user_question:
                parts = request.user_question.split(",", 1)
                if len(parts) == 2:
                    name, email = parts[0].strip(), parts[1].strip()

            if not name or len(name.strip()) < 2:
                return _stream(bot_config["initial_message"])

            if not email or not is_valid_email(email):
                return _stream("Please provide a valid email address.")

            user_id = get_or_create_user(request.bot_id, name, email)
            link_session_to_user(request.bot_id, user_id, request.user_session_id)
            get_or_create_conversation(user_id, request.bot_id, force_new=True)

            token = create_jwt_token(email)
            return {"message": f"Thank you {name}. How can I assist you today?", "token": token}

        # ── Normal flow ───────────────────────────────────────────────────
        user    = existing_user
        user_id = user["id"]

        # JWT verification (best-effort; ticket creation enforces it strictly)
        email_from_token: Optional[str] = None
        if authorization and authorization.startswith("Bearer "):
            try:
                email_from_token = verify_jwt_token(authorization.split(" ", 1)[1])
            except Exception as jwt_err:
                print(f"JWT verification failed: {jwt_err}")

        conversation_id = get_or_create_conversation(user_id, request.bot_id)
        history_limit   = bot_config.get("memory_limit", 6)
        history_rows    = get_recent_messages(conversation_id, limit=history_limit) or []
        history_text    = "\n".join(f"{role.upper()}: {msg}" for role, msg in history_rows)

        # ── Small-talk short-circuit ──────────────────────────────────────
        smalltalk_type = SmallTalkDetector.detect(request.user_question)
        if smalltalk_type:
            return _stream(get_smalltalk_response(smalltalk_type))

        # ── Ticket state machine ──────────────────────────────────────────
        current_step: Optional[str] = None
        if history_rows:
            last_role, last_msg = history_rows[-1]
            current_step = _get_ticket_step(last_role, last_msg)

        # Guard: user is explicitly asking to create a ticket (intent detected)
        # but we are NOT already inside a ticket flow → prompt for description first.
        if detect_ticket_intent(request.user_question) and current_step is None:
            reply = f"{bot_config.get('escalation_message', 'I can raise a ticket for you.')}" \
                    "\n\nPlease describe your issue."
            save_message(conversation_id, "assistant", reply)
            return _stream(reply)

        # Advance the ticket state machine if we are mid-flow
        if current_step is not None:
            return await _handle_ticket_step(
                current_step,
                request,
                conversation_id,
                user,
                email_from_token,
                history_text,
            )

        # ── Regular RAG flow ──────────────────────────────────────────────
        question_category = detect_category(request.user_question)
        save_message(conversation_id, "user", request.user_question, category=question_category)

        chunks, is_domain = retrieve_chunks(
            user_query=request.user_question,
            bot_id=request.bot_id,
            chat_history=history_rows,
            bot_config=bot_config.get("retriever_config", {}),
        )

        if not is_domain:
            return _stream(bot_config["domain_message"])

        if not chunks:
            escalation_text = (
                bot_config["escalation_message"]
                + "\n\nWould you like me to create a support ticket?"
            )
            save_message(conversation_id, "assistant", escalation_text)
            return _stream(escalation_text)

        context_text = "\n".join(chunks)

        # ── Streaming LLM response ────────────────────────────────────────
        async def stream_wrapper():
            tokens = await asyncio.to_thread(
                lambda: list(
                    get_answers(
                        history_text,
                        context_text,
                        request.user_question,
                        bot_config.get("llm_config", {}),
                    )
                )
            )
            full_answer = "".join(tokens)
            short_answer, detailed_answer = split_short_detailed(full_answer)
            final_answer = (
                f"{short_answer}\n\n{detailed_answer}" if detailed_answer else short_answer
            )

            for char in final_answer:
                yield char
                await asyncio.sleep(0.003)

            save_message(conversation_id, "assistant", full_answer, category=question_category)

        return StreamingResponse(
            stream_wrapper(),
            media_type="text/plain",
            headers={"X-Accel-Buffering": "no"},
        )

    except Exception:
        traceback.print_exc()
        return _stream("Internal server error.")


# ---------------------------------------------------------------------------
# Initial message endpoint
# ---------------------------------------------------------------------------

@router.get("/chat/initial-message/{bot_id}")
async def get_initial(bot_id: int):
    bot_config = get_bot_config(bot_id)
    if not bot_config:
        return {"response_type": "ERROR", "message": f"Bot with ID {bot_id} not found."}
    return {
        "response_type": "COLLECT_INFO",
        "message": bot_config.get("initial_message", "Welcome. Please provide your name and email."),
    }