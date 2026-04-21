import json
import logging
import re
import time
from app.db.database import get_connection, return_connection
from app.services.llm_service import create_chat_model
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.retrieval_service import retrieve_chunks
 
logger = logging.getLogger(__name__)
 
 
FALLBACK_SUGGESTIONS = {
    "issue":    ["Login issue", "Site down", "Payment error"],
    "site":     ["Production", "Staging", "Mobile App"],
    "duration": ["Just started", "Since 1 hour", "Since today"],
    "default":  ["What is JCore?", "How to setup Sigma Solr?", "How to restart Fragr?"],
}
 
 
def extract_suggestions(text: str) -> list:
    """
    Robustly extract up to 3 string suggestions from LLM JSON output.
 
    FIX: Original code double-counted dict values — it looped over all key/value
         pairs AND then separately checked for a 'question' key, causing duplicates.
         Now: if 'question' key exists, use only that; otherwise take first str value.
    """
    # Attempt direct parse first
    try:
        data = json.loads(text)
    except Exception:
       
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group())
        except Exception:
            return []
 
    suggestions = []
 
 
    if isinstance(data, list) and all(isinstance(i, str) for i in data):
        return data[:3]
 
 
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
 
            # FIX: was doing both a values-loop AND a question-key check,
            #      causing duplicate entries. Now pick one path only.
            if "question" in item and isinstance(item["question"], str):
                # Prefer explicit 'question' key if present
                suggestions.append(item["question"])
            else:
                # Otherwise take the first string value found
                for val in item.values():
                    if isinstance(val, str):
                        suggestions.append(val)
                        break  # only one value per dict item
 
    return suggestions[:3]
 
 
def get_suggestions(bot_id: int, user_query: str, step: str = None) -> list:
    conn = None
    cur  = None
 
    try:
        conn = get_connection()
        cur  = conn.cursor()
 
        # 1. Fetch KB context chunks (skip if empty query)
        if not user_query or not user_query.strip():
            return FALLBACK_SUGGESTIONS.get(step, FALLBACK_SUGGESTIONS["default"])
       
        chunks, is_valid = retrieve_chunks(user_query, bot_id)
        if not is_valid or not chunks:
            return FALLBACK_SUGGESTIONS.get(step, FALLBACK_SUGGESTIONS["default"])
        combined_text = " ".join(chunks)
 
        # 2. Model config
        # FIX: removed top_p — create_chat_model does not accept it and it caused
        #      a silent lru_cache key mismatch (extra kwarg was silently ignored
        #      but polluted the cache key hash in some vsuggestions = get_suggestions(bot_id)ersions).
        chat_model = create_chat_model({
            "max_new_tokens": 200,
            "temperature": 0.0,
        })
 
        # 3. Step config
        step_map = {
            "issue": {
                "desc": "3 short PROBLEM statements (max 5 words each)",
                "ex":   '["Site down", "Login failed", "Payment error"]',
            },
            "site": {
                "desc": "3 system/environment names",
                "ex":   '["Production", "Staging", "Mobile App"]',
            },
            "duration": {
                "desc": "3 time durations",
                "ex":   '["Just started", "Since 1 hour", "Since today"]',
            },
            "default": {
                "desc": "3 relevant follow-up questions based on the context",
                "ex":   '["Can you explain more?","What are the features?","How does it work?"]',
            },
        }
 
        config = step_map.get(step, step_map["default"])
 
        # 4. System prompt
        system_prompt = (
            f"You MUST return ONLY a valid JSON array.\n"
            f"DO NOT return numbered list.\n"
            f"DO NOT return text.\n"
            f"ONLY JSON.\n\n"
            f"Format:\n{config['ex']}\n\n"
            "Rules:\n"
            "- Only JSON array\n"
            "- No numbering\n"
            "- No explanation\n"
            "- Max 3 items\n"
            "- Questions MUST be related to the USER QUESTION\n"
)
 
        # 5. LLM call with retry
        response = None
        for attempt in range(3):
            try:
                response = chat_model.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Context:\n{combined_text[:1500]}"),
                ])
                break
            except Exception as e:
                logger.error(f"LLM attempt {attempt + 1} failed: {e}")
                time.sleep(2)
 
        if not response:
            return FALLBACK_SUGGESTIONS.get(step, FALLBACK_SUGGESTIONS["default"])
 
        raw_text = response.content.strip()
 
        # 6. Strip markdown fences
        clean_text = raw_text.replace("```json", "").replace("```", "").strip()
 
        # 7. Extract JSON array boundaries
        start = clean_text.find("[")
        end   = clean_text.rfind("]")
 
        if start == -1:
            logger.error(f"No JSON array found in LLM output: {raw_text!r}")
            return FALLBACK_SUGGESTIONS.get(step, FALLBACK_SUGGESTIONS["default"])
 
        json_candidate = (
            clean_text[start: end + 1] if end != -1
            else clean_text[start:] + "]"
        )
 
        # 8. Fix trailing commas before closing bracket
        json_candidate = re.sub(r",\s*\]", "]", json_candidate)
 
        # 9. Extract and validate
        suggestions = extract_suggestions(json_candidate)
 
        if not suggestions:
            logger.warning("extract_suggestions returned empty — using fallback.")
            return FALLBACK_SUGGESTIONS.get(step, FALLBACK_SUGGESTIONS["default"])
 
        return suggestions
 
    except Exception as e:
        logger.error(f"get_suggestions unexpected error: {e}")
        return FALLBACK_SUGGESTIONS.get(step, FALLBACK_SUGGESTIONS["default"])
 
    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)




# from app.db.database import get_connection
# from app.services.llm_service import create_chat_model
# from langchain_core.messages import SystemMessage, HumanMessage
# import json

# def get_suggestions(bot_id: int):
#     conn = get_connection()
#     cur = conn.cursor()

#     try:
#         cur.execute("""
#             SELECT chunk_text
#             FROM kb_chunks
#             WHERE bot_id = %s
#             ORDER BY RANDOM()
#             LIMIT 15;
#         """, (bot_id,))

#         rows = cur.fetchall()
#         #suggestions = []

#         if not rows:
#             return []

#         combined_text = "\n\n".join([row[0] for row in rows])
#         chat_model = create_chat_model({})

#         response = chat_model.invoke([
#             SystemMessage(content="""Return ONLY a valid JSON array of 3 short support questions.
# No explanation, no markdown, no extra text.
# Example: ["How do I reset my password?", "How do I contact support?", "What is JCore?"]"""),
#             HumanMessage(content=f"Generate 3 suggested questions from this:\n\n{combined_text}")
#         ])

#         text = response.content.strip()
#         text = text.replace("```json", "").replace("```", "").strip()
#         start = text.find("[")
#         end = text.rfind("]") + 1
#         if start == -1 or end == 0:
#             return []

#         suggestions = json.loads(text[start:end])
#         return [s for s in suggestions if isinstance(s, str)][:3]

#     except Exception as e:
#         print("Suggestion Error:", e)
#         return []

#     finally:
#         if cur: cur.close()
#         if conn: conn.close()