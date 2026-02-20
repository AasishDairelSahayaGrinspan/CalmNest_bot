import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.config import BOT_TOKEN, RATE_LIMIT
from bot.handlers import start, handle_message, checkin_command
from bot.memory import init_db
from bot.scheduler import create_scheduler

logger = logging.getLogger("calmnest")

# ---------------- TELEGRAM APP ---------------- #

telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("checkin", checkin_command))
telegram_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
)

# ---------------- RATE LIMITER ---------------- #

limiter = Limiter(key_func=get_remote_address)

# ---------------- LIFESPAN ---------------- #

scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    global scheduler

    # Startup
    init_db()
    await telegram_app.initialize()
    scheduler = create_scheduler(telegram_app.bot)
    scheduler.start()
    logger.info("CalmNest is alive 🌿")

    yield

    # Shutdown
    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


# ---------------- FASTAPI APP ---------------- #

app = FastAPI(title="CalmNest Bot", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return {"error": "Rate limit exceeded. Please slow down.", "ok": False}


@app.get("/")
async def health():
    return {"status": "CalmNest is alive 🌿"}


@app.post("/webhook")
@limiter.limit(RATE_LIMIT)
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error("Webhook error: %s", e)
        return {"ok": False}


# ---------------- GUNICORN ENTRYPOINT ---------------- #

web_app = app
