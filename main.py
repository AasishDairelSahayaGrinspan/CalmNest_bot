import os
import asyncio
import random
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from groq import Groq

# ---------------- ENV ---------------- #

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not set")

# ---------------- GROQ AI ---------------- #

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """
You are CalmNest, a calm, warm, and supportive mental wellbeing assistant.
You listen without judgment.
You do NOT give medical advice or diagnoses.
Keep responses gentle, empathetic, and concise.
"""

# ---------------- MEMORY ---------------- #

# user_id -> { messages, last_interaction, last_checkin_slot }
user_memory = {}

def save_message(user_id: int, role: str, content: str):
    if user_id not in user_memory:
        user_memory[user_id] = {
            "messages": [],
            "last_interaction": asyncio.get_event_loop().time(),
            "last_checkin_slot": None
        }

    user_memory[user_id]["messages"].append({
        "role": role,
        "content": content
    })

    # Keep last 6 messages
    if len(user_memory[user_id]["messages"]) > 6:
        user_memory[user_id]["messages"].pop(0)

    user_memory[user_id]["last_interaction"] = asyncio.get_event_loop().time()

# ---------------- TIME SLOTS ---------------- #

def get_time_slot():
    hour = int(asyncio.get_event_loop().time() // 3600 % 24)

    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"

CHECKIN_MESSAGES = {
    "morning": [
        "Good morning 🌤️ Hope today feels gentle on you."
    ],
    "afternoon": [
        "Just a small afternoon check-in 🤍 Take a breath if you can."
    ],
    "evening": [
        "Good evening 🌆 I hope your day is winding down softly."
    ],
    "night": [
        "Good night 🌙 Be kind to yourself today."
    ]
}

# ---------------- AI RESPONSE ---------------- #

def get_ai_reply(memory_messages: list) -> str:
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *memory_messages
        ],
        max_tokens=150,
        temperature=0.6,
    )
    return completion.choices[0].message.content

# ---------------- GENTLE CHECK-IN TASK ---------------- #

async def gentle_checkin_task():
    while True:
        await asyncio.sleep(10 * 60)  # check every 10 minutes
        current_slot = get_time_slot()

        for user_id, data in user_memory.items():
            # Only users who have interacted
            if not data["messages"]:
                continue

            # Already sent in this time slot
            if data["last_checkin_slot"] == current_slot:
                continue

            try:
                message = random.choice(CHECKIN_MESSAGES[current_slot])
                await telegram_app.bot.send_message(user_id, message)
                data["last_checkin_slot"] = current_slot
            except Exception as e:
                print("Check-in error:", e)

# ---------------- TELEGRAM HANDLERS ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi, I’m CalmNest 🌿\n"
        "You can talk to me anytime. I’m here to listen."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text

    save_message(user_id, "user", user_text)

    try:
        memory = user_memory[user_id]["messages"]
        reply = await asyncio.to_thread(get_ai_reply, memory)
        save_message(user_id, "assistant", reply)
        await update.message.reply_text(reply)
    except Exception as e:
        print("AI error:", e)
        await update.message.reply_text(
            "I’m here with you 🌿\nLet’s take a breath together."
        )

# ---------------- TELEGRAM APP ---------------- #

telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
)

# ---------------- FASTAPI APP ---------------- #

app = FastAPI()

@app.on_event("startup")
async def startup():
    await telegram_app.initialize()
    asyncio.create_task(gentle_checkin_task())

@app.get("/")
async def health():
    return {"status": "CalmNest is alive 🌿"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        print("Webhook error:", e)
        return {"ok": False}

# ---------------- GUNICORN ENTRYPOINT ---------------- #

web_app = app

