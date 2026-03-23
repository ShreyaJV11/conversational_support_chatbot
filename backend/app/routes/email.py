from fastapi import APIRouter, HTTPException
from app.services.email_processor import process_emails
from app.services.graph_service import GraphService
import requests

router = APIRouter()

@router.get("/process-emails")
async def run_email_bot():
    """
    Ye endpoint incoming unread emails ko scan karega, 
    LLM se reply generate karwayega aur Outlook mein draft banayega.
    """
    try:
        # process_emails() function ab email_processor.py se call hoga
        result = process_emails()
        return {"status": "success", "message": "Email processing completed.", "details": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing emails: {str(e)}")


@router.get("/drafts")
async def fetch_drafts():
    """
    Ye endpoint check karne ke liye hai ki Outlook mein kaunse drafts pade hain.
    """
    try:
        graph = GraphService()
        url = f"https://graph.microsoft.com/v1.0/users/{graph.user_id}/mailFolders/drafts/messages"
        response = requests.get(url, headers=graph._headers(), timeout=15)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching drafts: {str(e)}")