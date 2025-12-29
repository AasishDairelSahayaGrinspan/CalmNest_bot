# Changelog

All notable changes to this project will be documented in this file.

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

