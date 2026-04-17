"""
Base OpenRouter AI client.

Handles structured formats and simple retry workflows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from threading import Lock
import time
from typing import Any, Dict, Optional, cast

import untruncate_json
from openai import OpenAI

from .config import config
from .logger import llm_logger


@dataclass(frozen=True)
class ChatCompletionResult:
    """Normalized chat completion result with model metadata."""

    content: str
    model_used: str
    requested_model: str
    attempted_models: list[str]


class OpenRouterClientBase:
    """Client for interacting with OpenRouter AI service via OpenAI interface."""

    _model_rotation_lock = Lock()
    _next_model_index = 0
    _temporarily_disabled_models: dict[str, float] = {}
    _permanently_disabled_models: set[str] = set()

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

    @staticmethod
    def format_llm_error(exc: Exception) -> str:
        """Extract the most useful error message from an upstream API exception."""
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()

        response = getattr(exc, "response", None)
        if response is not None:
            try:
                payload = response.json()
            except Exception:
                payload = None

            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    message = error.get("message")
                    if isinstance(message, str) and message.strip():
                        return message.strip()

        message = str(exc).strip()
        return message or exc.__class__.__name__

    @staticmethod
    def _status_code_from_error(exc: Exception) -> Optional[int]:
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            return status_code

        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return status_code

        return None

    @classmethod
    def _next_rotation_offset(cls, pool_size: int) -> int:
        with cls._model_rotation_lock:
            offset = cls._next_model_index % pool_size
            cls._next_model_index += 1
        return offset

    @classmethod
    def _is_model_disabled(cls, model: str) -> bool:
        with cls._model_rotation_lock:
            if model in cls._permanently_disabled_models:
                return True

            disabled_until = cls._temporarily_disabled_models.get(model)
            if disabled_until is None:
                return False
            if disabled_until <= time.time():
                cls._temporarily_disabled_models.pop(model, None)
                return False
            return True

    @classmethod
    def _disable_model_permanently(cls, model: str) -> None:
        with cls._model_rotation_lock:
            cls._permanently_disabled_models.add(model)
            cls._temporarily_disabled_models.pop(model, None)

    @classmethod
    def _disable_model_until(cls, model: str, unix_timestamp: float) -> None:
        with cls._model_rotation_lock:
            existing = cls._temporarily_disabled_models.get(model, 0.0)
            cls._temporarily_disabled_models[model] = max(existing, unix_timestamp)

    @staticmethod
    def _rate_limit_reset_from_error(exc: Exception) -> Optional[float]:
        body = getattr(exc, "body", None)
        if not isinstance(body, dict):
            return None

        error = body.get("error")
        if not isinstance(error, dict):
            return None

        metadata = error.get("metadata")
        if not isinstance(metadata, dict):
            return None

        headers = metadata.get("headers")
        if not isinstance(headers, dict):
            return None

        reset_value = headers.get("X-RateLimit-Reset")
        try:
            reset = float(reset_value)
        except (TypeError, ValueError):
            return None

        if reset > 10_000_000_000:
            reset /= 1000.0
        return reset

    def _record_model_failure(self, model: str, exc: Exception, message: str) -> None:
        lowered = message.lower()
        status_code = self._status_code_from_error(exc)

        if status_code == 404 or "no endpoints found" in lowered:
            self._disable_model_permanently(model)
            llm_logger.warning("Permanently disabling unavailable model %s", model)
            return

        if status_code == 429 or "rate limit" in lowered:
            reset_at = self._rate_limit_reset_from_error(exc) or (time.time() + 60.0)
            self._disable_model_until(model, reset_at)
            llm_logger.info("Cooling down rate-limited model %s", model)

    def _model_candidates(self, preferred_model: Optional[str] = None) -> list[str]:
        configured_models = list(getattr(config, "openrouter_models", [config.default_model]))
        if not configured_models:
            configured_models = [config.default_model]

        candidates: list[str] = []
        if preferred_model:
            candidates.extend(
                model for model in [preferred_model, *configured_models] if model
            )
        elif getattr(config, "rotate_models", True) and len(configured_models) > 1:
            offset = self._next_rotation_offset(len(configured_models))
            candidates.extend(configured_models[offset:] + configured_models[:offset])
        else:
            candidates.extend(configured_models)

        deduped: list[str] = []
        for model in candidates:
            if model not in deduped:
                deduped.append(model)

        available_candidates = [
            model for model in deduped if model and not self._is_model_disabled(model)
        ]
        if available_candidates:
            return available_candidates

        fallback_model = "openrouter/free"
        if not self._is_model_disabled(fallback_model):
            return [fallback_model]
        return deduped

    def _should_try_next_model(
        self, exc: Exception, message: str, has_more_models: bool
    ) -> bool:
        if not has_more_models:
            return False

        status_code = self._status_code_from_error(exc)
        if status_code == 429 or status_code == 404:
            return True
        if status_code is not None and status_code >= 500:
            return True

        lowered = message.lower()
        retry_markers = (
            "rate limit",
            "temporarily rate-limited",
            "retry shortly",
            "provider returned error",
            "no endpoints found",
            "model not found",
            "upstream",
        )
        return any(marker in lowered for marker in retry_markers)

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        preferred_model: Optional[str] = None,
    ) -> ChatCompletionResult:
        """Create a chat completion with model rotation and fallback."""
        attempted_models: list[str] = []
        candidates = self._model_candidates(preferred_model)
        last_exc: Optional[Exception] = None

        for index, model in enumerate(candidates):
            attempted_models.append(model)
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content or ""
                raw_model = getattr(response, "model", None)
                model_used = raw_model if isinstance(raw_model, str) and raw_model else model
                if index > 0:
                    llm_logger.info(
                        "Fell back to model %s after failures in %s",
                        model_used,
                        attempted_models[:-1],
                    )
                return ChatCompletionResult(
                    content=content,
                    model_used=model_used,
                    requested_model=model,
                    attempted_models=list(attempted_models),
                )
            except Exception as exc:
                last_exc = exc
                message = self.format_llm_error(exc)
                self._record_model_failure(model, exc, message)
                llm_logger.warning("Model %s failed: %s", model, message)
                if not self._should_try_next_model(
                    exc, message, has_more_models=index < len(candidates) - 1
                ):
                    raise

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No OpenRouter models are configured")

    # -----------------
    # Robust JSON repair helpers (used by search + legacy README path)
    # -----------------
    def ask_llm_to_fix_json(self, broken_json: str) -> Optional[str]:
        """Makes a one-shot request to the LLM to fix a broken JSON string."""
        print("--- Attempting one-shot LLM call to fix JSON ---")
        try:
            response = self.create_chat_completion(
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
                temperature=0.0,
                max_tokens=4000,
            )
            fixed_content = response.content
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
            try:
                # Remove opening fence
                s = s.split("```", 1)[1]
                # If there's a language specifier like 'json', remove it
                if s.lower().startswith("json"):
                    s = s[4:]
                # Remove closing fence
                if "```" in s:
                    s = s.rsplit("```", 1)[0]
            except Exception:
                pass
        return cast(dict[str, Any], json.loads(s.strip()))
