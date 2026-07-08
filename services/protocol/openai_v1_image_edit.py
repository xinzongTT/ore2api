from __future__ import annotations

from typing import Any

from services import oreate_backend_api


def handle(body: dict[str, Any]) -> dict[str, Any]:
    return oreate_backend_api.image_generation(
        prompt=str(body.get("prompt") or ""),
        model=str(body.get("model") or "gpt-image-2"),
        n=int(body.get("n") or 1),
        size=str(body.get("size") or "1024x1024"),
        response_format=str(body.get("response_format") or "url"),
        quality=str(body.get("quality") or "auto"),
        aspect_ratio=str(body.get("aspect_ratio") or "1:1"),
        resolution=str(body.get("resolution") or "1K"),
        images=body.get("images") or [],
        image=body.get("image") or "",
        image_url=body.get("image_url") or "",
    )
