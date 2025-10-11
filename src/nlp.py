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
from .intents import NLCommand, ScheduleFromImage

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
- "assign_day" — призначити людей на ОДИН КОНКРЕТНИЙ день
- "assign_days" — призначити людей на ДЕКІЛЬКА КОНКРЕТНИХ днів (список)
- "assign_bulk" — призначити людей на декілька днів за шаблоном
- "who_works" — запитати, хто працює у певний день
- "help" — показати довідку

Люди (people):
- "diana" — Діана
- "dana" — Дана
- "zhenya" — Женя

ВАЖЛИВО: Поле "people" — це масив! Можна призначати ДЕКІЛЬКОХ людей одночасно.
Приклади: ["diana"], ["dana", "zhenya"], ["diana", "dana"], або навіть ["diana", "dana", "zhenya"]

Шаблони для assign_bulk (pattern):
- "all_sundays" — всі неділі
- "all_saturdays" — всі суботи
- "all_weekends" — всі вихідні (субота+неділя)
- "all_weekdays" — всі будні (понеділок-п'ятниця)
- "whole_month" — весь місяць (кожен день)

Не вигадуй інших імен. Якщо користувач згадує схожі імена (Діана, Діана, Diana — це diana; Дана, Dana — це dana; Женя, Жека, Евгения, Zhenya — це zhenya).

Приклади для ОДНОГО дня:
- "постав Діану на 5 жовтня" → {"action": "assign_day", "day": 5, "month": 10, "people": ["diana"]}
- "Діана і Женя на 15" → {"action": "assign_day", "day": 15, "people": ["diana", "zhenya"]}
- "дана, діана та женя на 20" → {"action": "assign_day", "day": 20, "people": ["dana", "diana", "zhenya"]}

Приклади для ДЕКІЛЬКОХ КОНКРЕТНИХ днів (assign_days):
- "постав Діану на 25 та 26 жовтня" → {"action": "assign_days", "days": [25, 26], "month": 10, "people": ["diana"]}
- "Дана на 10, 15 та 20" → {"action": "assign_days", "days": [10, 15, 20], "people": ["dana"]}
- "Женя на 5, 6, 7 листопада" → {"action": "assign_days", "days": [5, 6, 7], "month": 11, "people": ["zhenya"]}
- "діана на 1-5 жовтня" → {"action": "assign_days", "days": [1, 2, 3, 4, 5], "month": 10, "people": ["diana"]}
- "дана з 10 по 15" → {"action": "assign_days", "days": [10, 11, 12, 13, 14, 15], "people": ["dana"]}
- "признач дану та діану на 7, 8, та 20 число" → {"action": "assign_days", "days": [7, 8, 20], "people": ["dana", "diana"]}
- "діана та женя на 5-10" → {"action": "assign_days", "days": [5, 6, 7, 8, 9, 10], "people": ["diana", "zhenya"]}
- "всі троє на 15, 16, 17" → {"action": "assign_days", "days": [15, 16, 17], "people": ["diana", "dana", "zhenya"]}

Приклади для шаблонів (assign_bulk):
- "признач діану на усі неділі" → {"action": "assign_bulk", "pattern": "all_sundays", "people": ["diana"]}
- "постав дану на весь жовтень" → {"action": "assign_bulk", "pattern": "whole_month", "people": ["dana"], "month": 10}
- "женя на всі вихідні" → {"action": "assign_bulk", "pattern": "all_weekends", "people": ["zhenya"]}
- "діана на всі суботи листопада" → {"action": "assign_bulk", "pattern": "all_saturdays", "people": ["diana"], "month": 11}
- "дана на всі будні" → {"action": "assign_bulk", "pattern": "all_weekdays", "people": ["dana"]}
- "дана та діана на всі неділі" → {"action": "assign_bulk", "pattern": "all_sundays", "people": ["dana", "diana"]}
- "всіх на весь місяць" → {"action": "assign_bulk", "pattern": "whole_month", "people": ["diana", "dana", "zhenya"]}

Приклади загальні:
- "покажи жовтень" → {"action": "show_month", "month": 10, "year": <поточний рік>}
- "хто працює 10 числа?" → {"action": "who_works", "day": 10}
- "допомога" → {"action": "help"}

ЛОГІКА ВИБОРУ ДІЇ:
1. Якщо вказано 2+ конкретних дні (числа або діапазон) → "assign_days" з полем "days": [...]
2. Якщо вказано шаблон (всі неділі, весь місяць, всі вихідні) → "assign_bulk" з полем "pattern"
3. Якщо вказано лише ОДИН день → "assign_day" з полем "day"
4. Поле "people" ЗАВЖДИ масив, навіть для однієї людини!

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
        # Call Gemini with timeout and retry logic
        logger.debug(f"Parsing utterance: {text}")

        max_retries = 2
        timeout_seconds = 8.0  # Increased from 3 to 8 seconds

        for attempt in range(max_retries):
            try:
                # Use async client with timeout
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=config.GEMINI_MODEL,
                        contents=prompt,
                        config=_get_config(),
                    ),
                    timeout=timeout_seconds,
                )
                break  # Success, exit retry loop
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Gemini timeout attempt {attempt + 1}/{max_retries}, retrying..."
                    )
                    await asyncio.sleep(0.5)  # Brief delay before retry
                else:
                    raise  # Re-raise on final attempt

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


