from fastapi import APIRouter, Header ,HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict
import re
import asyncio

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
    get_or_create_organization
)
from app.services.bot_service import get_bot_config
from app.services.suggestion_service import get_suggestions

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
    short_answer = answer
    detailed_answer = None

    if "DETAILED ANSWER:" in answer:
        parts = answer.split("DETAILED ANSWER:")
        short_answer = parts[0].replace("SHORT ANSWER:", "").strip()
        detailed_answer = parts[1].strip()

    return short_answer, detailed_answer

def detect_smalltalk(query: str):
    import re
    # Normalize: lowercase, remove punctuation
    cleaned = re.sub(r'[^\w\s]', '', query.lower().strip())

    greetings = ["hi", "hello", "hey", "good morning", "good afternoon",
                 "good evening", "whats up", "howdy", "hiya", "hi there",
                 "hello there", "hey there"]
    
    closings = ["bye", "goodbye", "see you", "good night", "goodnight",
                "lets stop", "cya", "see ya", "take care", "talk later"]
    
    gratitude = ["thanks", "thank you", "thx", "thank u", "thanks a lot",
                 "many thanks", "much appreciated", "cheers"]
    
    apologies = ["sorry", "my bad", "apologies", "apology", "i apologize",
                 "excuse me", "pardon"]
    
    casual = ["okay", "ok", "alright", "sure", "cool", "got it", "noted",
              "i see", "makes sense", "sounds good", "fine", "understood"]

    for phrase in greetings:
        if cleaned == phrase or cleaned.startswith(phrase):
            return "greeting"
    
    for phrase in closings:
        if cleaned == phrase or cleaned.startswith(phrase):
            return "closing"
    
    for phrase in gratitude:
        if cleaned == phrase or phrase in cleaned:
            return "gratitude"
    
    for phrase in apologies:
        if cleaned == phrase or cleaned.startswith(phrase):
            return "apology"
    
    for phrase in casual:
        if cleaned == phrase or cleaned.startswith(phrase):
            return "casual"
    
    return None


SMALLTALK_RESPONSES = {
    "greeting": [
        "Hello! How can I assist you today?",
        "Hi there! What can I help you with?",
        "Hey! How can I help you today?"
    ],
    "closing": [
        "Goodbye! Feel free to reach out anytime.",
        "Take care! I'm here whenever you need help.",
        "Good night! Don't hesitate to come back if you need anything."
    ],
    "gratitude": [
        "You're welcome! Let me know if you need anything else.",
        "Happy to help! Is there anything else I can assist you with?",
        "Glad I could help! Feel free to ask if you have more questions."
    ],
    "apology": [
        "No worries at all! How can I assist you further?",
        "That's completely fine! What can I help you with?",
        "No problem at all. How can I help?"
    ],
    "casual": [
        "Got it! How can I help you next?",
        "Alright, let me know what you need.",
        "Sure! What would you like to know?"
    ]
}


import random

def get_smalltalk_response(smalltalk_type: str) -> str:
    responses = SMALLTALK_RESPONSES.get(smalltalk_type, ["How can I help you?"])
    return random.choice(responses)

def detect_category(query: str) -> str:
    query_lower = query.lower()

    if any(word in query_lower for word in ["chrome", "extension", "install", "developer mode", "github", "crx"]):
        return "chrome_extension"

    if any(word in query_lower for word in ["escalat", "jira", "salesforce case", "support lead", "sysops", "vp", "svp", "director"]):
        return "escalation_process"

    if any(word in query_lower for word in ["foxycart", "ecommerce", "commerce", "catalog", "drupal", "access control", "pricing"]):
        return "ecommerce_setup"

    if any(word in query_lower for word in ["jcore", "journal hosting", "publisher", "j-core", "maint", "demo site"]):
        return "jcore_platform"

    if any(word in query_lower for word in ["h10", "restart", "hwmaint", "stopsite", "startsite", "jserv", "ssh", "memory leak"]):
        return "site_operations"

    if any(word in query_lower for word in ["highwire", "mps", "platform", "ingestion", "discoverability", "hosting"]):
        return "platform_overview"

    return "general"

