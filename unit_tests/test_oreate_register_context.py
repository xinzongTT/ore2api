from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from services.register import oreate_register


class _FakeSession:
    def __init__(self) -> None:
        self.cookies = SimpleNamespace(jar=[])

    def close(self) -> None:
        return None


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.status_code = 200
        self._payload = payload
        self.headers = {"content-type": "application/json"}
        self.text = ""
        self.url = "https://www.oreateai.com/passport/api/mock"

    def json(self) -> dict:
        return self._payload


class OreateRegisterContextTest(unittest.TestCase):
    def setUp(self) -> None:
        session_patcher = mock.patch.object(oreate_register, "create_session", return_value=_FakeSession())
        self.addCleanup(session_patcher.stop)
        session_patcher.start()

    def test_register_context_comes_from_register_url_query(self) -> None:
        registrar = oreate_register.OreateRegistrar(
            proxy="",
            register_url=(
                "https://www.oreateai.com/userlogin/register/zh"
                "?fr=inviteFriend&inviteCode=url-invite&fissionCode=fission-123"
            ),
        )

        self.assertEqual(registrar.register_context["fr"], "inviteFriend")
        self.assertEqual(registrar.register_context["invite_code"], "url-invite")
        self.assertEqual(registrar.register_context["fission_code"], "fission-123")
        self.assertEqual(
            registrar.register_context["referer"],
            "https://www.oreateai.com/userlogin/register/zh?fr=inviteFriend&inviteCode=url-invite&fissionCode=fission-123",
        )

    def test_default_register_context_keeps_plain_register_referer(self) -> None:
        registrar = oreate_register.OreateRegistrar(proxy="")

        self.assertEqual(registrar.register_context["fr"], "main")
        self.assertEqual(registrar.register_context["referer"], "https://www.oreateai.com/userlogin/register")

    def test_register_context_with_invite_code_forces_invite_friend_fr(self) -> None:
        registrar = oreate_register.OreateRegistrar(
            proxy="",
            register_url="https://www.oreateai.com/userlogin/register/zh?inviteCode=url-invite",
        )

        self.assertEqual(registrar.register_context["fr"], "inviteFriend")
        self.assertEqual(
            registrar.register_context["referer"],
            "https://www.oreateai.com/userlogin/register/zh?fr=inviteFriend&inviteCode=url-invite",
        )

    def test_signup_payload_preserves_legacy_fields_and_uses_register_url_referer(self) -> None:
        request_calls: list[dict] = []

        def _fake_request(session, method: str, url: str, retry_attempts: int = 3, **kwargs):
            request_calls.append({"method": method, "url": url, **kwargs})
            return _FakeResponse({"status": {"code": 0}, "data": {"sendEmailCount": 1}}), ""

        registrar = oreate_register.OreateRegistrar(
            proxy="",
            register_url=(
                "https://www.oreateai.com/userlogin/register/zh"
                "?fr=inviteFriend&inviteCode=url-invite&fissionCode=fission-123"
            ),
        )

        with mock.patch.object(oreate_register, "_rsa_encrypt", return_value="encpwd"), mock.patch.object(
            registrar, "_get_ticket", return_value=("ticket-1", "pk-1")
        ), mock.patch.object(oreate_register, "request_with_local_retry", side_effect=_fake_request):
            ticket_id, encrypted_pwd = registrar._register_email("demo@example.com", "Password1@", 1)

        self.assertEqual(ticket_id, "ticket-1")
        self.assertEqual(encrypted_pwd, "encpwd")
        self.assertEqual(len(request_calls), 1)
        self.assertEqual(
            request_calls[0]["json"],
            {
                "email": "demo@example.com",
                "ticketID": "ticket-1",
                "password": "encpwd",
                "jt": "1",
                "plat": "wap",
                "fr": "inviteFriend",
                "inviteCode": "url-invite",
                "fissionCode": "fission-123",
            },
        )
        self.assertEqual(
            request_calls[0]["headers"]["referer"],
            "https://www.oreateai.com/userlogin/register/zh?fr=inviteFriend&inviteCode=url-invite&fissionCode=fission-123",
        )

    def test_default_signup_and_confirm_payload_use_string_jt(self) -> None:
        signup_calls: list[dict] = []
        confirm_calls: list[dict] = []

        def _fake_signup(session, method: str, url: str, retry_attempts: int = 3, **kwargs):
            signup_calls.append({"method": method, "url": url, **kwargs})
            return _FakeResponse({"status": {"code": 0}, "data": {"sendEmailCount": 1}}), ""

        def _fake_confirm(session, method: str, url: str, retry_attempts: int = 3, **kwargs):
            confirm_calls.append({"method": method, "url": url, **kwargs})
            return _FakeResponse({"status": {"code": 0}, "data": {"isLogin": True}}), ""

        registrar = oreate_register.OreateRegistrar(proxy="")
        registrar._password_plain = "Password1@"

        with mock.patch.object(oreate_register, "_rsa_encrypt", return_value="encpwd"), mock.patch.object(
            registrar, "_get_ticket", return_value=("ticket-1", "pk-1")
        ), mock.patch.object(oreate_register, "request_with_local_retry", side_effect=_fake_signup):
            registrar._register_email("demo@example.com", "Password1@", 1)

        with mock.patch.object(oreate_register, "_rsa_encrypt", return_value="enc-confirm"), mock.patch.object(
            registrar, "_get_ticket", return_value=("ticket-2", "pk-2")
        ), mock.patch.object(oreate_register, "request_with_local_retry", side_effect=_fake_confirm):
            confirmed = registrar._confirm_email("demo@example.com", "token-1", "old-ticket", "old-pwd", 1)

        self.assertTrue(confirmed)
        self.assertEqual(
            signup_calls[0]["json"],
            {
                "email": "demo@example.com",
                "ticketID": "ticket-1",
                "password": "encpwd",
                "jt": "1",
                "plat": "wap",
                "fr": "main",
            },
        )
        self.assertEqual(
            confirm_calls[0]["json"],
            {
                "email": "demo@example.com",
                "tokenID": "token-1",
                "ticketID": "ticket-2",
                "password": "enc-confirm",
                "jt": "1",
                "plat": "wap",
                "fr": "main",
            },
        )
        self.assertNotIn("inviteCode", signup_calls[0]["json"])
        self.assertNotIn("fissionCode", signup_calls[0]["json"])
        self.assertNotIn("inviteCode", confirm_calls[0]["json"])
        self.assertNotIn("fissionCode", confirm_calls[0]["json"])

    def test_confirm_payload_keeps_fission_code_and_overrides_invite_code(self) -> None:
        request_calls: list[dict] = []

        def _fake_request(session, method: str, url: str, retry_attempts: int = 3, **kwargs):
            request_calls.append({"method": method, "url": url, **kwargs})
            return _FakeResponse({"status": {"code": 0}, "data": {"isLogin": True}}), ""

        registrar = oreate_register.OreateRegistrar(
            proxy="",
            invite_code="pool-invite",
            register_url=(
                "https://www.oreateai.com/userlogin/register/zh"
                "?fr=main&inviteCode=url-invite&fissionCode=fission-123"
            ),
        )
        registrar._password_plain = "Password1@"

        with mock.patch.object(oreate_register, "_rsa_encrypt", return_value="enc-confirm"), mock.patch.object(
            registrar, "_get_ticket", return_value=("ticket-2", "pk-2")
        ), mock.patch.object(oreate_register, "request_with_local_retry", side_effect=_fake_request):
            confirmed = registrar._confirm_email("demo@example.com", "token-1", "old-ticket", "old-pwd", 1)

        self.assertTrue(confirmed)
        self.assertEqual(len(request_calls), 1)
        self.assertEqual(
            request_calls[0]["json"],
            {
                "email": "demo@example.com",
                "tokenID": "token-1",
                "ticketID": "ticket-2",
                "password": "enc-confirm",
                "jt": "1",
                "plat": "wap",
                "fr": "inviteFriend",
                "inviteCode": "pool-invite",
                "fissionCode": "fission-123",
            },
        )
        self.assertEqual(
            request_calls[0]["headers"]["referer"],
            "https://www.oreateai.com/userlogin/register/zh?fr=inviteFriend&inviteCode=pool-invite&fissionCode=fission-123",
        )

    def test_register_uses_fixed_requested_password(self) -> None:
        registrar = oreate_register.OreateRegistrar(proxy="")
        mailbox = {"address": "demo@example.com", "label": "test"}

        with mock.patch.object(oreate_register, "create_mailbox", return_value=mailbox), mock.patch.object(
            registrar, "_register_email", return_value=("ticket-1", "enc-pwd")
        ) as register_email, mock.patch.object(
            registrar, "_wait_and_confirm_email", return_value=True
        ), mock.patch.object(
            oreate_register.mail_provider, "mark_mailbox_result"
        ):
            result = registrar.register(1)

        self.assertEqual(result["password"], "Aa123132@")
        self.assertEqual(registrar._password_plain, "Aa123132@")
        register_email.assert_called_once_with("demo@example.com", "Aa123132@", 1)


if __name__ == "__main__":
    unittest.main()
