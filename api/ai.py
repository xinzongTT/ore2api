from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from api.image_inputs import parse_image_edit_request, read_image_sources
from api.support import require_identity, resolve_image_base_url
from services.content_filter import check_request, request_text
from services.log_service import LoggedCall
from services import oreate_backend_api as _oreate_api
from services.protocol import openai_v1_image_edit

# OreateAI 图像模型 ID 集合 —— 从后端模型表派生，避免与 /v1/models 漂移


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str = "gpt-image-2"
    n: int = Field(default=1, ge=1, le=4)
    size: str | None = None
    quality: str = "auto"
    response_format: str = "url"
    history_disabled: bool = True
    stream: bool | None = None
    # OreateAI 扩展参数
    aspect_ratio: str = "1:1"    # 16:9 / 1:1 / 2:3 / 3:2 / 3:4 / 4:3 / 4:5 / 5:4 / 9:16 / 21:9
    resolution: str = "1K"       # 4K / 2K / 1K
    images: list[str] = Field(default_factory=list)
    image: str = ""
    image_url: str = ""


class VideoGenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str = "seedance-2.0-fast"
    n: int = Field(default=1, ge=1, le=4)
    size: str = "1024x576"
    duration: int = Field(default=10, ge=1, le=120)
    aspect_ratio: str = "16:9"   # 16:9 / 9:16 / 1:1
    resolution: str = "480P"     # 1080P / 720P / 480P
    response_format: str = "url"
    audio: bool = False
    image: str = ""
    image_url: str = ""
    images: list[str] = Field(default_factory=list)


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str | None = None
    prompt: str | None = None
    n: int | None = None
    stream: bool | None = None
    modalities: list[str] | None = None
    messages: list[dict[str, object]] | None = None


class ResponseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str | None = None
    input: object | None = None
    tools: list[dict[str, object]] | None = None
    tool_choice: object | None = None
    stream: bool | None = None


class AnthropicMessageRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str | None = None
    messages: list[dict[str, object]] | None = None
    system: object | None = None
    stream: bool | None = None


class SearchRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


class EditableFileTaskRequest(BaseModel):
    prompt: str = ""
    kind: str = "ppt"
    base64_images: list[str] = Field(default_factory=list)
    client_task_id: str | None = None


TRACE_REQUEST_HEADERS = {
    "x-request-id": "x_request_id",
    "x-newapi-request-id": "x_newapi_request_id",
    "x-oneapi-request-id": "x_oneapi_request_id",
    "x-channel-id": "x_channel_id",
    "x-channel-name": "x_channel_name",
}


def attach_trace_headers(call: LoggedCall, request: Request) -> None:
    if not call._trace_image_perf():
        return
    headers: dict[str, str] = {}
    for header, field in TRACE_REQUEST_HEADERS.items():
        value = str(request.headers.get(header) or "").strip()
        if value:
            headers[field] = value[:160]
    if headers:
        existing = call.trace_metadata.get("request_headers")
        if isinstance(existing, dict):
            existing.update(headers)
        else:
            call.trace_metadata["request_headers"] = headers


async def filter_or_log(call: LoggedCall, text: str) -> None:
    try:
        await run_in_threadpool(check_request, text)
    except HTTPException as exc:
        call.log("调用失败", status="failed", error=str(exc.detail))
        raise


def _video_reference_image(payload: dict[str, object]) -> str:
    image = str(payload.get("image") or payload.get("image_url") or "").strip()
    if image:
        return image
    images = payload.get("images")
    if isinstance(images, list) and images:
        return str(images[0] or "").strip()
    return ""


