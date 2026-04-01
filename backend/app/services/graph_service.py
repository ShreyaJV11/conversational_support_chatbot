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
from app.services.retrieval_service import retrieve_chunks
from app.services.llm_service import get_answers
import re
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
HighwirePress Support Team</p>

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
    

def get_unread_emails(top: int = 10):
    # ✅ MOCK MODE if credentials not set
    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET, SENDER_EMAIL]) or \
       "your-" in str(TENANT_ID):

        return [
            {
                "id": "MOCK_MSG_1",
                "subject": "Login issue",
                "from": "user1@example.com",
                "body": "I cannot log into my account.",
                "received": "2026-03-24T10:00:00"
            },
            {
                "id": "MOCK_MSG_2",
                "subject": "Site down",
                "from": "user2@example.com",
                "body": "Our site is not loading.",
                "received": "2026-03-24T11:00:00"
            }
        ]

    # 🔽 REAL API (only when credentials exist)
    token = get_access_token()

    url = f"{GRAPH_BASE_URL}/users/{SENDER_EMAIL}/messages?$filter=isRead eq false&$top={top}"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch emails: {response.text}")

    emails = response.json().get("value", [])

    return [
        {
            "id": e.get("id"),
            "subject": e.get("subject"),
            "from": e.get("from", {}).get("emailAddress", {}).get("address"),
            "body": e.get("body", {}).get("content"),
            "received": e.get("receivedDateTime")
        }
        for e in emails
    ]
import html

def create_draft_reply(message_id:str,reply_html:str):
    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET, SENDER_EMAIL]) or \
    "your-" in str(TENANT_ID):

        return {
            "draft_id": "MOCK_REPLY_123",
            "status": "mock",
            "message": "Mock reply draft created successfully."
        }
    token=get_access_token()
    headers={
        "Authorization":f"Bearer {token}",
        "Content-Type":"application/json"
    }
    url=f"{GRAPH_BASE_URL}/users/{SENDER_EMAIL}/messages/{message_id}/createReply"
    response=requests.post(url,headers=headers)
    if response.status_code!=201:
        raise Exception(f"Failed to create reply draft: {response.text}")
    draft=response.json()
    draft_id=draft["id"]
    update_url=f"{GRAPH_BASE_URL}/users/{SENDER_EMAIL}/messages/{draft_id}"
    safe_html = reply_html
    update_payload={
        "body":{
            "contentType":"HTML",
            "content":safe_html
        }
    }
    update_response=requests.patch(update_url,json=update_payload,headers=headers)
    if update_response.status_code!=200:
        raise Exception(f"Failed to update draft: {update_response.text}")
    mark_url=f"{GRAPH_BASE_URL}/users/{SENDER_EMAIL}/messages/{message_id}"
    requests.patch(mark_url,json={"isRead":True}, headers=headers)
    return {
        "draft_id":draft_id,
        "status":"created"
    }
def process_emails():
    emails=get_unread_emails()
    if not emails:
        print("No new emails")
        return {"processed":0, "failed":0, "results":[]}
    processed=0
    failed=0
    results=[]
    for email in emails:
        print(f"📩 Processing email: {email.get('subject')}")
        try:
            subject=email.get("subject","")
            sender=email.get("from","")
            body=email.get("body","")
            message_id=email.get("id")
            if isinstance(sender, dict):
                sender = sender.get("emailAddress", {}).get("address", "")
            if not body or not sender or not message_id:
                failed+=1
                continue
             
            clean_body=re.sub('<.*?>','',body)
            clean_body=re.sub('\s+',' ',clean_body).strip()
            print("🔍 Retrieving context...")
            chunks,found=retrieve_chunks(
                user_query=clean_body,
                bot_id=1,
                chat_history=[]
            )
            if not found:
                ai_reply="I do not have enough internal information to answer that."
            else:
                context="\n".join(chunks)
                print("🧠 Generating LLM response...")
                response_generator=get_answers(
                    history=[],
                    context=context,
                    user_query=clean_body
                )
                try:
                    ai_reply = "".join(list(response_generator))
                except Exception as e:
                    print(f"❌ LLM ERROR: {e}")
                    ai_reply = "We have received your query and will get back to you shortly."
            short, detailed = format_llm_response(ai_reply)

            lines = [line.strip() for line in detailed.split("\n") if line.strip()]

            bullet_html = ""
            for line in lines:
                if line.startswith("-"):
                    bullet_html += f"<li>{line[1:].strip()}</li>"
                else:
                    bullet_html += f"<li>{line}</li>"

            reply_html = f"""
            <p>Hi,</p>

            <p>Thank you for reaching out. We have reviewed your query.</p>

            <table border="1" cellpadding="6" style="border-collapse: collapse;">
                <tr><td><b>Query</b></td><td>{subject}</td></tr>
            </table>

            <br>

            <p><b>Resolution:</b></p>

            <p>{short}</p>

            <ul>
                {bullet_html}
            </ul>

            <br>

            <p>If you have any further questions, feel free to reach out.</p>

            <p>Best regards,<br>IT Support Team</p>
            """
            print("📨 Creating draft reply...")
            draft = create_draft_reply(
                message_id=message_id,
                reply_html=reply_html
            )

            results.append({
                "message_id": message_id,
                "status": "ok",
                "draft": draft
            })

            processed += 1

        except Exception as e:
            print(f"❌ ERROR processing email {message_id}: {e}")  # 👈 ADD THIS
            failed += 1
            results.append({
                "message_id": message_id,
                "status": "failed",
                "error": str(e)
            })

    print(f"✅ Processed: {processed}, Failed: {failed}")

    return {
        "processed": processed,
        "failed": failed,
        "results": results
    }

def format_llm_response(ai_reply: str):
    short = ""
    detailed = ""

    if "SHORT_ANSWER:" in ai_reply:
        parts = ai_reply.split("DETAILED_ANSWER:")
        short = parts[0].replace("SHORT_ANSWER:", "").strip()
        if len(parts) > 1:
            detailed = parts[1].strip()
    else:
        # fallback if format breaks
        detailed = ai_reply.strip()
        short=detailed[:150]

    return short, detailed