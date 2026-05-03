import asyncio
import re
from difflib import SequenceMatcher
from typing import Optional
from groq import Groq
from bot.config import GROQ_API_KEY, SYSTEM_PROMPT, MODEL_NAME, MAX_TOKENS, TEMPERATURE, logger
from bot.persona import build_persona_constitution, build_choreography_instruction

# ---------------- GROQ CLIENT ---------------- #

client = Groq(api_key=GROQ_API_KEY)


# ---------------- AI RESPONSE ---------------- #


def _get_response_style(latest_user_text: str, memory_messages: list[dict]) -> tuple[str, int, str]:
    """Choose short/medium/long reply style and token budget from user intent."""
    text = (latest_user_text or "").strip()
    lowered = text.lower()
    words = re.findall(r"\b\w+\b", lowered)
    word_count = len(words)
    char_count = len(text)
    question_count = text.count("?")

    # Fall back to medium when we do not have enough signal.
    if not text:
        return (
            "Reply in a medium length by default: 3-6 short sentences (around 80-160 words).",
            min(MAX_TOKENS, 320),
            "medium",
        )

    short_intent_patterns = (
        r"\b(short|brief|quick|concise|summary|summarize|tl;dr|tldr|one line|in short|just answer)\b"
    )
    long_intent_patterns = (
        r"\b(long|detailed|detail|deep|in depth|step by step|comprehensive|elaborate|analy[sz]e|explain)\b"
    )

    asks_short = re.search(short_intent_patterns, lowered) is not None
    asks_long = re.search(long_intent_patterns, lowered) is not None
    is_very_short_prompt = word_count <= 8 and char_count <= 45
    is_large_context_prompt = char_count >= 280 or question_count >= 3

    if asks_short or is_very_short_prompt:
        return (
            "Keep it short: 1-3 sentences, under 60 words, warm and clear.",
            min(MAX_TOKENS, 140),
            "short",
        )

    if asks_long or is_large_context_prompt:
        return (
            "Go deeper when useful: 5-9 sentences, clear structure, still concise (under 280 words).",
            min(MAX_TOKENS, 520),
            "long",
        )

    # Default mode for normal chat is medium.
    return (
        "Reply in a medium length by default: 3-6 short sentences (around 80-160 words).",
        min(MAX_TOKENS, 320),
        "medium",
    )


def _target_word_limit(style_mode: str) -> int:
    if style_mode == "short":
        return 60
    if style_mode == "long":
        return 280
    return 160


def _quality_scores(reply: str, style_mode: str, previous_assistant_text: str = "") -> dict:
    words = re.findall(r"\b\w+\b", reply or "")
    word_count = len(words)
    target = _target_word_limit(style_mode)

    warmth_terms = {"hear", "with you", "understand", "thank you", "gentle", "support", "care"}
    warmth_hits = sum(1 for t in warmth_terms if t in (reply or "").lower())
    warmth = min(1.0, 0.4 + 0.2 * warmth_hits)

    sentence_count = max(1, len([s for s in re.split(r"[.!?]+", reply or "") if s.strip()]))
    avg_sentence_words = word_count / sentence_count if sentence_count else float(word_count)
    clarity = 1.0
    if avg_sentence_words > 24:
        clarity = 0.55
    elif avg_sentence_words > 18:
        clarity = 0.75

    brevity_fit = 1.0
    if word_count > target:
        overflow = word_count - target
        brevity_fit = max(0.2, 1.0 - (overflow / max(20, target)))

    repetition_penalty = 0.0
    if previous_assistant_text.strip() and reply.strip():
        ratio = SequenceMatcher(None, previous_assistant_text.strip().lower(), reply.strip().lower()).ratio()
        repetition_penalty = max(0.0, ratio - 0.65)

    overall = max(0.0, min(1.0, (0.35 * warmth) + (0.35 * clarity) + (0.30 * brevity_fit) - (0.40 * repetition_penalty)))
    return {
        "warmth": round(warmth, 2),
        "clarity": round(clarity, 2),
        "brevity_fit": round(brevity_fit, 2),
        "repetition_penalty": round(repetition_penalty, 2),
        "overall": round(overall, 2),
    }


def _trim_to_word_limit(text: str, limit: int) -> str:
    words = (text or "").split()
    if len(words) <= limit:
        return (text or "").strip()
    trimmed = " ".join(words[:limit]).rstrip(" ,;:")
    if not trimmed.endswith((".", "!", "?")):
        trimmed += "."
    return trimmed


