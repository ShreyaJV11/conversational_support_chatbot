from app.db.database import get_connection

import json
import logging
from app.db.database import get_connection
from app.services.llm_service import create_chat_model
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

def get_suggestions(bot_id: int, step: str = None):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT chunk_text 
            FROM kb_chunks 
            WHERE bot_id = %s 
            LIMIT 15;
        """, (bot_id,))
        rows = cur.fetchall()

        if not rows:
            return []

        combined_text = "\n\n".join([row[0] for row in rows])

        chat_model = create_chat_model({
            "max_new_tokens": 100,
            "temperature": 0.2
        })

        # 🔥 CHANGE ONLY THIS PART (PROMPT BASED ON STEP)

        if step == "issue":
            prompt = (
                "Return ONLY a valid JSON array of 3 short PROBLEM statements.\n"
                "These should describe issues a user might face.\n"
                "No explanation.\n"
                "Example: [\"Site down\", \"Login failed\", \"Payment error\"]"
            )

        elif step == "site":
            prompt = (
                "Return ONLY a valid JSON array of 3 system/site names.\n"
                "These should be environments or systems.\n"
                "No explanation.\n"
                "Example: [\"Production\", \"Staging\", \"Mobile App\"]"
            )

        elif step == "duration":
            prompt = (
                "Return ONLY a valid JSON array of 3 time durations.\n"
                "These should represent how long an issue exists.\n"
                "No explanation.\n"
                "Example: [\"Just started\", \"Since 1 hour\", \"Since today\"]"
            )

        else:
            # normal chat mode
            prompt = (
                "Return ONLY a valid JSON array of 3 short SUPPORT QUESTIONS.\n"
                "No explanation.\n"
                "Example: [\"Restart site\", \"Check logs\", \"Fix login issue\"]"
            )

        response = chat_model.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Generate suggestions from this:\n\n{combined_text}")
        ])

        text = response.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()

        start = text.find("[")
        end = text.rfind("]") + 1

        if start == -1 or end == 0:
            return []

        suggestions = json.loads(text[start:end])

        return [str(s) for s in suggestions][:3]

    except Exception as e:
        logger.error(f"get_suggestions error: {e}")
        return []

    finally:
        if cur: cur.close()
        if conn: conn.close()