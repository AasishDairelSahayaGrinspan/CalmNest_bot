import os
import tempfile
import pytest

# Set a temp DB path BEFORE importing bot modules
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["CALMNEST_DB_PATH"] = _tmp_db.name
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-123")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key-123")

from bot.memory import init_db, save_message, get_recent_messages, register_user, set_checkin_enabled, get_checkin_enabled, get_all_checkin_users, update_last_checkin_slot


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-initialize the DB before each test."""
    init_db()
    yield
    # Clean up messages & users between tests
    from bot.memory import _get_connection
    conn = _get_connection()
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()


class TestSaveMessage:
    def test_saves_and_retrieves_message(self):
        register_user(1, 1001)
        save_message(1, "user", "Hello")
        messages = get_recent_messages(1)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

    def test_saves_multiple_messages_in_order(self):
        register_user(1, 1001)
        save_message(1, "user", "First")
        save_message(1, "assistant", "Reply to first")
        save_message(1, "user", "Second")
        messages = get_recent_messages(1)
        assert len(messages) == 3
        assert messages[0]["content"] == "First"
        assert messages[1]["content"] == "Reply to first"
        assert messages[2]["content"] == "Second"

    def test_returns_all_messages(self):
        register_user(1, 1001)
        for i in range(10):
            save_message(1, "user", f"Message {i}")
        messages = get_recent_messages(1)
        # Should return ALL 10 messages now (no limit)
        assert len(messages) == 10
        assert messages[0]["content"] == "Message 0"
        assert messages[-1]["content"] == "Message 9"

    def test_isolates_users(self):
        register_user(1, 1001)
        register_user(2, 1002)
        save_message(1, "user", "User 1 msg")
        save_message(2, "user", "User 2 msg")
        msgs_1 = get_recent_messages(1)
        msgs_2 = get_recent_messages(2)
        assert len(msgs_1) == 1
        assert len(msgs_2) == 1
        assert msgs_1[0]["content"] == "User 1 msg"
        assert msgs_2[0]["content"] == "User 2 msg"


class TestUserRegistration:
    def test_registers_user(self):
        register_user(42, 4200)
        users = get_all_checkin_users()
        assert any(u["user_id"] == 42 for u in users)

    def test_updates_chat_id(self):
        register_user(42, 4200)
        register_user(42, 9999)  # update
        users = get_all_checkin_users()
        user = next(u for u in users if u["user_id"] == 42)
        assert user["chat_id"] == 9999

    def test_checkin_enabled_by_default(self):
        register_user(42, 4200)
        assert get_checkin_enabled(42) is True

    def test_disable_enable_checkin(self):
        register_user(42, 4200)
        set_checkin_enabled(42, False)
        assert get_checkin_enabled(42) is False
        set_checkin_enabled(42, True)
        assert get_checkin_enabled(42) is True


class TestCheckinSlot:
    def test_update_and_read_slot(self):
        register_user(1, 1001)
        update_last_checkin_slot(1, "morning")
        users = get_all_checkin_users()
        user = next(u for u in users if u["user_id"] == 1)
        assert user["last_checkin_slot"] == "morning"

    def test_anti_spam_different_slots(self):
        register_user(1, 1001)
        update_last_checkin_slot(1, "morning")
        users = get_all_checkin_users()
        user = next(u for u in users if u["user_id"] == 1)
        # Should NOT match afternoon
        assert user["last_checkin_slot"] != "afternoon"
