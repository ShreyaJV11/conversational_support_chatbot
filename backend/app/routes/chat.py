from fastapi import APIRouter
import re
from pydantic import BaseModel
from typing import Optional, Dict
from app.services.retrieval_service import retrieve_chunks
from app.services.llm_service import get_answers
from app.services.memory_service import (
    get_or_create_user,
    get_or_create_conversation,
    save_message,
    get_recent_messages
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

    try:
        #  STEP 1 — Ensure user_info exists
        if not request.user_info:
            return {
                "response_type": "COLLECT_INFO",
                "message": "Please provide your name and email to continue."
            }

        name = request.user_info.get("name")
        email = request.user_info.get("email")

        # 🚨 STEP 2 — Validate name
        if not name or len(name.strip()) < 2:
            return {
                "response_type": "COLLECT_INFO",
                "message": "Please enter a valid name."
            }

        # 🚨 STEP 3 — Validate email
        if not email or not is_valid_email(email):
            return {
                "response_type": "COLLECT_INFO",
                "message": "Please enter a valid email address."
            }

        # ✅ Normal chat flow starts here
        query = request.user_question

        user_id = get_or_create_user(name, email)
        conversation_id = get_or_create_conversation(user_id)
        history_rows = get_recent_messages(conversation_id, limit=6) or []

        history_text = "\n".join([f"{r[0].upper()}: {r[1]}" for r in history_rows])

        save_message(conversation_id, "user", query)

        chunks, is_domain = retrieve_chunks(query, history_rows)

        if not is_domain:
            return {
                "response_type": "ERROR",
                "message": "Sorry, I can only answer questions related to HighWirePress systems."
            }
        
        

        if not chunks:
            save_message(conversation_id, "assistant",
            "I couldn't find relevant information in our knowledge base. "
            "Would you like me to raise a support case for this issue?"
            )
            return {
                "response_type": "OFFER_ESCALATION",
                "message": "I couldn't find relevant information in our knowledge base. "
                "Would you like me to raise a support case for this issue?"
                }
        context_text = "\n".join(chunks)
        answer = get_answers(history_text, context_text, query)

        save_message(conversation_id, "assistant", answer)

        return {
            "response_type": "ANSWERED",
            "answer": answer,
            "confidence_score": 0.95
        }

    except Exception as e:
        return {
            "response_type": "ERROR",
            "message": f"Backend error: {str(e)}"
        }


@router.get("/chat/initial-message")
async def get_initial():
    return {
        "response_type": "COLLECT_INFO",
        "message": "Welcome to MPS Support. Please provide your name and email to continue."
    }