def _normalize_video_model(model: object) -> str:
    model_id = str(model or "").strip()
    if model_id == "seedance-2.0":
        return "seedance-2.0-fast"
    return model_id or "seedance-2.0-fast"


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/v1/models")
    async def list_models(authorization: str | None = Header(default=None)):
        require_identity(authorization)
        try:
            # OreateAI 生图/生视频模型（真实 modelName 见 oreate_backend_api）
            return await run_in_threadpool(_oreate_api.list_models)
        except Exception as exc:
            raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc

    @router.post("/v1/images/generations")
    async def generate_images(
            body: ImageGenerationRequest,
            request: Request,
            authorization: str | None = Header(default=None),
    ):
        identity = require_identity(authorization)
        payload = body.model_dump(mode="python")
        payload["base_url"] = resolve_image_base_url(request)
        call = LoggedCall(identity, "/v1/images/generations", body.model, "文生图", request_text=body.prompt)
        attach_trace_headers(call, request)
        call.attach_trace_metadata(payload)
        await filter_or_log(call, body.prompt)
        return await call.run(
            lambda p: _oreate_api.image_generation(
                prompt=p["prompt"],
                model=p["model"],
                n=p.get("n", 1),
                size=p.get("size") or "1024x1024",
                aspect_ratio=p.get("aspect_ratio", "1:1"),
                resolution=p.get("resolution", "1K"),
                response_format=p.get("response_format", "url"),
                images=p.get("images") or [],
                image=p.get("image", ""),
                image_url=p.get("image_url", ""),
            ),
            payload,
        )

    @router.post("/v1/video/generations")
    async def generate_video(
            body: VideoGenerationRequest,
            request: Request,
            authorization: str | None = Header(default=None),
    ):
        identity = require_identity(authorization)
        payload = body.model_dump(mode="python")
        payload["model"] = _normalize_video_model(payload.get("model"))
        call = LoggedCall(identity, "/v1/video/generations", payload["model"], "文生视频", request_text=body.prompt)
        attach_trace_headers(call, request)
        await filter_or_log(call, body.prompt)
        return await call.run(
            lambda p: _oreate_api.video_generation(
                prompt=p["prompt"],
                model=p["model"],
                n=p.get("n", 1),
                size=p.get("size") or "1024x576",
                duration=p.get("duration", 5),
                aspect_ratio=p.get("aspect_ratio", "16:9"),
                resolution=p.get("resolution", "480P"),
                response_format=p.get("response_format", "url"),
                audio=p.get("audio", False),
                image=_video_reference_image(p),
            ),
            payload,
        )

    def _removed_openai_feature(feature: str) -> HTTPException:
        return HTTPException(
            status_code=410,
            detail={
                "error": {
                    "message": f"{feature} has been removed in this oreate-only build",
                    "type": "gone",
                    "code": "410",
                }
            },
        )

    @router.post("/v1/images/edits")
    async def edit_images(
            request: Request,
            authorization: str | None = Header(default=None),
    ):
        identity = require_identity(authorization)
        payload, image_sources, mask_sources = await parse_image_edit_request(request)
        images = await read_image_sources(image_sources)
        masks = await read_image_sources(mask_sources) if mask_sources else []
        payload["images"] = images
        payload["mask"] = masks
        payload["base_url"] = resolve_image_base_url(request)

        call = LoggedCall(identity, "/v1/images/edits", str(payload.get("model") or "gpt-image-2"), "图生图", request_text=payload.get("prompt", ""))
        attach_trace_headers(call, request)
        await filter_or_log(call, str(payload.get("prompt") or ""))
        return await call.run(lambda p: openai_v1_image_edit.handle(p), payload)

    @router.post("/v1/chat/completions")
    async def create_chat_completion(body: Request, authorization: str | None = Header(default=None)):
        require_identity(authorization)
        raise _removed_openai_feature("/v1/chat/completions")

    @router.post("/v1/responses")
    async def create_response(body: Request, authorization: str | None = Header(default=None)):
        require_identity(authorization)
        raise _removed_openai_feature("/v1/responses")

    @router.post("/v1/messages")
    async def create_message(
            body: Request,
            authorization: str | None = Header(default=None),
            x_api_key: str | None = Header(default=None, alias="x-api-key"),
            anthropic_version: str | None = Header(default=None, alias="anthropic-version"),
    ):
        require_identity(authorization or (f"Bearer {x_api_key}" if x_api_key else None))
        raise _removed_openai_feature("/v1/messages")

    @router.post("/v1/search")
    async def search(body: Request, authorization: str | None = Header(default=None)):
        require_identity(authorization)
        raise _removed_openai_feature("/v1/search")

    @router.get("/v1/editable-file-tasks")
    async def list_editable_file_tasks(ids: str = "", authorization: str | None = Header(default=None)):
        require_identity(authorization)
        raise _removed_openai_feature("/v1/editable-file-tasks")

    @router.post("/v1/editable-file-tasks")
    async def create_editable_file_task(authorization: str | None = Header(default=None)):
        require_identity(authorization)
        raise _removed_openai_feature("/v1/editable-file-tasks")

    @router.get("/files/{file_path:path}")
    async def download_editable_file(file_path: str):
        raise _removed_openai_feature("/files/*")

    @router.post("/v1/ppt/generations")
    async def create_ppt_task(authorization: str | None = Header(default=None)):
        require_identity(authorization)
        raise _removed_openai_feature("/v1/ppt/generations")

    @router.post("/v1/psd/generations")
    async def create_psd_task(authorization: str | None = Header(default=None)):
        require_identity(authorization)
        raise _removed_openai_feature("/v1/psd/generations")

    return router
