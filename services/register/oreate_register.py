from __future__ import annotations

import base64
import json
import random
import secrets
import string
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from curl_cffi import requests

from services.account_service import account_service
from services.json_file import read_json_object, write_json_file
from services.register import mail_provider
from utils.timezone import TIME_FORMAT, beijing_now_str

base_dir = Path(__file__).resolve().parent

OREATE_BASE = "https://www.oreateai.com"
OREATE_API_BASE = "https://www.oreateai.com"
OREATE_REGISTER_PATH = "/userlogin/register"
DEFAULT_REGISTER_URL = f"{OREATE_BASE}{OREATE_REGISTER_PATH}"
DEFAULT_REGISTER_PASSWORD = "Aa123132@"

config = {
    "mail": {
        "request_timeout": 30,
        "wait_timeout": 30,
        "wait_interval": 2,
        "api_use_register_proxy": True,
        "providers": [],
    },
    "proxy": "",
    "register_url": DEFAULT_REGISTER_URL,
    "total": 10,
    "threads": 3,
    # 邀请裂变积分设置
    "invite_enabled": False,       # 是否在注册时使用邀请码（触发双方 +100 积分）
    "invite_daily_limit": 1,       # 每个收集号每天可邀请次数（oreateai 规则=1）
}

# 邀请码每日使用记录: {invite_code: {"date": "2026-07-07", "count": N}}
_invite_usage: dict[str, dict] = {}
_invite_lock = threading.Lock()

register_config_file = base_dir.parents[1] / "data" / "register.json"
try:
    saved_config = read_json_object(register_config_file, name="register.json")
    config.update(
        {
            key: saved_config[key]
            for key in ("mail", "proxy", "register_url", "total", "threads", "invite_enabled", "invite_daily_limit")
            if key in saved_config
        }
    )
except Exception:
    pass

