from bot.config import SUPERMEMORY_ENABLED, logger
from bot.memory import (
    get_recent_messages,
    save_message,
    get_user_profile,
    get_relational_memory,
    update_relational_memory,
    get_ritual_state,
    mark_weekly_reflection,
    mark_milestone_ack,
)
from bot.supermemory import SupermemoryClient, SupermemoryError
from typing import Optional
import re
import time


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

        if role == "user":
            extracted = self._extract_relational_facts(content)
            if any(extracted.values()):
                update_relational_memory(
                    user_id=user_id,
                    preferred_name=extracted["preferred_name"],
                    stressors=extracted["stressors"],
                    wins=extracted["wins"],
                    coping_preferences=extracted["coping_preferences"],
                    boundaries=extracted["boundaries"],
                    life_themes=extracted["life_themes"],
                )

        if not self.super_enabled or not self.super_client:
            return

        try:
            self.super_client.add_message(user_id=user_id, role=role, content=content, chat_id=chat_id)
            self.super_failures = 0
        except SupermemoryError as exc:
            self._record_failure(exc)

    def _extract_relational_facts(self, content: str) -> dict:
        """Extract lightweight structured relationship facts from user text."""
        text = (content or "").strip()
        lowered = text.lower()

        preferred_name = ""
        name_patterns = [
            r"\bmy name is\s+([A-Za-z][A-Za-z'\-]{1,31})\b",
            r"\bcall me\s+([A-Za-z][A-Za-z'\-]{1,31})\b",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                preferred_name = match.group(1).strip(" .,!?").capitalize()
                break

        stressors = []
        stress_match = re.search(
            r"\b(stressed|worried|anxious|overwhelmed)\s+(about|by)\s+([^.!?]{4,80})",
            lowered,
        )
        if stress_match:
            stressors.append(stress_match.group(3).strip(" .,!?"))

        wins = []
        win_match = re.search(
            r"\b(i managed to|i finally|i did|i'm proud that|i am proud that)\s+([^.!?]{4,90})",
            lowered,
        )
        if win_match:
            wins.append(win_match.group(2).strip(" .,!?"))

        coping_preferences = []
        coping_match = re.search(
            r"\b(it helps when i|i feel better when i|i calm down when i|i like to)\s+([^.!?]{4,90})",
            lowered,
        )
        if coping_match:
            coping_preferences.append(coping_match.group(2).strip(" .,!?"))

        boundaries = []
        boundary_match = re.search(
            r"\b(please don't|do not|don't|i don't want)\s+([^.!?]{4,90})",
            lowered,
        )
        if boundary_match:
            boundaries.append(boundary_match.group(2).strip(" .,!?"))

        life_themes = []
        theme_keywords = {
            "work": ["work", "job", "office", "boss"],
            "family": ["family", "parents", "mother", "father", "home"],
            "relationships": ["relationship", "partner", "boyfriend", "girlfriend", "marriage"],
            "sleep": ["sleep", "insomnia", "rest", "tired"],
            "health": ["health", "body", "exercise", "diet"],
            "studies": ["study", "exam", "school", "college", "university"],
            "finances": ["money", "finance", "debt", "rent", "bills"],
        }
        for theme, keywords in theme_keywords.items():
            if any(word in lowered for word in keywords):
                life_themes.append(theme)

        return {
            "preferred_name": preferred_name,
            "stressors": stressors,
            "wins": wins,
            "coping_preferences": coping_preferences,
            "boundaries": boundaries,
            "life_themes": life_themes,
        }

    def build_generation_metadata(self, user_id: int, latest_user_text: str) -> dict:
        """Build metadata for persona continuity, rituals, and emotional guidance."""
        relational = get_relational_memory(user_id)
        ritual_state = get_ritual_state(user_id)
        now = time.time()

        ritual_hints = []
        week_seconds = 7 * 24 * 60 * 60
        if now - ritual_state["last_weekly_reflection_at"] >= week_seconds:
            ritual_hints.append(
                "Offer a soft weekly reflection question (what felt heavy, what felt helpful this week)."
            )
            mark_weekly_reflection(user_id)

        count = ritual_state["user_message_count"]
        if count > 0 and count % 25 == 0 and now - ritual_state["last_milestone_ack_at"] > 12 * 60 * 60:
            ritual_hints.append(
                "Add a brief milestone acknowledgment about the user's consistency in showing up."
            )
            mark_milestone_ack(user_id)

        recent_user_texts = [
            m.get("content", "")
            for m in reversed(get_recent_messages(user_id))
            if m.get("role") == "user" and m.get("content")
        ]
        follow_up_hint = ""
        for prior in recent_user_texts:
            if prior.strip() and prior.strip() != (latest_user_text or "").strip():
                follow_up_hint = f"If relevant, gently reference continuity using: 'Last time you said {prior[:120]}'."
                break
        if follow_up_hint:
            ritual_hints.append(follow_up_hint)

        relational_hints = []
        preferred_name = relational.get("preferred_name", "").strip()
        if preferred_name:
            relational_hints.append(f"Preferred name: {preferred_name}")
        if relational["stressors"]:
            relational_hints.append(f"Known stressors: {', '.join(relational['stressors'][:3])}")
        if relational["wins"]:
            relational_hints.append(f"Known wins: {', '.join(relational['wins'][:3])}")
        if relational["coping_preferences"]:
            relational_hints.append(
                f"Helpful coping preferences: {', '.join(relational['coping_preferences'][:3])}"
            )
        if relational["boundaries"]:
            relational_hints.append(f"Respect boundaries: {', '.join(relational['boundaries'][:3])}")
        if relational["life_themes"]:
            relational_hints.append(f"Current life themes: {', '.join(relational['life_themes'][:4])}")

        return {
            "relational": relational,
            "relational_hints": relational_hints,
            "ritual_hints": ritual_hints,
        }

    def get_context(self, user_id: int, latest_user_text: str) -> list[dict]:
        local_messages = get_recent_messages(user_id)
        local_count = len(local_messages)
        profile = get_user_profile(user_id)

        profile_hint = None
        first_name = (profile.get("first_name") or "").strip()
        username = (profile.get("username") or "").strip()
        if first_name or username:
            profile_text = []
            if first_name:
                profile_text.append(f"User first name: {first_name}")
            if username:
                profile_text.append(f"Telegram username: @{username}")
            profile_hint = {
                "role": "system",
                "content": (
                    "Known profile details from prior interactions:\n"
                    + "\n".join(f"- {line}" for line in profile_text)
                ),
            }

        if not self.super_enabled or not self.super_client:
            logger.info("Context for user %d: sqlite_only=%d", user_id, local_count)
            return ([profile_hint] if profile_hint else []) + local_messages

        try:
            snippets = self.super_client.search_context(user_id=user_id, query_text=latest_user_text)
            self.super_failures = 0
        except SupermemoryError as exc:
            self._record_failure(exc)
            logger.info("Context for user %d: sqlite_only=%d (supermemory failed)", user_id, local_count)
            return ([profile_hint] if profile_hint else []) + local_messages

        if not snippets:
            logger.info("Context for user %d: sqlite_only=%d, supermemory=0", user_id, local_count)
            return ([profile_hint] if profile_hint else []) + local_messages

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
        prefix = [memory_hint]
        if profile_hint:
            prefix.append(profile_hint)
        return [*prefix, *local_messages]


memory_provider = MemoryProvider()
