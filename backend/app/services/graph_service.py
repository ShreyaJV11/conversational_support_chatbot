# app/services/graph_service.py
from dotenv import load_dotenv
load_dotenv()
import os
import html
import logging
from typing import Optional
import msal
import requests
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class GraphServiceError(Exception):
    """Raised when a Microsoft Graph API call fails."""
    pass


class GraphService:
    def __init__(self):
        self.client_id     = os.getenv("AZURE_CLIENT_ID")
        self.client_secret = os.getenv("AZURE_CLIENT_SECRET")
        self.tenant_id     = os.getenv("AZURE_TENANT_ID")
        self.user_id       = os.getenv("SUPPORT_MAILBOX_ADDRESS")
        self.authority     = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes        = ["https://graph.microsoft.com/.default"]

        self._validate_config()

        # MSAL app instance kept alive to reuse its token cache
        self._msal_app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )

    def _validate_config(self):
        missing = [
            var for var in [
                "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
                "AZURE_TENANT_ID", "SUPPORT_MAILBOX_ADDRESS"
            ]
            if not os.getenv(var)
        ]
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

    # ------------------------------------------------------------------
    # TOKEN MANAGEMENT
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """
        Acquire access token using MSAL cache.
        Only makes a network call when token is expired or missing.
        """
        # Try cache first
        result = self._msal_app.acquire_token_silent(self.scopes, account=None)

        if not result:
            logger.info("Token not in cache, acquiring from Azure...")
            result = self._msal_app.acquire_token_for_client(scopes=self.scopes)

        if "access_token" not in result:
            error = result.get("error_description", "Unknown error")
            raise GraphServiceError(f"Could not acquire Azure token: {error}")

        return result["access_token"]

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def _raise_for_status(self, response: requests.Response, context: str):
        """Raise GraphServiceError with context if response is not 2xx."""
        if not response.ok:
            raise GraphServiceError(
                f"{context} failed [{response.status_code}]: {response.text[:200]}"
            )

    # ------------------------------------------------------------------
    # EMAIL OPERATIONS
    # ------------------------------------------------------------------

    def get_unread_emails(self, top: int = 10) -> list[dict]:
        """
        Fetch unread emails from the support mailbox.
        Returns a list of message dicts.
        """
        url = (
            f"{GRAPH_BASE}/users/{self.user_id}/messages"
            f"?$filter=isRead eq false&$top={top}"
            f"&$select=id,subject,from,body,receivedDateTime"
        )

        try:
            response = requests.get(url, headers=self._headers(), timeout=15)
            self._raise_for_status(response, "get_unread_emails")
            emails = response.json().get("value", [])
            logger.info(f"Fetched {len(emails)} unread email(s).")
            return emails
        except GraphServiceError:
            raise
        except Exception as e:
            raise GraphServiceError(f"get_unread_emails unexpected error: {e}")

    def create_draft_reply(self, message_id: str, reply_content: str) -> str:
        """
        Create a draft reply for a given message.
        Returns the draft message ID.
        """
        headers = self._headers()

        # Step 1: Create reply draft
        create_url = (
            f"{GRAPH_BASE}/users/{self.user_id}"
            f"/messages/{message_id}/createReply"
        )
        create_response = requests.post(create_url, headers=headers, timeout=15)
        self._raise_for_status(create_response, "createReply")

        reply_msg = create_response.json()
        draft_id  = reply_msg.get("id")

        if not draft_id:
            raise GraphServiceError(
                f"createReply returned no draft ID for message {message_id}"
            )

        # Step 2: Update draft body — escape HTML to prevent injection
        safe_content = html.escape(reply_content).replace("\n", "<br>")
        update_url   = f"{GRAPH_BASE}/users/{self.user_id}/messages/{draft_id}"
        update_data  = {
            "body": {"contentType": "HTML", "content": safe_content}
        }
        update_response = requests.patch(
            update_url, headers=headers, json=update_data, timeout=15
        )
        self._raise_for_status(update_response, "updateDraft")

        # Step 3: Mark original email as read
        mark_read_url  = f"{GRAPH_BASE}/users/{self.user_id}/messages/{message_id}"
        mark_response  = requests.patch(
            mark_read_url, headers=headers, json={"isRead": True}, timeout=15
        )
        self._raise_for_status(mark_response, "markAsRead")

        logger.info(f"Draft created: {draft_id} for message: {message_id}")
        return draft_id