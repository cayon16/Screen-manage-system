import httpx
import pytest

from app.superdoc.base import SuperdocError, Turn
from app.superdoc.factory import build_provider
from app.superdoc.gemini_provider import GeminiSuperdocProvider
from app.superdoc.mock_provider import MockSuperdocProvider

# ---------- provider mac dinh (chay offline) ----------


async def test_mock_provider_answers_by_keyword():
    provider = MockSuperdocProvider(latency_sec=0)
    answer = await provider.reply([Turn(role="user", text="Bệnh viện mấy giờ mở cửa?")])
    assert "07:00" in answer


async def test_mock_provider_refuses_to_give_medical_advice():
    # Man hinh dat o hanh lang benh vien — tuyet doi khong duoc chan doan hay ke thuoc.
    provider = MockSuperdocProvider(latency_sec=0)
    answer = await provider.reply([Turn(role="user", text="Tôi bị đau bụng thì uống thuốc gì?")])
    assert "không thể chẩn đoán" in answer.lower()


async def test_mock_provider_rejects_empty_history():
    with pytest.raises(SuperdocError):
        await MockSuperdocProvider(latency_sec=0).reply([])


async def test_every_provider_implements_the_end_session_hook():
    # descryption.txt muc 3 yeu cau API bao cho AI biet doan chat da ket thuc. Provider hien tai
    # deu stateless nen day la no-op, nhung giao dien phai co san de provider Superdoc that
    # chi can dien vao, khong phai sua ChatSession.
    await MockSuperdocProvider(latency_sec=0).end_session("phien-bat-ky")

    gemini = GeminiSuperdocProvider(api_key="khoa-gia")
    await gemini.end_session("phien-bat-ky")
    await gemini.aclose()


# ---------- factory ----------


def test_factory_defaults_to_mock():
    assert build_provider("mock").name == "mock"


def test_factory_falls_back_to_mock_when_gemini_is_misconfigured(monkeypatch):
    # Thieu GEMINI_API_KEY khong duoc phep lam sap he thong man hinh cua benh vien.
    monkeypatch.setattr("app.superdoc.gemini_provider.GEMINI_API_KEY", "")
    assert build_provider("gemini").name == "mock"


def test_factory_falls_back_to_mock_for_unknown_name():
    assert build_provider("mot-provider-la-hoac").name == "mock"


# ---------- Gemini (khong cham mang that) ----------


def _provider_with_transport(handler) -> GeminiSuperdocProvider:
    provider = GeminiSuperdocProvider(api_key="khoa-gia", model="gemini-test")
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return provider


async def test_gemini_request_shape_and_answer_parsing():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["url"] = str(request.url)
        captured["key"] = request.headers.get("x-goog-api-key")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Bệnh viện mở cửa 7 giờ."}]}}]},
        )

    provider = _provider_with_transport(handler)
    answer = await provider.reply(
        [Turn(role="user", text="Mấy giờ?"), Turn(role="assistant", text="7h"), Turn(role="user", text="Chắc chứ?")]
    )
    await provider.aclose()

    assert answer == "Bệnh viện mở cửa 7 giờ."
    assert "gemini-test:generateContent" in captured["url"]
    assert captured["key"] == "khoa-gia"
    # Gemini goi vai tro cua AI la "model", khong phai "assistant" nhu ten dung noi bo.
    assert [c["role"] for c in captured["body"]["contents"]] == ["user", "model", "user"]
    assert captured["body"]["system_instruction"]["parts"][0]["text"]


async def test_gemini_http_error_becomes_superdoc_error():
    provider = _provider_with_transport(lambda request: httpx.Response(429, json={"error": "quota"}))
    with pytest.raises(SuperdocError, match="429"):
        await provider.reply([Turn(role="user", text="Xin chào")])
    await provider.aclose()


async def test_gemini_blocked_response_becomes_superdoc_error():
    # Bi bo loc an toan chan -> co candidates nhung khong co text nao.
    provider = _provider_with_transport(
        lambda request: httpx.Response(200, json={"candidates": [{"finishReason": "SAFETY"}]})
    )
    with pytest.raises(SuperdocError):
        await provider.reply([Turn(role="user", text="Xin chào")])
    await provider.aclose()


async def test_gemini_network_failure_becomes_superdoc_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("mat mang", request=request)

    provider = _provider_with_transport(handler)
    with pytest.raises(SuperdocError, match="ConnectError"):
        await provider.reply([Turn(role="user", text="Xin chào")])
    await provider.aclose()
