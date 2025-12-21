import os
import asyncio
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

# ---------------- AI ---------------- #

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """
You are CalmNest, a calm and supportive mental wellbeing assistant.
Do not give medical advice.
Be empathetic and concise.
"""

def get_ai_reply(text: str) -> str:
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        max_tokens=150,
        temperature=0.6,
    )
    return completion.choices[0].message.content

# ---------------- TELEGRAM HANDLERS ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi, I’m CalmNest 🌿\nI’m here to listen.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = await asyncio.to_thread(get_ai_reply, update.message.text)
    await update.message.reply_text(reply)

# ---------------- APP INIT ---------------- #

telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ---------------- FASTAPI ---------------- #

app = FastAPI()

@app.on_event("startup")
async def startup():
    await telegram_app.initialize()
    await telegram_app.start()

@app.on_event("shutdown")
async def shutdown():
    await telegram_app.stop()

@app.get("/")
async def health():
    return {"status": "CalmNest is alive 🌿"}

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

# For gunicorn
web_app = app

