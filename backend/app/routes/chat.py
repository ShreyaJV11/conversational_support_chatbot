from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict
import re
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

from app.services.auth_service import verify_jwt_token, check_rate_limit, create_jwt_token
from app.services.salesforce_service import create_salesforce_case
from app.services.retrieval_service import retrieve_chunks
from app.services.llm_service import get_answers, detect_ticket_intent, rewrite_query, detect_category
from app.services.suggestion_service import get_suggestions
from app.services.memory_service import (
    get_or_create_user,
    get_or_create_conversation,
    save_message,
    get_recent_messages,
    get_user_by_session,
    link_session_to_user
)
from app.services.bot_service import get_bot_config
TICKET_STEPS = ["issue", "duration", "site", "confirm"]

def get_ticket_step(history_rows):
    if not history_rows:
        return None

    last_role, last_msg = history_rows[-1]

    if last_role != "assistant":
        return None

    msg = last_msg.lower()

    if "describe your issue" in msg:
        return "issue"
    elif "since when" in msg or "how long" in msg:
        return "duration"
    elif "which site" in msg or "system affected" in msg:
        return "site"
    elif "confirm?" in msg:   # ✅ ADD THIS
        return "confirm"

    return None
router = APIRouter()


class ChatRequest(BaseModel):
    user_question: str
    user_info: Optional[Dict] = None
    user_session_id: Optional[str] = "default_session"
    bot_id: int


def is_valid_email(email: str) -> bool:
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email) is not None


def stream_text(text: str):
    async def generator():
        for char in text:
            yield char
            await asyncio.sleep(0.003)
    return generator()


def split_short_detailed(answer: str):
    """
    FIX: Original used "DETAILED ANSWER:" (space) but the model outputs
         "DETAILED_ANSWER:" (underscore). This caused the split to never
         match, so short_answer was always the full text and detailed_answer
         was always None — meaning the Hide Details section never appeared.
    """
    short_answer = answer
    detailed_answer = None

    # FIX: match the actual format tags the model uses
    if "DETAILED_ANSWER:" in answer:
        parts = answer.split("DETAILED_ANSWER:", 1)
        short_answer   = parts[0].replace("SHORT_ANSWER:", "").strip()
        detailed_answer = parts[1].strip()

    return short_answer, detailed_answer


def _get_query_based_suggestions(bot_id: int, user_query: str, answer: str) -> list:
    try:
        # 🔥 Combine query + answer → richer context
        enriched_query = f"{user_query}\n{answer[:300]}"

        # 🔥 Call suggestion engine WITHOUT forcing step
        return get_suggestions(
            bot_id,
            user_query=enriched_query,
            step=None
        )

    except Exception:
        return get_suggestions(
            bot_id,
            user_query=user_query,
            step=None
        )
def extract_ticket_data(history_rows):
    data = {"issue": None, "duration": None, "site": None}

    last_question = None

    for role, msg in history_rows:
        if role == "assistant":
            last_question = msg.lower()

        elif role == "user" and last_question:

            if "describe your issue" in last_question:
                data["issue"] = msg

            elif "since when" in last_question or "how long" in last_question:
                data["duration"] = msg

            elif "which site" in last_question or "system affected" in last_question:
                data["site"] = msg

    return data
