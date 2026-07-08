from __future__ import annotations

from typing import Any

from services.account_service import account_service
from services.config import config
from services.oreate_backend_api import OREATE_IMAGE_MODELS, OREATE_VIDEO_MODELS


FALLBACK_CHAT_MODELS: list[str] = []

FALLBACK_IMAGE_MODELS = [str(model.get("id") or "") for model in OREATE_IMAGE_MODELS if model.get("id")]

FALLBACK_VIDEO_MODELS = [str(model.get("id") or "") for model in OREATE_VIDEO_MODELS if model.get("id")]


def _normalize_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    seen: set[str] = set()
    for item in raw:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _settings_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _configured_chat_models(settings: dict[str, Any]) -> list[str]:
    catalog = _settings_dict(settings.get("model_catalog"))
    explicit = _normalize_list(catalog.get("chat_models"))
    if explicit:
        return explicit

    combined: list[str] = []
    for key in ("base_chat_models", "specialized_chat_models", "image_capable_chat_models"):
        for model in _normalize_list(catalog.get(key)):
            if model not in combined:
                combined.append(model)
    return combined


def _configured_image_models(settings: dict[str, Any]) -> list[str]:
    image_generation = _settings_dict(settings.get("image_generation"))
    catalog = _settings_dict(settings.get("model_catalog"))
    for source in (
        image_generation.get("model_options"),
        catalog.get("image_api_models"),
        image_generation.get("supported_models"),
    ):
        models = _normalize_list(source)
        if models:
            return models
    return []


def _image_models_from_accounts(accounts: list[dict[str, Any]]) -> list[str]:
    available_accounts = [
        account
        for account in accounts
        if isinstance(account, dict) and account_service._is_image_account_available(account)
    ]
    if not available_accounts:
        return []

    return list(FALLBACK_IMAGE_MODELS)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def get_model_catalog() -> dict[str, Any]:
    settings = config.get()
    configured_image_models = _configured_image_models(settings)

    chat_source = "removed"
    chat_models = list(FALLBACK_CHAT_MODELS)

    if configured_image_models:
        image_source = "config"
        image_models = configured_image_models
    else:
        account_models = _image_models_from_accounts(account_service.list_accounts())
        image_source = "accounts" if account_models else "fallback"
        image_models = account_models or list(FALLBACK_IMAGE_MODELS)

    image_models = _unique(image_models)
    video_models = _unique(list(FALLBACK_VIDEO_MODELS))
    all_models = _unique([*image_models, *video_models])

    return {
        "object": "model_catalog",
        "chat_models": _unique(chat_models),
        "image_models": image_models,
        "video_models": video_models,
        "all_models": all_models,
        "source": {
            "chat": chat_source,
            "image": image_source,
            "video": "fallback",
        },
        "openai_models_endpoint": "/v1/models",
    }