REGISTER_BROWSER_PROFILES: tuple[dict[str, str], ...] = (
    {
        "impersonate": "chrome142",
        "major": "142",
        "full_version": "142.0.0.0",
        "platform_version": "10.0.0",
        "accept_language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
    {
        "impersonate": "chrome136",
        "major": "136",
        "full_version": "136.0.0.0",
        "platform_version": "10.0.0",
        "accept_language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
    {
        "impersonate": "chrome131",
        "major": "131",
        "full_version": "131.0.0.0",
        "platform_version": "10.0.0",
        "accept_language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
)


def _chrome_user_agent(major: str, full_version: str) -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{full_version} Safari/537.36"
    )


def _chrome_sec_ch_ua(major: str) -> str:
    return f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not_A Brand";v="99"'


def _chrome_sec_ch_ua_full_version_list(major: str, full_version: str) -> str:
    return (
        f'"Chromium";v="{full_version}", '
        f'"Google Chrome";v="{full_version}", '
        '"Not_A Brand";v="99.0.0.0"'
    )


def _complete_browser_fingerprint(profile: dict[str, str]) -> dict[str, str]:
    major = str(profile.get("major") or "142").strip()
    full_version = str(profile.get("full_version") or f"{major}.0.0.0").strip()
    return {
        **profile,
        "major": major,
        "full_version": full_version,
        "user_agent": str(profile.get("user_agent") or _chrome_user_agent(major, full_version)),
        "sec_ch_ua": str(profile.get("sec_ch_ua") or _chrome_sec_ch_ua(major)),
        "sec_ch_ua_full_version_list": str(
            profile.get("sec_ch_ua_full_version_list") or _chrome_sec_ch_ua_full_version_list(major, full_version)
        ),
        "accept_language": str(profile.get("accept_language") or "zh-CN,zh;q=0.9,en;q=0.8"),
        "platform_version": str(profile.get("platform_version") or "10.0.0"),
        "impersonate": str(profile.get("impersonate") or "chrome142"),
    }


DEFAULT_BROWSER_FINGERPRINT = _complete_browser_fingerprint(REGISTER_BROWSER_PROFILES[0])
user_agent = DEFAULT_BROWSER_FINGERPRINT["user_agent"]
sec_ch_ua = DEFAULT_BROWSER_FINGERPRINT["sec_ch_ua"]
sec_ch_ua_full_version_list = DEFAULT_BROWSER_FINGERPRINT["sec_ch_ua_full_version_list"]
default_timeout = 30
print_lock = threading.Lock()
stats_lock = threading.Lock()
stats = {"done": 0, "success": 0, "fail": 0, "start_time": 0.0}
register_log_sink = None

common_headers = {
    "accept": "application/json",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "connection": "keep-alive",
    "content-type": "application/json",
    "dnt": "1",
    "origin": OREATE_BASE,
    "sec-ch-ua": sec_ch_ua,
    "sec-ch-ua-arch": '"x86_64"',
    "sec-ch-ua-bitness": '"64"',
    "sec-ch-ua-full-version-list": sec_ch_ua_full_version_list,
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-model": '""',
    "sec-ch-ua-platform": '"Windows"',
    "sec-ch-ua-platform-version": '"10.0.0"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": user_agent,
}

navigate_headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "cache-control": "max-age=0",
    "connection": "keep-alive",
    "dnt": "1",
    "sec-ch-ua": sec_ch_ua,
    "sec-ch-ua-arch": '"x86_64"',
    "sec-ch-ua-bitness": '"64"',
    "sec-ch-ua-full-version-list": sec_ch_ua_full_version_list,
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-model": '""',
    "sec-ch-ua-platform": '"Windows"',
    "sec-ch-ua-platform-version": '"10.0.0"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": user_agent,
}


def _browser_fingerprint(fingerprint: dict[str, str] | None = None) -> dict[str, str]:
    return _complete_browser_fingerprint(fingerprint or DEFAULT_BROWSER_FINGERPRINT)


def _make_browser_fingerprint() -> dict[str, str]:
    return _complete_browser_fingerprint(secrets.choice(REGISTER_BROWSER_PROFILES))


def log(text: str, color: str = "") -> None:
    colors = {"red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m"}
    if register_log_sink:
        try:
            register_log_sink(text, color)
        except Exception:
            pass
    with print_lock:
        prefix = colors.get(color, "")
        suffix = "\033[0m" if prefix else ""
        print(f"{prefix}{beijing_now_str(TIME_FORMAT)} {text}{suffix}")


def step(index: int, text: str, color: str = "") -> None:
    log(f"[任务{index}] {text}", color)


def _rsa_encrypt(password: str, public_key_pem: str) -> str:
    """用 OreateAI 提供的 RSA 公钥加密密码（PKCS1 v1.5，与前端 JSEncrypt 一致）

    OreateAI 的 getticket 返回 -----BEGIN RSA PUBLIC KEY----- 格式（PKCS#1）。
    cryptography >= 3.x 可直接通过 load_pem_public_key 加载此格式。
    """
    try:
        from cryptography.hazmat.primitives.asymmetric import padding as _padding
        from cryptography.hazmat.primitives.serialization import load_pem_public_key as _load_pem
        pk = str(public_key_pem or "").strip()
        if not pk.startswith("-----"):
            # 无头部的裸 base64，包装为 SubjectPublicKeyInfo
            pk = f"-----BEGIN PUBLIC KEY-----\n{pk}\n-----END PUBLIC KEY-----"
        try:
            key = _load_pem(pk.encode())
        except Exception:
            # PKCS#1 → SPKI 转换（使用 load_der_public_key）
            import base64 as _b64
            from cryptography.hazmat.primitives.serialization import load_der_public_key as _load_der
            # 提取 DER
            b64 = "".join(pk.split("\n")[1:-1])
            pkcs1_der = _b64.b64decode(b64)
            # RSA SPKI header (algorithm: rsaEncryption, NULL params)
            spki_header = bytes.fromhex("30820122300d06092a864886f70d01010105000382010f00")
            # 如果是 1024-bit
            if len(pkcs1_der) < 160:
                spki_header = bytes.fromhex("30819f300d06092a864886f70d0101010500038181")
                spki_header += b'\x00'
            else:
                spki_header = bytes.fromhex("30820122300d06092a864886f70d01010105000382010f00")
            spki_der = spki_header + pkcs1_der
            key = _load_der(spki_der)
        encrypted = key.encrypt(password.encode("utf-8"), _padding.PKCS1v15())
        return base64.b64encode(encrypted).decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"RSA 密码加密失败: {e}")