import json
def get_query_suggestions(bot_id: int, user_query: str, answer: str = ""):
    try:
        enriched = f"{user_query}\n{answer[:200]}"
        return json.dumps(
            get_suggestions(bot_id, user_query=enriched, step=None)
        )
    except:
        return json.dumps([])

@router.post("/chat")
async def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):

    try:

        # ---------------- BOT CONFIG ----------------

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

        # ---------------- FIX: Prevent session email mismatch ----------------

        if existing_user and request.user_info:
            incoming_email = request.user_info.get("email")
            if incoming_email and incoming_email != existing_user.get("email"):
                existing_user = None

        # ---------------- USER REGISTRATION ----------------

        if require_registration and not existing_user:

            name, email = None, None

            if request.user_info:
                name = request.user_info.get("name")
                email = request.user_info.get("email")

            elif "," in request.user_question:
                parts = request.user_question.split(",")
                if len(parts) == 2:
                    name = parts[0].strip()
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

            email_domain = email.split("@")[1]
            org_name = email_domain.split(".")[0].capitalize()

            get_or_create_organization(email_domain, org_name)

            user_id = get_or_create_user(
                request.bot_id,
                name,
                email
            )

            link_session_to_user(
                request.bot_id,
                user_id,
                request.user_session_id
            )

            get_or_create_conversation(user_id, request.bot_id, force_new=True)

            token = create_jwt_token(email)

            from fastapi.responses import JSONResponse
            import json

            suggestions = get_suggestions(
                request.bot_id,
                user_query="start",
                step=None
            )

            response = JSONResponse(
                content={
                    "message": f"Thank you {name}. How can I assist you today?",
                    "token": token
                }
            )

            response.headers["X-Suggestions"] = json.dumps(suggestions)

            return response

        # ---------------- NORMAL FLOW ----------------

        user = existing_user
        user_id = user["id"]

        # ---------------- JWT TOKEN VERIFICATION ----------------

        email_from_token = None

        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]

            try:
                email_from_token = verify_jwt_token(token)
            except Exception as e:
                print("JWT error:", e)
                email_from_token = None

        conversation_id = get_or_create_conversation(
            user_id,
            request.bot_id
        )

        history_limit = bot_config.get("memory_limit", 6)

        history_rows = get_recent_messages(
            conversation_id,
            limit=history_limit
        ) or []

        history_text = "\n".join(
            [f"{r[0].upper()}: {r[1]}" for r in history_rows]
        )

        user_msg = request.user_question.lower()
        # ---------------- SMALLTALK HANDLING ----------------
        smalltalk_type = detect_smalltalk(request.user_question)
        if smalltalk_type:
            response = get_smalltalk_response(smalltalk_type)

            return StreamingResponse(
                stream_text(response),
                media_type="text/plain",
                headers={
                    "X-Suggestions": get_query_suggestions(
                        request.bot_id,
                        request.user_question
                    )
                }
            )

        # ---------------- SMART TICKET INTENT ----------------

        if detect_ticket_intent(request.user_question):
            if history_rows:
                last_role, last_msg = history_rows[-1]
                if last_role == "assistant" and (
                    "describe your issue" in last_msg.lower() or
                    "site name or system affected" in last_msg.lower() or
                    "how long has this issue" in last_msg.lower()
                ):
                    pass
                else:
                     save_message(
                         conversation_id,
                         "assistant",
                          "Please describe your issue first."
                          )
                     return StreamingResponse(
                     stream_text("Please describe your issue first."),
                     media_type="text/plain"
                     )

        # ---------------- TICKET CREATION ----------------

        if history_rows:

            last_role, last_msg = history_rows[-1]

            # STEP 1: User just described their issue → ask for site name
            if last_role == "assistant" and "describe your issue" in last_msg.lower():
                save_message(conversation_id, "user", request.user_question)
                reply = "Thank you. What is the site name or system affected?"
                save_message(conversation_id, "assistant", reply)
                return StreamingResponse(stream_text(reply), media_type="text/plain")

            # STEP 2: User just gave site name → ask for duration
            if last_role == "assistant" and "site name or system affected" in last_msg.lower():
                save_message(conversation_id, "user", request.user_question)
                reply = "How long has this issue been occurring?"
                save_message(conversation_id, "assistant", reply)
                return StreamingResponse(stream_text(reply), media_type="text/plain",
                    headers={
                        "X-Suggestions": get_query_suggestions(
                            request.bot_id,
                            request.user_question
                        )
                    })

            # STEP 3: User just gave duration → now create the ticket
            if last_role == "assistant" and "how long has this issue" in last_msg.lower():

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

                # ---------------- RATE LIMIT ----------------
                try:
                    check_rate_limit(user_email)
                except HTTPException as e:
                    error_msg = e.detail
                    save_message(conversation_id, "assistant", error_msg)
                    return StreamingResponse(stream_text(error_msg), media_type="text/plain")

                # Retrieve collected details from history
                # Get last 6 messages which covers exactly the ticket flow:
                # [user: issue] [bot: site?] [user: site] [bot: duration?]
                recent = get_recent_messages(conversation_id, limit=6)
                
                # Filter to only the last 6 messages ticket flow
                ticket_user_messages = [m[1] for m in recent if m[0] == "user"]
                issue_desc = ticket_user_messages[-2] if len(ticket_user_messages) >= 2 else "N/A"
                site_name  = ticket_user_messages[-1] if len(ticket_user_messages) >= 1 else "N/A"
                duration   = request.user_question

                case = create_salesforce_case(
                    subject="Chatbot Technical Escalation",
                    description=f"Issue: {issue_desc}\nSite: {site_name}\nDuration: {duration}",
                    email=user_email,
                    chat_history=history_text
                )

                case_id = case.get("id", "N/A")
                ticket_category = detect_category(issue_desc)
                response_text = f"""Your support ticket has been created successfully.

--------------------------------
Case ID  : {case_id}
Name     : {user.get("name")}
Email    : {user_email}
User ID  : {user.get("id")}
Issue    : {issue_desc}
Site     : {site_name}
Duration : {duration}
Category : {ticket_category}
--------------------------------"""

                save_message(conversation_id, "user", request.user_question)
                save_message(conversation_id, "assistant", response_text)
                return StreamingResponse(stream_text(response_text), media_type="text/plain")

        # ---------------- SAVE USER MESSAGE ----------------
        question_category = detect_category(request.user_question)
        save_message(conversation_id, "user", request.user_question, category=question_category)

        # ---------------- RAG RETRIEVAL ----------------

        chunks, is_domain = retrieve_chunks(
            user_query=request.user_question,
            bot_id=request.bot_id,
            chat_history=history_rows,
            bot_config=bot_config.get("retriever_config", {})
        )

        if not is_domain:
            return StreamingResponse(
                stream_text(bot_config["domain_message"]),
                media_type="text/plain",
                headers={
                    "X-Suggestions": get_query_suggestions(
                        request.bot_id,
                        request.user_question
                    )
                }
            )

        if not chunks:

            escalation_text = bot_config["escalation_message"] + \
                "\n\nWould you like me to create a support ticket?"

            save_message(conversation_id, "assistant", escalation_text)

            return StreamingResponse(
                stream_text(escalation_text),
                media_type="text/plain",
                headers={
                    "X-Suggestions": json.dumps(["Yes", "No"])
                }
            )

        context_text = "\n".join(chunks)

        # ---------------- LLM RESPONSE ----------------

        async def stream_wrapper():

            tokens = await asyncio.to_thread(
                lambda: list(
                    get_answers(
                        history_text,
                        context_text,
                        request.user_question,
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

            for char in final_answer:
                yield char
                await asyncio.sleep(0.003)

            save_message(conversation_id, "assistant", full_answer, category=question_category)

        return StreamingResponse(
            stream_wrapper(),
            media_type="text/plain",
            headers={
                "X-Accel-Buffering": "no",
                "X-Suggestions": get_query_suggestions(
                    request.bot_id,
                    request.user_question
                )
            }
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
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

from fastapi import Query
from typing import Optional

@router.get("/bot/{bot_id}/suggestions")
async def get_bot_suggestions(
    bot_id: int,
    step: Optional[str] = None,
    last_query: Optional[str] = None,
):
    suggestions = get_suggestions(
        bot_id,
        user_query=last_query or "",
        step=step
    )
    return {"suggestions": suggestions}