def handle_ticket_flow(
    request,
    conversation_id,
    history_rows,
    user,
    email_from_token,
    category
):
    step = get_ticket_step(history_rows)

    # ── START FLOW ─────────────────────
    if not step:
        msg = (
            "Sure, I can help you raise a support ticket.\n\n"
            "Please describe your issue."
        )

        save_message(conversation_id, "assistant", msg, category)

        return StreamingResponse(
            stream_text(msg),
            media_type="text/plain",
            headers={
                "X-Suggestions": json.dumps(
                    get_suggestions(request.bot_id,request.user_question, step="issue")
                )
            }
        )

    # ── STEP 1: ISSUE ──────────────────
    if step == "issue":
        save_message(conversation_id, "user", request.user_question, category)

        msg = "Since when are you facing this issue?"
        save_message(conversation_id, "assistant", msg, category)

        return StreamingResponse(
            stream_text(msg),
            media_type="text/plain",
            headers={
                "X-Suggestions": json.dumps(
                    get_suggestions(request.bot_id, request.user_question,step="duration")
                )
            }
        )

    # ── STEP 2: DURATION ───────────────
    if step == "duration":
        save_message(conversation_id, "user", request.user_question, category)

        msg = "Which site or system is affected?"
        save_message(conversation_id, "assistant", msg, category)

        return StreamingResponse(
            stream_text(msg),
            media_type="text/plain",
            headers={
                "X-Suggestions": json.dumps(
                    get_suggestions(request.bot_id, request.user_question,step="site")
                )
            }
        )

    # ── STEP 3: SITE → CREATE TICKET ───
    # ── STEP 3: SITE → CONFIRM ───
    if step == "site":
        save_message(conversation_id, "user", request.user_question, category)
        ticket_data = extract_ticket_data(
            history_rows + [("user", request.user_question)]
            )
        msg = (
             "Here’s your ticket summary:\n"
               f"- Issue: {ticket_data['issue']}\n"
               f"- Duration: {ticket_data['duration']}\n"
               f"- System: {ticket_data['site']}\n\n"
               "Confirm? (Yes/No)"
    )

        save_message(conversation_id, "assistant", msg, category)

        return StreamingResponse(
        stream_text(msg),
        media_type="text/plain",
        headers={
            "X-Suggestions": json.dumps(["Yes", "No"])
        }
    )
        # ── STEP 4: CONFIRM → CREATE ───
    if step == "confirm":
        save_message(conversation_id, "user", request.user_question, category)

        user_input = request.user_question.lower().strip()

        if user_input in ["yes", "y"]:
            if not email_from_token:
                return StreamingResponse(
                stream_text("You must be logged in to create a ticket."),
                media_type="text/plain"
            )

            user_email = user.get("email")

            try:
                check_rate_limit(user_email)
            except HTTPException as e:
                return StreamingResponse(
                    stream_text(e.detail),
                    media_type="text/plain"
                      )

            history_text = "\n".join(
                 [f"{r[0]}: {r[1]}" for r in history_rows]
                 )

            case = create_salesforce_case(
                subject="Chatbot Support Ticket",
                description=history_text,
                email=user_email,
                chat_history=history_text
                )

            case_id = case.get("id", "N/A")

            msg = f"✅ Your support ticket has been created.\n\nCase ID: {case_id}"

            save_message(conversation_id, "assistant", msg, category)

            return StreamingResponse(
                stream_text(msg),
                media_type="text/plain",
                headers={"X-Suggestions": "[]"}
                )

        elif user_input in ["no", "n"]:
            msg = "Okay, let's restart. Please describe your issue again."
            save_message(conversation_id, "assistant", msg, category)

            return StreamingResponse(
                 stream_text(msg),
                 media_type="text/plain",
                 headers={
                      "X-Suggestions": json.dumps(
                           get_suggestions(request.bot_id, request.user_question, step="issue")
                           )
                             }
                             )

        else:
            msg = "Please reply with Yes or No."
            return StreamingResponse(
                stream_text(msg),
                media_type="text/plain",
                headers={"X-Suggestions": json.dumps(["Yes", "No"])}
                )
