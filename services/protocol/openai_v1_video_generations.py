from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from services.oreate_backend_api import video_generation


def _reference_image(body: dict) -> str:
    image = str(body.get("image") or body.get("image_url") or "").strip()
    if image:
        return image
    images = body.get("images")
    if isinstance(images, list) and images:
        return str(images[0] or "").strip()
    return ""


async def handle_video_generations(request: Request) -> JSONResponse:
    body = await request.json()

    prompt = body.get("prompt", "")
    model = body.get("model", "seedance-2.0-fast")
    n = body.get("n", 1)
    size = body.get("size", "1024x576")
    duration = body.get("duration", 10)
    aspect_ratio = body.get("aspect_ratio", "16:9")
    resolution = body.get("resolution", "480P")
    response_format = body.get("response_format", "url")
    audio = body.get("audio", False)
    image = _reference_image(body)
    user = body.get("user")

    result = video_generation(
        prompt=prompt,
        model=model,
        n=n,
        size=size,
        duration=duration,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        response_format=response_format,
        audio=audio,
        image=image,
        user=user,
    )
    return JSONResponse(content=result)