def _random_password(length: int = 12) -> str:
    # OreateAI 密码规则: 8-16位，含数字、字母、特殊字符 @#$%^&*
    special = "@#$%^&*"
    chars = string.ascii_letters + string.digits + special
    value = list(
        secrets.choice(string.ascii_uppercase)
        + secrets.choice(string.ascii_lowercase)
        + secrets.choice(string.digits)
        + secrets.choice(special)
        + "".join(secrets.choice(chars) for _ in range(max(0, length - 4)))
    )
    random.shuffle(value)
    return "".join(value)


def _random_name() -> tuple[str, str]:
    return random.choice(["张", "王", "李", "刘", "陈", "杨", "赵", "黄"]), random.choice(["伟", "芳", "建国", "丽", "敏", "静", "强", "明", "华"])


def _random_phone() -> str:
    prefixes = ["130", "131", "132", "133", "134", "135", "136", "137", "138", "139",
                "150", "151", "152", "153", "155", "156", "157", "158", "159",
                "180", "181", "182", "183", "184", "185", "186", "187", "188", "189"]
    return random.choice(prefixes) + "".join(str(random.randint(0, 9)) for _ in range(8))


def _response_json(resp) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _response_debug_detail(resp, limit: int = 800) -> str:
    if resp is None:
        return ""
    data = _response_json(resp)
    parts = [
        f"url={str(getattr(resp, 'url', '') or '')[:300]}",
        f"content_type={str(getattr(resp, 'headers', {}).get('content-type') or '')}",
    ]
    if data:
        parts.append(f"json={json.dumps(data, ensure_ascii=False)[:limit]}")
    else:
        parts.append(f"body={str(getattr(resp, 'text', '') or '')[:limit]}")
    return ", ".join(parts)


def _truthy(value: object, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return fallback


def _normalize_register_url(register_url: str = "") -> str:
    raw = str(register_url or "").strip()
    if not raw:
        return DEFAULT_REGISTER_URL
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        return urlunparse(parsed._replace(fragment=""))
    if raw.startswith("?"):
        return f"{DEFAULT_REGISTER_URL}{raw}"
    if raw.startswith("/"):
        return f"{OREATE_BASE}{raw}"
    return DEFAULT_REGISTER_URL


def _build_register_context(register_url: str = "", invite_code: str = "") -> dict[str, str]:
    normalized_url = _normalize_register_url(register_url)
    parsed = urlparse(normalized_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=False))

    explicit_invite_code = str(invite_code or "").strip()
    query_invite_code = str(query.get("inviteCode") or "").strip()
    final_invite_code = explicit_invite_code or query_invite_code

    query_fr = str(query.get("fr") or "").strip()
    fr = query_fr or "main"
    if final_invite_code:
        fr = "inviteFriend"

    fission_code = str(query.get("fissionCode") or "").strip()
    referer_query: list[tuple[str, str]] = []
    if query_fr or final_invite_code:
        referer_query.append(("fr", fr))
    if final_invite_code:
        referer_query.append(("inviteCode", final_invite_code))
    if fission_code:
        referer_query.append(("fissionCode", fission_code))
    referer = urlunparse(parsed._replace(query=urlencode(referer_query), fragment=""))

    return {
        "register_url": normalized_url,
        "referer": referer,
        "fr": fr,
        "invite_code": final_invite_code,
        "fission_code": fission_code,
    }


def _mail_config(register_proxy: str = "") -> dict:
    mail = config["mail"] if isinstance(config.get("mail"), dict) else {}
    use_register_proxy = _truthy(mail.get("api_use_register_proxy"), True)
    proxy = str(register_proxy or "").strip() if use_register_proxy else ""
    return {**mail, "api_use_register_proxy": use_register_proxy, "proxy": proxy}


def create_mailbox(username: str | None = None, register_proxy: str = "") -> dict:
    return mail_provider.create_mailbox(_mail_config(register_proxy), username)


def wait_for_code(mailbox: dict, register_proxy: str = "") -> str | None:
    return mail_provider.wait_for_code(_mail_config(register_proxy), mailbox)