@router.post("/chat")
async def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):

    try:

        # ── BOT CONFIG ──────────────────────────────────────────────────────

        bot_config = get_bot_config(request.bot_id)

        if not bot_config:
            return StreamingResponse(
                stream_text("Invalid bot configuration."),
                media_type="text/plain"
            )

        require_registration = bot_config.get("require_registration", True)

        existing_user = get_user_by_session(
            request.bot_id,
            request.user_session_id
        )

        # Prevent session email mismatch
        if existing_user and request.user_info:
            incoming_email = request.user_info.get("email")
            if incoming_email and incoming_email != existing_user.get("email"):
                existing_user = None

        # ── USER REGISTRATION ────────────────────────────────────────────────

        if require_registration and not existing_user:

            name, email = None, None

            if request.user_info:
                name  = request.user_info.get("name")
                email = request.user_info.get("email")

            elif "," in request.user_question:
                parts = request.user_question.split(",")
                if len(parts) == 2:
                    name  = parts[0].strip()
                    email = parts[1].strip()

            if not name or len(name.strip()) < 2:
                return StreamingResponse(
                    stream_text(bot_config["initial_message"]),
                    media_type="text/plain"
                )

            if not email or not is_valid_email(email):
                return StreamingResponse(
                    stream_text("Please provide a valid email address."),
                    media_type="text/plain"
                )

            user_id = get_or_create_user(request.bot_id, name, email)
            link_session_to_user(request.bot_id, user_id, request.user_session_id)
            get_or_create_conversation(user_id, request.bot_id)

            token = create_jwt_token(email)

            # FIX: Return login suggestions as a plain JSON response.
            # The frontend should check for `suggestions` key in the response
            # and render chips — these are generic "first question" prompts.
            login_suggestions = get_suggestions(
                request.bot_id,
                user_query="",
                step=None
                )

            return {
                "message":     f"Thank you {name}. How can I assist you today?",
                "token":       token,
                "suggestions": login_suggestions,   # ← chips shown right after login
            }

        # ── NORMAL FLOW ──────────────────────────────────────────────────────
        category = detect_category(request.user_question)
        user    = existing_user
        user_id = user["id"]

        # JWT verification
        email_from_token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            try:
                email_from_token = verify_jwt_token(token)
            except Exception as e:
                email_from_token = None

        conversation_id = get_or_create_conversation(user_id, request.bot_id)
        history_limit   = bot_config.get("memory_limit", 6)
        history_rows    = get_recent_messages(conversation_id, limit=history_limit) or []

        # Convert history rows to dicts for rewrite_query and get_answers
        history_dicts = [{"role": r[0], "content": r[1]} for r in history_rows]
        history_text  = "\n".join([f"{r[0].upper()}: {r[1]}" for r in history_rows])

        # ── TICKET STEP DETECTION ─────────────────────────────────────────────
        # Determine which ticket-creation step we're on based on last assistant message.
        # This drives the suggestion chips during ticket flow.

        current_step = None
        if history_rows:
            last_role, last_msg = history_rows[-1]
            if last_role == "assistant":
                msg_lower = last_msg.lower()
                if "how long has this issue"      in msg_lower: current_step = "duration"
                elif "site name or system affected" in msg_lower: current_step = "site"
                elif "describe your issue"          in msg_lower: current_step = "issue"

        # Check if user explicitly wants to create a ticket
        is_ticket_intent = detect_ticket_intent(request.user_question)
        ticket_step = get_ticket_step(history_rows)
        
        # Check if last assistant message asked about creating a ticket
        user_confirming_ticket = False
        if history_rows and len(history_rows) > 0:
            last_role, last_msg = history_rows[-1]
            if last_role == "assistant" and "would you like me to create a support ticket?" in last_msg.lower():
                # User is responding to ticket creation offer
                user_response = request.user_question.lower().strip()
                if user_response in ["yes", "y", "sure", "ok", "okay", "please", "yeah"]:
                    user_confirming_ticket = True
                elif user_response in ["no", "n", "nope", "not now", "later"]:
                    # User declined ticket creation, continue with normal flow
                    pass
                else:
                    # User asked a different question instead of answering yes/no
                    # Treat it as a new question, not ticket flow
                    pass
        
        # Only enter ticket flow if:
        # 1. User explicitly said they want a ticket, OR
        # 2. User confirmed ticket creation, OR  
        # 3. Already in ticket flow (ticket_step exists)
        if is_ticket_intent or user_confirming_ticket or ticket_step:
            return handle_ticket_flow(
                 request,
                 conversation_id,
                 history_rows,
                 user,
                 email_from_token,
                 category
    )

        
        save_message(conversation_id, "user", request.user_question,category)

        # ── HANDLE GREETINGS & PLEASANTRIES ───────────────────────────────────
        
        query_lower = request.user_question.lower().strip()
        
        # Only match standalone greetings (not questions starting with "how")
        standalone_greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "hi there", "hello there"]
        thanks_phrases = ["thank you", "thanks", "thank", "appreciate it", "thx", "ty"]
        
        # Check if it's ONLY a greeting (not a question)
        is_greeting = any(query_lower == greeting or query_lower.startswith(greeting + " ") for greeting in standalone_greetings)
        is_thanks = any(thank in query_lower for thank in thanks_phrases) and len(query_lower.split()) <= 5
        
        if is_greeting:
            response = "Hello! How can I help you today?"
            save_message(conversation_id, "assistant", response, category)
            suggestions_json = json.dumps(get_suggestions(request.bot_id, user_query="", step=None))
            return StreamingResponse(
                stream_text(response),
                media_type="text/plain",
                headers={"X-Suggestions": suggestions_json}
            )
        
        if is_thanks and not any(q in query_lower for q in ["how", "what", "why", "when", "where", "?"]):
            response = "You're welcome! Is there anything else I can help you with?"
            save_message(conversation_id, "assistant", response, category)
            suggestions_json = json.dumps(get_suggestions(request.bot_id, user_query="", step=None))
            return StreamingResponse(
                stream_text(response),
                media_type="text/plain",
                headers={"X-Suggestions": suggestions_json}
            )

        # ── RAG RETRIEVAL ─────────────────────────────────────────────────────

        # Rewrite query to resolve pronouns ("it", "they", etc.) before retrieval
        standalone_query = rewrite_query(request.user_question, history_dicts)
        
        # Debug logging
        logger.info(f"Original query: '{request.user_question}'")
        logger.info(f"Rewritten query: '{standalone_query}'")

        chunks, is_domain = retrieve_chunks(
            user_query=standalone_query,
            bot_id=request.bot_id,
            chat_history=history_rows,
            bot_config=bot_config.get("retriever_config", {})
        )
        
        logger.info(f"Retrieved {len(chunks) if chunks else 0} chunks for query: '{standalone_query}'")

        if not is_domain:
            # Off-topic query — generic suggestions
            suggestions_json = json.dumps(get_suggestions(request.bot_id,user_query=request.user_question, step=None))
            return StreamingResponse(
                stream_text(bot_config["domain_message"]),
                media_type="text/plain",
                headers={"X-Suggestions": suggestions_json}
            )

        if not chunks:
            escalation_text = (
                bot_config["escalation_message"]
                + "\n\nWould you like me to create a support ticket?"
            )
            save_message(conversation_id, "assistant", escalation_text,category)
            # Show Yes/No suggestions for ticket creation confirmation
            suggestions_json = json.dumps(["Yes, create a ticket", "No, try another question"])
            return StreamingResponse(
                stream_text(escalation_text),
                media_type="text/plain",
                headers={"X-Suggestions": suggestions_json}
            )

        context_text = "\n".join(chunks)

        # ── LLM RESPONSE ──────────────────────────────────────────────────────

        # Stream tokens directly from LLM with proper async handling
        def stream_llm_response():
            full_answer = ""
            
            # Stream each token as it's generated
            for token in get_answers(
                history_dicts,
                context_text,
                standalone_query,
                bot_config.get("llm_config", {})
            ):
                full_answer += token
                yield token.encode('utf-8')
            
            # Save the complete answer after streaming
            save_message(conversation_id, "assistant", full_answer, category)

        return StreamingResponse(
            stream_llm_response(),
            media_type="text/plain",
            headers={
                "X-Accel-Buffering": "no",
                "X-Suggestions": json.dumps(
                    _get_query_based_suggestions(
                        request.bot_id,
                        standalone_query,
                        ""  # Empty for now, suggestions will be generic
                    )
                ),
            }
        )

    except Exception as e:
        print(f"Error: {e}")
        return StreamingResponse(
            stream_text("Internal server error."),
            media_type="text/plain"
        )


