import os
import tempfile
from unittest.mock import MagicMock

# Configure env before importing project modules.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["CALMNEST_DB_PATH"] = _tmp_db.name
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-123")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key-123")

from bot.memory import init_db, register_user, get_recent_messages
from bot.memory_provider import MemoryProvider
from bot.supermemory import SupermemoryError


def setup_function():
    init_db()


def teardown_function():
    from bot.memory import _get_connection

    conn = _get_connection()
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()


def test_get_context_returns_sqlite_when_supermemory_disabled():
    register_user(1, 1001)
    provider = MemoryProvider()
    provider.super_enabled = False

    provider.save(1, "user", "hello", chat_id=1001)
    context = provider.get_context(1, latest_user_text="hello")

    assert len(context) == 1
    assert context[0]["role"] == "user"
    assert context[0]["content"] == "hello"


def test_get_context_injects_supermemory_hint_when_available():
    register_user(2, 2002)
    provider = MemoryProvider()
    provider.super_enabled = True

    mock_client = MagicMock()
    mock_client.search_context.return_value = ["User sleeps better after evening walks"]
    provider.super_client = mock_client

    provider.save(2, "user", "I did a walk", chat_id=2002)
    context = provider.get_context(2, latest_user_text="walk")

    assert context[0]["role"] == "system"
    assert "Relevant long-term memory" in context[0]["content"]
    assert "evening walks" in context[0]["content"]


def test_save_falls_back_to_sqlite_when_supermemory_add_fails():
    register_user(3, 3003)
    provider = MemoryProvider()
    provider.super_enabled = True

    mock_client = MagicMock()
    mock_client.add_message.side_effect = SupermemoryError("boom")
    provider.super_client = mock_client

    provider.save(3, "user", "fallback works", chat_id=3003)
    stored = get_recent_messages(3)

    assert len(stored) == 1
    assert stored[0]["content"] == "fallback works"
