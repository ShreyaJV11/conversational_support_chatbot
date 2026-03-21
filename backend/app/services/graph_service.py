# app/services/graph_service.py
# Microsoft Graph API Service
# Used to create Outlook email drafts for IT support team
# when a Salesforce case is resolved.
#
# SETUP REQUIRED:
# 1. Register an app in Azure Active Directory
# 2. Grant Mail.ReadWrite and Mail.Send permissions
# 3. Fill in GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET in .env

import os
import requests
from dotenv import load_dotenv 

load_dotenv()

TENANT_ID=os.getenv("GRAPH_TENANT_ID")
CLIENT_ID=os.getenv("GRAPH_CLIENT_ID")
CLIENT_SECRET=os.getenv("GRAPH_CLIENT_SECRET")
SENDER_EMAIL=os.getenv("GRAPH_SENDER_EMAIL")
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

#STEP 1: Get Access Token
def get_access_token()->str:
    """
    Authenticates with Microsoft Identity Platform 
    and returns and access bearer token.
    """
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    payload={
        "grant_type":"client_credentials",
        "client_id":CLIENT_ID,
        "client_secret":CLIENT_SECRET,
        "scope":"https://graph.microsoft.com/.default"
    }
    response=requests.post(url,data=payload)
    if response.status_code!=200:
        raise Exception(f"Failed to get access token: {response.text}")
    return response.json()["access_token"]

#STEP 2: Create Email Draft 

def build_email_body(
         case_id: str,
        user_name: str,
        user_email: str,
        issue_desc: str,
        site_name: str,
        duration: str,
        resolution_summary: str
)->str:
    """
    Builds the HTML body of the resolution email draft.
    """
    return f"""
<html>
<body style="font-family: Arial, sans-serif; font-size: 14px;">

<p>Dear {user_name},</p>

<p>We are pleased to inform you that your support ticket has been resolved.</p>

<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
    <tr><td><strong>Case ID</strong></td><td>{case_id}</td></tr>
    <tr><td><strong>Name</strong></td><td>{user_name}</td></tr>
    <tr><td><strong>Email</strong></td><td>{user_email}</td></tr>
    <tr><td><strong>Issue</strong></td><td>{issue_desc}</td></tr>
    <tr><td><strong>Site / System</strong></td><td>{site_name}</td></tr>
    <tr><td><strong>Duration</strong></td><td>{duration}</td></tr>
</table>

<br>
<p><strong>Resolution Summary:</strong></p>
<p>{resolution_summary}</p>

<br>
<p>If you have any further questions, feel free to reach out.</p>

<p>Best regards,<br>
MPS Support Team</p>

</body>
</html>
"""

#STEP 3: Create Draft in Outlook
def create_email_draft(
    case_id: str,
    user_name: str,
    user_email: str,
    issue_desc: str,
    site_name: str,
    duration: str,
    resolution_summary: str = "Your issue has been investigated and resolved."
) -> dict:
    """
    Creates a draft email in the IT support team's Outlook inbox.
    The draft is NOT sent automatically — the IT team reviews
    and sends it manually.

    Returns the draft message ID and web link.
    """

    # Check if credentials are configured
    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET, SENDER_EMAIL]) or \
   "your-" in str(TENANT_ID) or "your-" in str(CLIENT_ID):
        # Return mock response if credentials not yet configured
        return {
            "draft_id": "MOCK_DRAFT_123",
            "web_link": "https://outlook.office.com/mock",
            "status": "mock",
            "message": "Microsoft Graph API credentials not configured yet."
        }

    try:
        token = get_access_token()

        email_body = build_email_body(
            case_id, user_name, user_email,
            issue_desc, site_name, duration,
            resolution_summary
        )

        draft_payload = {
            "subject": f"[Resolved] Support Ticket - Case ID: {case_id}",
            "importance": "Normal",
            "body": {
                "contentType": "HTML",
                "content": email_body
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": user_email,
                        "name": user_name
                    }
                }
            ]
        }

        # Create draft in sender's mailbox
        url = f"{GRAPH_BASE_URL}/users/{SENDER_EMAIL}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=draft_payload, headers=headers)

        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create draft: {response.text}")

        data = response.json()
        return {
            "draft_id": data.get("id"),
            "web_link": data.get("webLink"),
            "status": "created"
        }

    except Exception as e:
        print(f"Graph API Error: {e}")
        return {
            "draft_id": None,
            "status": "error",
            "message": str(e)
        }