@router.get("/chat/initial-message/{bot_id}")
async def get_initial(bot_id: int):

    bot_config = get_bot_config(bot_id)

    if not bot_config:
        return {
            "response_type": "ERROR",
            "message": f"Bot with ID {bot_id} not found."
        }

    return {
        "response_type": "COLLECT_INFO",
        "message": bot_config.get(
            "initial_message",
            "Welcome. Please provide your name and email."
        )
    }

@router.get("/bot/{bot_id}/suggestions")
async def get_bot_suggestions(
    bot_id: int,
    step: Optional[str] = None,
    last_query: Optional[str] = None,
):
    """
    Return suggestion chips for a bot.

    FIX: The frontend calls GET /bot/{id}/suggestions after every message,
         ignoring the X-Suggestions header. Rather than fight the frontend,
         this endpoint now accepts an optional `last_query` param so it can
         return query-aware suggestions instead of always returning random ones.

    Frontend should call:
        GET /bot/1/suggestions?last_query=what+is+jcore
    to get follow-up chips relevant to the last question asked.
    """
    if last_query and last_query.strip():
        # Use category detection to pick a relevant step
        try:
            category = detect_category(last_query.strip())
            CATEGORY_TO_STEP = {
                "chrome_extension":   "issue",
                "jcore_platform":     "issue",
                "ecommerce_setup":    "issue",
                "site_operations":    "site",
                "escalation_process": "issue",
                "platform_overview":  None,
                "general":            None,
            }
            step = CATEGORY_TO_STEP.get(category, step)
        except Exception:
            pass  # fall through to default step

    suggestions = get_suggestions(
    bot_id,
    user_query=last_query or "",
    step=step
)
    return {"suggestions": suggestions}