def _fetch_latest_message_raw(mailbox: dict, mail_config: dict) -> str:
    """直接从 YYDS Mail provider 获取最新邮件的完整文本（html+text），用于提取 tokenID"""
    from services.register.mail_provider import _create_provider, _entries
    entries = [e for e in _entries(mail_config) if e.get("enable")]
    if not entries:
        return ""
    provider_name = str(mailbox.get("provider") or "")
    provider_ref = str(mailbox.get("provider_ref") or "")
    provider = _create_provider(mail_config, provider_name, provider_ref)
    try:
        msg = provider.fetch_latest_message(mailbox)
        if not msg:
            return ""
        html = msg.get("html_content") or msg.get("html") or ""
        text = msg.get("text_content") or msg.get("text") or ""
        if isinstance(html, list):
            html = "".join(html)
        if isinstance(text, list):
            text = "".join(text)
        return html + text
    except Exception:
        return ""
    finally:
        provider.close()


def _safe_impersonate(preferred: str) -> str:
    """确保 impersonate 目标被当前 curl_cffi 支持（0.13 不支持 chrome142）。

    curl_cffi 构造 Session 不报错，只有发请求时才抛 ImpersonateError，
    故这里对不确定的高版本主动探测，失败则回退到稳定版本。
    """
    preferred = str(preferred or "").strip() or "chrome131"
    global _IMPERSONATE_CACHE
    try:
        return _IMPERSONATE_CACHE  # 已探测过
    except NameError:
        pass
    candidates = [preferred, "chrome136", "chrome131", "chrome124", "chrome120", "chrome116"]
    for cand in candidates:
        try:
            s = requests.Session(impersonate=cand)
            try:
                s.get("http://127.0.0.1:1/", timeout=1)
            except Exception as e:
                if "not supported" in str(e).lower():
                    continue
            # 连接失败但指纹被接受
            _IMPERSONATE_CACHE = cand
            return cand
        except Exception:
            continue
    _IMPERSONATE_CACHE = "chrome131"
    return "chrome131"


def create_session(proxy: str = "", fingerprint: dict[str, str] | None = None) -> Any:
    fp = _browser_fingerprint(fingerprint)
    session = requests.Session(impersonate=_safe_impersonate(fp["impersonate"]))
    session.headers.update({"user-agent": fp["user_agent"]})
    proxy = str(proxy or "").strip()
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    return session


def request_with_local_retry(session: requests.Session, method: str, url: str, retry_attempts: int = 3, **kwargs):
    last_error = ""
    for _ in range(max(1, retry_attempts)):
        try:
            return session.request(method.upper(), url, timeout=default_timeout, **kwargs), ""
        except Exception as error:
            last_error = str(error)
            time.sleep(1)
    return None, last_error


