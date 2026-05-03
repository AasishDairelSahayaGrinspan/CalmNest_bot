import sqlite3
import time
import json
from bot.config import DB_PATH, logger

# ---------------- DATABASE SETUP ---------------- #


def _get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                chat_id    INTEGER NOT NULL,
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

            CREATE TABLE IF NOT EXISTS relational_memory (
                user_id INTEGER PRIMARY KEY,
                preferred_name TEXT DEFAULT '',
                stressors TEXT DEFAULT '[]',
                wins TEXT DEFAULT '[]',
                coping_preferences TEXT DEFAULT '[]',
                boundaries TEXT DEFAULT '[]',
                life_themes TEXT DEFAULT '[]',
                updated_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_ritual_state (
                user_id INTEGER PRIMARY KEY,
                user_message_count INTEGER DEFAULT 0,
                last_weekly_reflection_at REAL DEFAULT 0,
                last_milestone_ack_at REAL DEFAULT 0,
                updated_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
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


def register_user(user_id: int, chat_id: int, first_name: str = "", username: str = ""):
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
            (user_id, chat_id, (first_name or "").strip(), (username or "").strip(), time.time()),
        )
        now = time.time()
        conn.execute(
            """
            INSERT INTO relational_memory (user_id, preferred_name, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id, (first_name or "").strip(), now),
        )
        conn.execute(
            """
            INSERT INTO user_ritual_state (user_id, updated_at)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id, now),
        )
        conn.commit()
        logger.info("Registered user %d (chat_id=%d)", user_id, chat_id)
    finally:
        conn.close()


def get_user_profile(user_id: int) -> dict:
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


def set_checkin_enabled(user_id: int, enabled: bool):
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


def get_checkin_enabled(user_id: int) -> bool:
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


def update_last_checkin_slot(user_id: int, slot: str):
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


def save_message(user_id: int, role: str, content: str):
    """Save a message to the database."""
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, time.time()),
        )
        if role == "user":
            now = time.time()
            conn.execute(
                """
                INSERT INTO user_ritual_state (user_id, user_message_count, updated_at)
                VALUES (?, 1, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    user_message_count = user_ritual_state.user_message_count + 1,
                    updated_at = excluded.updated_at
                """,
                (user_id, now),
            )
        conn.commit()
    finally:
        conn.close()


def _safe_load_list(raw: str) -> list[str]:
    try:
        value = json.loads(raw or "[]")
        if isinstance(value, list):
            cleaned = [str(v).strip() for v in value if str(v).strip()]
            return cleaned
    except Exception:
        pass
    return []


def _merge_unique(existing: list[str], new_items: list[str], limit: int = 10) -> list[str]:
    seen = {item.lower() for item in existing}
    merged = list(existing)
    for item in new_items:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        merged.append(normalized)
        seen.add(key)
    return merged[-limit:]


def get_relational_memory(user_id: int) -> dict:
    """Return structured relational memory for long-term personalization."""
    conn = _get_connection()
    try:
        row = conn.execute(
            """
            SELECT preferred_name, stressors, wins, coping_preferences, boundaries, life_themes
            FROM relational_memory
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return {
                "preferred_name": "",
                "stressors": [],
                "wins": [],
                "coping_preferences": [],
                "boundaries": [],
                "life_themes": [],
            }
        return {
            "preferred_name": (row["preferred_name"] or "").strip(),
            "stressors": _safe_load_list(row["stressors"]),
            "wins": _safe_load_list(row["wins"]),
            "coping_preferences": _safe_load_list(row["coping_preferences"]),
            "boundaries": _safe_load_list(row["boundaries"]),
            "life_themes": _safe_load_list(row["life_themes"]),
        }
    finally:
        conn.close()


def update_relational_memory(
    user_id: int,
    preferred_name: str = "",
    stressors: list[str] | None = None,
    wins: list[str] | None = None,
    coping_preferences: list[str] | None = None,
    boundaries: list[str] | None = None,
    life_themes: list[str] | None = None,
):
    """Merge new relational facts into persistent structured profile."""
    existing = get_relational_memory(user_id)
    merged_preferred_name = (preferred_name or "").strip() or existing["preferred_name"]
    merged_stressors = _merge_unique(existing["stressors"], stressors or [])
    merged_wins = _merge_unique(existing["wins"], wins or [])
    merged_coping = _merge_unique(existing["coping_preferences"], coping_preferences or [])
    merged_boundaries = _merge_unique(existing["boundaries"], boundaries or [])
    merged_themes = _merge_unique(existing["life_themes"], life_themes or [], limit=8)

    conn = _get_connection()
    try:
        now = time.time()
        conn.execute(
            """
            INSERT INTO relational_memory (
                user_id,
                preferred_name,
                stressors,
                wins,
                coping_preferences,
                boundaries,
                life_themes,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                preferred_name = excluded.preferred_name,
                stressors = excluded.stressors,
                wins = excluded.wins,
                coping_preferences = excluded.coping_preferences,
                boundaries = excluded.boundaries,
                life_themes = excluded.life_themes,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                merged_preferred_name,
                json.dumps(merged_stressors),
                json.dumps(merged_wins),
                json.dumps(merged_coping),
                json.dumps(merged_boundaries),
                json.dumps(merged_themes),
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_ritual_state(user_id: int) -> dict:
    """Return continuity state used for weekly reflections and milestone acknowledgments."""
    conn = _get_connection()
    try:
        row = conn.execute(
            """
            SELECT user_message_count, last_weekly_reflection_at, last_milestone_ack_at
            FROM user_ritual_state
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return {
                "user_message_count": 0,
                "last_weekly_reflection_at": 0.0,
                "last_milestone_ack_at": 0.0,
            }
        return {
            "user_message_count": int(row["user_message_count"] or 0),
            "last_weekly_reflection_at": float(row["last_weekly_reflection_at"] or 0.0),
            "last_milestone_ack_at": float(row["last_milestone_ack_at"] or 0.0),
        }
    finally:
        conn.close()


def mark_weekly_reflection(user_id: int):
    """Mark that a weekly reflection ritual was suggested."""
    conn = _get_connection()
    try:
        now = time.time()
        conn.execute(
            """
            INSERT INTO user_ritual_state (user_id, last_weekly_reflection_at, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_weekly_reflection_at = excluded.last_weekly_reflection_at,
                updated_at = excluded.updated_at
            """,
            (user_id, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def mark_milestone_ack(user_id: int):
    """Mark that a milestone acknowledgment was suggested."""
    conn = _get_connection()
    try:
        now = time.time()
        conn.execute(
            """
            INSERT INTO user_ritual_state (user_id, last_milestone_ack_at, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_milestone_ack_at = excluded.last_milestone_ack_at,
                updated_at = excluded.updated_at
            """,
            (user_id, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_messages(user_id: int) -> list[dict]:
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
