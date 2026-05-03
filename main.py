import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from bot.config import WHATSAPP_VERIFY_TOKEN, RATE_LIMIT
from bot.handlers import handle_incoming, send_whatsapp_message
from bot.memory import init_db
from bot.scheduler import create_scheduler

logger = logging.getLogger("calmnest")

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
    scheduler = create_scheduler(send_whatsapp_message)
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


@app.get("/webhook")
async def verify_webhook(request: Request):
    """Handle Meta's one-time webhook verification challenge."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified")
        return PlainTextResponse(content=challenge)

    logger.warning("Webhook verification failed (token mismatch)")
    return PlainTextResponse(content="Forbidden", status_code=403)


@app.post("/webhook")
@limiter.limit(RATE_LIMIT)
async def whatsapp_webhook(request: Request):
    """Receive and process incoming WhatsApp messages."""
    try:
        data = await request.json()
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    if message.get("type") != "text":
                        continue
                    sender = message.get("from", "")
                    text = (message.get("text") or {}).get("body", "").strip()
                    if sender and text:
                        await handle_incoming(sender, text)
        return {"ok": True}
    except Exception as e:
        logger.error("Webhook error: %s", e)
        return {"ok": False}


# ---------------- GUNICORN ENTRYPOINT ---------------- #

web_app = app

