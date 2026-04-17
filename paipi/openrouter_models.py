"""
Helpers for discovering and selecting usable OpenRouter models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx


FALLBACK_ROUTER_MODEL = "openrouter/free"


def to_float(value: Any, default: float = 999999.0) -> float:
    """Best-effort float conversion for pricing fields."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_text_only(model: dict[str, Any]) -> bool:
    """Return True when the model is text-in/text-out."""
    architecture = model.get("architecture", {}) or {}
    return architecture.get("modality") == "text->text"


def score_model(model: dict[str, Any]) -> tuple[Any, ...]:
    """
    Lower scores are better.

    Preference order:
    1. free
    2. cheap
    3. larger context
    4. newer model metadata
    5. names that suggest instruct/chat/text use
    """
    pricing = model.get("pricing", {}) or {}
    prompt = to_float(pricing.get("prompt"))
    completion = to_float(pricing.get("completion"))
    free = prompt == 0.0 and completion == 0.0

    context = model.get("context_length", 0) or 0
    created = model.get("created", 0) or 0
    name = (model.get("name") or model.get("id") or "").lower()

    textish_bonus = 0
    for token in ("instruct", "chat", "text", "assistant"):
        if token in name:
            textish_bonus -= 1

    total_price = prompt + completion
    return (
        0 if free else 1,
        total_price,
        -context,
        -created,
        textish_bonus,
    )


def shortlist_models(
    models: list[dict[str, Any]],
    max_free: int = 3,
    max_cheap: int = 3,
    cheap_prompt_cap: float = 0.20,
    cheap_completion_cap: float = 0.80,
) -> dict[str, list[dict[str, Any]]]:
    """Split text models into preferred free and cheap buckets."""
    text_models = [model for model in models if is_text_only(model)]

    free: list[dict[str, Any]] = []
    cheap: list[dict[str, Any]] = []

    for model in text_models:
        pricing = model.get("pricing", {}) or {}
        prompt = to_float(pricing.get("prompt"))
        completion = to_float(pricing.get("completion"))

        if prompt == 0.0 and completion == 0.0:
            free.append(model)
        elif (
            prompt <= cheap_prompt_cap / 1_000_000
            and completion <= cheap_completion_cap / 1_000_000
        ):
            cheap.append(model)

    return {
        "free": sorted(free, key=score_model)[:max_free],
        "cheap": sorted(cheap, key=score_model)[:max_cheap],
    }


def shortlisted_model_ids(shortlist: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Flatten shortlist buckets into a de-duplicated ordered list of model ids."""
    model_ids: list[str] = []
    for bucket_name in ("free", "cheap"):
        for model in shortlist.get(bucket_name, []):
            model_id = model.get("id")
            if isinstance(model_id, str) and model_id and model_id not in model_ids:
                model_ids.append(model_id)

    if FALLBACK_ROUTER_MODEL not in model_ids:
        model_ids.append(FALLBACK_ROUTER_MODEL)
    return model_ids


def _models_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/models"


def fetch_models(
    api_key: str,
    base_url: str = "https://openrouter.ai/api/v1",
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """Fetch the currently available OpenRouter model catalog."""
    with httpx.Client(timeout=timeout) as client:
        response = client.get(
            _models_url(base_url),
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        payload = response.json()

    data = payload.get("data", [])
    return [item for item in data if isinstance(item, dict)]


@dataclass(frozen=True)
class ModelPoolResolution:
    """Resolved model pool for runtime usage."""

    selected_models: list[str]
    unavailable_configured_models: list[str]
    discovered_shortlist: list[str]


def resolve_model_pool(
    *,
    api_key: Optional[str],
    base_url: str,
    configured_models: list[str],
) -> ModelPoolResolution:
    """Resolve a usable model pool from config plus live catalog data."""
    configured_deduped: list[str] = []
    for model in configured_models:
        if model and model not in configured_deduped:
            configured_deduped.append(model)

    if not api_key:
        return ModelPoolResolution(
            selected_models=configured_deduped or [FALLBACK_ROUTER_MODEL],
            unavailable_configured_models=[],
            discovered_shortlist=[FALLBACK_ROUTER_MODEL],
        )

    try:
        available_models = fetch_models(api_key=api_key, base_url=base_url)
    except Exception:
        return ModelPoolResolution(
            selected_models=configured_deduped or [FALLBACK_ROUTER_MODEL],
            unavailable_configured_models=[],
            discovered_shortlist=[FALLBACK_ROUTER_MODEL],
        )

    available_ids = {
        model_id
        for model in available_models
        if isinstance((model_id := model.get("id")), str) and model_id
    }

    valid_configured = [
        model for model in configured_deduped if model == FALLBACK_ROUTER_MODEL or model in available_ids
    ]
    unavailable_configured = [
        model
        for model in configured_deduped
        if model != FALLBACK_ROUTER_MODEL and model not in available_ids
    ]

    shortlist = shortlisted_model_ids(shortlist_models(available_models))
    selected_models = valid_configured or shortlist or [FALLBACK_ROUTER_MODEL]

    if FALLBACK_ROUTER_MODEL not in selected_models:
        selected_models.append(FALLBACK_ROUTER_MODEL)

    return ModelPoolResolution(
        selected_models=selected_models,
        unavailable_configured_models=unavailable_configured,
        discovered_shortlist=shortlist,
    )


def format_shortlist(bucket_name: str, models: list[dict[str, Any]]) -> str:
    """Render a shortlist bucket for terminal display."""
    lines = [f"\n{bucket_name.upper()}", "-" * len(bucket_name)]
    for model in models:
        pricing = model.get("pricing", {}) or {}
        created = model.get("created")
        created_str = (
            datetime.fromtimestamp(created, tz=timezone.utc).date().isoformat()
            if created
            else "unknown"
        )
        lines.append(
            f"{model['id']}\n"
            f"  name:    {model.get('name')}\n"
            f"  context: {model.get('context_length')}\n"
            f"  prompt:  ${to_float(pricing.get('prompt')) * 1_000_000:.4f}/1M\n"
            f"  output:  ${to_float(pricing.get('completion')) * 1_000_000:.4f}/1M\n"
            f"  created: {created_str}\n"
        )
    return "\n".join(lines)
