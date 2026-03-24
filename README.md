# 🌿 CalmNest Bot

A warm, empathetic **mental wellbeing companion** on Telegram — powered by AI.

CalmNest listens without judgment, offers gentle support, and sends optional daily check-ins. It **does not** provide medical advice or diagnoses.

---

## ✨ Features

- 💬 **Empathetic AI conversations** — powered by Llama 3.3 70B via Groq
- 🧠 **Persistent local memory** — SQLite-backed conversation history (survives restarts)
- 🔎 **Optional Supermemory recall** — hybrid semantic search (`/v4/search`) for long-term context
- 🧯 **Resilient fallback design** — SQLite stays source-of-truth; Supermemory auto-disables after repeated failures
- ⏰ **Scheduled check-ins** — gentle morning, afternoon, evening & night messages (opt-in)
- 🛡️ **Rate limiting** — webhook abuse protection
- 🔒 **Ethical guardrails** — system prompt prevents medical advice/diagnoses

## 🧰 Tech Stack

| Component | Technology |
|-----------|-----------|
| Bot Platform | Telegram (webhooks) |
| Backend | FastAPI + Gunicorn |
| AI / LLM | Groq — Llama 3.3 70B Versatile |
| Memory | SQLite + optional Supermemory |
| Scheduler | APScheduler |

## 🚀 Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/calmnest-bot.git
cd calmnest-bot
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
touch .env
```

Edit `.env` and add:
- **TELEGRAM_BOT_TOKEN** — get from [@BotFather](https://t.me/BotFather)
- **GROQ_API_KEY** — get from [Groq Console](https://console.groq.com/keys)
- **CALMNEST_DB_PATH** *(optional)* — SQLite path override (defaults to `calmnest.db`, or `/home/site/calmnest.db` on Azure App Service)

Optional (Supermemory enhancement):
- **ENABLE_SUPERMEMORY** — `true` to enable external memory search/write (default: `false`)
- **SUPERMEMORY_API_KEY** — required when Supermemory is enabled
- **SUPERMEMORY_BASE_URL** — default: `https://api.supermemory.ai`
- **SUPERMEMORY_TIMEOUT_MS** — request timeout in milliseconds (default: `2500`)
- **SUPERMEMORY_SEARCH_LIMIT** — max search results used for context (default: `6`)

### 5. How memory works

- All incoming/outgoing messages are always saved to SQLite.
- If Supermemory is enabled, messages are also indexed remotely with role metadata.
- At response time, CalmNest fetches local recent messages and may prepend a compact system memory hint from Supermemory search results.
- If Supermemory errors repeatedly, CalmNest automatically falls back to SQLite-only mode.

### 6. Run locally

```bash
uvicorn main:app --reload
```

Visit `http://localhost:8000/` to see the health check.

### 7. Set your webhook

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=<YOUR_PUBLIC_URL>/webhook"
```

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and register |
| `/checkin on` | Enable automatic check-in messages |
| `/checkin off` | Disable check-ins |

## 🧪 Running Tests

```bash
python3 -m pytest -q
```

## 📁 Project Structure

```
calmnest-bot/
├── main.py              # FastAPI app, webhook, startup
├── bot/
│   ├── config.py        # Env, logging, constants
│   ├── memory.py        # SQLite conversation memory
│   ├── memory_provider.py # Memory facade: SQLite + optional Supermemory
│   ├── supermemory.py   # Supermemory REST client
│   ├── ai.py            # Groq LLM integration
│   ├── handlers.py      # Telegram command & message handlers
│   └── scheduler.py     # Automatic check-in scheduler
├── tests/               # Unit tests
├── requirements.txt     # Pinned dependencies
└── CHANGELOG.md         # Version history
```

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Push and open a Pull Request

## 📄 License

This project is open source. Feel free to use and modify.
