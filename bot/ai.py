import asyncio
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
