
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict
import re
import asyncio

from app.services.retrieval_service import retrieve_chunks
from app.services.llm_service import get_answers
from app.services.memory_service import (
    get_or_create_user,
    get_or_create_conversation,
    save_message,
    get_recent_messages,
    get_user_by_session,
    link_session_to_user
)

router = APIRouter()


class ChatRequest(BaseModel):
    user_question: str
    user_info: Optional[Dict] = None
    user_session_id: Optional[str] = "default_session"
    bot_id: Optional[int] = None


def is_valid_email(email: str) -> bool:
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email) is not None
@router.post("/chat")

async def chat_with_highwire(request: ChatRequest):
    print("Incoming request:", request.dict())

    async def stream_text(text: str):
        for char in text:
            yield char
            await asyncio.sleep(0.005)

    try:

        # =============================
        # STEP 1: Check Existing Session
        # =============================

        existing_user = get_user_by_session(request.user_session_id)

        if existing_user:
            name = existing_user["name"]
            email = existing_user["email"]
        else:
            name = None
            email = None

            # Structured user_info
            if request.user_info:
                name = request.user_info.get("name")
                email = request.user_info.get("email")

            # Typed "name,email"
            elif "," in request.user_question:
                parts = request.user_question.split(",")
                if len(parts) == 2:
                    name = parts[0].strip()
                    email = parts[1].strip()

            # Validate registration input
            if not name or len(name.strip()) < 2:
                return StreamingResponse(
                    stream_text("Please provide your name and email to continue."),
                    media_type="text/plain"
                )

            if not email or not is_valid_email(email):
                return StreamingResponse(
                    stream_text("Please provide a valid email address."),
                    media_type="text/plain"
                )

            # Register + link session
            user_id = get_or_create_user(name, email)
            link_session_to_user(user_id, request.user_session_id)
            get_or_create_conversation(user_id)

            return StreamingResponse(
                stream_text(f"Thank you {name}. You are now registered. How can I assist you today?"),
                media_type="text/plain"
            )

        # =============================
        # STEP 2: Normal Conversation Flow
        # =============================

        query = request.user_question

        user_id = get_or_create_user(name, email)
        conversation_id = get_or_create_conversation(user_id)

        history_rows = get_recent_messages(conversation_id, limit=6) or []

        history_text = "\n".join(
            [f"{r[0].upper()}: {r[1]}" for r in history_rows]
        )

        save_message(conversation_id, "user", query)

        # =============================
        # STEP 3: Retrieval
        # =============================

        chunks, is_domain = retrieve_chunks(query, history_rows)

        if not is_domain:
            return StreamingResponse(
                stream_text("Sorry, I can only answer questions related to HighWirePress systems."),
                media_type="text/plain"
            )

        if not chunks:
            escalation_text = (
                "I couldn't find relevant information in our knowledge base. "
                "Would you like me to raise a support case for this issue?"
            )

            save_message(conversation_id, "assistant", escalation_text)

            return StreamingResponse(
                stream_text(escalation_text),
                media_type="text/plain"
            )

        context_text = "\n".join(chunks)

        # =============================
        # STEP 4: Stream LLM
        # =============================

        async def stream_wrapper():
            full_answer = ""

            tokens = await asyncio.to_thread(
                lambda: list(get_answers(history_text, context_text, query))
            )

            for token in tokens:
                full_answer += token
                yield token
                await asyncio.sleep(0.005)

            save_message(conversation_id, "assistant", full_answer)

        return StreamingResponse(
            stream_wrapper(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        print(f"Error: {e}")
        return StreamingResponse(
            stream_text("An internal error occurred."),
            media_type="text/plain"
        )
@router.get("/chat/initial-message")
async def get_initial():
    return {
        "response_type": "COLLECT_INFO",
        "message": "Welcome to MPS Support. Please provide your name and email to continue."
    }