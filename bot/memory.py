import sqlite3
import time
from bot.config import DB_PATH, logger

# ---------------- DATABASE SETUP ---------------- #


def _get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    TEXT PRIMARY KEY,
                chat_id    TEXT NOT NULL,
                first_name TEXT DEFAULT '',
                username   TEXT DEFAULT '',
                checkin_enabled INTEGER DEFAULT 1,
                last_checkin_slot TEXT DEFAULT '',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_user
                ON messages(user_id, created_at DESC);
        """)

        # Lightweight forward-compatible migration for older DBs.
        user_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "first_name" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN first_name TEXT DEFAULT ''")
        if "username" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN username TEXT DEFAULT ''")

        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        conn.close()


# ---------------- USER MANAGEMENT ---------------- #


def register_user(user_id: str, chat_id: str, first_name: str = "", username: str = ""):
    """Register a user and keep profile fields fresh."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO users (user_id, chat_id, first_name, username, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                first_name = CASE
                    WHEN excluded.first_name != '' THEN excluded.first_name
                    ELSE users.first_name
                END,
                username = CASE
                    WHEN excluded.username != '' THEN excluded.username
                    ELSE users.username
                END
            """,
            (str(user_id), str(chat_id), (first_name or "").strip(), (username or "").strip(), time.time()),
        )
        conn.commit()
        logger.info("Registered user %s (chat_id=%s)", user_id, chat_id)
    finally:
        conn.close()


def get_user_profile(user_id: str) -> dict:
    """Return persisted user profile fields used for personalization."""
    conn = _get_connection()
    try:
        row = conn.execute(
            """
            SELECT user_id, chat_id, first_name, username
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return {}
        return {
            "user_id": row["user_id"],
            "chat_id": row["chat_id"],
            "first_name": row["first_name"] or "",
            "username": row["username"] or "",
        }
    finally:
        conn.close()


def set_checkin_enabled(user_id: str, enabled: bool):
    """Enable or disable check-ins for a user."""
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE users SET checkin_enabled = ? WHERE user_id = ?",
            (1 if enabled else 0, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_checkin_enabled(user_id: str) -> bool:
    """Check if a user has check-ins enabled."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT checkin_enabled FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return bool(row["checkin_enabled"]) if row else False
    finally:
        conn.close()


def get_all_checkin_users() -> list[dict]:
    """Get all users with check-ins enabled."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT user_id, chat_id, first_name, username, last_checkin_slot
            FROM users
            WHERE checkin_enabled = 1
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_last_checkin_slot(user_id: str, slot: str):
    """Update the last check-in slot for anti-spam."""
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE users SET last_checkin_slot = ? WHERE user_id = ?",
            (slot, user_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------- MESSAGE MEMORY ---------------- #


def save_message(user_id: str, role: str, content: str):
    """Save a message to the database."""
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_messages(user_id: str) -> list[dict]:
    """Get ALL messages for a user (oldest first)."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT role, content
            FROM (
                SELECT role, content, created_at
                FROM messages
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 50
            ) 
            ORDER BY created_at ASC
            """,
            (user_id,),
        ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    finally:
        conn.close()
