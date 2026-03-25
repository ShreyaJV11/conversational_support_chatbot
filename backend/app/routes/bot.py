from fastapi import APIRouter, Query
from app.services.suggestion_service import get_suggestions

router = APIRouter()


@router.get("/bot/{bot_id}/suggestions")
def fetch_suggestions(
    bot_id: int,
    user_query: str = Query(...),
    step: str = Query(None)
):
    suggestions = get_suggestions(bot_id, user_query, step)
    return {"status": "SUCCESS", "suggestions": suggestions}