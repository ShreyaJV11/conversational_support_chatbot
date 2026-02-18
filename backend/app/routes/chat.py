from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.retrieval_service import retrieve_chunks
from app.services.llm_service import get_answers
from app.services.memory_service import (
    get_or_create_user,
    get_or_create_conversation,
    save_message,
    get_recent_messages
)
router=APIRouter()
class ChatRequest(BaseModel):
    name:str
    email:str
    query:str
@router.post("/chat")
async def chat_with_highwire(request: ChatRequest):
    try:
        user_id = get_or_create_user(request.name, request.email)
        conversation_id = get_or_create_conversation(user_id)
        history_rows = get_recent_messages(conversation_id)

        history_text = ""
        for role, content in history_rows:
            history_text += f"{role.upper()}: {content}\n"
        chunks, is_domain = retrieve_chunks(request.query)

        if not is_domain:
            return {
                "answer": "Sorry, I can only answer questions related to HighWirePress systems and services.",
                "sources": []
            }

        if not chunks:
            return {
                "answer": "I do not have enough internal information to answer that.",
                "sources": []
            }
        combined_context = history_text + "\n\n" + "\n".join(chunks)
        answer = get_answers(combined_context, request.query)
        save_message(conversation_id, "user", request.query)
        save_message(conversation_id, "assistant", answer)
        return {
            "answer": answer,
            "sources": chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backend error: {str(e)}")
