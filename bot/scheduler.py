from datetime import datetime
from typing import Callable, Awaitable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.ai import generate_checkin_message_async
from bot.memory import get_all_checkin_users, update_last_checkin_slot, get_recent_messages
from bot.config import CHECKIN_SLOTS, logger


# ---------------- TIME SLOT DETECTION ---------------- #


def get_current_slot() -> str:
    """Determine the current time slot based on server local time."""
    hour = datetime.now().hour

    for slot_name, (start, end) in CHECKIN_SLOTS.items():
        if start < end:
            # Normal range (e.g., morning: 6–12)
            if start <= hour < end:
                return slot_name
        else:
            # Wraps around midnight (e.g., night: 21–6)
            if hour >= start or hour < end:
                return slot_name

    return "night"  # fallback


# ---------------- CHECK-IN TASK ---------------- #


async def send_checkins(send_fn: Callable[[str, str], Awaitable[None]]):
    """Send check-in messages to all opted-in users (once per slot)."""
    slot = get_current_slot()

    users = get_all_checkin_users()
    sent_count = 0

    fallback_by_slot = {
        "morning": "Good morning. How are you feeling as your day begins?",
        "afternoon": "Checking in for a moment. How is your afternoon going so far?",
        "evening": "How has your day been? If you want to talk, I am here.",
        "night": "Winding down can be a lot. How are you feeling tonight?",
    }

    for user in users:
        # Anti-spam: skip if already pinged in this slot
        if user["last_checkin_slot"] == slot:
            continue

        try:
            recent = get_recent_messages(user["user_id"])
            recent_tail = recent[-8:]
            message = await generate_checkin_message_async(
                slot=slot,
                first_name=user.get("first_name") or "",
                recent_messages=recent_tail,
            )
            if not message:
                message = fallback_by_slot.get(slot, fallback_by_slot["evening"])

            await send_fn(user["chat_id"], message)
            update_last_checkin_slot(user["user_id"], slot)
            sent_count += 1
            logger.info("Sent %s check-in to user %s", slot, user["user_id"])
        except Exception as e:
            try:
                fallback = fallback_by_slot.get(slot, fallback_by_slot["evening"])
                await send_fn(user["chat_id"], fallback)
                update_last_checkin_slot(user["user_id"], slot)
                sent_count += 1
                logger.warning("Sent fallback %s check-in to user %s", slot, user["user_id"])
            except Exception:
                pass
            logger.warning(
                "Failed to send check-in to user %s: %s", user["user_id"], e
            )

    if sent_count > 0:
        logger.info("Sent %d %s check-ins", sent_count, slot)


# ---------------- SCHEDULER SETUP ---------------- #


def create_scheduler(send_fn: Callable[[str, str], Awaitable[None]]) -> AsyncIOScheduler:
    """Create and configure the check-in scheduler."""
    scheduler = AsyncIOScheduler()

    # Run every 30 minutes
    scheduler.add_job(
        send_checkins,
        "interval",
        minutes=30,
        args=[send_fn],
        id="checkin_job",
        replace_existing=True,
    )

    logger.info("Check-in scheduler created (runs every 30 minutes)")
    return scheduler
