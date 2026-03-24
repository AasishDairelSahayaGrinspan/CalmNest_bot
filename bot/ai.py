import asyncio
from typing import Optional
from groq import Groq
from bot.config import GROQ_API_KEY, SYSTEM_PROMPT, MODEL_NAME, MAX_TOKENS, TEMPERATURE, logger

# ---------------- GROQ CLIENT ---------------- #

client = Groq(api_key=GROQ_API_KEY)


# ---------------- AI RESPONSE ---------------- #


def get_ai_reply(memory_messages: list[dict]) -> str:
    """Generate a reply using the Groq LLM (synchronous — call via asyncio.to_thread)."""
    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *memory_messages,
        ],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )
    return completion.choices[0].message.content


async def get_ai_reply_async(memory_messages: list[dict]) -> str:
    """Async wrapper around get_ai_reply."""
    return await asyncio.to_thread(get_ai_reply, memory_messages)


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
