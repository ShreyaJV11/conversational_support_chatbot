# app/routes/graph.py
# Endpoint to trigger email draft creation for a resolved case

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.graph_service import create_email_draft

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
def create_draft(request: DraftRequest):
    """
    Called by IT team (or automatically) when a case is resolved.
    Creates a draft email in Outlook ready to send to the user.
    """
    result = create_email_draft(
        case_id=request.case_id,
        user_name=request.user_name,
        user_email=request.user_email,
        issue_desc=request.issue_desc,
        site_name=request.site_name,
        duration=request.duration,
        resolution_summary=request.resolution_summary
    )
    return result