async def parse_schedule_from_image(
    image_bytes: bytes, today: date
) -> ScheduleFromImage:
    """
    Parse schedule from calendar image using Gemini Vision.

    Args:
        image_bytes: Image file bytes (JPEG, PNG, etc.)
        today: Current date for context

    Returns:
        ScheduleFromImage with extracted month, year, and assignments

    Example:
        >>> with open("calendar.jpg", "rb") as f:
        >>>     schedule = await parse_schedule_from_image(f.read(), date.today())
        >>> schedule.month
        10
        >>> schedule.assignments[0].day
        1
    """
    # System instruction for image parsing
    image_instruction = """
Ти — помічник аналізу календарів розкладу кав'ярні Coffee Dealer.
Аналізуй зображення календаря і витягуй інформацію про призначення працівників.

ВАЖЛИВО:
1. Визнач місяць та рік з календаря (зазвичай вказано вгорі)
2. Для кожного дня з кольоровим обведенням визнач, хто працює
3. Використовуй ЛИШЕ ці імена: "diana", "dana", "zhenya"

Кольорова легенда (типові кольори):
- 🔵 Синій (блакитний) = diana (Діана)
- 🟣 Фіолетовий (purple) = dana (Дана)  
- 🟢 Зелений = zhenya (Женя)
- 🔴 Червоний/коричневий = комбінація (diana + dana)
- 🩷 Рожевий = комбінація (diana + zhenya)
- 🟡 Жовтий = комбінація (dana + zhenya)
- 🌈 Різнокольорові = всі троє (diana, dana, zhenya)

ЛОГІКА РОЗПІЗНАВАННЯ:
- Якщо день обведено ОДНИМ кольором → одна людина
- Якщо день обведено ДВОМА кольорами або має специфічний колір комбінації → дві людини
- Якщо день має три/багато кольорів або веселковий → всі троє
- Якщо день БІЛИЙ або БЕЗ обведення → ПРОПУСТИ (не додавай в список)
- Чорне обведення з білим фоном (як день 1) → diana працює
- Білий текст на темному фоні → diana працює

Приклади:
- День 1: чорне обведення → {"day": 1, "people": ["diana"]}
- День 2: синє обведення → {"day": 2, "people": ["diana"]}
- День 3: зелене обведення → {"day": 3, "people": ["zhenya"]}
- День 4: червоне/коричневе обведення → {"day": 4, "people": ["diana", "dana"]}
- День 5: синє+фіолетове → {"day": 5, "people": ["diana", "dana"]}
- День 9: фіолетове обведення → {"day": 9, "people": ["dana"]}
- День 11: сірий/світлий без кольору → НЕ ВКЛЮЧАТИ (вихідний/вільний)

Повертай СТРОГО JSON згідно схеми ScheduleFromImage:
{
  "month": <номер місяця 1-12>,
  "year": <рік>,
  "assignments": [
    {"day": <день>, "people": [<список людей>]},
    ...
  ]
}

Місяці українською:
Січень=1, Лютий=2, Березень=3, Квітень=4, Травень=5, Червень=6,
Липень=7, Серпень=8, Вересень=9, Жовтень=10, Листопад=11, Грудень=12
"""

    try:
        logger.info("Parsing schedule from image")

        # Prepare image part for Gemini
        # Convert bytes to base64 for inline data
        import base64

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Create content with image
        content = [
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            f"Проаналізуй цей календар і витягни всі призначення працівників. Сьогодні: {today.strftime('%d.%m.%Y')}. Поверни JSON згідно схеми ScheduleFromImage.",
        ]

        # Config for image parsing
        config_vision = types.GenerateContentConfig(
            system_instruction=image_instruction,
            response_mime_type="application/json",
            response_schema=ScheduleFromImage,
            temperature=0.1,
        )

        # Call Gemini Vision with timeout
        timeout_seconds = 15.0  # Longer timeout for vision

        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=config.GEMINI_MODEL,  # gemini-2.0-flash-exp supports vision
                contents=content,
                config=config_vision,
            ),
            timeout=timeout_seconds,
        )

        # Parse response
        response_text = resp.text or "{}"
        logger.debug(f"Gemini vision response: {response_text}")

        data = json.loads(response_text)
        schedule = ScheduleFromImage(**data)

        logger.info(
            f"Extracted schedule: {schedule.month}/{schedule.year} "
            f"with {len(schedule.assignments)} assignments"
        )
        return schedule

    except asyncio.TimeoutError:
        logger.error("Gemini vision timeout", exc_info=True)
        raise ValueError("Час очікування відповіді від AI минув. Спробуйте ще раз.")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in vision response: {e}", exc_info=True)
        raise ValueError("Не вдалось розпізнати календар. Спробуйте інше зображення.")
    except Exception as e:
        logger.error(f"Image parsing failed: {e}", exc_info=True)
        raise ValueError(f"Помилка аналізу зображення: {str(e)}")
