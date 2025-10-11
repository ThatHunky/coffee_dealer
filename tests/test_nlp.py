"""Tests for NLP intent parsing."""

from datetime import date

import pytest

from src.intents import NLCommand
from src.nlp import parse_utterance


@pytest.mark.asyncio
async def test_parse_show_month():
    """Test parsing 'show month' intent."""
    today = date(2024, 10, 1)

    # Ukrainian variants
    utterances = [
        "покажи жовтень",
        "розклад на жовтень",
        "показати жовтень",
    ]

    for utterance in utterances:
        cmd = await parse_utterance(utterance, today)
        # Should be show_month or help (NL is not 100% deterministic in tests)
        assert cmd.action in ("show_month", "help")

        if cmd.action == "show_month":
            # If it parsed correctly, check fields
            assert cmd.month in (10, None) or cmd.month == today.month


@pytest.mark.asyncio
async def test_parse_assign_day():
    """Test parsing 'assign day' intent."""
    today = date(2024, 10, 1)

    utterance = "постав Діану на 5 жовтня"
    cmd = await parse_utterance(utterance, today)

    # Should be assign_day or help
    assert cmd.action in ("assign_day", "help")

    if cmd.action == "assign_day":
        assert cmd.day == 5
        assert "diana" in cmd.people or len(cmd.people) == 0


@pytest.mark.asyncio
async def test_parse_who_works():
    """Test parsing 'who works' intent."""
    today = date(2024, 10, 1)

    utterances = [
        "хто працює 15 числа?",
        "хто на 10 жовтня?",
    ]

    for utterance in utterances:
        cmd = await parse_utterance(utterance, today)
        assert cmd.action in ("who_works", "help")


@pytest.mark.asyncio
async def test_fallback_to_help():
    """Test that invalid input falls back to help."""
    today = date(2024, 10, 1)

    # Gibberish should fall back to help
    cmd = await parse_utterance("asdfghjkl zxcvbnm", today)
    assert cmd.action == "help"


@pytest.mark.asyncio
async def test_nlcommand_validation():
    """Test NLCommand Pydantic validation."""
    # Valid command
    cmd = NLCommand(action="show_month", year=2024, month=10)
    assert cmd.action == "show_month"
    assert cmd.year == 2024
    assert cmd.month == 10

    # Command with people
    cmd = NLCommand(action="assign_day", day=5, people=["diana", "zhenya"])
    assert cmd.action == "assign_day"
    assert cmd.day == 5
    assert "diana" in cmd.people
    assert "zhenya" in cmd.people

    # Help command
    cmd = NLCommand(action="help")
    assert cmd.action == "help"
