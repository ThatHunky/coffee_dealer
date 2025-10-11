"""Natural language processing using Google Gen AI SDK.

Goal: Parse Ukrainian free text with Google Gen AI SDK ("genai") into safe JSON intents.
Constraints: use google-genai; response_mime_type="application/json"; response_schema=NLCommand (Pydantic); 3s timeout; admin-gated writes.
Signature: async parse_utterance(text:str, today:date) -> NLCommand
Steps: build client; call client.aio.models.generate_content(model, contents, config); json.loads(resp.text); validate.
"""

import asyncio
import json
import os
from datetime import date

from google import genai
from google.genai import types
from loguru import logger

from .config import config
from .intents import NLCommand

# Initialize Gemini client
# Client picks up GOOGLE_API_KEY env var or accept explicit api_key
# Docs: pip install google-genai; from google import genai; genai.Client(...)
client = genai.Client(api_key=config.GOOGLE_API_KEY)


# System instruction for Gemini
SYSTEM_INSTRUCTION = """
Ти — помічник бота розкладу кав'ярні Coffee Dealer. 
Повертаєш СТРОГО JSON, що відповідає схемі NLCommand.
Відповідай українською мовою.

Доступні дії (action):
- "show_month" — показати календар місяця
- "assign_day" — призначити людей на день
- "who_works" — запитати, хто працює у певний день
- "help" — показати довідку

Люди (people):
- "diana" — Діана
- "dana" — Дана
- "zhenya" — Женя

Не вигадуй інших імен. Якщо користувач згадує схожі імена (Діана, Діана, Diana — це diana; Дана, Dana — це dana; Женя, Жека, Евгения, Zhenya — це zhenya).

Приклади:
- "покажи жовтень" → {"action": "show_month", "month": 10, "year": <поточний рік>}
- "постав Діану на 5 жовтня" → {"action": "assign_day", "day": 5, "month": 10, "people": ["diana"]}
- "хто працює 10 числа?" → {"action": "who_works", "day": 10}
- "Діана і Женя на 15" → {"action": "assign_day", "day": 15, "people": ["diana", "zhenya"]}
- "допомога" → {"action": "help"}

Якщо місяць або рік не вказано явно, використовуй поточну дату.
Якщо запит незрозумілий, поверни {"action": "help"}.
"""


def _get_config() -> types.GenerateContentConfig:
    """
    Create GenerateContentConfig with JSON schema enforcement.

    Uses:
    - response_mime_type="application/json" to enforce JSON output
    - response_schema=NLCommand to validate against Pydantic model
    """
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=NLCommand,  # Pydantic model schema support
        temperature=0.1,  # Low temperature for deterministic output
    )


async def parse_utterance(text: str, today: date) -> NLCommand:
    """
    Parse natural language utterance into structured command.

    Args:
        text: User's message in Ukrainian
        today: Current date for context

    Returns:
        NLCommand with parsed intent

    Example:
        >>> cmd = await parse_utterance("постав Діану на 5 жовтня", date(2024, 10, 1))
        >>> cmd.action
        'assign_day'
        >>> cmd.people
        ['diana']
    """
    prompt = [
        f"Сьогодні: {today.strftime('%d.%m.%Y')} ({today.day} {_get_month_name_ua(today.month)} {today.year}).",
        f"Користувач пише: {text}",
        "Відповідай ЛИШЕ JSON згідно схеми NLCommand.",
    ]

    try:
        # Call Gemini with timeout
        logger.debug(f"Parsing utterance: {text}")

        # Use async client with timeout
        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=_get_config(),
            ),
            timeout=3.0,
        )

        # Parse JSON response
        response_text = resp.text or "{}"
        logger.debug(f"Gemini response: {response_text}")

        data = json.loads(response_text)

        # Validate with Pydantic
        command = NLCommand(**data)

        # Fill in missing year/month if needed
        if command.action in ("show_month", "assign_day", "who_works"):
            if command.year is None:
                command.year = today.year
            if command.month is None and command.action == "show_month":
                command.month = today.month
            elif command.month is None and command.day is not None:
                # If day is specified but not month, use current month
                command.month = today.month

        logger.info(f"Parsed command: {command.action} - {command.model_dump()}")
        return command

    except asyncio.TimeoutError:
        logger.warning(f"Gemini timeout for: {text}")
        return NLCommand(action="help")
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode error: {e}")
        return NLCommand(action="help")
    except Exception as e:
        logger.warning(f"NL parse failed: {e}")
        return NLCommand(action="help")


def _get_month_name_ua(month: int) -> str:
    """Get Ukrainian month name."""
    months = [
        "січня",
        "лютого",
        "березня",
        "квітня",
        "травня",
        "червня",
        "липня",
        "серпня",
        "вересня",
        "жовтня",
        "листопада",
        "грудня",
    ]
    return months[month - 1]