class OreateRegistrar:
    """OreateAI 注册器 - 模拟网页注册流程

    认证方式: Cookie JWT (ics_vsid + ouss), 不是 Bearer token
    """

    def __init__(self, proxy: str = "", invite_code: str = "", register_url: str = "") -> None:
        self.proxy = str(proxy or "").strip()
        self.invite_code = str(invite_code or "").strip()  # 邀请码，触发双方 +100 积分
        self.register_context = _build_register_context(register_url or str(config.get("register_url") or ""), self.invite_code)
        self.fingerprint = _make_browser_fingerprint()
        self.session = create_session(self.proxy, self.fingerprint)
        self.access_token = ""
        self.refresh_token = ""
        self.ics_vsid = ""
        self.ouss = ""
        self.cookies = {}
        self._password_plain = ""

    @property
    def register_referer(self) -> str:
        return str(self.register_context.get("referer") or DEFAULT_REGISTER_URL)

    def _js_token(self) -> str:
        # 前端 axios 拦截器：payload 含 jt 时会替换为 banti jsToken 字符串。
        # 上游校验 jt 必须是非空字符串；布尔 true / 空串会返回 code=100002 Invalid parameter。
        return "1"

    def _register_context_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jt": self._js_token(),
            "fr": str(self.register_context.get("fr") or "main"),
            "plat": "wap",
        }
        invite_code = str(self.register_context.get("invite_code") or "").strip()
        fission_code = str(self.register_context.get("fission_code") or "").strip()
        if invite_code:
            payload["inviteCode"] = invite_code
        if fission_code:
            payload["fissionCode"] = fission_code
        return payload

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def _save_cookies(self) -> None:
        """从 session 提取认证 cookie"""
        for cookie in self.session.cookies.jar:
            try:
                name = str(cookie.name)
                if name in ("ics_vsid", "ouss"):
                    setattr(self, name, str(cookie.value))
                self.cookies[name] = str(cookie.value)
            except Exception:
                continue
        if self.ics_vsid:
            self.access_token = self.ics_vsid  # 兼容旧字段

    def _get_ticket(self, index: int) -> tuple[str, str]:
        """获取注册 ticket 和 RSA 公钥 (GET /passport/api/getticket)

        通过代理访问 oreateai 偶发 TLS 握手返回空，做多轮带退避的重试。
        """
        step(index, "获取注册 ticket")
        last_err = ""
        for attempt in range(5):
            resp, error = request_with_local_retry(
                self.session,
                "get",
                f"{OREATE_API_BASE}/passport/api/getticket",
                retry_attempts=2,
                headers={**common_headers, "referer": self.register_referer},
            )
            if resp is not None and resp.status_code == 200 and resp.text:
                break
            last_err = error or _response_debug_detail(resp) or "空响应"
            time.sleep(1.5 * (attempt + 1))
        else:
            raise RuntimeError(f"getticket 失败（重试5轮）: {last_err}")
        data = _response_json(resp)
        ticket_id = str((data.get("data") or {}).get("ticketID") or "").strip()
        pk = str((data.get("data") or {}).get("pk") or "").strip()
        if not ticket_id or not pk:
            raise RuntimeError(f"getticket 返回无效: {json.dumps(data)[:200]}")
        step(index, f"ticket 获取成功: {ticket_id[:8]}...")
        return ticket_id, pk

    def _register_email(self, email: str, password_raw: str, index: int) -> tuple[str, str]:
        """邮箱注册 (POST /passport/api/emailsignupin)

        流程（浏览器抓包 + JS 逆向确认）：
        1. GET /passport/api/getticket → {ticketID, pk}
        2. RSA-PKCS1v15 加密密码
        3. POST /passport/api/emailsignupin {email, ticketID, password}
           → 平台发验证邮件到 email

        返回: (ticket_id, encrypted_pwd)
        """
        step(index, "开始 OreateAI 邮箱注册")
        ticket_id, pk = self._get_ticket(index)
        encrypted_pwd = _rsa_encrypt(password_raw, pk)
        context_invite = str(self.register_context.get("invite_code") or "").strip()
        if context_invite:
            step(index, f"使用邀请码: {context_invite[:16]}...（成功后双方 +100 积分）")
        # 与前端 mke()/createAccount 对齐：jt 必须是非空字符串，并带 fr/plat。
        # inviteCode/fissionCode 可在 signup 出现，但邀请绑定仍以 confirm 为准。
        payload = {
            "email": email,
            "ticketID": ticket_id,
            "password": encrypted_pwd,
            **self._register_context_payload(),
        }
        resp, error = request_with_local_retry(
            self.session, "post",
            f"{OREATE_API_BASE}/passport/api/emailsignupin",
            json=payload,
            headers={**common_headers, "referer": self.register_referer},
        )
        if resp is None or resp.status_code not in (200, 201):
            raise RuntimeError(f"emailsignupin 失败: {_response_debug_detail(resp)}")
        data = _response_json(resp)
        status = (data.get("status") or {})
        if status.get("code") not in (0, None):
            raise RuntimeError(f"注册失败: code={status.get('code')}, msg={status.get('msg')}")
        send_count = (data.get("data") or {}).get("sendEmailCount", 0)
        step(index, f"注册成功，验证邮件已发送 (sendEmailCount={send_count})")
        return ticket_id, encrypted_pwd

    def _wait_and_confirm_email(
        self,
        email: str,
        ticket_id: str,
        encrypted_pwd: str,
        mailbox: dict,
        index: int,
        timeout: int = 120,
        interval: int = 3,
    ) -> bool:
        """等待验证邮件并调用 emailregisterconfirm 完成验证

        JS 逆向确认（index-CpcStoMO.js，函数 pke / vs）：
          POST /passport/api/emailregisterconfirm
          { email, tokenID, ticketID, password(RSA加密), jt(非空字符串), fr, plat, inviteCode, fissionCode }
        tokenID 来自验证邮件链接:
          https://oreateai.com/userlogin/register?email=X&tokenID={UUID}
        """
        import re as _re
        step(index, f"等待验证邮件 (最多 {timeout}s)...")
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = _fetch_latest_message_raw(mailbox, _mail_config(self.proxy))
            if raw:
                token_match = _re.search(r'tokenID=([0-9a-f-]{30,})', raw)
                if token_match:
                    token_id = token_match.group(1)
                    step(index, f"提取 tokenID: {token_id[:16]}...")
                    return self._confirm_email(email, token_id, ticket_id, encrypted_pwd, index)
            time.sleep(interval)
        step(index, "等待验证邮件超时", "yellow")
        return False

    def _confirm_email(
        self,
        email: str,
        token_id: str,
        ticket_id: str,
        encrypted_pwd: str,
        index: int,
    ) -> bool:
        """调用 emailregisterconfirm 完成邮箱验证并获取登录 Cookie

        端点: POST /passport/api/emailregisterconfirm
        参数: {email, tokenID, ticketID, password, plat, fr, fissionCode, inviteCode}

        JS 逆向（index-CpcStoMO.js 函数 pke/vs）真实 payload：
          v = {email, tokenID, plat:"wap", fr, fissionCode, inviteCode}
          fr/fissionCode/inviteCode 来自 URL query（Bh("...")）
        邀请链接格式：{origin}/userlogin/register?fr=inviteFriend&inviteCode={CODE}
        ★ 关键：邀请绑定发生在 confirm 这一步，必须带 fr="inviteFriend"+inviteCode，
          仅在 emailsignupin 传 inviteCode 不会记入邀请（之前失败原因）。

        实测（2026-07-07）：confirm 需独立新 ticket + 新 pk 重新加密密码。
        成功响应 {status:{code:0}, data:{isLogin:true}}，set-cookie ouss/ics_vsid。
        """
        step(index, "调用 emailregisterconfirm 完成验证")
        # confirm 需要独立的新 ticket + 用新 pk 重新加密同一密码
        confirm_ticket, confirm_pk = self._get_ticket(index)
        confirm_pwd = _rsa_encrypt(self._password_plain, confirm_pk)
        payload = {
            "email": email,
            "tokenID": token_id,
            "ticketID": confirm_ticket,
            "password": confirm_pwd,
            **self._register_context_payload(),
        }
        resp, error = request_with_local_retry(
            self.session, "post",
            f"{OREATE_API_BASE}/passport/api/emailregisterconfirm",
            json=payload,
            headers={**common_headers, "referer": self.register_referer},
        )
        if resp is None or resp.status_code not in (200, 201):
            step(index, f"emailregisterconfirm 失败: {_response_debug_detail(resp)}", "red")
            return False
        data = _response_json(resp)
        status = (data.get("status") or {})
        if status.get("code") not in (0, None):
            step(index, f"确认失败: code={status.get('code')}, msg={status.get('msg')}", "red")
            return False
        is_login = (data.get("data") or {}).get("isLogin")
        self._save_cookies()
        # 认证成功判据：拿到 ics_vsid 或 ouss Cookie，或 isLogin=True
        if self.ics_vsid or self.ouss or is_login:
            step(index, "邮箱验证成功，已获取登录态", "green")
            return True
        step(index, "emailregisterconfirm 返回成功但未获取到 Cookie", "yellow")
        return False


    def register(self, index: int) -> dict:
        step(index, "开始创建邮箱")
        mailbox = create_mailbox(register_proxy=self.proxy)
        email = str(mailbox.get("address") or "").strip()
        if not email:
            mail_provider.release_mailbox(mailbox)
            raise RuntimeError("邮箱服务未返回 address")
        label = str(mailbox.get("label") or "")
        step(index, f"邮箱创建完成[{label}]: {email}")

        try:
            password = DEFAULT_REGISTER_PASSWORD
            self._password_plain = password  # confirm 阶段需用新 pk 重新加密
            # 1. 注册：emailsignupin → 平台发验证邮件
            ticket_id, encrypted_pwd = self._register_email(email, password, index)
            # 2. 等待验证邮件 → 提取 tokenID → emailregisterconfirm
            confirmed = self._wait_and_confirm_email(
                email, ticket_id, encrypted_pwd, mailbox, index
            )
            if not confirmed:
                raise RuntimeError(
                    "邮箱验证未完成。可能原因：验证邮件未收到、"
                    "tokenID 提取失败或确认接口异常。"
                )
        except Exception as error:
            mail_provider.mark_mailbox_result(mailbox, success=False, error=error)
            raise
        mail_provider.mark_mailbox_result(mailbox, success=True)

        return {
            "email": email,
            "password": password,
            "access_token": self.ics_vsid or self.ouss,  # 认证用 Cookie（优先 ics_vsid）
            "refresh_token": self.refresh_token,
            "ics_vsid": self.ics_vsid,
            "ouss": self.ouss,
            "cookies": self.cookies,
            "source_type": "oreateai",
            "status": "正常",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


def _today_str() -> str:
    return beijing_now_str("%Y-%m-%d")


def _account_auth(acc: dict) -> str:
    """账号是否具备可用认证态（ics_vsid 或 ouss，含 cookies 兜底）。"""
    cookies = acc.get("cookies") or {}
    return (
        acc.get("ics_vsid") or acc.get("ouss")
        or cookies.get("ics_vsid") or cookies.get("ouss")
        or acc.get("access_token") or ""
    )


def _pick_invite_code() -> str:
    """从收集号池中选一个当天还有邀请额度的收集号，返回其邀请码。

    收集号 = account_service 中已注册的正常 oreateai 账号（有认证态即可）。
    每个收集号每天最多邀请 invite_daily_limit 次（oreateai 规则=1）。

    限额 key 用账号 email（邀请码带时间戳每次都变，不能做 key）。
    优先选最早注册、当天用得最少的收集号，让老号先被邀满。
    """
    if not config.get("invite_enabled"):
        return ""
    from services.oreate_backend_api import get_invite_code

    daily_limit = int(config.get("invite_daily_limit") or 1)
    today = _today_str()
    accounts = account_service.list_accounts()
    # 收集号：正常状态 + 有认证态 + 是 oreateai 号
    collectors = [
        a for a in accounts
        if a.get("status") == "正常"
        and str(a.get("source_type") or "") in ("oreateai", "")
        and _account_auth(a)
    ]
    # 稳定顺序：按创建时间升序（老号优先）
    collectors.sort(key=lambda a: str(a.get("created_at") or ""))

    with _invite_lock:
        for acc in collectors:
            email = str(acc.get("email") or "").strip()
            if not email:
                continue
            usage = _invite_usage.get(email)
            if usage is None or usage.get("date") != today:
                usage = {"date": today, "count": 0}
                _invite_usage[email] = usage
            if usage["count"] >= daily_limit:
                continue
            # 该号今天还有额度 → 取其邀请码
            code = get_invite_code(acc)
            if not code:
                continue
            usage["count"] += 1
            log(f"邀请码来自收集号 {email}（今日第 {usage['count']}/{daily_limit} 次邀请）", "yellow")
            return code
    return ""


def worker(index: int) -> dict:
    start = time.time()
    invite_code = _pick_invite_code()
    registrar = OreateRegistrar(config["proxy"], invite_code=invite_code, register_url=str(config.get("register_url") or ""))
    try:
        step(index, "任务启动" + (f"（带邀请码，双方 +100 积分）" if invite_code else ""))
        result = registrar.register(index)
        cost = time.time() - start
        access_token = str(result["access_token"])
        account_service.add_account_items([result])
        with stats_lock:
            stats["done"] += 1
            stats["success"] += 1
            avg = (time.time() - stats["start_time"]) / stats["success"]
        log(f'{result["email"]} 注册成功，本次耗时{cost:.1f}s，全局平均每个号注册耗时{avg:.1f}s', "green")
        return {"ok": True, "index": index, "result": result}
    except Exception as e:
        cost = time.time() - start
        with stats_lock:
            stats["done"] += 1
            stats["fail"] += 1
        log(f"任务{index} 注册失败，本次耗时{cost:.1f}s，原因: {e}", "red")
        return {"ok": False, "index": index, "error": str(e)}
    finally:
        registrar.close()
