from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.memory import get_all_checkin_users, update_last_checkin_slot
from bot.config import CHECKIN_SLOTS, CHECKIN_MESSAGES, logger


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


async def send_checkins(bot):
    """Send check-in messages to all opted-in users (once per slot)."""
    slot = get_current_slot()
    message = CHECKIN_MESSAGES.get(slot, CHECKIN_MESSAGES["evening"])

    users = get_all_checkin_users()
    sent_count = 0

    for user in users:
        # Anti-spam: skip if already pinged in this slot
        if user["last_checkin_slot"] == slot:
            continue

        try:
            await bot.send_message(chat_id=user["chat_id"], text=message)
            update_last_checkin_slot(user["user_id"], slot)
            sent_count += 1
            logger.info("Sent %s check-in to user %d", slot, user["user_id"])
        except Exception as e:
            logger.warning(
                "Failed to send check-in to user %d: %s", user["user_id"], e
            )

    if sent_count > 0:
        logger.info("Sent %d %s check-ins", sent_count, slot)


# ---------------- SCHEDULER SETUP ---------------- #


def create_scheduler(bot) -> AsyncIOScheduler:
    """Create and configure the check-in scheduler."""
    scheduler = AsyncIOScheduler()

    # Run every 30 minutes
    scheduler.add_job(
        send_checkins,
        "interval",
        minutes=30,
        args=[bot],
        id="checkin_job",
        replace_existing=True,
    )

    logger.info("Check-in scheduler created (runs every 30 minutes)")
    return scheduler
