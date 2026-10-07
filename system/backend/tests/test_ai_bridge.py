import json

import httpx
import pytest

from app.superdoc.base import ChatContext, SuperdocError, Turn
from app.superdoc.bridge_provider import BridgeProvider
from app.superdoc.bridge_reference import create_app

CTX = ChatContext(session_id="9b2f0c11", screen_id=4, system_prompt="Bạn là Superdoc thử nghiệm.")
HOI = [Turn(role="user", text="Bệnh viện mấy giờ mở cửa?")]


def _with_transport(provider: BridgeProvider, transport) -> BridgeProvider:
    """Thay duong mang that bang duong mang gia, GIU nguyen header (token) da cau hinh."""
    provider._client = httpx.AsyncClient(transport=transport, headers=provider._client.headers, timeout=5)
    return provider


def _against_reference(token: str | None = None, client_token: str | None = None):
    app = create_app(token=token, latency_sec=0)
    provider = BridgeProvider(base_url="http://bridge.test", token=client_token, timeout_sec=5)
    return app, _with_transport(provider, httpx.ASGITransport(app=app))


def _with_handler(handler) -> BridgeProvider:
    provider = BridgeProvider(base_url="http://bridge.test", token="tok", timeout_sec=5)
    return _with_transport(provider, httpx.MockTransport(handler))


# ---------- hop dong voi may chu mau that (trong tien trinh) ----------


async def test_bridge_round_trip_against_the_reference_server():
    app, provider = _against_reference()
    answer = await provider.reply(HOI, CTX)
    await provider.aclose()
    assert "07:00" in answer
    assert app.state.received == 1


async def test_bridge_end_session_reaches_the_server_with_the_reason():
    app, provider = _against_reference()
    await provider.end_session(CTX, "tier1_timeout")
    await provider.aclose()
    assert app.state.ended == [("9b2f0c11", "tier1_timeout")]


async def test_bridge_wrong_token_is_refused_and_right_token_is_accepted():
    _, provider = _against_reference(token="bi-mat", client_token="sai")
    with pytest.raises(SuperdocError) as info:
        await provider.reply(HOI, CTX)
    assert info.value.code == "http_401"
    await provider.aclose()

    _, provider = _against_reference(token="bi-mat", client_token="bi-mat")
    assert await provider.reply(HOI, CTX)
    await provider.aclose()


async def test_bridge_server_complaint_is_shown_to_the_operator():
    # Lich su ket thuc bang luot assistant -> may chu mau tra 422 kem ly do trong phong bi loi.
    _, provider = _against_reference()
    with pytest.raises(SuperdocError) as info:
        await provider.reply([Turn("user", "Hỏi"), Turn("assistant", "Đáp")], CTX)
    assert info.value.code == "http_422"
    assert "Lượt cuối cùng" in str(info.value)
    await provider.aclose()


# ---------- hinh dang request / xu ly phan hoi ----------


async def test_bridge_request_shape_matches_the_published_standard():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"reply": "Xin chào"})

    provider = _with_handler(handler)
    await provider.reply([Turn("user", "A"), Turn("assistant", "B"), Turn("user", "C")], CTX)
    await provider.aclose()

    assert captured["url"] == "http://bridge.test/v1/chat"
    assert captured["headers"]["authorization"] == "Bearer tok"
    assert captured["headers"]["x-pentasync-bridge"] == "1"
    assert captured["body"] == {
        "session_id": "9b2f0c11",
        "screen": 4,
        "locale": "vi-VN",
        "system_prompt": CTX.system_prompt,
        "messages": [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
        ],
    }


async def test_bridge_sends_no_authorization_header_when_no_token_is_configured():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["has_auth"] = "authorization" in request.headers
        return httpx.Response(200, json={"reply": "ok"})

    provider = BridgeProvider(base_url="http://bridge.test", token=None, timeout_sec=5)
    await _with_transport(provider, httpx.MockTransport(handler)).reply(HOI, CTX)
    assert seen["has_auth"] is False
    await provider.aclose()


@pytest.mark.parametrize(
    ("body", "code"),
    [({"khong_co": 1}, "bad_response"), ({"reply": 5}, "bad_response"), (["x"], "bad_response"),
     ({"reply": "   "}, "empty_reply")],
)
async def test_bridge_unusable_answers_become_coded_errors(body, code):
    provider = _with_handler(lambda request: httpx.Response(200, json=body))
    with pytest.raises(SuperdocError) as info:
        await provider.reply(HOI, CTX)
    assert info.value.code == code
    await provider.aclose()


async def test_bridge_network_failure_and_timeout_are_told_apart():
    def refuse(request):
        raise httpx.ConnectError("mat mang", request=request)

    def too_slow(request):
        raise httpx.ReadTimeout("cham qua", request=request)

    for handler, code in ((refuse, "network"), (too_slow, "timeout")):
        provider = _with_handler(handler)
        with pytest.raises(SuperdocError) as info:
            await provider.reply(HOI, CTX)
        assert info.value.code == code
        await provider.aclose()


# ---------- ket thuc phien ----------


@pytest.mark.parametrize("status", [404, 405])
async def test_bridge_end_session_tolerates_bots_that_do_not_support_it(status):
    provider = _with_handler(lambda request: httpx.Response(status))
    await provider.end_session(CTX, "user_exit")  # khong nem loi
    await provider.aclose()


async def test_bridge_end_session_surfaces_real_failures():
    # ChatSession se nuot loi nay va ghi log; provider thi khong duoc giau no.
    provider = _with_handler(lambda request: httpx.Response(500))
    with pytest.raises(SuperdocError) as info:
        await provider.end_session(CTX, "user_exit")
    assert info.value.code == "http_500"
    await provider.aclose()


async def test_bridge_session_id_is_url_encoded_in_the_path():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.raw_path.decode()
        return httpx.Response(204)

    provider = _with_handler(handler)
    await provider.end_session(ChatContext("a/b c", 4, "p"), "user_exit")
    await provider.aclose()
    assert seen["path"] == "/v1/sessions/a%2Fb%20c/end"


async def test_bridge_health_endpoint_of_the_reference_server():
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://bridge.test") as client:
        response = await client.get("/v1/health")
    assert response.json() == {"status": "ok"}
