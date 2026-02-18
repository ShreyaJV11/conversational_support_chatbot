from app.db.database import get_connection
def get_or_create_user(name:str,email:str):
    conn=get_connection()
    cur=conn.cursor()
    cur.execute("SELECT id FROM users WHERE email=%s",(email,))
    user=cur.fetchone()
    if user:
        user_id=user[0]
    else:
        cur.execute(
            "INSERT INTO users (name,email) VALUES (%s,%s) RETURNING id",
            (name,email)
        )
        user_id=cur.fetchone()[0]
        conn.commit()
    cur.close()
    conn.close()
    return user_id

def get_or_create_conversation(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id FROM conversations
        WHERE user_id = %s AND status = 'active'
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (user_id,)
    )
    convo = cur.fetchone()
    if convo:
        convo_id = convo[0]
    else:
        cur.execute(
            """
            INSERT INTO conversations (user_id, status)
            VALUES (%s, 'active')
            RETURNING id
            """,
            (user_id,)
        )
        convo_id = cur.fetchone()[0]
        conn.commit()
    cur.close()
    conn.close()
    return convo_id

def save_message(conversation_id: int, role: str, content: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messages (conversation_id, role, content)
        VALUES (%s, %s, %s)
        """,
        (conversation_id, role, content)
    )
    cur.execute(
        """
        UPDATE conversations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (conversation_id,)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_recent_messages(conversation_id:int,limit:int=6):
    conn=get_connection()
    cur=conn.cursor()
    cur.execute(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (conversation_id, limit)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return rows[::-1]
