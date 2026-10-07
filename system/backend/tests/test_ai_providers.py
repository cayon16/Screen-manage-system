import json

import httpx
import pytest

from app.superdoc.anthropic_provider import AnthropicProvider
from app.superdoc.base import ChatContext, SuperdocError, Turn
from app.superdoc.openai_provider import OpenAIProvider
from app.superdoc.unavailable_provider import UnavailableProvider

CTX = ChatContext(session_id="phien-1", screen_id=4, system_prompt="Bạn là Superdoc thử nghiệm.")
HOI = [Turn(role="user", text="Khoa cấp cứu ở đâu?")]


def _openai(handler, **kwargs) -> OpenAIProvider:
    kwargs.setdefault("base_url", "https://api.openai.com/v1")
    kwargs.setdefault("model", "gpt-test")
    kwargs.setdefault("api_key", "khoa-gia")
    provider = OpenAIProvider(**kwargs)
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return provider


def _anthropic(handler) -> AnthropicProvider:
    provider = AnthropicProvider(api_key="khoa-gia", model="claude-test")
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return provider


def _chat_ok(text: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]}


# ---------- OpenAI / chuan OpenAI ----------


async def test_openai_request_shape_and_answer_parsing():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_chat_ok("Khu A, Tầng 1."))

    provider = _openai(handler)
    answer = await provider.reply(
        [Turn("user", "Mấy giờ?"), Turn("assistant", "7h"), Turn("user", "Cấp cứu ở đâu?")], CTX
    )
    await provider.aclose()

    assert answer == "Khu A, Tầng 1."
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["auth"] == "Bearer khoa-gia"
    body = captured["body"]
    assert body["model"] == "gpt-test"
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "user"]
    assert body["messages"][0]["content"] == CTX.system_prompt
    # Khong gui tham so gioi han token de tuong thich cac may chu noi chuan OpenAI khac.
    assert not {"max_tokens", "max_completion_tokens"} & body.keys()


async def test_openai_compatible_uses_custom_base_url_and_works_without_a_key():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["has_auth"] = "authorization" in request.headers
        return httpx.Response(200, json=_chat_ok("Xin chào"))

    provider = _openai(
        handler, base_url="http://bot.local:8000/v1/", api_key=None, name="openai_compatible", model="llama"
    )
    assert await provider.reply(HOI, CTX) == "Xin chào"
    assert captured == {"url": "http://bot.local:8000/v1/chat/completions", "has_auth": False}
    await provider.aclose()


async def test_openai_merges_consecutive_user_turns():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_chat_ok("ok"))

    provider = _openai(handler)
    # AI loi roi nguoi dung hoi tiep: lich su co 2 luot user lien nhau.
    await provider.reply([Turn("user", "Câu 1"), Turn("user", "Câu 2")], CTX)
    await provider.aclose()
    roles = [m["role"] for m in captured["body"]["messages"]]
    assert roles == ["system", "user"]


async def test_openai_accepts_content_given_as_a_list_of_text_blocks():
    body = {"choices": [{"message": {"content": [{"type": "text", "text": "Xin "}, {"type": "text", "text": "chào"}]}}]}
    provider = _openai(lambda request: httpx.Response(200, json=body))
    assert await provider.reply(HOI, CTX) == "Xin chào"
    await provider.aclose()


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"choices": [{"message": {"content": None}, "finish_reason": "content_filter"}]}, "filtered"),
        ({"choices": [{"message": {"content": None, "refusal": "Tôi không thể"}, "finish_reason": "stop"}]}, "filtered"),
        ({"choices": [{"message": {"content": "  "}, "finish_reason": "stop"}]}, "empty_reply"),
        ({"choices": []}, "bad_response"),
        ({"khong_co_choices": 1}, "bad_response"),
        (["sai", "dinh", "dang"], "bad_response"),
    ],
)
async def test_openai_unusable_answers_become_coded_errors(body, code):
    provider = _openai(lambda request: httpx.Response(200, json=body))
    with pytest.raises(SuperdocError) as info:
        await provider.reply(HOI, CTX)
    assert info.value.code == code
    await provider.aclose()


@pytest.mark.parametrize("status", [401, 429, 500, 503])
async def test_openai_http_errors_carry_the_status_in_the_code(status):
    provider = _openai(lambda request: httpx.Response(status, json={"error": {"message": "x"}}))
    with pytest.raises(SuperdocError, match=str(status)) as info:
        await provider.reply(HOI, CTX)
    assert info.value.code == f"http_{status}"
    await provider.aclose()


