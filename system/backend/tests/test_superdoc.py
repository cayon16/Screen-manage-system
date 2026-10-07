import httpx
import pytest

from app.superdoc.base import ChatContext, SuperdocError, Turn, normalize_history
from app.superdoc.gemini_provider import GeminiSuperdocProvider
from app.superdoc.mock_provider import MockSuperdocProvider

CTX = ChatContext(session_id="phien-1", screen_id=2, system_prompt="Bạn là Superdoc thử nghiệm.")


# ---------- provider mac dinh (chay offline) ----------


async def test_mock_provider_answers_by_keyword():
    provider = MockSuperdocProvider(latency_sec=0)
    answer = await provider.reply([Turn(role="user", text="Bệnh viện mấy giờ mở cửa?")], CTX)
    assert "07:00" in answer


async def test_mock_provider_refuses_to_give_medical_advice():
    # Man hinh dat o hanh lang benh vien — tuyet doi khong duoc chan doan hay ke thuoc.
    provider = MockSuperdocProvider(latency_sec=0)
    answer = await provider.reply([Turn(role="user", text="Tôi bị đau bụng thì uống thuốc gì?")], CTX)
    assert "không thể chẩn đoán" in answer.lower()


async def test_mock_provider_rejects_empty_history():
    with pytest.raises(SuperdocError):
        await MockSuperdocProvider(latency_sec=0).reply([], CTX)


async def test_every_provider_implements_the_end_session_hook():
    # descryption.txt muc 3 yeu cau API bao cho AI biet doan chat da ket thuc. Provider hien tai
    # deu stateless nen day la no-op, nhung giao dien phai co san de provider Superdoc that
    # chi can dien vao, khong phai sua ChatSession.
    await MockSuperdocProvider(latency_sec=0).end_session(CTX, "user_exit")

    gemini = GeminiSuperdocProvider(api_key="khoa-gia", model="gemini-test")
    await gemini.end_session(CTX, "user_exit")
    await gemini.aclose()


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
        [Turn(role="user", text="Mấy giờ?"), Turn(role="assistant", text="7h"), Turn(role="user", text="Chắc chứ?")],
        CTX,
    )
    await provider.aclose()

    assert answer == "Bệnh viện mở cửa 7 giờ."
    assert "gemini-test:generateContent" in captured["url"]
    assert captured["key"] == "khoa-gia"
    # Gemini goi vai tro cua AI la "model", khong phai "assistant" nhu ten dung noi bo.
    assert [c["role"] for c in captured["body"]["contents"]] == ["user", "model", "user"]
    assert captured["body"]["system_instruction"]["parts"][0]["text"] == CTX.system_prompt


async def test_gemini_http_error_becomes_superdoc_error():
    provider = _provider_with_transport(lambda request: httpx.Response(429, json={"error": "quota"}))
    with pytest.raises(SuperdocError, match="429"):
        await provider.reply([Turn(role="user", text="Xin chào")], CTX)
    await provider.aclose()


async def test_gemini_blocked_response_becomes_superdoc_error():
    # Bi bo loc an toan chan -> co candidates nhung khong co text nao.
    provider = _provider_with_transport(
        lambda request: httpx.Response(200, json={"candidates": [{"finishReason": "SAFETY"}]})
    )
    with pytest.raises(SuperdocError):
        await provider.reply([Turn(role="user", text="Xin chào")], CTX)
    await provider.aclose()


async def test_gemini_network_failure_becomes_superdoc_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("mat mang", request=request)

    provider = _provider_with_transport(handler)
    with pytest.raises(SuperdocError, match="ConnectError"):
        await provider.reply([Turn(role="user", text="Xin chào")], CTX)
    await provider.aclose()


async def test_gemini_errors_carry_a_code_for_the_status_panel():
    provider = _provider_with_transport(lambda request: httpx.Response(429, json={"error": "quota"}))
    with pytest.raises(SuperdocError) as info:
        await provider.reply([Turn(role="user", text="Xin chào")], CTX)
    assert info.value.code == "http_429"
    await provider.aclose()

    provider = _provider_with_transport(
        lambda request: httpx.Response(200, json={"candidates": [{"finishReason": "SAFETY"}]})
    )
    with pytest.raises(SuperdocError) as info:
        await provider.reply([Turn(role="user", text="Xin chào")], CTX)
    assert info.value.code == "filtered"
    await provider.aclose()


# ---------- chuan hoa lich su ----------


def test_normalize_history_merges_consecutive_turns_of_the_same_role():
    # AI loi -> nguoi dung hoi tiep: lich su co 2 luot user lien nhau, nha cung cap khong chap nhan.
    turns = normalize_history([Turn("user", "Câu 1"), Turn("user", "Câu 2"), Turn("assistant", "Trả lời")])
    assert [(t.role, t.text) for t in turns] == [("user", "Câu 1" + chr(10) + "Câu 2"), ("assistant", "Trả lời")]


def test_normalize_history_drops_empty_turns_and_a_leading_assistant_turn():
    # Cat bot lich su cu co the de lai cau tra loi cua AI o dau.
    turns = normalize_history([Turn("assistant", "Cũ"), Turn("user", "   "), Turn("user", "Hỏi")])
    assert [(t.role, t.text) for t in turns] == [("user", "Hỏi")]
