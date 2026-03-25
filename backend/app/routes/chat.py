from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict
import re
import asyncio
import json

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

        is_ticket_intent = detect_ticket_intent(request.user_question)

        # ── TICKET INTENT GUARD ───────────────────────────────────────────────

        if is_ticket_intent:
            if history_rows:
                last_role, last_msg = history_rows[-1]
                if last_role == "assistant" and "describe your issue" in last_msg.lower():
                    pass  # allow — user is now describing their issue
                else:
                    ticket_prompt = "Please describe your issue first."
                    save_message(conversation_id, "assistant", ticket_prompt,category)
                    # Suggestions: issue-type chips to help them describe the problem
                    suggestions_json = json.dumps(get_suggestions(request.bot_id,user_query=request.user_question,step="issue"))
                    return StreamingResponse(
                        stream_text(ticket_prompt),
                        media_type="text/plain",
                        headers={
                            "X-Suggestions":    suggestions_json,
                            "X-Accel-Buffering": "no",
                        }
                    )

        # ── TICKET CREATION ───────────────────────────────────────────────────

        if history_rows:
            last_role, last_msg = history_rows[-1]

            if last_role == "assistant" and "describe your issue" in last_msg.lower():

                if not email_from_token:
                    return StreamingResponse(
                        stream_text("You must be logged in to create a support ticket."),
                        media_type="text/plain"
                    )

                user_email = user.get("email")
                if user_email != email_from_token:
                    return StreamingResponse(
                        stream_text("Your email does not match the authorized account."),
                        media_type="text/plain"
                    )

                try:
                    check_rate_limit(user_email)
                except HTTPException as e:
                    error_msg = e.detail
                    save_message(conversation_id, "assistant", error_msg,category)
                    return StreamingResponse(
                        stream_text(error_msg),
                        media_type="text/plain"
                    )

                case    = create_salesforce_case(
                    subject="Chatbot Technical Escalation",
                    description=request.user_question,
                    email=user_email,
                    chat_history=history_text
                )
                case_id       = case.get("id", "N/A")
                response_text = f"Your support ticket has been created successfully.\n\nCase ID: {case_id}"

                save_message(conversation_id, "assistant", response_text,category)
                return StreamingResponse(
                    stream_text(response_text),
                    media_type="text/plain",
                    headers={"X-Suggestions": "[]"}
                )

        # ── SAVE USER MESSAGE ─────────────────────────────────────────────────
        
        save_message(conversation_id, "user", request.user_question,category)

        # ── RAG RETRIEVAL ─────────────────────────────────────────────────────

        # Rewrite query to resolve pronouns ("it", "they", etc.) before retrieval
        standalone_query = rewrite_query(request.user_question, history_dicts)

        chunks, is_domain = retrieve_chunks(
            user_query=standalone_query,
            bot_id=request.bot_id,
            chat_history=history_rows,
            bot_config=bot_config.get("retriever_config", {})
        )

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
            # Ticket flow starting — show issue-type chips
            suggestions_json = json.dumps(get_suggestions(request.bot_id, step="issue"))
            return StreamingResponse(
                stream_text(escalation_text),
                media_type="text/plain",
                headers={"X-Suggestions": suggestions_json}
            )

        context_text = "\n".join(chunks)

        # ── LLM RESPONSE ──────────────────────────────────────────────────────

        # Run LLM before opening the stream so suggestions can be computed from
        # the actual answer and placed in the header — never embedded in the body.
        tokens = await asyncio.to_thread(
            lambda: list(
                get_answers(
                    history_dicts,
                    context_text,
                    standalone_query,
                    bot_config.get("llm_config", {})
                )
            )
        )
        full_answer = "".join(tokens)

        short_answer, detailed_answer = split_short_detailed(full_answer)
        final_answer = (
            f"{short_answer}\n\n{detailed_answer}"
            if detailed_answer
            else short_answer
        )

        # Suggestions are query-aware and go ONLY in the X-Suggestions header
        query_suggestions = _get_query_based_suggestions(
            request.bot_id,
            standalone_query,
            full_answer
        )

        save_message(conversation_id, "assistant", full_answer, category)

        async def stream_wrapper():
            for char in final_answer:
                yield char
                await asyncio.sleep(0.003)

        return StreamingResponse(
            stream_wrapper(),
            media_type="text/plain",
            headers={
                "X-Accel-Buffering": "no",
                "X-Suggestions": json.dumps(query_suggestions),
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