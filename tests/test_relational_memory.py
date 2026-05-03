import os
import tempfile

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["CALMNEST_DB_PATH"] = _tmp_db.name
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-123")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key-123")

from bot.memory import (
    init_db,
    register_user,
    save_message,
    get_relational_memory,
    update_relational_memory,
    get_ritual_state,
    mark_weekly_reflection,
    mark_milestone_ack,
)


def setup_function():
    init_db()


def teardown_function():
    from bot.memory import _get_connection

    conn = _get_connection()
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM relational_memory")
        conn.execute("DELETE FROM user_ritual_state")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM users")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
    finally:
        conn.close()


def test_relational_memory_merges_unique_values():
    register_user(501, 1501, first_name="Asha", username="")
    update_relational_memory(
        user_id=501,
        stressors=["deadlines"],
        wins=["went for a walk"],
        coping_preferences=["deep breathing"],
        boundaries=["late-night calls"],
        life_themes=["work"],
    )
    update_relational_memory(
        user_id=501,
        stressors=["deadlines", "money pressure"],
        wins=["went for a walk", "slept earlier"],
    )

    profile = get_relational_memory(501)
    assert "deadlines" in profile["stressors"]
    assert "money pressure" in profile["stressors"]
    assert "slept earlier" in profile["wins"]


def test_user_message_count_increments_for_ritual_state():
    register_user(502, 1502, first_name="", username="")
    save_message(502, "user", "hello")
    save_message(502, "assistant", "hi")
    save_message(502, "user", "another message")

    state = get_ritual_state(502)
    assert state["user_message_count"] == 2


def test_mark_ritual_timestamps():
    register_user(503, 1503, first_name="", username="")
    mark_weekly_reflection(503)
    mark_milestone_ack(503)

    state = get_ritual_state(503)
    assert state["last_weekly_reflection_at"] > 0
    assert state["last_milestone_ack_at"] > 0
