from app.db.database import get_connection


# ==========================================================
# USER FUNCTIONS
# ==========================================================

def get_or_create_user(bot_id: int, name: str, email: str) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO users (bot_id, name, email)
            VALUES (%s, %s, %s)
            ON CONFLICT (bot_id, email)
            DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (bot_id, name, email)
        )

        user_id = cur.fetchone()[0]
        conn.commit()
        return user_id

    finally:
        cur.close()
        conn.close()


def link_session_to_user(bot_id: int, user_id: int, session_id: str):
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO sessions (bot_id, user_id, session_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (session_id)
            DO UPDATE SET user_id = EXCLUDED.user_id
            """,
            (bot_id, user_id, session_id)
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()


def get_user_by_session(bot_id: int, session_id: str):
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT u.id, u.name, u.email
            FROM users u
            JOIN sessions s ON u.id = s.user_id
            WHERE s.session_id = %s
            AND s.bot_id = %s
            """,
            (session_id, bot_id)
        )

        row = cur.fetchone()

        if row:
            return {
                "id": row[0],
                "name": row[1],
                "email": row[2]
            }

        return None

    finally:
        cur.close()
        conn.close()


# ==========================================================
# CONVERSATION FUNCTIONS
# ==========================================================

def get_or_create_conversation(user_id: int, bot_id: int, force_new: bool = False) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()

        # If force_new, close all existing active conversations first
        if force_new:
            cur.execute(
                """
                UPDATE conversations
                SET status = 'closed'
                WHERE user_id = %s AND bot_id = %s AND status = 'active'
                """,
                (user_id, bot_id)
            )
            conn.commit()

        cur.execute(
            """
           SELECT id FROM conversations
           WHERE user_id = %s
           AND bot_id = %s
           AND status = 'active'
            """,
            (user_id, bot_id)
        )

        convo = cur.fetchone()

        if convo:
            return convo[0]

        cur.execute(
            """
            INSERT INTO conversations (user_id, bot_id, status)
            VALUES (%s, %s, 'active')
            RETURNING id
            """,
            (user_id, bot_id)
        )

        convo_id = cur.fetchone()[0]
        conn.commit()
        return convo_id

    finally:
        cur.close()
        conn.close()


def save_message(conversation_id: int, role: str, content: str, category: str = None):
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO messages (conversation_id, role, content, category)
            VALUES (%s, %s, %s, %s)
            """,
            (conversation_id, role, content, category)
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

    finally:
        cur.close()
        conn.close()


def get_recent_messages(conversation_id: int, limit: int = 6):
    conn = get_connection()
    try:
        cur = conn.cursor()

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
        return rows[::-1]  # chronological order

    finally:
        cur.close()
        conn.close()