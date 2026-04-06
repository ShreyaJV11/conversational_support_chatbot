import asyncio
import logging
import requests
from fastapi import APIRouter, HTTPException
from app.services.email_processor import process_emails
from app.services.graph_service import GraphService

router = APIRouter()
logger = logging.getLogger(__name__)

# ✅ Global instance (important)
graph = GraphService()


@router.get("/process-emails")
async def run_email_bot():
    try:
        logger.info("Starting email processing...")
        result = await asyncio.to_thread(process_emails)

        return {
            "status": "success",
            "message": "Email processing completed.",
            "details": result
        }

    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drafts")
async def fetch_drafts():
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{graph.user_id}/mailFolders/drafts/messages"
        response = requests.get(url, headers=graph._headers(), timeout=15)

        response.raise_for_status()
        data = response.json()

        return {
            "status": "success",
            "count": len(data.get("value", [])),
            "data": data.get("value", [])
        }

    except Exception as e:
        logger.error(f"Draft fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))