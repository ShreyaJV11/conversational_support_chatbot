import logging
import re
from bs4 import BeautifulSoup

from app.services.graph_service import GraphService, GraphServiceError
from app.services.llm_service import (
    generate_email_reply,
    get_answers
)
from app.services.retrieval_service import retrieve_chunks

logger = logging.getLogger(__name__)

# 🔥 Initialize globally so the MSAL token cache stays alive!
graph = GraphService()


# -------------------------------
# CLEAN HTML EMAIL
# -------------------------------
def clean_email_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    return "\n".join(lines)


# -------------------------------
# MARKETING FILTER
# -------------------------------
def is_marketing_email(subject: str, body: str) -> bool:
    keywords = [
        "unsubscribe",
        "manage preferences",
        "privacy policy",
        "view in browser",
        "product updates"
    ]

    content = (subject + " " + body).lower()
    return any(k in content for k in keywords)


# -------------------------------
# CLEAN LLM OUTPUT
# -------------------------------
def clean_llm_answer(answer: str) -> str:
    if not answer:
        return ""

    answer = answer.replace("SHORT_ANSWER:", "")
    answer = answer.replace("DETAILED_ANSWER:", "")
    return answer.strip()


# -------------------------------
# BETTER QUERY EXTRACTION (FIXED)
# -------------------------------
def extract_clean_query(subject: str, body: str) -> str:
    """
    Cleaner + safer query extraction using Regex to drop IT warning banners.
    """
    # Ignore default empty subjects so they don't get appended to the query
    if subject.strip().lower() in ["no subject", "(no subject)", ""]:
        text = body
    else:
        text = f"{subject}\n{body}"

    # 1. NUKE THE ENTIRE IT WARNING BANNER
    text = re.sub(r'(?is)caution:.*?is safe\.', '', text)
    text = re.sub(r'(?is)this email originated from outside.*?is safe\.', '', text)

    # 2. LINE-BY-LINE FILTERING
    noise_lines = [
        "unsubscribe",
        "privacy policy",
        "view in browser",
        "click here",
        "external email"
    ]

    lines = []
    for line in text.splitlines():
        line_clean = line.strip()
        line_lower = line_clean.lower()

        # Skip empty lines
        if not line_clean:
            continue

        # If the line contains a noise keyword, drop the WHOLE line
        if any(noise in line_lower for noise in noise_lines):
            continue

        # Keep lines that are at least 8 chars OR contain a question mark
        if len(line_clean) < 8 and "?" not in line_clean:
            continue
            
        # Skip URLs and emails
        if line_lower.startswith("http") or "@" in line_clean:
            continue

        lines.append(line_clean)

    cleaned = " ".join(lines)

    return cleaned[:400].strip()


# -------------------------------
# CONTEXT BUILDER
# -------------------------------
def build_context(chunks, user_query):
    if chunks:
        return f"""
You are a helpful support assistant.

Use the following knowledge to answer the query.
Even partial matches are useful. Do NOT say "no information found".

Knowledge:
{chr(10).join(chunks)}

User Query:
{user_query}
"""
    else:
        return f"""
You are a helpful support assistant.

No exact knowledge base match was found.
Still try to answer based on general support knowledge.

User Query:
{user_query}
"""


# -------------------------------
# MAIN PIPELINE
# -------------------------------
def process_emails() -> dict:
    
    # Use the global graph service instance
    emails = graph.get_unread_emails()

    processed = 0
    failed = 0
    results = []

    # Increased to 20 for production so it processes batches of emails!
    MAX_EMAILS = 20

    for idx, email in enumerate(emails):
        if idx >= MAX_EMAILS:
            logger.warning("Stopping early to prevent overload")
            break

        subject = email.get("subject") or "No Subject"
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "")
        raw_body = email.get("body", {}).get("content", "")
        message_id = email.get("id")

        logger.info(f"Processing message_id: {message_id}")

        # -------------------------------
        # VALIDATION
        # -------------------------------
        if not raw_body or not sender or not message_id:
            failed += 1
            continue

        if email.get("isDraft"):
            continue

        if sender.endswith("yourdomain.com"):
            continue

        body = clean_email_html(raw_body)

        if is_marketing_email(subject, body):
            continue

        if len(body.strip()) < 20:
            continue

        try:
            logger.info(f"Processing email from: {sender} | subject: {subject}")

            # -------------------------------
            # QUERY
            # -------------------------------
            user_query = extract_clean_query(subject, body)
            logger.info(f"CLEAN QUERY: {user_query}")

            # -------------------------------
            # RETRIEVAL
            # -------------------------------
            chunks, is_valid = retrieve_chunks(
                user_query=user_query,
                bot_id=1,
                chat_history=[]
            )
            
            # Debugging - feel free to remove this print in production
            print("\n=== WHAT THE LLM SEES ===")
            print(chunks)
            print("=========================\n")

            logger.info(f"Chunks valid: {is_valid}")

            if chunks:
                logger.info(f"Retrieved {len(chunks)} chunks")
            else:
                logger.warning("No chunks retrieved")

            # -------------------------------
            # CONTEXT & LLM ANSWER
            # -------------------------------
            context = build_context(chunks, user_query)
            answer_parts = []

            try:
                for chunk in get_answers([], context, user_query):
                    answer_parts.append(chunk)
            except Exception as e:
                logger.error(f"LLM streaming error: {e}")

            answer = clean_llm_answer("".join(answer_parts).strip())

            logger.info(f"FINAL ANSWER: {answer}")

            # -------------------------------
            # RELAXED FALLBACK & DRAFTING
            # -------------------------------
            if not answer:
                logger.warning("Empty answer → fallback")

                ai_reply = f"""Hello,

Thank you for reaching out.

Based on your query:
"{user_query}"

Our team will review and get back to you shortly.

Regards,  
Support Team
"""
            else:
                email_body = f"""Customer Query:
{user_query}

Answer:
{answer}
"""
                ai_reply = generate_email_reply(subject, email_body)

            # -------------------------------
            # CREATE DRAFT
            # -------------------------------
            draft_id = graph.create_draft_reply(message_id, ai_reply)

            results.append({
                "message_id": message_id,
                "draft_id": draft_id,
                "status": "ok"
            })

            processed += 1

        except Exception as e:
            logger.error(f"Error: {e}")

            results.append({
                "message_id": message_id,
                "status": "failed",
                "error": str(e)
            })

            failed += 1

    return {
        "processed": processed,
        "failed": failed,
        "results": results
    }