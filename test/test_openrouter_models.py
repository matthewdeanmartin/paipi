from paipi.openrouter_models import (
    FALLBACK_ROUTER_MODEL,
    resolve_model_pool,
    shortlist_models,
    shortlisted_model_ids,
)


def test_shortlist_models_prefers_free_and_cheap_text_models():
    models = [
        {
            "id": "free-chat",
            "name": "Free Chat",
            "architecture": {"modality": "text->text"},
            "pricing": {"prompt": "0", "completion": "0"},
            "context_length": 100000,
            "created": 2,
        },
        {
            "id": "cheap-chat",
            "name": "Cheap Chat",
            "architecture": {"modality": "text->text"},
            "pricing": {"prompt": "0.0000001", "completion": "0.0000002"},
            "context_length": 200000,
            "created": 3,
        },
        {
            "id": "image-model",
            "name": "Image Model",
            "architecture": {"modality": "text+image->text"},
            "pricing": {"prompt": "0", "completion": "0"},
        },
    ]

    shortlist = shortlist_models(models)

    assert [model["id"] for model in shortlist["free"]] == ["free-chat"]
    assert [model["id"] for model in shortlist["cheap"]] == ["cheap-chat"]
    assert shortlisted_model_ids(shortlist) == [
        "free-chat",
        "cheap-chat",
        FALLBACK_ROUTER_MODEL,
    ]


def test_resolve_model_pool_filters_unavailable_configured_models(monkeypatch):
    monkeypatch.setattr(
        "paipi.openrouter_models.fetch_models",
        lambda api_key, base_url="https://openrouter.ai/api/v1", timeout=30.0: [
            {
                "id": "good-model",
                "name": "Good Model",
                "architecture": {"modality": "text->text"},
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 100000,
                "created": 4,
            }
        ],
    )

    resolution = resolve_model_pool(
        api_key="sk-or-test",
        base_url="https://openrouter.ai/api/v1",
        configured_models=["dead-model", "good-model"],
    )

    assert resolution.selected_models == ["good-model", FALLBACK_ROUTER_MODEL]
    assert resolution.unavailable_configured_models == ["dead-model"]
