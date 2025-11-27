"""Gemini API integration for natural language processing"""

import os
import json
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

            # Try to get the first available model
            for model_name, version in model_names:
                try:
                    # Check if model exists by trying to get it
                    genai_client.models.get(name=f"models/{model_name}")
                    self.model_name = model_name
                    self.model_version = version
                    break
                except Exception:
                    continue

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

        prompt = f"""You are a shift scheduling assistant. Parse the following user request and extract the intent.

Available users:
{users_context}

User request: "{message}"

Extract the following information:
1. Action type: "swap", "assign", "unassign", "query", or "other"
2. Dates mentioned (in YYYY-MM-DD format)
3. User names or IDs mentioned
4. Confidence level (0.0 to 1.0)

Return ONLY a valid JSON object with this structure:
{{
    "action": "swap|assign|unassign|query|other",
    "dates": ["YYYY-MM-DD"],
    "user_names": ["name1", "name2"],
    "user_ids": [123, 456],
    "confidence": 0.95,
    "summary": "Brief summary of the request"
}}

If dates are relative (e.g., "tomorrow", "next Monday"), try to infer the actual date based on today's context, but note it in the summary.
If user names are mentioned, try to match them to the available users list.
If the request is unclear, set confidence below 0.5 and action to "other".
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
            return None

        users_context = "\n".join(
            [
                f"- {user['name']} (ID: {user['user_id']}, Color: {user.get('color_code', 'N/A')})"
                for user in available_users
            ]
        )

        prompt = f"""You are a user management assistant for admins. Parse the following admin command for adding or editing users.

Available users:
{users_context}

Admin command: "{message}"

Extract the following information:
1. Action: "add", "edit", "update", or "other"
2. User ID (if mentioned)
3. User name
4. Color (if mentioned)
5. Other properties to update

Return ONLY a valid JSON object with this structure:
{{
    "action": "add|edit|update|other",
    "user_id": 123,
    "name": "User Name",
    "color": "#FFD700",
    "confidence": 0.95,
    "summary": "Brief summary"
}}

If adding a new user, user_id might not be provided - in that case, set it to null.
"""

        try:
            complexity = self._calculate_complexity(message, len(available_users))
            thinking_config = self._get_thinking_config(complexity)

            config = None
            if thinking_config:
                config = genai_types.GenerateContentConfig(
                    thinking_config=thinking_config
                )

            response = self.client.models.generate_content(
                model=f"models/{self.model_name}", contents=prompt, config=config
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
        except Exception as e:
            if config and "thinking" in str(e).lower():
                try:
                    response = self.client.models.generate_content(
                        model=f"models/{self.model_name}", contents=prompt, config=None
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
                except:
                    return None
            print(f"Error parsing user management command: {e}")
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
            return None

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

Extract the following information:
1. Year and month shown in the calendar
2. For each day with a colored assignment, extract:
   - Date (YYYY-MM-DD format)
   - User name(s) based on color matching
   - Color code (if visible or can be inferred)

Return ONLY a valid JSON object with this structure:
{{
    "year": 2025,
    "month": 7,
    "assignments": [
        {{
            "date": "2025-07-15",
            "user_names": ["Дана"],
            "user_ids": [123],
            "color": "#FF69B4"
        }},
        {{
            "date": "2025-07-16",
            "user_names": ["Діана", "Дана"],
            "user_ids": [456, 123],
            "color": "#9370DB"
        }}
    ]
}}

Important:
- Match colors to users based on the available users list
- If multiple users share a day (combined color), list all of them
- Only include days that have assignments (colored days)
- If you can't determine the exact date, use the month/year from the calendar header
- Match user names exactly as they appear in the available users list
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
            # Create image part using inline data
            image_part = genai_types.Part(
                inline_data=genai_types.Blob(data=image_data, mimeType="image/png")
            )

            response = self.client.models.generate_content(
                model=f"models/{self.model_name}",
                contents=[prompt, image_part],
                config=config,
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
            # If thinking config fails, retry without it
            if config and "thinking" in str(e).lower():
                print(f"Thinking config failed for image, retrying without: {e}")
                try:
                    image_part = genai_types.Part(
                        inline_data=genai_types.Blob(
                            data=image_data, mimeType="image/png"
                        )
                    )
                    response = self.client.models.generate_content(
                        model=f"models/{self.model_name}",
                        contents=[prompt, image_part],
                        config=None,
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
                    print(f"Error parsing calendar image (retry failed): {retry_error}")
                    return None
            else:
                print(f"Error parsing calendar image: {e}")
                return None


# Global instance
gemini_service = GeminiService()
