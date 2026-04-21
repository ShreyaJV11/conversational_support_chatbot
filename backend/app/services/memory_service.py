from app.db.database import get_connection, return_connection


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def get_or_create_organization(email: str) -> int:
    """
    Extract domain from email and get or create organization.
    Returns organization_id.
    """
    try:
        domain = email.split('@')[1].lower()
        # Extract organization name from domain (e.g., highwirepress.com -> HighWirePress)
        org_name = domain.split('.')[0].capitalize()
    except (IndexError, AttributeError):
        domain = "unknown.com"
        org_name = "Unknown"
    
    conn = get_connection()
    try:
        cur = conn.cursor()
        
        # Try to get existing organization
        cur.execute(
            """
            SELECT id FROM organizations 
            WHERE domain = %s
            """,
            (domain,)
        )
        
        result = cur.fetchone()
        if result:
            return result[0]
        
        # Create new organization
        cur.execute(
            """
            INSERT INTO organizations (domain, organization_name)
            VALUES (%s, %s)
            RETURNING id
            """,
            (domain, org_name)
        )
        
        org_id = cur.fetchone()[0]
        conn.commit()
        return org_id
        
    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)  # Return to pool instead of closing


# ==========================================================
# USER FUNCTIONS
# ==========================================================

def get_or_create_user(bot_id: int, name: str, email: str) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        
        # Get or create organization
        organization_id = get_or_create_organization(email)

        cur.execute(
            """
            INSERT INTO users (bot_id, name, email, organization_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (bot_id, email)
            DO UPDATE SET name = EXCLUDED.name, organization_id = EXCLUDED.organization_id
            RETURNING id
            """,
            (bot_id, name, email, organization_id)
        )

        user_id = cur.fetchone()[0]
        conn.commit()
        return user_id

    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)


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
        if cur:
            cur.close()
        if conn:
            return_connection(conn)


def get_user_by_session(bot_id: int, session_id: str):
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT u.id, u.name, u.email, o.organization_name, o.domain
            FROM users u
            JOIN sessions s ON u.id = s.user_id
            LEFT JOIN organizations o ON u.organization_id = o.id
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
                "email": row[2],
                "organization": row[3],
                "domain": row[4]
            }

        return None

    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)


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
        if cur:
            cur.close()
        if conn:
            return_connection(conn)


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
        if cur:
            cur.close()
        if conn:
            return_connection(conn)


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
        if cur:
            cur.close()
        if conn:
            return_connection(conn)