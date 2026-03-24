from bot.config import SUPERMEMORY_ENABLED, logger
from bot.memory import get_recent_messages, save_message
from bot.supermemory import SupermemoryClient, SupermemoryError
from typing import Optional


class MemoryProvider:
    """Conversation memory facade with optional Supermemory enhancement."""

    def __init__(self):
        self.super_enabled = SUPERMEMORY_ENABLED
        self.super_failures = 0
        self.super_failure_limit = 3
        self.super_client = SupermemoryClient() if self.super_enabled else None

    def _record_failure(self, exc: Exception):
        self.super_failures += 1
        logger.warning("Supermemory call failed (%d/%d): %s", self.super_failures, self.super_failure_limit, exc)
        if self.super_failures >= self.super_failure_limit:
            self.super_enabled = False
            logger.warning("Supermemory disabled after repeated failures; falling back to SQLite only.")

    def save(self, user_id: int, role: str, content: str, chat_id: Optional[int] = None):
        # SQLite remains source-of-truth fallback.
        save_message(user_id, role, content)

        if not self.super_enabled or not self.super_client:
            return

        try:
            self.super_client.add_message(user_id=user_id, role=role, content=content, chat_id=chat_id)
            self.super_failures = 0
        except SupermemoryError as exc:
            self._record_failure(exc)

    def get_context(self, user_id: int, latest_user_text: str) -> list[dict]:
        local_messages = get_recent_messages(user_id)
        local_count = len(local_messages)

        if not self.super_enabled or not self.super_client:
            logger.info("Context for user %d: sqlite_only=%d", user_id, local_count)
            return local_messages

        try:
            snippets = self.super_client.search_context(user_id=user_id, query_text=latest_user_text)
            self.super_failures = 0
        except SupermemoryError as exc:
            self._record_failure(exc)
            logger.info("Context for user %d: sqlite_only=%d (supermemory failed)", user_id, local_count)
            return local_messages

        if not snippets:
            logger.info("Context for user %d: sqlite_only=%d, supermemory=0", user_id, local_count)
            return local_messages

        # Keep injected context concise to avoid excessive token usage.
        joined = "\n".join(f"- {s}" for s in snippets[:5])
        memory_hint = {
            "role": "system",
            "content": (
                "Relevant long-term memory from previous conversations "
                "(may be partial):\n"
                f"{joined}"
            ),
        }
        logger.info(
            "Context for user %d: sqlite_only=%d, supermemory=%d",
            user_id,
            local_count,
            min(len(snippets), 5),
        )
        return [memory_hint, *local_messages]


memory_provider = MemoryProvider()
