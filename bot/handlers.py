import re

from telegram import Update
from telegram.ext import ContextTypes
from bot.ai import get_ai_reply_async
from bot.memory import register_user, set_checkin_enabled, get_checkin_enabled
from bot.memory_provider import memory_provider
from bot.config import logger


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


# ---------------- /start COMMAND ---------------- #


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command — greet user and register them."""
    user = update.message.from_user
    register_user(
        user.id,
        update.message.chat_id,
        first_name=user.first_name or "",
        username=user.username or "",
    )
    logger.info("User %d started the bot", user.id)

    greeting_name = f" {user.first_name.strip()}" if user.first_name else ""

    await update.message.reply_text(
        f"Hi{greeting_name}, I'm CalmNest.\n"
        "You can talk to me anytime. I'm here to listen.\n\n"
        "Commands:\n"
        "/checkin on — enable daily check-ins\n"
        "/checkin off — disable check-ins"
    )


# ---------------- /checkin COMMAND ---------------- #


async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /checkin on|off — toggle automatic check-in messages."""
    user = update.message.from_user
    register_user(
        user.id,
        update.message.chat_id,
        first_name=user.first_name or "",
        username=user.username or "",
    )

    args = context.args
    if not args or args[0].lower() not in ("on", "off"):
        enabled = get_checkin_enabled(user.id)
        status = "enabled ✅" if enabled else "disabled ❌"
        await update.message.reply_text(
            f"Check-ins are currently {status}\n\n"
            "Usage:\n"
            "/checkin on — I'll send gentle check-ins throughout the day\n"
            "/checkin off — No automatic messages"
        )
        return

    enable = args[0].lower() == "on"
    set_checkin_enabled(user.id, enable)

    if enable:
        await update.message.reply_text(
            "Check-ins enabled.\n"
            "I'll send a gentle, natural check-in a few times a day."
        )
        logger.info("User %d enabled check-ins", user.id)
    else:
        await update.message.reply_text(
            "Check-ins disabled.\n"
            "You won't receive automatic messages. You can always re-enable with /checkin on"
        )
        logger.info("User %d disabled check-ins", user.id)


# ---------------- MESSAGE HANDLER ---------------- #


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages — save, get AI reply, respond."""
    user = update.message.from_user
    user_text = update.message.text
    inferred_name = _extract_preferred_name(user_text)
    effective_name = inferred_name or (user.first_name or "")

    # Ensure user is registered
    register_user(
        user.id,
        update.message.chat_id,
        first_name=effective_name,
        username=user.username or "",
    )
    memory_provider.save(user.id, "user", user_text, chat_id=update.message.chat_id)

    try:
        memory = memory_provider.get_context(user.id, latest_user_text=user_text)
        reply = await get_ai_reply_async(memory)
        memory_provider.save(user.id, "assistant", reply, chat_id=update.message.chat_id)
        await update.message.reply_text(reply)
        logger.info("Replied to user %d", user.id)
    except Exception as e:
        logger.error("AI error for user %d: %s", user.id, e)
        await update.message.reply_text(
            "I'm here with you.\nLet's take a breath together."
        )
