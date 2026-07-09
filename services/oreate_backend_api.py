from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import random
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, AsyncIterator
from urllib.parse import quote, unquote, unquote_to_bytes, urlparse

from curl_cffi import requests
from fastapi import HTTPException

from services.account_service import ImageAccountSelectionError, account_service
from services.proxy_service import proxy_settings
from utils.log import logger

OREATE_BASE = "https://www.oreateai.com"
OREATE_API_BASE = "https://www.oreateai.com"

# ✅ 已确认的真实 API 路径（通过浏览器 CLI 抓包验证 2026-07-07）:
#
# 认证方式: Cookie JWT
#   - ics_vsid: 主身份 JWT (HttpOnly, Secure, ~24h)
#   - ouss: OAuth SSO JWT (HttpOnly, Secure, ~30天)
#   - JWT 字段: tenant_id, crm_user_id, id, external_id, device_id, sid, type, appkey
#
# 核心生成流程:
# 1. 创建会话: POST /oreate/create/chat
#    请求体: {"type":"aiImage","docId":""} 或 {"type":"aiVideo","docId":""}
#    响应: {"status":{"code":0},"data":{"chatId":"6a92ccc..."}}
#
# 2. SSE 流式生成: GET /oreate/sse/stream
#    类型: Server-Sent Events 流
#    页面导航到: /home/chat/aiImage/{chatId} 或 /home/chat/aiVideo/{chatId}
#
# 辅助端点:
#   - 用户信息: GET /oreate/user/getuserinfo
#   - 剩余积分: GET /bizapi/point/getrestpoints
#   - 模型配置: GET /oreate/img/getmodelconfig

# ✅ 图像模型（来自页面 UI: Nano Banana / GPT Image / Seedream / Kling）
# ✅ 视频模型（来自页面 UI: Seedance 系列 / Kling / Veo / Pixverse / Wan）

