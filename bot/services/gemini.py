"""Gemini API integration for natural language processing"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from google.genai import Client
from google.genai import types as genai_types
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Dynamic thinking budget: -1 for dynamic, or specific number for fixed budget
THINKING_BUDGET = int(os.getenv("THINKING_BUDGET", "2048"))

# Initialize client if API key is available
genai_client = None
if GEMINI_API_KEY:
    genai_client = Client(api_key=GEMINI_API_KEY)


class GeminiService:
    """Service for parsing natural language requests using Gemini Flash"""

    def __init__(self):
        self.client = genai_client
        self.model_name = None
        self.model_version = None  # Track model version for thinking config
        if genai_client:
            # Try models in order of preference (latest first)
            model_names = [
                ("gemini-2.5-flash", "2.5"),  # Latest 2.5 flash
                ("gemini-2.0-flash-exp", "2.0"),  # Experimental 2.0
                ("gemini-2.0-flash", "2.0"),  # Stable 2.0 flash
                ("gemini-1.5-flash", "1.5"),  # Fallback to 1.5 flash
            ]

            # Try to use the first available model (just set it, API will error if invalid)
            # We'll use the latest model by default and let API calls fail gracefully
            for model_name, version in model_names:
                # Just set the model - we'll discover if it works when we use it
                self.model_name = model_name
                self.model_version = version
                print(f"✅ Gemini model set to: {model_name} (v{version})")
                break
            
            if not self.model_name:
                print(f"❌ No Gemini models configured!")

    def _get_thinking_config(
        self, message_complexity: float = 1.0
    ) -> Optional[genai_types.ThinkingConfig]:
        """
        Get thinking configuration based on model version and message complexity.

        Args:
            message_complexity: Complexity factor (0.0 to 1.0) based on message length/complexity

        Returns:
            ThinkingConfig or None if thinking not supported
        """
        if not self.model_name or not self.client:
            return None

        # Calculate dynamic budget based on complexity
        # For simple messages: lower budget, for complex: higher budget
        # Base budget from env, adjusted by complexity
        base_budget = THINKING_BUDGET

        # For Gemini 2.5 models, use thinking_budget
        if self.model_version in ["2.5", "2.0"]:
            if base_budget == -1:
                # Dynamic thinking - let model decide (if supported)
                # Note: -1 may not be supported by all 2.5 Flash models
                # If it fails, the API will reject it and we'll handle gracefully
                budget = -1
            else:
                # Scale budget by complexity (min 1, max base_budget)
                budget = max(1, int(base_budget * message_complexity))

            return genai_types.ThinkingConfig(thinking_budget=budget)

        # For Gemini 3.0+ models, use thinking_level
        elif self.model_version and float(self.model_version) >= 3.0:
            # Map complexity to thinking level
            if message_complexity > 0.7:
                level = "high"
            elif message_complexity > 0.4:
                level = "medium"
            else:
                level = "low"

            return genai_types.ThinkingConfig(thinking_level=level)

        # For older models, no thinking support
        return None

    def _calculate_complexity(self, message: str, context_size: int = 0) -> float:
        """
        Calculate message complexity factor (0.0 to 1.0).

        Args:
            message: The message text
            context_size: Size of additional context (users, shifts, etc.)

        Returns:
            Complexity factor between 0.0 and 1.0
        """
        # Base complexity from message length
        message_length = len(message)
        length_factor = min(1.0, message_length / 500)  # Normalize to 500 chars

        # Context complexity
        context_factor = min(1.0, context_size / 50)  # Normalize to 50 items

        # Combined complexity (weighted average)
        complexity = (length_factor * 0.6) + (context_factor * 0.4)

        return max(0.1, min(1.0, complexity))  # Clamp between 0.1 and 1.0

    async def parse_user_request(
        self, message: str, available_users: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse user request into structured format.

        Args:
            message: User's natural language message
            available_users: List of users with their info (user_id, name, etc.)

        Returns:
            Parsed intent dict or None if parsing fails
        """
        if not self.client or not self.model_name:
            return None

        # Build user context
        users_context = "\n".join(
            [f"- {user['name']} (ID: {user['user_id']})" for user in available_users]
        )

        prompt = f"""You are a helpful and explainative shift scheduling assistant for a coffee shop. The user sent you a message. Respond with detailed, helpful explanations in Ukrainian.

Available users:
{users_context}

User message: "{message}"

First, determine the message type:
- "greeting" - greetings (привіт, добрий день, дякую, etc.)
- "shift_request" - requests about shifts (swap, assign, unassign, query about shifts)
- "general" - general questions or conversation
- "unclear" - unclear or ambiguous messages

For shift requests, extract:
- Action type: "swap", "request_shift", "query", "assign", "unassign"
- Dates mentioned (in YYYY-MM-DD format)
- User names or IDs mentioned

For ALL message types, provide a detailed, explainative response in Ukrainian that:
- Explains what you understood
- Provides helpful information about what the user can do
- Suggests relevant commands or actions
- Is friendly and conversational

Return ONLY a valid JSON object with this structure:
{{
    "message_type": "greeting|shift_request|general|unclear",
    "action": "swap|request_shift|query|assign|unassign|none",
    "dates": ["2025-07-15"],
    "user_names": ["name1"],
    "user_ids": [123],
    "confidence": 0.95,
    "summary": "Brief description",
    "response": "Detailed, explainative response message in Ukrainian (ALWAYS required, be helpful and explain what the user can do)"
}}

Important:
- For greetings: set message_type="greeting", provide a friendly, detailed response explaining what the bot can do
- For shift requests: set message_type="shift_request", extract dates and users, AND provide a detailed response explaining what will happen
- For general questions: set message_type="general", provide a detailed, helpful response explaining capabilities
- For unclear messages: set message_type="unclear", provide detailed guidance on how to use the bot, what commands are available, and examples
- ALWAYS include a detailed "response" field that explains what you understood and what the user can do next
- Be explainative, helpful, and provide examples when appropriate
- Always respond in Ukrainian language
- Be friendly, conversational, and educational
"""

        try:
            # Calculate message complexity for dynamic thinking budget
            complexity = self._calculate_complexity(message, len(available_users))
            thinking_config = self._get_thinking_config(complexity)

            # Build config with thinking
            config = None
            if thinking_config:
                config = genai_types.GenerateContentConfig(
                    thinking_config=thinking_config
                )

            response = self.client.models.generate_content(
                model=f"models/{self.model_name}", contents=prompt, config=config
            )
            # Extract text from response
            if hasattr(response, "text"):
                text = response.text.strip()
            elif hasattr(response, "candidates") and response.candidates:
                text = response.candidates[0].content.parts[0].text.strip()
            else:
                text = str(response).strip()

            # Remove markdown code blocks if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            parsed = json.loads(text)
            
            # Validate and set defaults
            if "message_type" not in parsed:
                parsed["message_type"] = "unclear"
            
            # Ensure response field exists for all message types (make it explainative)
            if "response" not in parsed or not parsed.get("response"):
                message_type = parsed.get("message_type", "unclear")
                if message_type == "greeting":
                    parsed["response"] = (
                        "Привіт! 👋 Я бот для управління змінами в кав'ярні.\n\n"
                        "Я можу допомогти вам:\n"
                        "• Переглянути календар змін: /calendar\n"
                        "• Переглянути історію: /history\n"
                        "• Запитати про зміни природною мовою\n"
                        "• Попросити змінити зміну (адміністратори розглянуть ваш запит)\n\n"
                        "Використайте /help для повного списку команд. Чим можу допомогти?"
                    )
                elif message_type == "general":
                    parsed["response"] = (
                        "Я допоможу вам з управлінням змінами! 📅\n\n"
                        "Ось що ви можете зробити:\n"
                        "• /calendar - переглянути календар змін на поточний місяць\n"
                        "• /history - переглянути минулі місяці\n"
                        "• Надішліть повідомлення природною мовою, щоб запитати про зміни або попросити змінити їх\n\n"
                        "Якщо у вас є питання про конкретні дні або зміни, просто напишіть мені!"
                    )
                elif message_type == "shift_request":
                    parsed["response"] = (
                        "Зрозумів ваш запит про зміни! ✅\n\n"
                        "Ваш запит буде передано адміністраторам для розгляду. "
                        "Вони отримають повідомлення та зможуть виконати ваш запит найближчим часом.\n\n"
                        "Якщо потрібно переглянути календар, використайте /calendar"
                    )
                else:
                    parsed["response"] = (
                        "Не зовсім зрозумів ваш запит. 😅\n\n"
                        "Ось що я можу зробити:\n"
                        "• Показати календар змін: /calendar\n"
                        "• Показати історію: /history\n"
                        "• Прийняти запит на зміну зміни (наприклад: \"Поміняйся зі мною 15 липня\")\n"
                        "• Відповісти на питання про зміни\n\n"
                        "Спробуйте сформулювати запит інакше або використайте /help для довідки.\n\n"
                        "Приклади запитів:\n"
                        "• \"Які зміни у мене наступного тижня?\"\n"
                        "• \"Можу я помінятися зміною 20 липня?\"\n"
                        "• \"Покажи календар\""
                    )
            
            return parsed
        except Exception as e:
            # If thinking config fails (e.g., -1 not supported), retry without it
            if config and "thinking" in str(e).lower():
                print(f"Thinking config failed, retrying without: {e}")
                try:
                    response = self.client.models.generate_content(
                        model=f"models/{self.model_name}",
                        contents=prompt,
                        config=None,  # Retry without thinking config
                    )
                    if hasattr(response, "text"):
                        text = response.text.strip()
                    elif hasattr(response, "candidates") and response.candidates:
                        text = response.candidates[0].content.parts[0].text.strip()
                    else:
                        text = str(response).strip()

                    if text.startswith("```"):
                        text = text.split("```")[1]
                        if text.startswith("json"):
                            text = text[4:]
                        text = text.strip()

                    parsed = json.loads(text)
                    
                    # Validate and set defaults
                    if "message_type" not in parsed:
                        parsed["message_type"] = "unclear"
                    
                    # Ensure response field exists for non-shift requests
                    if parsed.get("message_type") in ["greeting", "general", "unclear"]:
                        if "response" not in parsed or not parsed.get("response"):
                            if parsed["message_type"] == "greeting":
                                parsed["response"] = "Привіт! 👋 Я бот для управління змінами. Чим можу допомогти?"
                            elif parsed["message_type"] == "general":
                                parsed["response"] = "Я допоможу вам з управлінням змінами. Використайте /calendar для перегляду календаря."
                            else:
                                parsed["response"] = "Не зовсім зрозумів. Спробуйте сформулювати інакше або використайте /help."
                    
                    return parsed
                except Exception as retry_error:
                    print(
                        f"Error parsing request with Gemini (retry failed): {retry_error}"
                    )
                    return None
            else:
                print(f"Error parsing request with Gemini: {e}")
                return None

    async def parse_user_management_command(
        self, message: str, available_users: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse admin command for user management (add/edit users).

        Args:
            message: Admin's natural language command
            available_users: List of users

        Returns:
            Parsed command dict
        """
        if not self.client or not self.model_name:
            print(f"❌ Gemini service not available: client={self.client is not None}, model={self.model_name}")
            return None

        print(f"🔍 Starting parse_user_management_command for: '{message[:100]}...'")
        
        users_context = "\n".join(
            [
                f"- {user['name']} (ID: {user['user_id']}, Color: {user.get('color_code', 'N/A')})"
                for user in available_users
            ]
        )

        prompt = f"""You are a flexible user management assistant for admins. Parse the following admin command for adding or editing users. Be lenient and try to understand the intent even if the command is informal or incomplete.

Available users:
{users_context}

Admin command: "{message}"

Extract the following information (be flexible - extract what you can):
1. Action: "add", "edit", "update", or "other"
2. User ID (if mentioned) - extract ALL digits, can be any length (e.g., 6503698207, 123456789)
3. User name - extract the full name mentioned (can be partial match from available users)
4. Color (if mentioned) - can be hex code, color name in English/Ukrainian, or emoji
5. Other properties to update

Supported color formats:
- Hex codes: #FFD700, #FF69B4, #00CED1, etc.
- English names: yellow, pink, blue, purple, green, orange, teal, lightblue, lightgreen, darkorange
- Ukrainian names: жовтий, рожевий, голубий, фіолетовий, зелений, оранжевий, персиковий, синій
- Emojis: 💛 (yellow), 🩷 (pink), 💙 (blue), 💜 (purple), 💚 (green), 🧡 (orange)

Common command patterns (be flexible with variations):
- "додай користувача 6503698207 з ім'ям Діана" → action: "add", user_id: 6503698207, name: "Діана"
- "Створи користувача з ID 123456789, ім'я Марія" → action: "add", user_id: 123456789, name: "Марія"
- "Зміни ім'я користувача 123456789 на Петро" → action: "edit", user_id: 123456789, name: "Петро"
- "Зміни колір Діана на синій" → action: "edit", name: "Діана", color: "синій" (match name to available users)
- "Зміни колір користувача Діана на синій" → action: "edit", name: "Діана", color: "синій"
- "Діана синій" → action: "edit", name: "Діана", color: "синій" (if context suggests color change)

Return ONLY a valid JSON object with this structure:
{{
    "action": "add|edit|update|other",
    "user_id": 6503698207 or null,
    "name": "User Name" or null,
    "color": "#FFD700" or "yellow" or "жовтий" or "💛" or null,
    "confidence": 0.95,
    "summary": "Brief summary"
}}

Important:
- ALWAYS extract user_id as a NUMBER (integer), not a string - convert "6503698207" to 6503698207
- If user_id is not mentioned but a name is, try to match the name to available users and extract their user_id
- For colors, return the EXACT value mentioned by the user (hex, name, or emoji) - the system will convert it automatically
- Be flexible: if the command is "Зміни колір Діана на синій", extract name="Діана" and color="синій", then match "Діана" to available users
- If you can understand the intent even partially, set confidence >= 0.7 (be lenient)
- If the command is unclear, set confidence < 0.7 and action to "other"
"""

        try:
            complexity = self._calculate_complexity(message, len(available_users))
            thinking_config = self._get_thinking_config(complexity)

            config = None
            if thinking_config:
                config = genai_types.GenerateContentConfig(
                    thinking_config=thinking_config
                )

            print(f"🤖 Calling Gemini API for user management command: '{message[:100]}...'")
            response = self.client.models.generate_content(
                model=f"models/{self.model_name}", contents=prompt, config=config
            )

            if hasattr(response, "text"):
                text = response.text.strip()
                print(f"📝 Got response text (length: {len(text)})")
            elif hasattr(response, "candidates") and response.candidates:
                if response.candidates[0].content and response.candidates[0].content.parts:
                    text = response.candidates[0].content.parts[0].text.strip()
                    print(f"📝 Got response from candidates (length: {len(text)})")
                else:
                    print(f"⚠️ Response has candidates but no content/parts")
                    text = str(response).strip()
            else:
                print(f"⚠️ Unexpected response format: {type(response)}")
                text = str(response).strip()

            print(f"📄 Raw response (first 500 chars): {text[:500]}")

            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
                print(f"📄 Cleaned response (first 500 chars): {text[:500]}")

            parsed = json.loads(text)
            
            # Log successful parsing for debugging
            print(f"✅ Parsed user management command: action={parsed.get('action')}, user_id={parsed.get('user_id')}, name={parsed.get('name')}, confidence={parsed.get('confidence')}")
            
            return parsed
        except json.JSONDecodeError as json_error:
            print(f"❌ JSON parsing error in user management command: {json_error}")
            print(f"❌ Response text (first 1000 chars): {text[:1000] if 'text' in locals() else 'N/A'}")
            print(f"❌ Full response text: {text if 'text' in locals() else 'N/A'}")
            return None
        except Exception as e:
            print(f"❌ Error parsing user management command: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            
            if config and "thinking" in str(e).lower():
                print(f"🔄 Thinking config failed, retrying without thinking config...")
                try:
                    response = self.client.models.generate_content(
                        model=f"models/{self.model_name}", contents=prompt, config=None
                    )
                    if hasattr(response, "text"):
                        text = response.text.strip()
                        print(f"📝 Retry: Got response text (length: {len(text)})")
                    elif hasattr(response, "candidates") and response.candidates:
                        if response.candidates[0].content and response.candidates[0].content.parts:
                            text = response.candidates[0].content.parts[0].text.strip()
                            print(f"📝 Retry: Got response from candidates (length: {len(text)})")
                        else:
                            text = str(response).strip()
                    else:
                        text = str(response).strip()

                    print(f"📄 Retry: Raw response (first 500 chars): {text[:500]}")

                    if text.startswith("```"):
                        text = text.split("```")[1]
                        if text.startswith("json"):
                            text = text[4:]
                        text = text.strip()

                    parsed = json.loads(text)
                    print(f"✅ Parsed user management command (retry): action={parsed.get('action')}, user_id={parsed.get('user_id')}, name={parsed.get('name')}, confidence={parsed.get('confidence')}")
                    return parsed
                except Exception as retry_error:
                    print(f"❌ Error parsing user management command (retry failed): {retry_error}")
                    import traceback
                    print(f"❌ Retry traceback: {traceback.format_exc()}")
                    if 'text' in locals():
                        print(f"❌ Retry response text (first 1000 chars): {text[:1000]}")
                    return None
            else:
                return None

    async def parse_admin_command(
        self,
        message: str,
        available_users: List[Dict[str, Any]],
        current_shifts: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Parse admin natural language command for mass changes.

        Args:
            message: Admin's natural language command
            available_users: List of users
            current_shifts: Current shift assignments

        Returns:
            Parsed command dict with actions to execute
        """
        if not self.client or not self.model_name:
            return None

        users_context = "\n".join(
            [f"- {user['name']} (ID: {user['user_id']})" for user in available_users]
        )

        shifts_context = "\n".join(
            [
                f"- {shift['date']}: {', '.join(shift['user_names'])}"
                for shift in current_shifts[:20]  # Limit context
            ]
        )

        prompt = f"""You are a shift scheduling assistant for admins. Parse the following admin command and extract the actions to execute.

Available users:
{users_context}

Current shifts (sample):
{shifts_context}

Admin command: "{message}"

Extract the following information:
1. Action type: "assign", "unassign", "swap", "clear", or "other"
2. Dates to modify (in YYYY-MM-DD format, or patterns like "all Mondays in July")
3. User names or IDs to assign/unassign
4. Confidence level (0.0 to 1.0)

Return ONLY a valid JSON object with this structure:
{{
    "action": "assign|unassign|swap|clear|other",
    "date_patterns": ["all Mondays in July", "2025-07-15"],
    "dates": ["YYYY-MM-DD"],
    "user_names": ["name1"],
    "user_ids": [123],
    "confidence": 0.95,
    "summary": "Brief summary of what will be done"
}}

For date patterns like "all Mondays in July", include both the pattern and try to list specific dates if possible.
Only return actions with confidence > 0.7.
"""

        try:
            # Calculate message complexity for dynamic thinking budget
            complexity = self._calculate_complexity(
                message, len(available_users) + len(current_shifts)
            )
            thinking_config = self._get_thinking_config(complexity)

            # Build config with thinking
            config = None
            if thinking_config:
                config = genai_types.GenerateContentConfig(
                    thinking_config=thinking_config
                )

            response = self.client.models.generate_content(
                model=f"models/{self.model_name}", contents=prompt, config=config
            )
            # Extract text from response
            if hasattr(response, "text"):
                text = response.text.strip()
            elif hasattr(response, "candidates") and response.candidates:
                text = response.candidates[0].content.parts[0].text.strip()
            else:
                text = str(response).strip()

            # Remove markdown code blocks if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            parsed = json.loads(text)
            return parsed
        except Exception as e:
            # If thinking config fails (e.g., -1 not supported), retry without it
            if config and "thinking" in str(e).lower():
                print(f"Thinking config failed, retrying without: {e}")
                try:
                    response = self.client.models.generate_content(
                        model=f"models/{self.model_name}",
                        contents=prompt,
                        config=None,  # Retry without thinking config
                    )
                    if hasattr(response, "text"):
                        text = response.text.strip()
                    elif hasattr(response, "candidates") and response.candidates:
                        text = response.candidates[0].content.parts[0].text.strip()
                    else:
                        text = str(response).strip()

                    if text.startswith("```"):
                        text = text.split("```")[1]
                        if text.startswith("json"):
                            text = text[4:]
                        text = text.strip()

                    parsed = json.loads(text)
                    return parsed
                except Exception as retry_error:
                    print(
                        f"Error parsing admin command with Gemini (retry failed): {retry_error}"
                    )
                    return None
            else:
                print(f"Error parsing admin command with Gemini: {e}")
                return None

    def _detect_image_format(self, image_data: bytes) -> str:
        """Detect image format from magic bytes"""
        if len(image_data) < 8:
            return "image/jpeg"  # Default to JPEG
        
        # Check magic bytes
        if image_data[:2] == b'\xff\xd8':
            return "image/jpeg"
        elif image_data[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            return "image/webp"
        else:
            # Default to JPEG (Telegram standard)
            return "image/jpeg"

    async def parse_calendar_image(
        self, image_data: bytes, available_users: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse calendar image to extract shift assignments.

        Args:
            image_data: Image bytes
            available_users: List of users with their info

        Returns:
            Dict with parsed assignments: {
                "year": 2025,
                "month": 7,
                "assignments": [
                    {"date": "2025-07-15", "user_names": ["Дана"], "colors": ["#FF69B4"]},
                    ...
                ]
            }
        """
        if not self.client or not self.model_name:
            print("❌ Gemini client or model not initialized")
            return None
        
        # Detect image format
        mime_type = self._detect_image_format(image_data)
        print(f"📸 Detected image format: {mime_type}, size: {len(image_data)} bytes")

        # Build user context with color mappings
        users_context = "\n".join(
            [
                f"- {user['name']} (ID: {user['user_id']}, Color: {user.get('color_code', 'N/A')})"
                for user in available_users
            ]
        )

        prompt = f"""You are analyzing a calendar image for shift scheduling. Extract all shift assignments from this calendar.

Available users and their colors:
{users_context}

The calendar shows colored days representing shift assignments. Each color corresponds to a user or combination of users.

CRITICAL: Carefully examine the calendar image to determine:
1. The EXACT month and year displayed in the calendar header/title (look for month names like "листопад", "November", "липень", "July", etc.)
2. The day numbers visible in the calendar grid
3. Which days have colored assignments

Extract the following information:
1. Year and month - READ THE CALENDAR HEADER CAREFULLY. Do NOT guess or assume. Look for:
   - Month names in Ukrainian (січень, лютий, березень, квітень, травень, червень, липень, серпень, вересень, жовтень, листопад, грудень)
   - Month names in English (January, February, March, April, May, June, July, August, September, October, November, December)
   - Year number (e.g., 2025, 2024)
   - If the calendar shows "листопад" or "November", the month is 11, NOT 7
   - If the calendar shows "липень" or "July", the month is 7
   - Be VERY careful to match the month name you see in the image

2. For each day with a colored assignment, extract:
   - Date (YYYY-MM-DD format) - use the EXACT month/year from the calendar header
   - User name(s) based on color matching to available users
   - Color code (if visible or can be inferred)

Return ONLY a valid JSON object with this structure:
{{
    "year": 2025,
    "month": 11,
    "assignments": [
        {{
            "date": "2025-11-15",
            "user_names": ["Дана"],
            "user_ids": [123],
            "color": "#FF69B4"
        }},
        {{
            "date": "2025-11-16",
            "user_names": ["Діана", "Дана"],
            "user_ids": [456, 123],
            "color": "#9370DB"
        }}
    ]
}}

Important:
- READ THE CALENDAR HEADER FIRST - identify the month name and year before extracting dates
- Match colors to users based on the available users list
- If multiple users share a day (combined color), list all of them
- Only include days that have assignments (colored days)
- Use the EXACT month and year from the calendar image, not assumptions
- Match user names exactly as they appear in the available users list
- Double-check: if you see "листопад" or "November" in the calendar, month should be 11, not 7
- Double-check: if you see "липень" or "July" in the calendar, month should be 7, not 11
"""

        try:
            # Calculate complexity for thinking
            complexity = self._calculate_complexity("image_parse", len(available_users))
            thinking_config = self._get_thinking_config(complexity)

            config = None
            if thinking_config:
                config = genai_types.GenerateContentConfig(
                    thinking_config=thinking_config
                )

            # Send image to Gemini
            # Create image part using inline data with detected format
            image_part = genai_types.Part(
                inline_data=genai_types.Blob(data=image_data, mimeType=mime_type)
            )

            print(f"🤖 Sending image to Gemini API (model: {self.model_name})...")
            response = self.client.models.generate_content(
                model=f"models/{self.model_name}",
                contents=[prompt, image_part],
                config=config,
            )

            # Extract text from response
            text = None
            if hasattr(response, "text"):
                text = response.text.strip()
                print(f"✅ Got response text (length: {len(text)})")
            elif hasattr(response, "candidates") and response.candidates:
                if response.candidates[0].content and response.candidates[0].content.parts:
                    text = response.candidates[0].content.parts[0].text.strip()
                    print(f"✅ Got response from candidates (length: {len(text)})")
                else:
                    print(f"⚠️ Response candidates exist but no content parts found")
                    print(f"Response structure: {type(response.candidates[0])}")
            else:
                text = str(response).strip()
                print(f"⚠️ Using string representation of response (length: {len(text)})")
            
            if not text:
                print("❌ No text content in Gemini response")
                print(f"Response type: {type(response)}")
                print(f"Response attributes: {dir(response)}")
                return None

            # Remove markdown code blocks if present
            original_text = text
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            # Log first 200 chars of response for debugging
            preview = text[:200] if len(text) > 200 else text
            print(f"📝 Response preview: {preview}...")

            try:
                parsed = json.loads(text)
                print(f"✅ Successfully parsed JSON response")
                
                # Validate response structure
                if not isinstance(parsed, dict):
                    print(f"❌ Parsed response is not a dict: {type(parsed)}")
                    return None
                
                if "year" not in parsed or "month" not in parsed:
                    print(f"❌ Missing year or month in response: {parsed.keys()}")
                    return None
                
                # Validate month is reasonable (1-12)
                month = parsed.get("month")
                if not isinstance(month, int) or month < 1 or month > 12:
                    print(f"❌ Invalid month value: {month} (must be 1-12)")
                    return None
                
                # Validate year is reasonable (2020-2030)
                year = parsed.get("year")
                if not isinstance(year, int) or year < 2020 or year > 2030:
                    print(f"❌ Invalid year value: {year} (must be 2020-2030)")
                    return None
                
                if "assignments" not in parsed:
                    print(f"⚠️ No assignments in response, using empty list")
                    parsed["assignments"] = []
                
                # Validate all assignment dates match the extracted month/year
                for assignment in parsed.get("assignments", []):
                    date_str = assignment.get("date", "")
                    if date_str:
                        try:
                            from datetime import datetime
                            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
                            if parsed_date.year != year or parsed_date.month != month:
                                print(f"⚠️ Assignment date {date_str} doesn't match calendar month/year ({year}-{month:02d})")
                                # Fix the date to match the calendar month/year
                                assignment["date"] = f"{year}-{month:02d}-{parsed_date.day:02d}"
                                print(f"✅ Fixed date to: {assignment['date']}")
                        except ValueError:
                            print(f"⚠️ Invalid date format in assignment: {date_str}")
                
                print(f"✅ Validated response: year={year}, month={month}, assignments={len(parsed.get('assignments', []))}")
                return parsed
            except json.JSONDecodeError as json_error:
                print(f"❌ JSON parsing error: {json_error}")
                print(f"❌ Text that failed to parse: {text[:500]}")
                return None
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"❌ Error parsing calendar image: {e}")
            print(f"❌ Full traceback:\n{error_traceback}")
            
            # If thinking config fails, retry without it
            if config and "thinking" in str(e).lower():
                print(f"🔄 Thinking config failed, retrying without thinking config...")
                try:
                    image_part = genai_types.Part(
                        inline_data=genai_types.Blob(
                            data=image_data, mimeType=mime_type
                        )
                    )
                    print(f"🤖 Retrying Gemini API call without thinking config...")
                    response = self.client.models.generate_content(
                        model=f"models/{self.model_name}",
                        contents=[prompt, image_part],
                        config=None,
                    )
                    
                    # Extract text from response
                    text = None
                    if hasattr(response, "text"):
                        text = response.text.strip()
                        print(f"✅ Got response text on retry (length: {len(text)})")
                    elif hasattr(response, "candidates") and response.candidates:
                        if response.candidates[0].content and response.candidates[0].content.parts:
                            text = response.candidates[0].content.parts[0].text.strip()
                            print(f"✅ Got response from candidates on retry (length: {len(text)})")
                    else:
                        text = str(response).strip()
                        print(f"⚠️ Using string representation on retry (length: {len(text)})")
                    
                    if not text:
                        print("❌ No text content in Gemini response (retry)")
                        return None

                    # Remove markdown code blocks if present
                    if text.startswith("```"):
                        text = text.split("```")[1]
                        if text.startswith("json"):
                            text = text[4:]
                        text = text.strip()

                    # Log preview
                    preview = text[:200] if len(text) > 200 else text
                    print(f"📝 Retry response preview: {preview}...")

                    try:
                        parsed = json.loads(text)
                        print(f"✅ Successfully parsed JSON response on retry")
                        
                        # Validate response structure
                        if not isinstance(parsed, dict):
                            print(f"❌ Parsed response is not a dict: {type(parsed)}")
                            return None
                        
                        if "year" not in parsed or "month" not in parsed:
                            print(f"❌ Missing year or month in response: {parsed.keys()}")
                            return None
                        
                        # Validate month is reasonable (1-12)
                        month = parsed.get("month")
                        if not isinstance(month, int) or month < 1 or month > 12:
                            print(f"❌ Invalid month value: {month} (must be 1-12)")
                            return None
                        
                        # Validate year is reasonable (2020-2030)
                        year = parsed.get("year")
                        if not isinstance(year, int) or year < 2020 or year > 2030:
                            print(f"❌ Invalid year value: {year} (must be 2020-2030)")
                            return None
                        
                        if "assignments" not in parsed:
                            parsed["assignments"] = []
                        
                        # Validate all assignment dates match the extracted month/year
                        for assignment in parsed.get("assignments", []):
                            date_str = assignment.get("date", "")
                            if date_str:
                                try:
                                    parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
                                    if parsed_date.year != year or parsed_date.month != month:
                                        print(f"⚠️ Assignment date {date_str} doesn't match calendar month/year ({year}-{month:02d})")
                                        # Fix the date to match the calendar month/year
                                        assignment["date"] = f"{year}-{month:02d}-{parsed_date.day:02d}"
                                        print(f"✅ Fixed date to: {assignment['date']}")
                                except ValueError:
                                    print(f"⚠️ Invalid date format in assignment: {date_str}")
                        
                        print(f"✅ Validated retry response: year={year}, month={month}, assignments={len(parsed.get('assignments', []))}")
                        return parsed
                    except json.JSONDecodeError as json_error:
                        print(f"❌ JSON parsing error on retry: {json_error}")
                        print(f"❌ Text that failed to parse: {text[:500]}")
                        return None
                except Exception as retry_error:
                    retry_traceback = traceback.format_exc()
                    print(f"❌ Error parsing calendar image (retry failed): {retry_error}")
                    print(f"❌ Retry traceback:\n{retry_traceback}")
                    return None
            else:
                return None


# Global instance
gemini_service = GeminiService()
