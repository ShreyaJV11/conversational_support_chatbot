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
from app.services.bot_service import get_bot_config


router = APIRouter()

# ==========================================================
# REQUEST MODEL
# ==========================================================

class ChatRequest(BaseModel):
    user_question: str
    user_info: Optional[Dict] = None
    user_session_id: Optional[str] = "default_session"
    bot_id: int


# ==========================================================
# HELPERS
# ==========================================================

def is_valid_email(email: str) -> bool:
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email) is not None


def stream_text(text: str):
    async def generator():
        for char in text:
            yield char
            await asyncio.sleep(0.003)
    return generator()


# ==========================================================
# MAIN CHAT ENDPOINT
# ==========================================================

@router.post("/chat")
async def chat(request: ChatRequest):

    try:

        # -----------------------------------------
        # 1️⃣ Load Bot Config
        # -----------------------------------------

        bot_config = get_bot_config(request.bot_id)

        if not bot_config:
            return StreamingResponse(
                stream_text("Invalid bot configuration."),
                media_type="text/plain"
            )

        require_registration = bot_config.get("require_registration", True)

        # -----------------------------------------
        # 2️⃣ Check Session
        # -----------------------------------------

        existing_user = get_user_by_session( request.bot_id,request.user_session_id)

        if require_registration and not existing_user:

            name = None
            email = None

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

            user_id = get_or_create_user(request.bot_id, name, email)
            link_session_to_user( request.bot_id,user_id, request.user_session_id)
            get_or_create_conversation(user_id, request.bot_id)

            return StreamingResponse(
                stream_text(f"Thank you {name}. How can I assist you today?"),
                media_type="text/plain"
            )

        # -----------------------------------------
        # 3️⃣ Normal Flow
        # -----------------------------------------

        user = existing_user
        user_id = user["id"]
        conversation_id = get_or_create_conversation(user_id, request.bot_id)

        history_limit = bot_config.get("memory_limit", 6)

        history_rows = get_recent_messages(conversation_id, limit=history_limit) or []

        history_text = "\n".join(
            [f"{r[0].upper()}: {r[1]}" for r in history_rows]
        )

        save_message(conversation_id, "user", request.user_question)

        # -----------------------------------------
        # 4️⃣ Retrieval (Bot Scoped)
        # -----------------------------------------

        chunks, is_domain = retrieve_chunks(
            user_query=request.user_question,
            bot_id=request.bot_id,
            chat_history=history_rows,
            bot_config=bot_config.get("retriever_config", {})
        )

        if not is_domain:
            return StreamingResponse(
                stream_text(bot_config["domain_message"]),
                media_type="text/plain"
            )

        if not chunks:
            escalation_text = bot_config["escalation_message"]

            save_message(conversation_id, "assistant", escalation_text)

            return StreamingResponse(
                stream_text(escalation_text),
                media_type="text/plain"
            )

        context_text = "\n".join(chunks)

        # -----------------------------------------
        # 5️⃣ Stream LLM (Configurable)
        # -----------------------------------------

        async def stream_wrapper():
            full_answer = ""

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

            for token in tokens:
                full_answer += token
                yield token
                await asyncio.sleep(0.003)

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
            stream_text("Internal server error."),
            media_type="text/plain"
        )


# ==========================================================
# INITIAL MESSAGE ENDPOINT (Bot Based)
# ==========================================================

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