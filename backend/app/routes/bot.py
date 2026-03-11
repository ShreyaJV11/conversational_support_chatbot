from fastapi import APIRouter
from app.services.suggestion_service import get_suggestions

router = APIRouter()


@router.get("/bot/{bot_id}/suggestions")
def fetch_suggestions(bot_id: int):
    # Ab FastAPI bina kisi nakhre ke sidha suggestions bhej dega
    suggestions = get_suggestions(bot_id)
    return {"status": "SUCCESS", "suggestions": suggestions}