OREATE_IMAGE_MODELS = [
    # Nano Banana 系列
    {"id": "nano-banana",          "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Nano Banana"},
    {"id": "nano-banana-2",        "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Google Nano Banana 2"},
    # GPT Image 系列
    {"id": "gpt-image",            "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "GPT Image"},
    {"id": "gpt-image-2",          "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "GPT Image 2.0"},
    # Seedream 系列
    {"id": "seedream",             "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Seedream"},
    # Kling 图像
    {"id": "kling-image",          "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Kling Image"},
]

OREATE_VIDEO_MODELS = [
    # Seedance 系列
    {"id": "seedance-2.0",         "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Seedance 2.0"},
    {"id": "seedance-2.0-fast",    "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Seedance 2.0 Fast"},
    {"id": "seedance-2.0-mini",    "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Seedance 2.0 Mini"},
    {"id": "seedance-1.5-pro",     "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Seedance 1.5 Pro"},
    # Kling 视频
    {"id": "kling",                "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Kling"},
    # Veo
    {"id": "veo",                  "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Veo"},
    # Pixverse
    {"id": "pixverse",             "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Pixverse"},
    # Wan
    {"id": "wan",                  "object": "model", "created": 1700000000, "owned_by": "oreate", "display": "Wan"},
]

# 图像支持的比例（来自 UI）
OREATE_IMAGE_ASPECT_RATIOS = ["16:9", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "21:9"]

# 图像支持的分辨率（来自 UI）
OREATE_IMAGE_RESOLUTIONS = ["4K", "2K", "1K"]

# 视频支持的比例（getmodelconfigv3 的 videoSize[].ratio，抓包确认）
OREATE_VIDEO_ASPECT_RATIOS = ["16:9", "1:1", "3:4", "4:3", "9:16", "21:9"]

# 视频分辨率（getmodelconfigv3 的 videoResolution，是纯数字 "480"/"720"，非 "480P"）
OREATE_VIDEO_RESOLUTIONS = ["480", "720", "1080"]

_VIDEO_MODEL_CONFIG_TTL_SECONDS = 3600
_VIDEO_MODEL_CONFIG_CACHE: tuple[float, list[dict[str, Any]]] | None = None

_FALLBACK_VIDEO_MODEL_CONFIGS: list[dict[str, Any]] = [
    {
        "modelName": "Seedance 2.0 Fast",
        "supportAudio": True,
        "videoResolution": ["480", "720"],
        "videoSize": [
            {"ratio": "16:9"},
            {"ratio": "1:1"},
            {"ratio": "3:4"},
            {"ratio": "4:3"},
            {"ratio": "9:16"},
            {"ratio": "21:9"},
        ],
        "duration": [{"value": 5}, {"value": 10}],
        "pointCostImage": [
            {"audio": False, "duration": 5, "point": 25, "resolution": "480", "aiType": 14072},
            {"audio": True, "duration": 5, "point": 25, "resolution": "480", "aiType": 14073},
            {"audio": False, "duration": 5, "point": 70, "resolution": "720", "aiType": 14074},
            {"audio": True, "duration": 5, "point": 70, "resolution": "720", "aiType": 14075},
            {"audio": False, "duration": 10, "point": 65, "resolution": "480", "aiType": 14076},
            {"audio": True, "duration": 10, "point": 65, "resolution": "480", "aiType": 14077},
            {"audio": False, "duration": 10, "point": 145, "resolution": "720", "aiType": 14078},
            {"audio": True, "duration": 10, "point": 145, "resolution": "720", "aiType": 14079},
        ],
    }
]

MAX_REFERENCE_MEDIA_BYTES = 50 * 1024 * 1024

OREATE_MODELS = {
    "chat": [
        {"id": "oreate-chat",      "object": "model", "created": 1700000000, "owned_by": "oreate"},
        {"id": "oreate-chat-pro",  "object": "model", "created": 1700000000, "owned_by": "oreate"},
        {"id": "oreate-research",  "object": "model", "created": 1700000000, "owned_by": "oreate"},
        {"id": "oreate-essay",     "object": "model", "created": 1700000000, "owned_by": "oreate"},
    ],
    "image": OREATE_IMAGE_MODELS,
    "video": OREATE_VIDEO_MODELS,
}

# OpenAI 风格 model id → OreateAI 真实 modelName（用于 sse/stream 的 config.modelName）
# 真实名称来自 /oreate/img/getmodelconfig 与 /oreate/aivideo/getmodelconfigv3
IMAGE_MODEL_NAME_MAP = {
    "nano-banana": "Google Nano Banana",
    "nano-banana-2": "Google Nano Banana 2",
    "nano-banana-pro": "Google Nano Banana Pro",
    "gpt-image": "GPT Image 1.5",
    "gpt-image-1.5": "GPT Image 1.5",
    "gpt-image-2": "GPT Image 2.0",
    "seedream": "Seedream 4.0",
    "seedream-4.0": "Seedream 4.0",
    "seedream-4.5": "Seedream 4.5",
    "seedream-5.0-lite": "Seedream 5.0 Lite",
    "kling-image": "Kling3.0 Omini",
    "kling-o1-image": "Kling O1 Image",
}

VIDEO_MODEL_NAME_MAP = {
    "seedance-2.0": "Seedance 2.0",
    "seedance-2.0-fast": "Seedance 2.0 Fast",
    "seedance-2.0-mini": "Seedance 2.0 Mini",
    "seedance-1.5-pro": "Seedance 1.5 Pro",
    "kling": "Kling 3.0",
    "kling-3.0": "Kling 3.0",
    "kling-3.0-omni": "Kling 3.0 Omni",
    "kling-2.6": "Kling 2.6",
    "kling-2.5": "Kling 2.5",
    "kling-o1": "Kling o1",
    "veo": "Veo 3.1",
    "veo-3.1": "Veo 3.1",
    "veo-3": "Veo 3",
    "pixverse": "Pixverse V5",
    "pixverse-v5": "Pixverse V5",
    "wan": "Wan 2.6",
    "wan-2.5": "Wan 2.5",
    "wan-2.6": "Wan 2.6",
    "wan-2.7": "Wan 2.7",
}


def _resolve_image_model_name(model: str) -> str:
    """把传入的 model 解析为 OreateAI 真实 modelName。支持 id、真实名、大小写。"""
    m = str(model or "").strip()
    if not m:
        return "Google Nano Banana 2"
    if m in IMAGE_MODEL_NAME_MAP:
        return IMAGE_MODEL_NAME_MAP[m]
    # 已是真实名（在配置里出现过）直接用
    real_names = {x["display"] for x in OREATE_IMAGE_MODELS if x.get("display")}
    if m in real_names or m.startswith(("Google", "GPT", "Seedream", "Kling")):
        return m
    return IMAGE_MODEL_NAME_MAP.get(m.lower(), "Google Nano Banana 2")


def _resolve_video_model_name(model: str) -> str:
    m = str(model or "").strip()
    if not m:
        return "Seedance 2.0 Fast"
    if m in VIDEO_MODEL_NAME_MAP:
        return VIDEO_MODEL_NAME_MAP[m]
    if m.startswith(("Seedance", "Kling", "Veo", "Pixverse", "Wan")):
        return m
    return VIDEO_MODEL_NAME_MAP.get(m.lower(), "Seedance 2.0 Fast")


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_video_duration(duration: Any) -> int:
    return 10 if _to_int(duration, 10) >= 8 else 5


def _normalize_video_resolution(resolution: Any) -> str:
    normalized = str(resolution or "").upper().replace("P", "").strip()
    return normalized if normalized in OREATE_VIDEO_RESOLUTIONS else "480"


def _infer_video_aspect_ratio(size: str, aspect_ratio: str) -> str:
    ratio = str(aspect_ratio or "16:9").strip()
    if size and "x" in size and ratio == "16:9":
        w, h = str(size).split("x", 1)
        if w.isdigit() and h.isdigit():
            iw, ih = int(w), int(h)
            if iw < ih:
                ratio = "9:16"
            elif iw == ih:
                ratio = "1:1"
    return ratio if ratio in OREATE_VIDEO_ASPECT_RATIOS else "16:9"


def _extract_video_model_configs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    models = data.get("models") or []
    if isinstance(models, list):
        return [m for m in models if isinstance(m, dict)]
    return []


def _fetch_video_model_configs(session: requests.Session) -> list[dict[str, Any]]:
    global _VIDEO_MODEL_CONFIG_CACHE
    now = time.time()
    if _VIDEO_MODEL_CONFIG_CACHE and now - _VIDEO_MODEL_CONFIG_CACHE[0] < _VIDEO_MODEL_CONFIG_TTL_SECONDS:
        return _VIDEO_MODEL_CONFIG_CACHE[1]
    try:
        resp = session.get(f"{OREATE_API_BASE}/oreate/aivideo/getmodelconfigv3", timeout=30)
        if resp.status_code == 200:
            models = _extract_video_model_configs(resp.json() if resp.text else {})
            if models:
                _VIDEO_MODEL_CONFIG_CACHE = (now, models)
                return models
        logger.warning(f"OreateAI video model config error: HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"OreateAI video model config exception: {e}")
    return _FALLBACK_VIDEO_MODEL_CONFIGS


def _find_video_model_config(model_name: str, model_configs: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    wanted = str(model_name or "").strip().lower()
    for item in model_configs or []:
        if str(item.get("modelName") or "").strip().lower() == wanted:
            return item
    return None


def _video_size_ratios(model_config: dict[str, Any]) -> list[str]:
    return [
        str(item.get("ratio") or "").strip()
        for item in (model_config.get("videoSize") or [])
        if isinstance(item, dict) and item.get("ratio")
    ]


def _video_duration_values(model_config: dict[str, Any]) -> list[int]:
    values: list[int] = []
    for item in model_config.get("duration") or []:
        if isinstance(item, dict) and item.get("value") is not None:
            values.append(_to_int(item.get("value"), 0))
    return [v for v in values if v > 0]


def _video_costs(model_config: dict[str, Any]) -> list[dict[str, Any]]:
    costs = model_config.get("pointCostImage") or model_config.get("pointCost") or []
    return [item for item in costs if isinstance(item, dict)]


def _select_video_cost(
    costs: list[dict[str, Any]],
    resolution: str,
    duration: int,
    audio: bool,
) -> dict[str, Any] | None:
    def matches(item: dict[str, Any]) -> bool:
        if str(item.get("resolution") or "") != resolution:
            return False
        if _to_int(item.get("duration"), 0) != duration:
            return False
        return True

    for item in costs:
        if matches(item) and _to_bool(item.get("audio")) == audio:
            return item
    for item in costs:
        if matches(item):
            return item
    return costs[0] if costs else None


def _build_video_config(
    *,
    model: str,
    size: str,
    duration: Any,
    aspect_ratio: str,
    resolution: Any,
    audio: Any = False,
    image: Any = "",
    model_configs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    model_name = _resolve_video_model_name(model)
    ratio = _infer_video_aspect_ratio(size, aspect_ratio)
    normalized_resolution = _normalize_video_resolution(resolution)
    normalized_duration = _normalize_video_duration(duration)
    is_audio = _to_bool(audio)
    ai_type = 0

    configs = model_configs if model_configs is not None else _FALLBACK_VIDEO_MODEL_CONFIGS
    model_config = _find_video_model_config(model_name, configs)
    if model_config:
        supported_ratios = _video_size_ratios(model_config)
        if supported_ratios and ratio not in supported_ratios:
            ratio = "16:9" if "16:9" in supported_ratios else supported_ratios[0]

        supported_resolutions = [str(v) for v in (model_config.get("videoResolution") or [])]
        if supported_resolutions and normalized_resolution not in supported_resolutions:
            normalized_resolution = "480" if "480" in supported_resolutions else supported_resolutions[0]

        supported_durations = _video_duration_values(model_config)
        if supported_durations and normalized_duration not in supported_durations:
            normalized_duration = 5 if 5 in supported_durations else supported_durations[0]

        if not _to_bool(model_config.get("supportAudio")):
            is_audio = False

        cost = _select_video_cost(_video_costs(model_config), normalized_resolution, normalized_duration, is_audio)
        if cost:
            normalized_resolution = str(cost.get("resolution") or normalized_resolution)
            normalized_duration = _to_int(cost.get("duration"), normalized_duration)
            is_audio = _to_bool(cost.get("audio"))
            ai_type = _to_int(cost.get("aiType"), 0)

    return {
        "modelName": model_name,
        "ratio": ratio,
        "resolution": normalized_resolution,
        "duration": normalized_duration,
        "isAudio": is_audio,
        "aiType": ai_type,
        "scene": "text_or_image",
        "textOrImage": {"image": str(image or "")},
    }


def _pick_account() -> dict:
    accounts = account_service.list_accounts()
    normal = [a for a in accounts if a.get("status") != "异常"]
    if not normal:
        normal = accounts
    if not normal:
        return {}
    return random.choice(normal)


def _impersonate_target() -> str:
    """选择 curl_cffi 支持的 Chrome 指纹。

    注意：curl_cffi 0.13 中 Session(impersonate=...) 构造不会报错，
    只有真正发请求时才抛 ImpersonateError，所以要检查支持列表本身。
    """
    try:
        from curl_cffi.requests import impersonate as _imp
        supported = set()
        for attr in ("BrowserTypeLiteral", "DEFAULT_CHROME", "BrowserType"):
            obj = getattr(_imp, attr, None)
            if obj is not None and hasattr(obj, "__members__"):
                supported |= set(obj.__members__.keys())
        # curl_cffi 暴露的支持列表
        try:
            from curl_cffi.const import CurlOpt  # noqa
        except Exception:
            pass
        for target in ("chrome142", "chrome136", "chrome131", "chrome124", "chrome120", "chrome116"):
            if not supported or target in supported:
                # 真实探测：发一个到本地不存在端口的请求会因指纹不支持而立即抛 ImpersonateError
                try:
                    s = requests.Session(impersonate=target)
                    s.get("http://127.0.0.1:1/", timeout=1)
                except Exception as e:
                    if "not supported" in str(e).lower():
                        continue
                    return target  # 连接错误说明指纹被接受了
                return target
    except Exception:
        pass
    # 保守回退：0.13 稳定支持 chrome131
    return "chrome131"


_IMPERSONATE = _impersonate_target()


def _make_session(account: dict) -> requests.Session:
    session = requests.Session(impersonate=_IMPERSONATE)
    # 使用抓包获取的 Cookie 认证 (ics_vsid + ouss)
    # 注：ouss (OAuth SSO, ~30天) 是主凭据，单独即可通过认证；
    #     ics_vsid (~24h) 由平台在访问部分接口时动态换取，注册阶段通常只拿到 ouss。
    cookies = account.get("cookies", {})
    ics_vsid = account.get("ics_vsid", "") or cookies.get("ics_vsid", "")
    ouss = account.get("ouss", "") or cookies.get("ouss", "")

    if ics_vsid:
        session.cookies.set("ics_vsid", ics_vsid, domain=".oreateai.com")
    if ouss:
        session.cookies.set("ouss", ouss, domain=".oreateai.com")
    # 也设置必要的非关键 cookie
    session.cookies.set("i18n_locale", "zh-CN", domain=".oreateai.com")

    # 出口代理策略（与注册分离）：
    #   注册走 register.json 的动态代理（每次换 IP 躲风控）；
    #   生图/生视频/邀请查询默认走服务器固定 IP（账号长期同 IP 使用更像真人）。
    # 优先级：账号显式 proxy > config 的 oreate-proxy（生图专用）。
    #   注意：真实注册入库的账号 proxy 为空，不会继承注册用的动态代理。
    #   若确需生图也走代理，在 config.yaml 配 oreate-proxy（留空=服务器直连）。
    proxy = str(account.get("proxy") or "").strip()
    if not proxy:
        try:
            from services.config import config as _cfg
            proxy = str(_cfg.get("oreate-proxy") or "").strip()
        except Exception:
            proxy = ""
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}

    session.headers["Content-Type"] = "application/json"
    session.headers["Accept"] = "application/json, text/plain, */*"
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    )
    session.headers["Accept-Language"] = "zh-CN,zh;q=0.9,en;q=0.8"
    session.headers["Origin"] = OREATE_BASE
    session.headers["Referer"] = f"{OREATE_BASE}/home/index/zh"
    return session


# ── 生成核心：create/chat + sse/stream（抓包+逆向确认 2026-07-07）──────
import re as _re

_IMG_URL_RE = _re.compile(r"https?://cdn\.oreateai\.com/aiimage/[^\s\\\"')]+")
_VIDEO_URL_RE = _re.compile(r"https?://cdn\.oreateai\.com/aivideo/[^\s\\\"')]+")
_MEDIA_URL_RE = _re.compile(r"https?://[^\s\\\"')]+\.(?:png|jpg|jpeg|webp|mp4|mov|webm)")
_SSE_ERR_RE = _re.compile(r'"code":(\d+),"msg":"([^"]+)"')


def _extract_generation_urls(raw: str, chat_type: str) -> list[str]:
    if chat_type == "aiVideo":
        urls = _VIDEO_URL_RE.findall(raw) or _MEDIA_URL_RE.findall(raw)
    else:
        urls = _IMG_URL_RE.findall(raw) or _MEDIA_URL_RE.findall(raw)
    return list(dict.fromkeys(u.rstrip("\\") for u in urls))


class OreateAuthError(RuntimeError):
    pass


def _generation_error(
    status_code: int,
    message: str,
    error_type: str = "server_error",
    code: str | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "message": str(message or "OreateAI generation failed"),
                "type": error_type,
                "code": str(code or status_code),
            }
        },
    )


def _ensure_url_response_format(response_format: str | None) -> None:
    normalized = str(response_format or "url").strip().lower()
    if normalized and normalized != "url":
        raise _generation_error(
            400,
            "OreateAI only supports response_format=url",
            "invalid_request_error",
            "unsupported_response_format",
        )


def _extension_from_mime(mime_type: str) -> str:
    subtype = mime_type.split("/", 1)[1].split("+", 1)[0] if "/" in mime_type else "png"
    if subtype == "jpeg":
        return "jpg"
    return re.sub(r"[^A-Za-z0-9]+", "", subtype.lower()) or "png"


def _safe_reference_filename(filename: object, content_type: str, fallback: str = "reference") -> str:
    raw = PurePosixPath(str(filename or "")).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._")
    if not cleaned:
        cleaned = fallback
    if "." not in cleaned:
        cleaned = f"{cleaned}.{_extension_from_mime(content_type)}"
    return cleaned


def _reference_content_type(filename: str, content_type: object = "") -> str:
    candidate = str(content_type or "").split(";", 1)[0].strip().lower()
    if candidate.startswith("image/"):
        return candidate
    guessed = mimetypes.guess_type(filename)[0] or ""
    return guessed if guessed.startswith("image/") else "image/png"


def _decode_reference_data_url(value: str) -> tuple[bytes, str, str]:
    header, separator, payload = value.partition(",")
    if not separator:
        raise _generation_error(400, "invalid data image URL", "invalid_request_error", "invalid_image")
    content_type = header.split(";", 1)[0].removeprefix("data:") or "image/png"
    if not content_type.startswith("image/"):
        raise _generation_error(400, "image must be an image/* data URL", "invalid_request_error", "invalid_image")
    try:
        data = base64.b64decode(payload, validate=True) if ";base64" in header else unquote_to_bytes(payload)
    except (binascii.Error, ValueError) as exc:
        raise _generation_error(400, "invalid data image URL", "invalid_request_error", "invalid_image") from exc
    if not data:
        raise _generation_error(400, "image data is empty", "invalid_request_error", "invalid_image")
    if len(data) > MAX_REFERENCE_MEDIA_BYTES:
        raise _generation_error(400, "image exceeds 50MB limit", "invalid_request_error", "image_too_large")
    return data, f"reference.{_extension_from_mime(content_type)}", content_type


def _should_skip_ssl_verify_for_reference_url(url: str) -> bool:
    if proxy_settings.should_skip_ssl_verify():
        return True
    parsed = urlparse(str(url or "").strip())
    host = str(parsed.hostname or "").strip().lower()
    return host == "cdn.oreateai.com" or host.endswith(".oreateai.com")


def _download_reference_image(url: str) -> tuple[bytes, str, str]:
    source = str(url or "").strip()
    parsed = urlparse(source)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise _generation_error(400, "image URL must be http or https", "invalid_request_error", "invalid_image_url")
    try:
        request_kwargs: dict[str, Any] = {}
        if _should_skip_ssl_verify_for_reference_url(source):
            request_kwargs["verify"] = False
        response = requests.get(
            source,
            headers={"Accept": "image/*,*/*;q=0.8", "User-Agent": "oreate2api image fetcher"},
            timeout=60,
            allow_redirects=True,
            **request_kwargs,
        )
    except Exception as exc:
        raise _generation_error(400, f"image URL fetch failed: {exc}", "invalid_request_error", "invalid_image_url") from exc
    if not 200 <= response.status_code < 300:
        raise _generation_error(
            400,
            f"image URL fetch failed: HTTP {response.status_code}",
            "invalid_request_error",
            "invalid_image_url",
        )
    content_length = str(response.headers.get("content-length") or "").strip()
    if content_length.isdigit() and int(content_length) > MAX_REFERENCE_MEDIA_BYTES:
        raise _generation_error(400, "image exceeds 50MB limit", "invalid_request_error", "image_too_large")
    data = response.content
    if not data:
        raise _generation_error(400, "image URL returned empty content", "invalid_request_error", "invalid_image_url")
    if len(data) > MAX_REFERENCE_MEDIA_BYTES:
        raise _generation_error(400, "image exceeds 50MB limit", "invalid_request_error", "image_too_large")
    filename = _safe_reference_filename(PurePosixPath(unquote(parsed.path)).name, str(response.headers.get("content-type") or ""))
    content_type = _reference_content_type(filename, response.headers.get("content-type"))
    return data, filename, content_type


def _media_tuple_from_value(value: Any) -> tuple[bytes, str, str] | None:
    if isinstance(value, tuple) and len(value) >= 3:
        data, filename, content_type = value[:3]
        if isinstance(data, (bytes, bytearray)):
            content_type_text = _reference_content_type(str(filename or ""), content_type)
            return bytes(data), _safe_reference_filename(filename, content_type_text), content_type_text
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith("data:"):
        return _decode_reference_data_url(text)
    if text.startswith(("http://", "https://")):
        return _download_reference_image(text)
    return None


def _upload_token_items(payload: dict[str, Any]) -> list[dict[str, str]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return []
    key_list = data.get("KeyList") or data.get("keyList") or {}
    if not isinstance(key_list, dict):
        return []
    items: list[dict[str, str]] = []
    for _, value in key_list.items():
        if isinstance(value, dict):
            bucket = str(value.get("bucket") or data.get("bucket") or "").strip()
            object_path = str(value.get("objectPath") or value.get("object") or "").strip()
            session_key = str(value.get("sessionkey") or value.get("sessionKey") or data.get("sessionkey") or "").strip()
        else:
            bucket = str(data.get("bucket") or "").strip()
            object_path = str(value or "").strip()
            session_key = str(data.get("sessionkey") or data.get("sessionKey") or "").strip()
        if bucket and object_path and session_key:
            items.append({"bucket": bucket, "object": object_path, "token": session_key})
    return items


def _upload_oreate_media(
    session: requests.Session,
    media: tuple[bytes, str, str],
    *,
    source: str = "aiImage",
) -> dict[str, Any]:
    data, filename, content_type = media
    if not data:
        raise _generation_error(400, "image data is empty", "invalid_request_error", "invalid_image")
    if len(data) > MAX_REFERENCE_MEDIA_BYTES:
        raise _generation_error(400, "image exceeds 50MB limit", "invalid_request_error", "image_too_large")

    filename = _safe_reference_filename(filename, content_type)
    content_type = _reference_content_type(filename, content_type)
    file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else _extension_from_mime(content_type)
    token_resp = session.post(
        f"{OREATE_API_BASE}/oreate/convert/getuploadbostoken",
        json={"mFileList": [{"filename": filename, "fileExt": file_ext, "size": len(data)}], "source": source},
        timeout=30,
    )
    token_resp.raise_for_status()
    token_payload = token_resp.json() if token_resp.text else {}
    token_items = _upload_token_items(token_payload)
    if not token_items:
        raise RuntimeError("Oreate upload token response did not include an upload target")

    target = token_items[0]
    bucket = target["bucket"]
    object_path = target["object"]
    upload_token = target["token"]
    request_kwargs: dict[str, Any] = {}
    proxies = getattr(session, "proxies", None)
    if proxies:
        request_kwargs["proxies"] = proxies

    init_url = (
        "https://storage.googleapis.com/upload/storage/v1/b/"
        f"{quote(bucket, safe='')}/o?uploadType=resumable&name={quote(object_path, safe='')}"
    )
    init_resp = requests.post(
        init_url,
        headers={
            "Authorization": f"Bearer {upload_token}",
            "X-Upload-Content-Type": content_type,
            "X-Upload-Content-Length": str(len(data)),
        },
        data=b"",
        timeout=60,
        impersonate=_IMPERSONATE,
        **request_kwargs,
    )
    init_resp.raise_for_status()
    location = str(init_resp.headers.get("Location") or init_resp.headers.get("location") or "").strip()
    if not location:
        raise RuntimeError("GCS resumable upload did not return a Location header")

    put_resp = requests.put(
        location,
        headers={"Content-Type": content_type, "Content-Length": str(len(data))},
        data=data,
        timeout=120,
        impersonate=_IMPERSONATE,
        **request_kwargs,
    )
    put_resp.raise_for_status()
    try:
        put_payload = put_resp.json() if put_resp.text else {}
    except Exception:
        put_payload = {}
    media_link = str(put_payload.get("mediaLink") or put_payload.get("selfLink") or "").strip() if isinstance(put_payload, dict) else ""
    return {
        "object": object_path,
        "bosObjectPath": object_path,
        "bosUrl": media_link or object_path,
        "filename": filename,
        "content_type": content_type,
        "size": len(data),
    }


def _upload_value(uploaded: dict[str, Any]) -> str:
    return str(
        uploaded.get("object")
        or uploaded.get("bosObjectPath")
        or uploaded.get("bosUrl")
        or uploaded.get("mediaLink")
        or ""
    ).strip()


def _oreate_attachment_from_uploaded(uploaded: dict[str, Any]) -> dict[str, Any] | None:
    object_ref = _upload_value(uploaded)
    if not object_ref:
        return None
    filename = _safe_reference_filename(uploaded.get("filename"), str(uploaded.get("content_type") or "image/png"))
    stem, _, ext = filename.rpartition(".")
    return {
        "bos_url": object_ref,
        "bosUrl": object_ref,
        "docId": "",
        "doc_title": stem or filename,
        "doc_type": ext or _extension_from_mime(str(uploaded.get("content_type") or "image/png")),
        "size": int(uploaded.get("size") or 0),
        "flag": "upload",
        "type": "file",
        "status": 1,
    }


def _uploaded_from_internal_reference(value: str) -> dict[str, Any]:
    filename = PurePosixPath(value).name or "reference.png"
    content_type = _reference_content_type(filename)
    return {
        "object": value,
        "bosObjectPath": value,
        "bosUrl": value,
        "filename": filename,
        "content_type": content_type,
        "size": 0,
    }


def _prepare_oreate_media_reference(session: requests.Session, value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        ref = _upload_value(value)
        if ref:
            filename = str(value.get("filename") or value.get("fileName") or PurePosixPath(ref).name or "reference.png")
            content_type = _reference_content_type(filename, value.get("content_type") or value.get("type"))
            return {
                "object": ref,
                "bosObjectPath": ref,
                "bosUrl": str(value.get("bosUrl") or value.get("bos_url") or ref),
                "filename": _safe_reference_filename(filename, content_type),
                "content_type": content_type,
                "size": int(value.get("size") or 0),
            }

    media = _media_tuple_from_value(value)
    if media is not None:
        return _upload_oreate_media(session, media)

    if isinstance(value, str) and value.strip():
        return _uploaded_from_internal_reference(value.strip())
    return None


def _iter_reference_values(value: Any) -> list[Any]:
    if value in (None, "", []):
        return []
    if isinstance(value, (list, tuple)):
        if len(value) >= 3 and isinstance(value[0], (bytes, bytearray)):
            return [value]
        return [item for item in value if item not in (None, "")]
    return [value]


def _build_oreate_attachments(session: requests.Session, values: Any) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    for value in _iter_reference_values(values):
        uploaded = _prepare_oreate_media_reference(session, value)
        if not uploaded:
            continue
        attachment = _oreate_attachment_from_uploaded(uploaded)
        if attachment:
            attachments.append(attachment)
    return attachments


def _resolve_video_reference_image(session: requests.Session, value: Any) -> tuple[str, list[dict[str, Any]]]:
    if not value:
        return "", []
    uploaded = _prepare_oreate_media_reference(session, value)
    if not uploaded:
        return "", []
    object_ref = _upload_value(uploaded)
    attachment = _oreate_attachment_from_uploaded(uploaded)
    return object_ref, [attachment] if attachment else []


def _first_video_reference(kwargs: dict[str, Any]) -> Any:
    value = kwargs.get("image") or kwargs.get("image_url")
    if value:
        return value
    images = kwargs.get("images")
    if isinstance(images, list) and images:
        return images[0]
    return ""


def _acquire_generation_account() -> tuple[str, dict]:
    try:
        access_token = account_service.get_available_access_token(source_type="oreateai")
    except ImageAccountSelectionError as exc:
        raise _generation_error(exc.status_code, str(exc), exc.error_type, exc.code) from exc

    account = account_service.get_account(access_token)
    if not account:
        try:
            account_service.release_image_slot(access_token)
        except Exception as exc:
            logger.warning(f"OreateAI release missing account slot failed: {exc}")
        raise _generation_error(
            503,
            "Selected OreateAI account is no longer available",
            "server_error",
            "no_available_account",
        )
    return access_token, account


def _mark_generation_result(access_token: str, success: bool) -> None:
    if not access_token:
        return
    try:
        account_service.mark_image_result(access_token, success)
    except Exception as exc:
        logger.warning(f"OreateAI generation account result update failed: {exc}")


def _close_session(session: Any) -> None:
    try:
        close = getattr(session, "close", None)
        if callable(close):
            close()
    except Exception:
        pass


def _create_chat(session: requests.Session, chat_type: str) -> str:
    """POST /oreate/create/chat → chatId。chat_type: aiImage / aiVideo"""
    resp = session.post(
        f"{OREATE_API_BASE}/oreate/create/chat",
        json={"type": chat_type, "docId": ""},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json() if resp.text else {}
    chat_id = str((data.get("data") or {}).get("chatId") or "").strip()
    if not chat_id:
        raise RuntimeError(f"create/chat 未返回 chatId: {str(data)[:200]}")
    return chat_id


def _run_generation_stream(
    session: requests.Session,
    chat_type: str,
    prompt: str,
    config_key: str,
    config: dict,
    timeout: int = 300,
    attachments: list[dict[str, Any]] | None = None,
) -> dict:
    """执行 create/chat + sse/stream，返回 {urls:[...], raw, error}

    config_key: 'imageConfig' 或 'videoConfig'
    config: {modelName, ratio, resolution, (duration)}
    """
    chat_id = _create_chat(session, chat_type)
    body = {
        "clientType": "pc",
        "type": "chat",
        "chatId": chat_id,
        "chatType": chat_type,
        "focusId": chat_id,
        "from": "home",
        "chatTitle": "Unnamed Session",
        "messages": [{"role": "user", "content": prompt, "attachments": attachments or []}],
        config_key: config,
        "extra": {"doc_name": "", "module_name": "gpt4o"},
    }
    resp = session.post(
        f"{OREATE_API_BASE}/oreate/sse/stream",
        json=body,
        headers={"Accept": "text/event-stream"},
        timeout=timeout,
        stream=True,
    )
    if resp.status_code != 200:
        return {"urls": [], "raw": "", "error": f"HTTP {resp.status_code}", "chat_id": chat_id}

    chunks: list[str] = []
    for line in resp.iter_lines():
        if not line:
            continue
        text = line.decode("utf-8") if isinstance(line, (bytes, bytearray)) else str(line)
        chunks.append(text)
        if _extract_generation_urls(text, chat_type):
            break
        if '"event":"end"' in text:
            break
    raw = "\n".join(chunks)

    err = _SSE_ERR_RE.search(raw)
    error = None
    if err and err.group(1) not in ("0",):
        error = err.group(2)

    urls = _extract_generation_urls(raw, chat_type)
    return {"urls": urls, "raw": raw, "error": error, "chat_id": chat_id}


# ── 邀请裂变积分相关 ──────────────────────────────────────────
def get_invite_code(account: dict) -> str:
    """获取账号的邀请码 (GET /oreate/activity/getinviteurl)

    返回格式: "370c68ea9f246f4378f6ba62,1783421929" (用户哈希,时间戳)
    注册新账号时把该值传入 inviteCode，注册成功后双方各 +100 积分。
    """
    session = _make_session(account)
    try:
        resp = session.get(f"{OREATE_API_BASE}/oreate/activity/getinviteurl", timeout=30)
        if resp.status_code != 200:
            logger.error(f"getinviteurl error: {resp.status_code}")
            return ""
        data = resp.json() if resp.text else {}
        return str((data.get("data") or {}).get("inviteCode") or "").strip()
    except Exception as e:
        logger.error(f"get_invite_code exception: {e}")
        return ""


def get_invite_history(account: dict, page: int = 1, size: int = 20) -> dict:
    """获取账号的邀请历史 (GET /oreate/activity/getinvitehistory)"""
    session = _make_session(account)
    try:
        resp = session.get(
            f"{OREATE_API_BASE}/oreate/activity/getinvitehistory",
            params={"pn": page, "rn": size},
            timeout=30,
        )
        if resp.status_code != 200:
            return {"list": [], "total": 0}
        data = resp.json() if resp.text else {}
        d = data.get("data") or {}
        return {"list": d.get("inviteHistoryList") or [], "total": int(d.get("total") or 0)}
    except Exception as e:
        logger.error(f"get_invite_history exception: {e}")
        return {"list": [], "total": 0}


def _get_rest_points_with_session(session: requests.Session) -> int:
    try:
        resp = session.get(f"{OREATE_API_BASE}/bizapi/point/getrestpoints", timeout=30)
        if resp.status_code != 200:
            return -1
        data = resp.json() if resp.text else {}
        return int((data.get("data") or {}).get("restPoint") or 0)
    except Exception as e:
        logger.error(f"get_rest_points exception: {e}")
        return -1


def get_rest_points(account: dict) -> int:
    """获取账号剩余积分 (GET /bizapi/point/getrestpoints)"""
    session = _make_session(account)
    try:
        return _get_rest_points_with_session(session)
    finally:
        try:
            session.close()
        except Exception:
            pass


def fetch_account_remote_info(account: dict) -> dict:
    """Probe an OreateAI account without using ChatGPT/OpenAI token APIs."""
    session = _make_session(account)
    try:
        resp = session.get(f"{OREATE_API_BASE}/oreate/user/getuserinfo", timeout=30)
        if resp.status_code in (401, 403):
            raise OreateAuthError(f"oreate user info auth failed: HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise RuntimeError(f"oreate user info failed: HTTP {resp.status_code}")

        data = resp.json() if resp.text else {}
        status = data.get("status") if isinstance(data, dict) else {}
        status = status if isinstance(status, dict) else {}
        code = status.get("code")
        if code not in (0, None):
            msg = str(status.get("msg") or status.get("message") or "")
            if str(code) in {"401", "403"} or "login" in msg.lower() or "auth" in msg.lower():
                raise OreateAuthError(f"oreate user info auth failed: code={code}, msg={msg}")
            raise RuntimeError(f"oreate user info failed: code={code}, msg={msg}")

        points = _get_rest_points_with_session(session)
        user = data.get("data") if isinstance(data, dict) else {}
        user = user if isinstance(user, dict) else {}
        result = {
            "status": "正常",
            "source_type": "oreateai",
            "image_quota_unknown": points < 0,
        }
        if points >= 0:
            result["quota"] = points
        email = str(user.get("email") or account.get("email") or "").strip()
        if email:
            result["email"] = email
        user_id = str(user.get("id") or user.get("userId") or user.get("user_id") or "").strip()
        if user_id:
            result["user_id"] = user_id
        return result
    finally:
        try:
            session.close()
        except Exception:
            pass


def chat_completion(
    messages: list[dict],
    model: str = "oreate-chat",
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    top_p: float = 1.0,
    stop: list[str] | None = None,
    user: str | None = None,
    **kwargs,
) -> dict:
    account = _pick_account()
    session = _make_session(account)

    payload = {
        "messages": messages,
        "model": model,
        "stream": stream,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
    }
    if stop:
        payload["stop"] = stop
    if user:
        payload["user"] = user

    try:
        resp = session.post(
            f"{OREATE_API_BASE}/home/api/conversation/chat",
            json=payload,
            timeout=120,
        )
        if resp.status_code != 200:
            logger.error(f"OreateAI chat error: {resp.status_code} {resp.text[:500]}")
            return _error_response(resp.status_code, "Chat completion failed")

        data = resp.json() if resp.text else {}
        return _format_chat_response(data, model)
    except Exception as e:
        logger.error(f"OreateAI chat exception: {e}")
        return _error_response(500, str(e))


async def chat_completion_stream(
    messages: list[dict],
    model: str = "oreate-chat",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    top_p: float = 1.0,
    stop: list[str] | None = None,
    user: str | None = None,
    **kwargs,
) -> AsyncIterator[str]:
    account = _pick_account()
    session = _make_session(account)

    payload = {
        "messages": messages,
        "model": model,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
    }
    if stop:
        payload["stop"] = stop
    if user:
        payload["user"] = user

    try:
        resp = session.post(
            f"{OREATE_API_BASE}/home/api/conversation/chat",
            json=payload,
            timeout=300,
            stream=True,
        )
        if resp.status_code != 200:
            err = json.dumps(_error_response(resp.status_code, "Stream failed"))
            yield f"data: {err}\n\ndata: [DONE]\n\n"
            return

        for line in resp.iter_lines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(b"data: "):
                yield line.decode("utf-8") + "\n\n"

        yield "data: [DONE]\n\n"
    except Exception as e:
        err = json.dumps(_error_response(500, str(e)))
        yield f"data: {err}\n\ndata: [DONE]\n\n"


def image_generation(
    prompt: str,
    model: str = "nano-banana-2",
    n: int = 1,
    size: str = "1024x1024",
    response_format: str = "url",
    quality: str = "standard",
    style: str | None = None,
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    user: str | None = None,
    **kwargs,
) -> dict:
    _ensure_url_response_format(response_format)
    access_token = ""
    session = None
    success = False
    try:
        access_token, account = _acquire_generation_account()
        session = _make_session(account)

        if size and "x" in size and aspect_ratio == "1:1":
            w, h = size.split("x", 1)
            if w.isdigit() and h.isdigit():
                iw, ih = int(w), int(h)
                if iw > ih:
                    aspect_ratio = "16:9"
                elif iw < ih:
                    aspect_ratio = "9:16"

        if aspect_ratio not in OREATE_IMAGE_ASPECT_RATIOS:
            aspect_ratio = "1:1"
        if resolution not in OREATE_IMAGE_RESOLUTIONS:
            resolution = "1K"

        model_name = _resolve_image_model_name(model)
        img_config = {"modelName": model_name, "ratio": aspect_ratio, "resolution": resolution}
        if model_name == "Google Nano Banana":
            img_config["resolution"] = ""

        reference_values = kwargs.get("images") or kwargs.get("image") or kwargs.get("image_url") or []
        attachments = _build_oreate_attachments(session, reference_values)
        result = _run_generation_stream(
            session, "aiImage", prompt, "imageConfig", img_config, timeout=240, attachments=attachments
        )
        if result.get("error"):
            logger.error(f"OreateAI image gen error: {result['error']}")
            raise _generation_error(400, result["error"], "server_error", "generation_failed")
        urls = result.get("urls") or []
        if not urls:
            raise _generation_error(502, "Generation completed without image URL", "server_error", "empty_generation_result")
        success = True
        return {
            "created": int(time.time()),
            "data": [{"url": u, "revised_prompt": prompt} for u in urls[: max(1, n)]],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OreateAI image gen exception: {e}")
        raise _generation_error(502, str(e), "server_error", "generation_failed") from e
    finally:
        _mark_generation_result(access_token, success)
        _close_session(session)


def video_generation(
    prompt: str,
    model: str = "seedance-2.0-fast",
    n: int = 1,
    size: str = "1024x576",
    duration: int = 10,
    aspect_ratio: str = "16:9",
    resolution: str = "480P",
    response_format: str = "url",
    user: str | None = None,
    **kwargs,
) -> dict:
    _ensure_url_response_format(response_format)
    access_token = ""
    session = None
    success = False
    try:
        access_token, account = _acquire_generation_account()
        session = _make_session(account)

        model_configs = _fetch_video_model_configs(session)
        reference_image, attachments = _resolve_video_reference_image(session, _first_video_reference(kwargs))
        video_config = _build_video_config(
            model=model,
            size=size,
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            audio=kwargs.get("audio", False),
            image=reference_image,
            model_configs=model_configs,
        )

        result = _run_generation_stream(
            session, "aiVideo", prompt, "videoConfig", video_config, timeout=600, attachments=attachments
        )
        if result.get("error"):
            logger.error(f"OreateAI video gen error: {result['error']}")
            raise _generation_error(400, result["error"], "server_error", "generation_failed")
        urls = result.get("urls") or []
        if not urls:
            raise _generation_error(502, "Generation completed without video URL", "server_error", "empty_generation_result")
        success = True
        return {
            "created": int(time.time()),
            "data": [{"url": u} for u in urls[: max(1, n)]],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OreateAI video gen exception: {e}")
        raise _generation_error(502, str(e), "server_error", "generation_failed") from e
    finally:
        _mark_generation_result(access_token, success)
        _close_session(session)


def list_models() -> dict:
    all_models = []
    for category in ("image", "video"):
        models = OREATE_MODELS.get(category, [])
        all_models.extend(models)
    return {
        "object": "list",
        "data": all_models,
    }


def _format_chat_response(data: dict, model: str) -> dict:
    if not data:
        return _error_response(500, "Empty response")

    choices = data.get("choices") or []
    if not choices and data.get("content"):
        choices = [{"message": {"role": "assistant", "content": data["content"]}, "index": 0, "finish_reason": "stop"}]

    request_id = str(uuid.uuid4())
    return {
        "id": f"chatcmpl-{request_id[:29]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": choices if choices else [
            {
                "index": 0,
                "message": {"role": "assistant", "content": data.get("content", "")},
                "finish_reason": "stop",
            }
        ],
        "usage": data.get("usage", {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }),
    }


def _error_response(status_code: int, message: str) -> dict:
    return {
        "error": {
            "message": message,
            "type": "server_error",
            "code": str(status_code),
        },
    }
