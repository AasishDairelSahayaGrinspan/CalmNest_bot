import os
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-123")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key-123")

from bot.ai import get_ai_reply
from bot.config import SYSTEM_PROMPT


class TestGetAiReply:
    @patch("bot.ai.client")
    def test_returns_reply_content(self, mock_client):
        # Arrange
        mock_choice = MagicMock()
        mock_choice.message.content = "I'm here for you."
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        # Act
        reply = get_ai_reply([{"role": "user", "content": "I feel sad"}])

        # Assert
        assert reply == "I'm here for you."

    @patch("bot.ai.client")
    def test_includes_system_prompt(self, mock_client):
        mock_choice = MagicMock()
        mock_choice.message.content = "Response"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        get_ai_reply([{"role": "user", "content": "Hello"}])

        # Verify system prompt was passed
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == SYSTEM_PROMPT
        assert messages[1]["role"] == "system"
        assert messages[2]["role"] == "system"
        assert messages[3]["role"] == "system"

    @patch("bot.ai.client")
    def test_includes_memory_messages(self, mock_client):
        mock_choice = MagicMock()
        mock_choice.message.content = "Response"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        memory = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
            {"role": "user", "content": "How are you?"},
        ]
        get_ai_reply(memory)

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        # System prompt + constitution + style + choreography + 3 memory messages
        assert len(messages) == 7
        assert messages[4]["content"] == "Hi"
        assert messages[6]["content"] == "How are you?"

    @patch("bot.ai.client")
    def test_uses_short_token_budget_for_short_intent(self, mock_client):
        mock_choice = MagicMock()
        mock_choice.message.content = "Short response"
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        get_ai_reply([{"role": "user", "content": "Can you summarize this?"}], latest_user_text="brief summary please")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 140

    @patch("bot.ai.client")
    def test_uses_medium_token_budget_by_default(self, mock_client):
        mock_choice = MagicMock()
        mock_choice.message.content = "Medium response"
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        get_ai_reply([{"role": "user", "content": "I had a hard day at work."}], latest_user_text="I had a hard day at work and feel low")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 320

    @patch("bot.ai.client")
    def test_uses_long_token_budget_for_detailed_intent(self, mock_client):
        mock_choice = MagicMock()
        mock_choice.message.content = "Long response"
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        get_ai_reply([{"role": "user", "content": "Explain deeply"}], latest_user_text="Can you explain in detail step by step what I should do?")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 520
