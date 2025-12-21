import os
import asyncio
from groq import Groq
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------- SAFETY FILTER ---------------- #

EXTREME_WORDS = [
    "suicide",
    "kill myself",
    "end my life",
    "want to die",
    "self harm",
    "no reason to live",
]

def is_extreme_message(text: str) -> bool:
    text = text.lower()
    return any(word in text for word in EXTREME_WORDS)

# ---------------- GROQ AI ---------------- #

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are CalmNest, a calm and supportive mental wellbeing assistant.
Do not give medical advice or diagnoses.
Be empathetic, warm, and non-judgmental.
Keep responses short and comforting.
Encourage reflection and healthy coping.
"""

def get_ai_reply(user_message: str) -> str:
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=150,
        temperature=0.6,
    )
    return completion.choices[0].message.content

# ---------------- TELEGRAM BOT ---------------- #

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi, I’m CalmNest 🌿\n"
        "You can talk to me anytime. I’m here to listen."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    if is_extreme_message(user_text):
        await update.message.reply_text(
            "I’m really glad you reached out.\n"
            "You deserve real support.\n"
            "Please talk to someone you trust or a mental health professional.\n"
            "If you’re in immediate danger, contact local emergency services."
        )
        return

    # 🔑 Run Groq call in background thread
    ai_reply = await asyncio.to_thread(get_ai_reply, user_text)

    await update.message.reply_text(ai_reply)


# ---------------- RUN BOT ---------------- #

from flask import Flask, request

# Flask web app
web_app = Flask(__name__)

# Telegram application (no polling)
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@web_app.route("/", methods=["GET"])
def health():
    return "CalmNest is alive 🌿"

@web_app.route("/webhook", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)
    return "ok"