async def test_openai_config_errors_explain_what_the_provider_complained_about():
    # Model sai ten la loi cau hinh pho bien nhat — nguoi van hanh can thay ly do do trong thong bao.
    body = {"error": {"message": "The model `gpt-sai` does not exist"}}
    provider = _openai(lambda request: httpx.Response(404, json=body))
    with pytest.raises(SuperdocError) as info:
        await provider.reply(HOI, CTX)
    assert "does not exist" in str(info.value)
    assert info.value.code == "http_404"
    await provider.aclose()


async def test_openai_network_timeout_and_garbage_are_told_apart():
    def refuse(request):
        raise httpx.ConnectError("mat mang", request=request)

    def too_slow(request):
        raise httpx.ReadTimeout("cham qua", request=request)

    for handler, code in ((refuse, "network"), (too_slow, "timeout"), (lambda r: httpx.Response(200, text="<html>"), "bad_response")):
        provider = _openai(handler)
        with pytest.raises(SuperdocError) as info:
            await provider.reply(HOI, CTX)
        assert info.value.code == code
        await provider.aclose()


async def test_openai_rejects_empty_history():
    provider = _openai(lambda request: httpx.Response(200, json=_chat_ok("x")))
    with pytest.raises(SuperdocError):
        await provider.reply([], CTX)
    await provider.aclose()


async def test_internal_openai_compatible_errors_name_the_internal_bot():
    provider = _openai(lambda request: httpx.Response(500), name="openai_compatible", base_url="http://bot.local/v1")
    with pytest.raises(SuperdocError, match="Chatbot nội bộ"):
        await provider.reply(HOI, CTX)
    await provider.aclose()


# ---------- Anthropic (Claude) ----------


async def test_anthropic_request_shape_and_answer_parsing():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "Khu A, "}, {"type": "tool_use"}, {"type": "text", "text": "Tầng 1."}],
                  "stop_reason": "end_turn"},
        )

    provider = _anthropic(handler)
    answer = await provider.reply([Turn("user", "Mấy giờ?"), Turn("assistant", "7h"), Turn("user", "Cấp cứu?")], CTX)
    await provider.aclose()

    assert answer == "Khu A, Tầng 1."
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "khoa-gia"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    body = captured["body"]
    assert body["model"] == "claude-test"
    assert body["max_tokens"] > 0  # thieu max_tokens la HTTP 400
    assert body["system"] == CTX.system_prompt  # system o cap tren cung, khong nam trong messages
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]


async def test_anthropic_merges_consecutive_turns_because_the_api_requires_alternation():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    provider = _anthropic(handler)
    await provider.reply([Turn("assistant", "Cũ"), Turn("user", "Câu 1"), Turn("user", "Câu 2")], CTX)
    await provider.aclose()
    assert [m["role"] for m in captured["body"]["messages"]] == ["user"]


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"content": [], "stop_reason": "refusal"}, "filtered"),
        ({"content": [{"type": "text", "text": "  "}], "stop_reason": "end_turn"}, "empty_reply"),
        ("sai dinh dang", "bad_response"),
    ],
)
async def test_anthropic_unusable_answers_become_coded_errors(body, code):
    provider = _anthropic(lambda request: httpx.Response(200, json=body))
    with pytest.raises(SuperdocError) as info:
        await provider.reply(HOI, CTX)
    assert info.value.code == code
    await provider.aclose()


@pytest.mark.parametrize("status", [401, 429, 529])
async def test_anthropic_http_errors_carry_the_status_in_the_code(status):
    # 529 la Anthropic dang qua tai — phai nhan ra rieng de bang quan ly hien dung ly do.
    provider = _anthropic(lambda request: httpx.Response(status, json={"error": {"message": "x"}}))
    with pytest.raises(SuperdocError) as info:
        await provider.reply(HOI, CTX)
    assert info.value.code == f"http_{status}"
    await provider.aclose()


def test_anthropic_refuses_to_start_without_a_key():
    with pytest.raises(ValueError):
        AnthropicProvider(api_key="", model="claude-test")


# ---------- provider "khong kha dung" ----------


async def test_unavailable_provider_fails_every_question_with_a_clear_code():
    provider = UnavailableProvider("Chưa đặt biến môi trường OPENAI_API_KEY")
    with pytest.raises(SuperdocError, match="OPENAI_API_KEY") as info:
        await provider.reply(HOI, CTX)
    assert info.value.code == "not_configured"
    await provider.end_session(CTX, "user_exit")
    await provider.aclose()
