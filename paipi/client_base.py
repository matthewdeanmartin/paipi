"""
Base OpenRouter AI client.

Handles structured formats and simple retry workflows.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, cast

import untruncate_json
from openai import OpenAI

from .config import config
from .logger import llm_logger  # <--- IMPORT THE NEW LOGGER


class OpenRouterClientBase:
    """Client for interacting with OpenRouter AI service via OpenAI interface."""

    def __init__(
        self, api_key: Optional[str] = None, base_url: Optional[str] = None
    ) -> None:
        """Initialize the OpenRouter client."""
        self.api_key = api_key or config.openrouter_api_key
        self.base_url = base_url or config.openrouter_base_url

        if not self.api_key:
            raise ValueError("OpenRouter API key is required")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    # -----------------
    # Robust JSON repair helpers (used by search + legacy README path)
    # -----------------
    def ask_llm_to_fix_json(self, broken_json: str) -> Optional[str]:
        """Makes a one-shot request to the LLM to fix a broken JSON string."""
        print("--- Attempting one-shot LLM call to fix JSON ---")
        try:
            response = self.client.chat.completions.create(
                model=config.default_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a JSON repair utility. The user will provide a malformed JSON string. "
                        "Your sole task is to correct any syntax errors (e.g., trailing commas, "
                        "missing brackets, incorrect quoting) and return only the valid, minified JSON object. "
                        "Do not add any commentary, explanations, or markdown fences.",
                    },
                    {"role": "user", "content": broken_json},
                ],
                temperature=0.0,  # Be deterministic
                max_tokens=4000,
            )
            fixed_content = response.choices[0].message.content
            llm_logger.debug(
                f"LLM attempt to fix JSON resulted in:\n---\n{fixed_content}\n---"
            )
            return fixed_content
        except Exception as e:
            print(f"Error during LLM JSON fix attempt: {e}")
            llm_logger.error(f"Error during LLM JSON fix attempt: {e}")
            return None

    def parse_and_repair_json(self, content: str) -> Dict[str, Any]:
        """
        A robust method to parse JSON, with multiple repair strategies.

        Raises:
            ValueError: If all parsing and repair attempts fail.
        """
        # 1. Clean up common markdown fences
        s = content.strip()
        if s.startswith("```json"):
            s = s.split("```json", 1)[1]
            if "```" in s:
                s = s.rsplit("```", 1)[0]
        elif s.startswith("```"):
            s = s.split("```", 1)[1]
            if "```" in s:
                s = s.rsplit("```", 1)[0]

        s = s.strip()

        # 2. First attempt: Standard JSON load
        try:
            return cast(dict[str, Any], json.loads(s))
        except json.JSONDecodeError as e:
            print(f"Initial JSON decode failed: {e}. Attempting repairs...")
            llm_logger.warning(f"Initial JSON decode failed: {e}. Raw content:\n{s}")

        # 3. Second attempt: Use untruncate_json for common truncation issues
        try:
            repaired_s = untruncate_json.complete(s)
            data = json.loads(repaired_s)
            print("Successfully repaired JSON with `untruncate_json`.")
            llm_logger.info("Successfully repaired JSON with `untruncate_json`.")
            return cast(dict[str, Any], data)
        except (json.JSONDecodeError, Exception) as e:
            print(f"`untruncate_json` failed: {e}. Attempting LLM-based fix.")
            llm_logger.warning(f"`untruncate_json` failed: {e}.")

        # 4. Third attempt: One-shot call to the LLM to fix the JSON
        fixed_json_str = self.ask_llm_to_fix_json(s)
        if fixed_json_str:
            try:
                data = json.loads(fixed_json_str)
                print("Successfully repaired JSON with a one-shot LLM call.")
                llm_logger.info("Successfully repaired JSON with a one-shot LLM call.")
                return cast(dict[str, Any], data)
            except json.JSONDecodeError as e:
                print(f"LLM-repaired JSON is still invalid: {e}")
                llm_logger.error(
                    f"LLM-repaired JSON is still invalid: {e}\nRepaired content:\n{fixed_json_str}"
                )

        # 5. If all else fails, raise an error.
        raise ValueError("All attempts to parse and repair the JSON response failed.")

    # --- END: NEW HELPER METHODS ---

    def extract_json(self, content: str) -> Dict[str, Any]:
        """
        Extract JSON whether or not the model wrapped it in code fences.
        (Legacy helper used by JSON-based README path.)
        """
        s = content.strip()
        if s.startswith("```"):
            # tolerate ```json or ``` wrapping
            try:
                s = s.split("```", 1)[1]
                s = s.split("```", 1)[0]
            except Exception:
                pass
        return cast(dict[str, Any], json.loads(s))
