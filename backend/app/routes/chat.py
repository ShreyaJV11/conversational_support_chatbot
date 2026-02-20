from fastapi import APIRouter, HTTPException
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

# 1. Request model update kiya (Frontend 'user_question' bhej raha hai)
class ChatRequest(BaseModel):
    user_question: str
    user_info: Optional[Dict] = None  # Frontend name/email info yahan bhejta hai
    user_session_id: Optional[str] = "default_session"

@router.post("/chat")
async def chat_with_highwire(request: ChatRequest):
    try:
        # User info extract karna (Name/Email)
        name = request.user_info.get("name", "Anonymous") if request.user_info else "Anonymous"
        email = request.user_info.get("email", "unknown@mps.com") if request.user_info else "unknown@mps.com"
        query = request.user_question

        user_id = get_or_create_user(name, email)
        conversation_id = get_or_create_conversation(user_id)
        history_rows = get_recent_messages(conversation_id, limit=6)

        history_text = "\n".join([f"{r[0].upper()}: {r[1]}" for r in history_rows])
        chunks, is_domain = retrieve_chunks(query)

        # 2. Response format update kiya (Frontend ke switch-case ke liye)
        if not is_domain:
            ans = "I am a HighWire specialist. I can only assist with HighWirePress systems."
            save_message(conversation_id, "assistant", ans)
            return {
                "response_type": "ERROR",
                "message": "Sorry, I can only answer questions related to HighWirePress systems."
            }

        if not chunks:
            ans = "I don't have enough technical data on this. Escalating..."
            save_message(conversation_id, "assistant", ans)
            return {
                "response_type": "ESCALATED",
                "message": "I don't have enough info. A support ticket has been raised.",
                "case_id": f"REQ-{user_id}"
            }
        

        context_text = "\n".join(chunks)
        answer = get_answers(history_text, context_text, query)
        save_message(conversation_id, "assistant", answer)

        # Frontend expects 'response_type' and 'answer'
        return {
            "response_type": "ANSWERED",
            "answer": answer,
            "confidence_score": 0.95
        }

    except Exception as e:
        # Frontend catch block handle karega
        return {
            "response_type": "ERROR",
            "message": f"Backend error: {str(e)}"
        }

# Initial message endpoint (Frontend uses this)
@router.get("/chat/initial-message")
async def get_initial():
    return "Hi, I'm the MPS Support Assistant. How can I help you today?"