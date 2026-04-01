from app.db.database import get_connection
from app.services.llm_service import create_chat_model
from langchain_core.messages import SystemMessage, HumanMessage
import json

def get_suggestions(bot_id: int):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT chunk_text
            FROM kb_chunks
            WHERE bot_id = %s
            ORDER BY RANDOM()
            LIMIT 15;
        """, (bot_id,))

        rows = cur.fetchall()
        #suggestions = []

        if not rows:
            return []

        combined_text = "\n\n".join([row[0] for row in rows])
        chat_model = create_chat_model({})

        response = chat_model.invoke([
            SystemMessage(content="""Return ONLY a valid JSON array of 3 short support questions.
No explanation, no markdown, no extra text.
Example: ["How do I reset my password?", "How do I contact support?", "What is JCore?"]"""),
            HumanMessage(content=f"Generate 3 suggested questions from this:\n\n{combined_text}")
        ])

        text = response.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            return []

        suggestions = json.loads(text[start:end])
        return [s for s in suggestions if isinstance(s, str)][:3]

    except Exception as e:
        print("Suggestion Error:", e)
        return []

    finally:
        if cur: cur.close()
        if conn: conn.close()