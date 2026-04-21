# app/routes/graph.py
# Endpoint to trigger email draft creation for a resolved case

import logging
from fastapi import APIRouter, Header
from pydantic import BaseModel
from typing import Optional
from app.services.graph_service import create_email_draft, get_unread_emails, create_draft_reply, process_emails
from app.services.auth_service import verify_admin_token

logger = logging.getLogger(__name__)

router = APIRouter()


class DraftRequest(BaseModel):
    case_id: str
    user_name: str
    user_email: str
    issue_desc: str
    site_name: str
    duration: str
    resolution_summary: Optional[str] = "Your issue has been investigated and resolved."


@router.post("/graph/create-draft")
def create_draft(request: DraftRequest, authorization: str = Header(None)):
    """
    Called by IT team (or automatically) when a case is resolved.
    Creates a draft email in Outlook ready to send to the user.
    """
    # Verify admin authentication
    verify_admin_token(authorization)
    
    logger.info(f"Creating draft email for case_id={request.case_id}, user_email={request.user_email}")
    
    result = create_email_draft(
        case_id=request.case_id,
        user_name=request.user_name,
        user_email=request.user_email,
        issue_desc=request.issue_desc,
        site_name=request.site_name,
        duration=request.duration,
        resolution_summary=request.resolution_summary
    )
    
    logger.info(f"Draft email created successfully for case_id={request.case_id}")
    return result

@router.get("/graph/unread")
def fetch_unread(authorization: str = Header(None)):
    # Verify admin authentication
    verify_admin_token(authorization)
    
    logger.info("Fetching unread emails")
    return get_unread_emails()

class ReplyRequest(BaseModel):
    message_id:str
    reply_body:str

@router.post("/graph/reply-draft")
def reply_draft(request: ReplyRequest, authorization: str = Header(None)):
    # Verify admin authentication
    verify_admin_token(authorization)
    
    logger.info(f"Creating reply draft for message_id={request.message_id}")
    return create_draft_reply(
        message_id=request.message_id,
        reply_html=request.reply_body
    )

@router.get("/graph/process-emails")
def process_all_emails(authorization: str = Header(None)):
    # Verify admin authentication
    verify_admin_token(authorization)
    
    logger.info("Processing all emails")
    return process_emails()