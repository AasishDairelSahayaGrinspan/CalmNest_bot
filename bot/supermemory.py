import json
import time
from typing import Optional
from urllib import error, request

from bot.config import (
    SUPERMEMORY_API_KEY,
    SUPERMEMORY_BASE_URL,
    SUPERMEMORY_TIMEOUT_MS,
    SUPERMEMORY_SEARCH_LIMIT,
    logger,
)


class SupermemoryError(Exception):
    """Raised for Supermemory request/response failures."""


class SupermemoryClient:
    """Minimal REST client for the Supermemory API."""

    def __init__(self):
        self.base_url = SUPERMEMORY_BASE_URL
        self.api_key = SUPERMEMORY_API_KEY
        self.timeout_seconds = max(0.1, SUPERMEMORY_TIMEOUT_MS / 1000)

    def _request(self, method: str, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}{path}",
            method=method,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        started = time.time()
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SupermemoryError(f"HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise SupermemoryError(f"Network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SupermemoryError("Request timed out") from exc

        elapsed_ms = int((time.time() - started) * 1000)
        logger.debug("Supermemory %s %s completed in %dms", method, path, elapsed_ms)

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupermemoryError("Invalid JSON response") from exc

    @staticmethod
    def _container_tag(user_id: int) -> str:
        return f"user_{user_id}"

    def add_message(self, user_id: int, role: str, content: str, chat_id: Optional[int] = None):
        payload = {
            "content": content,
            "containerTag": self._container_tag(user_id),
            "metadata": {
                "role": role,
                "source": "telegram",
            },
        }
        if chat_id is not None:
            payload["metadata"]["chat_id"] = chat_id

        self._request("POST", "/v3/documents", payload)

    def search_context(self, user_id: int, query_text: str) -> list[str]:
        payload = {
            "q": query_text,
            "containerTags": [self._container_tag(user_id)],
            "limit": SUPERMEMORY_SEARCH_LIMIT,
            "onlyMatchingChunks": True,
            "rerank": True,
        }
        data = self._request("POST", "/v3/search", payload)

        snippets: list[str] = []
        for result in data.get("results", []):
            chunks = result.get("chunks") or []
            if chunks:
                text = (chunks[0].get("content") or "").strip()
            else:
                text = (result.get("content") or "").strip()
            if text:
                snippets.append(text)

        return snippets
