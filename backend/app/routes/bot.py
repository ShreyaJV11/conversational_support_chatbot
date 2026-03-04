from fastapi import APIRouter
from app.services.suggestion_service import get_suggestions

router = APIRouter()

@router.get("/bot/{bot_id}/suggestions")
def fetch_suggestions(bot_id: int):
    return get_suggestions(bot_id)