def _apply_quality_refinement(
    reply: str,
    style_mode: str,
    latest_user_text: str,
    previous_assistant_text: str = "",
) -> tuple[str, dict]:
    refined = (reply or "").strip()
    target_limit = _target_word_limit(style_mode)

    # Brevity control comes first to keep output inside channel expectations.
    refined = _trim_to_word_limit(refined, target_limit)

    if (
        latest_user_text.strip()
        and style_mode in {"short", "medium"}
        and refined
        and not re.search(r"\b(i hear you|that sounds|thanks for sharing)\b", refined.lower())
    ):
        refined = f"I hear you. {refined}"

    if previous_assistant_text.strip():
        similarity = SequenceMatcher(None, previous_assistant_text.strip().lower(), refined.lower()).ratio()
        if similarity > 0.82:
            refined = f"Thank you for sharing that. {refined}"

    scores = _quality_scores(refined, style_mode, previous_assistant_text=previous_assistant_text)
    logger.info(
        "Reply quality scores: warmth=%.2f clarity=%.2f brevity=%.2f repetition=%.2f overall=%.2f",
        scores["warmth"],
        scores["clarity"],
        scores["brevity_fit"],
        scores["repetition_penalty"],
        scores["overall"],
    )
    return refined, scores


def _latest_assistant_reply(memory_messages: list[dict]) -> str:
    for item in reversed(memory_messages):
        if item.get("role") == "assistant" and item.get("content"):
            return str(item["content"])
    return ""


def get_ai_reply(
    memory_messages: list[dict],
    latest_user_text: str = "",
    generation_metadata: Optional[dict] = None,
) -> str:
    """Generate a reply using the Groq LLM (synchronous — call via asyncio.to_thread)."""
    style_instruction, token_budget, style_mode = _get_response_style(latest_user_text, memory_messages)
    generation_metadata = generation_metadata or {}
    ritual_hints = generation_metadata.get("ritual_hints", [])
    relational_hints = generation_metadata.get("relational_hints", [])
    choreography_instruction = build_choreography_instruction(
        latest_user_text=latest_user_text,
        ritual_hints=ritual_hints,
        relational_hints=relational_hints,
    )

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": build_persona_constitution()},
            {"role": "system", "content": style_instruction},
            {"role": "system", "content": choreography_instruction},
            *memory_messages,
        ],
        max_tokens=token_budget,
        temperature=TEMPERATURE,
    )
    raw_reply = completion.choices[0].message.content or ""
    previous_assistant = _latest_assistant_reply(memory_messages)
    refined_reply, _scores = _apply_quality_refinement(
        raw_reply,
        style_mode=style_mode,
        latest_user_text=latest_user_text,
        previous_assistant_text=previous_assistant,
    )
    return refined_reply


async def get_ai_reply_async(
    memory_messages: list[dict],
    latest_user_text: str = "",
    generation_metadata: Optional[dict] = None,
) -> str:
    """Async wrapper around get_ai_reply."""
    return await asyncio.to_thread(get_ai_reply, memory_messages, latest_user_text, generation_metadata)


def generate_checkin_message(slot: str, first_name: str = "", recent_messages: Optional[list[dict]] = None) -> str:
    """Generate a varied, human check-in message for scheduled outreach."""
    name = (first_name or "").strip()
    recent_messages = recent_messages or []

    recent_user_bits = []
    for item in reversed(recent_messages):
        if item.get("role") == "user" and item.get("content"):
            recent_user_bits.append(item["content"].strip())
        if len(recent_user_bits) >= 2:
            break

    memory_line = ""
    if recent_user_bits:
        memory_line = (
            "Recent user context (for personalization only, do not quote directly unless natural):\n"
            + "\n".join(f"- {text}" for text in recent_user_bits)
        )

    prompt = (
        "Write one short check-in message from a warm, emotionally intelligent companion.\n"
        f"Time slot: {slot}.\n"
        f"User first name: {name or 'unknown'}.\n"
        "Constraints:\n"
        "- 1 to 2 sentences, under 45 words.\n"
        "- Sound human and natural, not robotic or templated.\n"
        "- Vary wording each time.\n"
        "- Gentle tone, no medical advice.\n"
        "- No emojis.\n"
    )
    if memory_line:
        prompt += "\n" + memory_line

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You write caring check-in messages that feel personal and grounded. "
                    "Avoid repetitive openings and avoid sounding scripted."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=120,
        temperature=0.9,
    )
    return (completion.choices[0].message.content or "").strip()


async def generate_checkin_message_async(slot: str, first_name: str = "", recent_messages: Optional[list[dict]] = None) -> str:
    """Async wrapper around check-in generation."""
    return await asyncio.to_thread(generate_checkin_message, slot, first_name, recent_messages)
