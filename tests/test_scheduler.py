import os
import pytest
from unittest.mock import patch
from datetime import datetime

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-123")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key-123")

from bot.scheduler import get_current_slot


class TestGetCurrentSlot:
    @patch("bot.scheduler.datetime")
    def test_morning(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 8, 0)
        assert get_current_slot() == "morning"

    @patch("bot.scheduler.datetime")
    def test_early_morning(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 6, 0)
        assert get_current_slot() == "morning"

    @patch("bot.scheduler.datetime")
    def test_afternoon(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 14, 0)
        assert get_current_slot() == "afternoon"

    @patch("bot.scheduler.datetime")
    def test_evening(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 19, 0)
        assert get_current_slot() == "evening"

    @patch("bot.scheduler.datetime")
    def test_night_late(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 23, 0)
        assert get_current_slot() == "night"

    @patch("bot.scheduler.datetime")
    def test_night_early(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 3, 0)
        assert get_current_slot() == "night"

    @patch("bot.scheduler.datetime")
    def test_boundary_noon(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 12, 0)
        assert get_current_slot() == "afternoon"

    @patch("bot.scheduler.datetime")
    def test_boundary_evening_start(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 17, 0)
        assert get_current_slot() == "evening"

    @patch("bot.scheduler.datetime")
    def test_boundary_night_start(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 21, 0)
        assert get_current_slot() == "night"
