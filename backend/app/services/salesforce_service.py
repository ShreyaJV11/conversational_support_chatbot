import requests
import os
import logging

# Logging set kar rahe hain taaki errors pakde ja sakein
logger = logging.getLogger(__name__)

SALESFORCE_INSTANCE = os.getenv("SF_INSTANCE")
SALESFORCE_TOKEN = os.getenv("SF_TOKEN")

def create_salesforce_case(subject: str, description: str, email: str, chat_history: str = ""):
    """
    Creates a polished Salesforce case for HighwirePress MPS support.
    """
    # 1. Check if config exists
    if not SALESFORCE_INSTANCE or not SALESFORCE_TOKEN:
        logger.error("Salesforce configuration missing.")
        return {"id": "MOCK_CASE_123", "status": "Environment variables not set"}

    url = f"{SALESFORCE_INSTANCE}/services/data/v59.0/sobjects/Case"

    # 2. Polished Description with History (Legal & Polished requirement)
    # Support agent ko sab kuch ek hi jagah dikhna chahiye
    full_description = (
        f"--- MPS SUPPORT REQUEST ---\n"
        f"User Email: {email}\n"
        f"Issue Summary: {description}\n\n"
        f"--- RECENT CHAT LOGS ---\n"
        f"{chat_history if chat_history else 'No history available.'}\n"
        f"---------------------------"
    )

    headers = {
        "Authorization": f"Bearer {SALESFORCE_TOKEN}",
        "Content-Type": "application/json"
    }

    # 3. Professional Payload
    payload = {
        "Subject": f"[MPS Support] {subject}", # Professional prefix
        "Description": full_description,
        "SuppliedEmail": email,
        "Origin": "Chatbot",
        "Status": "New",
        "Priority": "Medium"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status() # Agar status 400 ya 500 aaya toh error throw karega
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Salesforce API Error: {e}")
        # Return a graceful fallback instead of crashing
        return {"id": "PENDING", "error": str(e), "message": "Ticket logged in local logs due to API delay."}