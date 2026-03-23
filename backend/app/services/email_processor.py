

import logging
from app.services.graph_service import GraphService, GraphServiceError
from app.services.llm_service import generate_email_reply

logger = logging.getLogger(__name__)


def process_emails() -> dict:
    """
    Fetch unread emails, generate AI replies, and save as drafts.
    Returns a summary dict with processed/failed counts.
    """
    graph     = GraphService()
    emails    = graph.get_unread_emails()

    processed = 0
    failed    = 0
    results   = []

    for email in emails:
        subject    = email.get("subject", "No Subject")
        sender     = email.get("from", {}).get("emailAddress", {}).get("address", "")
        body       = email.get("body", {}).get("content", "")
        message_id = email.get("id")

        # Skip malformed emails
        if not body or not sender or not message_id:
            logger.warning(f"Skipping malformed email — missing fields. ID: {message_id}")
            failed += 1
            continue

        # Isolate per-email errors so one failure doesn't stop the rest
        try:
            logger.info(f"Processing email from: {sender} | subject: {subject}")

            ai_reply = generate_email_reply(subject, body)
            draft_id = graph.create_draft_reply(message_id, ai_reply)

            logger.info(f"Draft created: {draft_id}")
            results.append({"message_id": message_id, "draft_id": draft_id, "status": "ok"})
            processed += 1

        except GraphServiceError as e:
            logger.error(f"Graph API error for message {message_id}: {e}")
            results.append({"message_id": message_id, "status": "failed", "error": str(e)})
            failed += 1

        except Exception as e:
            logger.error(f"Unexpected error for message {message_id}: {e}")
            results.append({"message_id": message_id, "status": "failed", "error": str(e)})
            failed += 1

    logger.info(f"Email processing complete — processed: {processed}, failed: {failed}")
    return {"processed": processed, "failed": failed, "results": results}