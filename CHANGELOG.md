# Changelog

All notable changes to this project will be documented in this file.

---

## [1.2.0]

### Added
- SQLite persistent memory (conversation history survives restarts)
- `/checkin on|off` command for opt-in/out of automatic check-ins
- Scheduled check-in messages (morning, afternoon, evening, night)
- Anti-spam logic (one check-in per time slot)
- Rate limiting on webhook endpoint (30 req/min via slowapi)
- Structured logging via Python `logging` module
- `.env` support via `python-dotenv`
- `.env.example` template for easy setup
- Proper `README.md` with project description and setup guide
- Unit tests with `pytest`

### Changed
- Upgraded LLM to `llama-3.3-70b-versatile`
- Refactored single `main.py` into modular `bot/` package
- Replaced `asyncio.get_event_loop().time()` with `time.time()`
- Replaced deprecated `@app.on_event("startup")` with `lifespan` context manager
- Replaced all `print()` calls with structured `logging`
- Pinned all dependency versions in `requirements.txt`

---

## [1.1.0]

### Added
- Conversation memory (remembers last 6 messages per user)
- Context-aware AI responses using recent conversation history
- Gentle automatic check-in messages based on time of day:
  - Morning
  - Afternoon
  - Evening
  - Night
- Anti-spam logic (only one message per time slot)
- Ethical system prompt to avoid medical advice and diagnoses
- Background scheduler for automatic wellbeing pings

### Changed
- Updated message handling to include user-specific context
- Improved response tone to be more calm, empathetic, and concise
- Refactored AI calls to include conversation memory

### Notes
- Memory is currently in-memory and resets on server restart
- Time slots are based on server time
- Users must interact at least once before receiving check-ins

---

## [1.0.0] – Initial Release

### Added
- Telegram bot integration using webhooks
- FastAPI backend
- Groq LLM integration for AI responses
- Basic message handling
- Health check endpoint
