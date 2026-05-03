import re

import httpx

from bot.ai import get_ai_reply_async
from bot.memory import register_user, set_checkin_enabled, get_checkin_enabled
from bot.memory_provider import memory_provider
from bot.config import WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, logger

_WHATSAPP_API_URL = (
    "https://graph.facebook.com/v19.0/{phone_number_id}/messages"
)


def _extract_preferred_name(text: str) -> str:
    """Extract a simple preferred name from explicit self-introduction text."""
    lowered = (text or "").strip()
    patterns = [
        r"\bmy name is\s+([A-Za-z][A-Za-z'\-]{1,31})\b",
        r"\bi am\s+([A-Za-z][A-Za-z'\-]{1,31})\b",
        r"\bi'm\s+([A-Za-z][A-Za-z'\-]{1,31})\b",
        r"\bcall me\s+([A-Za-z][A-Za-z'\-]{1,31})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip(" .,!?")
            return value.capitalize()
    return ""


# ---------------- WHATSAPP SEND ---------------- #


async def send_whatsapp_message(to: str, body: str) -> None:
    """Send a text message via the Meta WhatsApp Cloud API."""
    url = _WHATSAPP_API_URL.format(phone_number_id=WHATSAPP_PHONE_NUMBER_ID)
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()


# ---------------- MESSAGE HANDLER ---------------- #


async def handle_incoming(sender_phone: str, message_text: str) -> None:
    """Handle an incoming WhatsApp message — register, route commands, get AI reply."""
    inferred_name = _extract_preferred_name(message_text)

    register_user(
        sender_phone,
        sender_phone,
        first_name=inferred_name,
        username="",
    )

    lowered = message_text.strip().lower()

    # Keyword commands (replaces Telegram slash commands)
    if lowered in ("hi", "hello", "start"):
        await send_whatsapp_message(
            sender_phone,
            "Hi, I'm CalmNest.\n"
            "You can talk to me anytime. I'm here to listen.\n\n"
            "Send 'checkin on' to enable daily check-ins, "
            "or 'checkin off' to disable them.",
        )
        logger.info("Greeted user %s", sender_phone)
        return

    if lowered == "checkin on":
        set_checkin_enabled(sender_phone, True)
        await send_whatsapp_message(
            sender_phone,
            "Check-ins enabled.\n"
            "I'll send a gentle check-in a few times a day.",
        )
        logger.info("User %s enabled check-ins", sender_phone)
        return

    if lowered == "checkin off":
        set_checkin_enabled(sender_phone, False)
        await send_whatsapp_message(
            sender_phone,
            "Check-ins disabled.\n"
            "You won't receive automatic messages. "
            "Send 'checkin on' to re-enable.",
        )
        logger.info("User %s disabled check-ins", sender_phone)
        return

    if lowered == "checkin":
        enabled = get_checkin_enabled(sender_phone)
        status = "enabled ✅" if enabled else "disabled ❌"
        await send_whatsapp_message(
            sender_phone,
            f"Check-ins are currently {status}\n\n"
            "Send 'checkin on' or 'checkin off' to change.",
        )
        return

    # Regular conversational message
    memory_provider.save(sender_phone, "user", message_text, chat_id=sender_phone)

    try:
        memory = memory_provider.get_context(sender_phone, latest_user_text=message_text)
        reply = await get_ai_reply_async(memory)
        memory_provider.save(sender_phone, "assistant", reply, chat_id=sender_phone)
        await send_whatsapp_message(sender_phone, reply)
        logger.info("Replied to user %s", sender_phone)
    except Exception as e:
        logger.error("AI error for user %s: %s", sender_phone, e)
        await send_whatsapp_message(
            sender_phone,
            "I'm here with you.\nLet's take a breath together.",
        )

