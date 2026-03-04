from app.db.database import get_connection

def get_suggestions(bot_id: int):
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
        suggestions = []

        for row in rows:
            text = row[0]
            lines = text.split("\n")

            for line in lines:
                clean_line = line.strip()

                # Skip empty lines
                if not clean_line:
                    continue

                # Only keep lines with question mark
                if "?" in clean_line:

                    # Remove "- Yes", "- Not", etc.
                    clean_line = clean_line.split("?")[0] + "?"

                    if clean_line not in suggestions:
                        suggestions.append(clean_line)

                if len(suggestions) >= 5:
                    break

            if len(suggestions) >= 5:
                break

        return suggestions

    except Exception as e:
        print("Suggestion Error:", e)
        return []

    finally:
        cur.close()
        conn.close()