# Quản lý kết nối AI: 2 chế độ (Nội bộ / Công khai) + API quản lý

> **Trạng thái: ĐÃ LÀM XONG ngày 2026-10-06** (kết quả và những gì chưa thử được: `TIEN_DO.md` giai đoạn 10).
> Giữ lại làm tài liệu thiết kế; vận hành xem `ai_api.md`.
> Kế hoạch này viết để **một phiên/model khác đọc và code được ngay**, không cần hỏi lại.
> Thư mục gốc code: `outsource/system/`. Mọi đường dẫn bên dưới tính từ đó.
>
> **Việc đầu tiên của phiên code** (trước bước 1 ở mục 9):
> 1. Chép nguyên file này vào `system/docs/ke_hoach_ai.md` để kế hoạch nằm trong dự án.
> 2. Thêm mục "Giai đoạn 10 — Quản lý kết nối AI" vào `system/TIEN_DO.md`, trỏ tới file đó và đánh dấu từng bước khi xong.
>
> Giai đoạn 9 (video chờ bị méo) trong `TIEN_DO.md` vẫn đang chờ khách chọn hướng — không liên quan kế hoạch này.

## Context

**Câu hỏi của khách: "system hiện tại đã có API quản lý kết nối AI chưa?" → CHƯA.** Hiện có:

- Lớp trừu tượng `SuperdocProvider` (`backend/app/superdoc/base.py`): `reply(history)`, `end_session(session_id)`, `aclose()`.
- 2 provider: `mock` (trả lời theo từ khoá, offline) và `gemini` (gọi REST `generateContent` bằng `httpx`).
- Chọn provider **1 lần lúc backend khởi động**, bằng biến môi trường `SUPERDOC_PROVIDER` (`factory.py`). Cấu hình đọc thành hằng số lúc import (`config.py`).

**Còn thiếu:** API xem/đổi AI lúc đang chạy; GPT, Claude; kết nối chatbot nội bộ (chưa có tài liệu API); lưu cấu hình; theo dõi trạng thái kết nối; nút "kiểm tra kết nối". Ngoài ra, khi cấu hình AI sai, hệ thống hiện **lùi về mock** — trên máy thật nghĩa là màn hình trả lời bằng dữ liệu bệnh viện bịa (giờ khám, vị trí khoa…) ⇒ nguy hiểm, phải đổi.

**Khách đã chốt (2026-10-06):**

| Câu hỏi | Quyết định |
|---|---|
| Chatbot nội bộ có tài liệu API chưa? | **Chưa** → PentaSync tự định nghĩa chuẩn **Superdoc Bridge v1** + máy chủ mẫu; IT công ty làm lớp bọc theo chuẩn. Hỗ trợ thêm `openai_compatible` cho bot nội bộ nói chuẩn OpenAI |
| AI công khai cần hỗ trợ | **Gemini, GPT (OpenAI), Claude (Anthropic)** |
| API key lưu ở đâu | **Chỉ biến môi trường.** API quản lý KHÔNG nhận, KHÔNG trả key; chỉ báo key "có / chưa có" |
| Giao diện | **Chỉ API** (gọi bằng PowerShell/curl). Bảng điều khiển chỉ **hiển thị** AI đang dùng + trạng thái |

**Kết quả mong muốn:**
- Đổi giữa 3 chế độ `internal` (chatbot nội bộ), `public` (Gemini/GPT/Claude) và `demo` (mock, offline) lúc đang chạy, không khởi động lại.
- Cấu hình được lưu lại.
- Có kiểm tra kết nối trước khi chuyển.
- Thêm nhà cung cấp mới = thêm 1 file.

---

## Ràng buộc bắt buộc — đọc trước khi code

1. **API key chỉ nằm trong biến môi trường.** Không bao giờ ghi vào file dự án, file cấu hình, log, response API hay test (test dùng chuỗi giả như `"khoa-gia"`). Model `AiSettings` **không có trường chứa key** ⇒ về cấu trúc không thể lưu nhầm.
2. **Không log nội dung chat**, không log body request/response. Chỉ log: provider, model, mã HTTP, mã lỗi, độ trễ.
3. **Single-writer:**
   - Mọi thay đổi trạng thái cụm vẫn đi qua hàng đợi command của `ClusterController`.
   - Việc gọi mạng (thử kết nối, gọi AI) **không được chạy trong hàng đợi**, vì sẽ làm treo cả 5 màn.
   - `AiManager` có `asyncio.Lock` riêng cho apply/test.
4. **Chỉ dùng `httpx`** (đã có trong `requirements.txt`). Không thêm SDK `openai` / `anthropic` / `google-genai`. Lý do:
   - Không tăng dung lượng bản exe, không phải xử lý hook PyInstaller.
   - Ánh xạ lỗi thống nhất cho mọi provider.
   - Test bằng `httpx.MockTransport` như test Gemini hiện có.
5. Theo `CLAUDE.md` (thay đổi tối thiểu, đúng phong cách xung quanh):
   - Comment trong `backend/app/` viết **tiếng Việt không dấu** như các file lân cận. `config.py` thì có dấu.
   - Không thêm tính năng ngoài kế hoạch.
6. **Xong mỗi bước:** `pytest` backend + desktop xanh, `ruff check .` sạch, `pyside6-qmllint` sạch (lệnh ở mục Kiểm thử). Ghi tiến độ vào `TIEN_DO.md` (yêu cầu thường trực của khách).

---

## Kiến trúc mới

```
HTTP /api/ai/*  ──►  AiManager  ──build──►  registry.build(settings, env)
 (ai_routes.py)       │  settings (ai_settings.json, không có key)
                      │  provider đang dùng (bọc _Tracked → đo trễ/lỗi)
                      │  provider cũ đang "nghỉ hưu" (chờ phiên chat cuối đóng)
                      ▼
ClusterController ── acquire() ──► AiLease(provider, system_prompt, timeout_sec)
                                        │  gắn chặt vào 1 ChatSession tới khi đóng
                                        ▼
                                   ChatSession._run_ai → provider.reply(history, ChatContext)
```

**Đổi AI giữa chừng:** chat mới dùng AI mới. Chat đang dở **giữ AI cũ tới khi kết thúc**, vì bot nội bộ có thể giữ phiên phía nó. Provider cũ được `aclose()` khi phiên cuối dùng nó đóng.

---

## 1. Giao diện provider — sửa `backend/app/superdoc/base.py`

```python
@dataclass(frozen=True)
class ChatContext:
    session_id: str
    screen_id: int          # vai trò màn (2 hoặc 4); 0 = lần kiểm tra kết nối
    system_prompt: str

class SuperdocError(Exception):
    def __init__(self, message: str, code: str = "ai_unavailable"):
        super().__init__(message)
        self.code = code
    # code chỉ dùng cho trạng thái/thống kê: "http_401", "http_429", "http_529", "timeout",
    # "network", "bad_response", "empty_reply", "filtered", "not_configured"

class SuperdocProvider(Protocol):
    name: str               # "mock" | "gemini" | "openai" | "anthropic" | "bridge" | "openai_compatible" | "unavailable"
    model: str | None
    async def reply(self, history: Sequence[Turn], context: ChatContext) -> str: ...
    async def end_session(self, context: ChatContext, reason: str) -> None: ...
    async def aclose(self) -> None: ...

def normalize_history(history: Sequence[Turn]) -> list[Turn]:
    """Bo luot rong; bo cac luot assistant dung dau (cat lich su co the bat dau bang assistant);
    gop cac luot lien tiep cung vai tro bang '\n' (AI loi -> nguoi dung hoi tiep -> 2 luot user lien)."""
```

- Câu trả lời lỗi hiện trên màn **giữ nguyên** (`ai_timeout` / `ai_unavailable` / `ai_error` trong `chat_session.py`). `SuperdocError.code` chỉ để thống kê.
- **Helper dùng chung** (đặt trong `base.py` hoặc file mới `superdoc/http_common.py`): `to_superdoc_error(exc, provider_name) -> SuperdocError`.
  - `HTTPStatusError` → `http_{status}`, message `"<provider> trả về HTTP <status>"`.
    - Riêng mã 400–404: nối thêm `error.message` lấy từ JSON phản hồi, cắt ≤ 200 ký tự (giúp người vận hành sửa cấu hình, vd model sai tên).
  - `TimeoutException` → `timeout`.
  - `HTTPError` khác → `network`.
  - JSON hỏng → `bad_response`.

---

## 2. Cấu hình — file mới `backend/app/superdoc/settings.py`

```python
class InternalSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol: Literal["bridge", "openai_compatible"] = "bridge"
    base_url: str | None = None      # vd "http://10.0.0.20:9000"; bắt buộc khi mode=internal
    model: str | None = None         # chỉ openai_compatible (bắt buộc khi đó)

class PublicSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["gemini", "openai", "anthropic"] = "gemini"
    model: str | None = None         # None = mặc định của provider; openai KHÔNG có mặc định
    base_url: str | None = None      # chỉ openai; None = https://api.openai.com/v1

class AiSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    mode: Literal["demo", "internal", "public"] = "demo"
    internal: InternalSettings = InternalSettings()
    public: PublicSettings = PublicSettings()
    timeout_sec: float = Field(30, ge=5, le=60)
    system_prompt: str | None = Field(None, max_length=4000)   # None = SUPERDOC_SYSTEM_PROMPT
```

- **`base_url`:** validator kiểm tra phải bắt đầu bằng `http://` hoặc `https://`, rồi bỏ `/` ở cuối.
- **Validator cấu trúc chỉ kiểm hình dạng**, không kiểm độ đầy đủ theo chế độ. Nhờ vậy được lưu cấu hình `internal` dở dang trong lúc vẫn chạy `public`. Độ đầy đủ do `registry.problems()` kiểm (mục 4).
- **`load_settings(path, env) -> AiSettings`:**
  - File tồn tại → đọc file; **biến môi trường không ghi đè file**.
  - File hỏng → log lỗi rồi dùng mặc định từ env.
  - Chưa có file → dựng từ env (giữ tương thích bản cũ):
    - `SUPERDOC_PROVIDER=gemini` → `mode=public, provider=gemini`.
    - `mock` hoặc không đặt → `mode=demo`.
    - `GEMINI_MODEL` / `OPENAI_MODEL` / `ANTHROPIC_MODEL` → `public.model` của provider tương ứng.
    - `SUPERDOC_INTERNAL_URL` → `internal.base_url`.
- **`save_settings(path, settings)`:** ghi nguyên tử (file tạm → `os.replace`), JSON `indent=2, ensure_ascii=False`.

**Sửa `config.py`:**
- Thêm hằng số:
  - `AI_SETTINGS_PATH = DATA_DIR / "ai_settings.json"`.
  - Tên biến môi trường: `GEMINI_API_KEY_ENV = "GEMINI_API_KEY"`, `OPENAI_API_KEY_ENV`, `ANTHROPIC_API_KEY_ENV`, `INTERNAL_TOKEN_ENV = "SUPERDOC_INTERNAL_TOKEN"`.
  - Model mặc định: `GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"`, `ANTHROPIC_DEFAULT_MODEL = "claude-opus-5-5"`.
- Giữ `SUPERDOC_TIMEOUT_SEC` (mặc định), `SUPERDOC_HISTORY_LIMIT`, `SUPERDOC_SYSTEM_PROMPT`.
- **Bỏ** `GEMINI_API_KEY` / `GEMINI_MODEL` dạng hằng số đọc lúc import. Key phải đọc từ `env` **lúc dựng provider**, để test `monkeypatch` được.

**`.gitignore` gốc (`outsource/.gitignore`):** thêm `ai_settings.json` (cấu hình riêng từng máy).

---

## 3. Các provider

Quy ước chung:
- Constructor nhận tham số rõ ràng (`api_key`, `model`, `base_url`, `timeout_sec`), **không import key từ config**.
- Có `self._client = httpx.AsyncClient(timeout=timeout_sec)`.
- `reply()` gọi `normalize_history()`.
- Rỗng lịch sử → `SuperdocError(code="bad_response")`.
- Lỗi đi qua `to_superdoc_error`.

| File | Provider | Gọi | Header | Body chính | Lấy câu trả lời |
|---|---|---|---|---|---|
| `mock_provider.py` (sửa chữ ký) | `mock` | — | — | — | như cũ |
| `unavailable_provider.py` **mới** | `unavailable` | — | — | — | luôn ném `SuperdocError(reason, "not_configured")` |
| `gemini_provider.py` (sửa) | `gemini` | `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | `x-goog-api-key` | như cũ; `system_instruction` lấy từ `context.system_prompt` | như cũ |
| `openai_provider.py` **mới** | `openai` / `openai_compatible` | `POST {base_url}/chat/completions` | `Authorization: Bearer <key>` (bỏ qua nếu không có key — bot nội bộ có thể không cần) | `{"model", "messages": [{"role":"system","content":prompt}, …{"role":"user"/"assistant","content"}]}` — **không** gửi tham số giới hạn token (để tương thích server khác) | `choices[0].message.content` (nếu là list thì nối các phần `text`); `finish_reason=="content_filter"` → `filtered` |
| `anthropic_provider.py` **mới** | `anthropic` | `POST https://api.anthropic.com/v1/messages` | `x-api-key`, `anthropic-version: 2023-06-01` | `{"model", "max_tokens": 1024, "system": prompt, "messages": [...]}` (`max_tokens` bắt buộc, thiếu là HTTP 400) | nối các khối `content[]` có `type=="text"`; `stop_reason=="refusal"` → `filtered`; lỗi 529 (quá tải) → `http_529` |
| `bridge_provider.py` **mới** | `bridge` | theo **Superdoc Bridge v1** (mục 6) | `Authorization: Bearer <SUPERDOC_INTERNAL_TOKEN>` nếu có, `X-PentaSync-Bridge: 1` | xem mục 6 | `reply` |

- `end_session`:
  - **bridge** gọi `POST {base}/v1/sessions/{id}/end` kèm `{"reason": reason}`. 404/405 coi như bot không hỗ trợ → bỏ qua. Lỗi khác thì ném; `ChatSession` đã tự nuốt và log.
  - Các provider còn lại: no-op.
- **Riêng tư:** gemini/openai/anthropic chỉ nhận nội dung hội thoại + system prompt, **không gửi `session_id`, `screen_id`**. Bridge (mạng nội bộ) được nhận cả hai.

---

## 4. Registry — file mới `backend/app/superdoc/registry.py` (THAY `factory.py`, xoá `factory.py`)

```python
class ProviderConfigError(ValueError):
    def __init__(self, field: str, message: str): ...   # message tiếng Việt cho người vận hành

def problems(settings: AiSettings, env: Mapping[str, str] = os.environ) -> list[ProviderConfigError]
def build(settings: AiSettings, env: Mapping[str, str] = os.environ) -> SuperdocProvider   # có problems → raise cái đầu
def describe(settings: AiSettings, env=os.environ) -> dict   # {"mode","provider","model","base_url"} đang có hiệu lực
CATALOG: list[dict]   # cho GET /api/ai: mode, provider, secret_env, default_model, model_required, base_url_default
```

Quy tắc kiểm, **chỉ áp cho chế độ đang chọn**:

| mode / provider | Bắt buộc | Lỗi (field → message) |
|---|---|---|
| `demo` | — | — |
| `public` / `gemini` | env `GEMINI_API_KEY` | `secrets.GEMINI_API_KEY` → "Chưa đặt biến môi trường GEMINI_API_KEY" |
| `public` / `openai` | env `OPENAI_API_KEY`; `public.model` (hoặc env `OPENAI_MODEL`) | "Chưa chọn model cho OpenAI" — **không có model mặc định** vì tên model OpenAI đổi liên tục |
| `public` / `anthropic` | env `ANTHROPIC_API_KEY` | model mặc định `ANTHROPIC_DEFAULT_MODEL` |
| `internal` / `bridge` | `internal.base_url` | token tuỳ chọn |
| `internal` / `openai_compatible` | `internal.base_url`, `internal.model` | token tuỳ chọn, gửi dạng Bearer |

Cập nhật `superdoc/__init__.py`: export `ChatContext`, `SuperdocError`, `SuperdocProvider`, `Turn`, `normalize_history`.

---

## 5. AiManager — file mới `backend/app/superdoc/manager.py`

```python
@dataclass
class AiLease:
    provider: SuperdocProvider
    system_prompt: str
    timeout_sec: float
    def release(self) -> None        # gọi nhiều lần vẫn an toàn

class AiManager:
    def __init__(self, settings_path: Path | None, env: Mapping[str, str] = os.environ,
                 on_change: Callable[[], Awaitable[None]] | None = None): ...
    @classmethod
    def fixed(cls, provider, system_prompt=SUPERDOC_SYSTEM_PROMPT,
              timeout_sec=SUPERDOC_TIMEOUT_SEC) -> "AiManager"   # cho test: không file, không đổi được
    async def start(self) -> None
    def acquire(self) -> AiLease                                 # ĐỒNG BỘ, không await
    async def apply(self, settings: AiSettings, *, test_first: bool = True) -> dict
    async def set_mode(self, mode: str, *, test_first: bool = True) -> dict
    async def test(self, settings: AiSettings | None = None) -> dict
    def snapshot(self) -> dict                                   # GET /api/ai — không bao giờ chứa giá trị key
    def brief(self) -> dict                                      # cho bảng điều khiển
    async def aclose(self) -> None
```

**`start()`:**
- `load_settings` → `build`.
- `build` lỗi: **không lùi về mock**. Dùng `UnavailableProvider(lý do)` cho mode internal/public, ghi `state="down"` kèm lý do, log ERROR.
- Màn hình sẽ báo "Hiện chưa kết nối được tới Superdoc…" thay vì trả lời bịa.

**`apply()`, chạy dưới `asyncio.Lock`:**
1. Kiểm `problems` → có lỗi thì raise `ProviderConfigError`.
2. `build` provider mới.
3. Nếu `test_first`: thử 1 câu (như `test()`). Thất bại → `aclose` provider mới, raise `AiTestFailed(result)`, **giữ nguyên** provider cũ.
4. Hoán đổi: provider cũ chuyển sang `_retiring`. Hết phiên giữ nó thì `asyncio.create_task(old.aclose())`.
5. `save_settings`.
6. Reset trạng thái (`unknown`).
7. `await on_change()`.
8. Trả về `{"applied": true, "active": describe(...), "test": result|None, "pinned_sessions": n}`.

**`test(settings=None)`:**
- Dựng provider tạm từ `settings`, hoặc dùng provider đang chạy nếu `None`.
- Gửi 1 lượt: `Turn("user", "Đây là tin nhắn kiểm tra kết nối. Hãy trả lời ngắn: OK.")`, với `ChatContext(session_id=f"test-{uuid4()}", screen_id=0, system_prompt=…)` và `asyncio.wait_for(timeout_sec)`.
- Sau đó gọi `end_session(ctx, "connection_test")`, nuốt lỗi.
- `aclose` provider tạm.
- Trả `{"ok", "latency_ms", "provider", "model", "reply_preview" (≤ 200 ký tự) | "error": {"code","message"}}`.
- **Không** tính vào `calls_today`, nhưng ghi vào `last_test`.

**Theo dõi trạng thái (`_Tracked`):** bọc provider thật, đo thời gian `reply()`, cập nhật:
- `state`:
  - `unknown`: chưa gọi lần nào.
  - `ok`: lần gần nhất thành công.
  - `degraded`: 1–2 lần lỗi liên tiếp.
  - `down`: từ 3 lần lỗi liên tiếp, hoặc dựng provider lỗi.
- `last_ok_at`, `last_latency_ms`, `last_error {at, code, message}`, `consecutive_failures`.
- `calls_today`, `errors_today` (về 0 lúc nửa đêm theo giờ máy).
- `name` / `model` đọc xuyên qua provider bên trong, bằng `getattr(inner, "model", None)` vì `FakeProvider` trong test không có thuộc tính `model`.

**`snapshot()`:**
```json
{
  "active": {"mode": "public", "provider": "gemini", "model": "gemini-2.5-flash", "base_url": null},
  "settings": { "...AiSettings đang lưu..." },
  "secrets": {"GEMINI_API_KEY": true, "OPENAI_API_KEY": false, "ANTHROPIC_API_KEY": false, "SUPERDOC_INTERNAL_TOKEN": false},
  "status": {"state": "ok", "last_ok_at": 1760000000.0, "last_latency_ms": 1840, "last_error": null,
             "consecutive_failures": 0, "calls_today": 37, "errors_today": 1, "last_test": null},
  "problems": [],
  "pinned_sessions": 0,
  "catalog": [ ... ]
}
```

**`brief()`:** `{"mode", "provider", "model", "state", "last_error_code"}`.

---

## 6. Chuẩn kết nối chatbot nội bộ — **Superdoc Bridge v1** (tài liệu gửi IT công ty)

- **Quy ước chung:**
  - Base URL cấu hình ở `internal.base_url`. Toàn bộ là JSON UTF-8.
  - Header `Authorization: Bearer <token>` khi có biến môi trường `SUPERDOC_INTERNAL_TOKEN`, cùng `X-PentaSync-Bridge: 1`.
- **`POST /v1/chat`**
  ```json
  {"session_id": "9b2f0c…", "screen": 4, "locale": "vi-VN",
   "system_prompt": "Bạn là Superdoc…",
   "messages": [{"role": "user", "content": "Khoa cấp cứu ở đâu?"},
                {"role": "assistant", "content": "…"},
                {"role": "user", "content": "Mở cửa mấy giờ?"}]}
  ```
  - `messages` là lịch sử gần nhất (≤ 20 lượt), lượt cuối luôn là `user`.
  - Bot **không lưu trạng thái** thì dùng `messages`; bot **có lưu phiên** thì dùng `session_id`.
  - `session_id` ngẫu nhiên mỗi lượt chat, không gắn với danh tính ai.
  - **200** → `{"reply": "Khoa Cấp cứu ở Khu A…"}`: chữ thường, không markdown, nên ≤ 600 ký tự.
  - **Lỗi:** mã ≠ 2xx kèm `{"error": {"code": "…", "message": "…"}}`. PentaSync hiện thông báo lỗi chung cho người dùng và ghi mã vào log.
  - Phải trả lời trong `timeout_sec` (mặc định 30 s).
- **`POST /v1/sessions/{session_id}/end`**, body `{"reason": "<lý do>"}` → **204**. Không bắt buộc: 404/405 được bỏ qua.
  - `reason` lấy đúng tập `Literal` trong `SessionClosedMsg` (`backend/app/schemas.py`: `user_exit`, `tier1_timeout`, `error_timeout`, `mode_switch`, `cluster_reset`, `blackout`, `system_reset`, `screen_removed`), cộng thêm `connection_test`.
- **`GET /v1/health`** → `{"status": "ok"}`. Không bắt buộc, để IT giám sát.
- **Đổi phiên bản:** thay đổi phá vỡ tương thích thì sang `/v2`.

**Máy chủ mẫu:** file mới `backend/app/superdoc/bridge_reference.py`.
- App FastAPI riêng, làm đúng chuẩn trên, trả lời bằng `MockSuperdocProvider`.
- Lưu `ended` (danh sách phiên đã đóng) và `received` (số request) để test.
- Có `--token` để thử xác thực.
- Chạy: `python -m app.superdoc.bridge_reference --port 9000 [--token abc]`.
- **Không** gắn vào app chính. Dùng cho test hợp đồng và làm ví dụ cho IT.

Tài liệu đầy đủ: file mới `docs/superdoc_bridge_api.md` (nội dung mục này + ví dụ request/response + bảng mã lỗi + hướng dẫn chạy máy chủ mẫu).

---

## 7. API quản lý — file mới `backend/app/routes/ai_routes.py`

- Gắn trong `main.py`: `app.include_router(ai_router)`.
- **Mọi route** dùng dependency `require_local(request)`: chỉ chấp nhận `request.client.host` thuộc `{"127.0.0.1", "::1"}`; ngược lại trả **403** `{"error": "Chỉ gọi được từ chính máy chạy PentaSync"}`.
- Backend vốn chỉ nghe `127.0.0.1`; đây là lớp phòng thủ thêm.
- **Khi tách backend lên server phải thêm xác thực (token)** — ghi rõ trong tài liệu.

| Method | Path | Body | Trả về |
|---|---|---|---|
| `GET` | `/api/ai` | — | 200 `snapshot()` |
| `PUT` | `/api/ai/settings?test=true` | `AiSettings` | 200 kết quả `apply`<br>400 `{"error", "field"}` (`ProviderConfigError`)<br>422 sai cấu trúc<br>424 `{"error": "Thử kết nối thất bại — chưa đổi", "test": {...}}` |
| `POST` | `/api/ai/mode?test=true` | `{"mode": "internal" \| "public" \| "demo"}` | như `PUT`; giữ nguyên phần cấu hình khác |
| `POST` | `/api/ai/test` | `AiSettings` hoặc rỗng | 200 kết quả `test()` (kể cả `ok: false`)<br>400 nếu cấu hình ứng viên thiếu bắt buộc |

- `test` mặc định `true`. `?test=false` dùng để ép đổi kể cả khi AI chưa trả lời được.
- **Đọc `apply` từ `app.state.ai`**: route chạy ngoài hàng đợi command, đúng ràng buộc 3.

---

## 8. Nối vào hệ thống hiện có

- **`backend/app/state/chat_session.py`:**
  - Tham số `provider` → `ai: AiLease`.
  - `_run_ai`: dựng `ChatContext(self.session_id, self.screen_id, self._ai.system_prompt)`, gọi `self._ai.provider.reply(context_turns, ctx)` với `timeout=self._ai.timeout_sec` (thay hằng số `SUPERDOC_TIMEOUT_SEC`).
  - `close(reason)`: `await provider.end_session(ctx, reason)` (vẫn nuốt lỗi), rồi `self._ai.release()`.
- **`backend/app/state/cluster_controller.py`:**
  - Constructor nhận `ai: AiManager | None = None`. **Giữ** `provider=` để không phải sửa hàng loạt test: có `provider` thì `AiManager.fixed(provider)`; không có gì thì `AiManager.fixed(MockSuperdocProvider())`.
  - `_open_chat_session`: `ai=self._ai.acquire()`.
  - `admin_snapshot()` thêm `ai=self._ai.brief()`.
  - Thêm xử lý `AiChangedCommand` → `self._admin_dirty = True` (cơ chế phát lại snapshot đã có ở dòng ~252).
- **`backend/app/commands.py`:** thêm `AiChangedCommand` (không trường), đưa vào union `Command`.
- **`backend/app/schemas.py`:** `AdminSnapshotMsg` thêm `ai: dict[str, Any] = Field(default_factory=dict)`.
- **`backend/app/main.py` (lifespan):**
  - `ai = AiManager(AI_SETTINGS_PATH, on_change=lambda: cluster.submit(AiChangedCommand()))`.
  - `await ai.start()` trước khi tạo `cluster`.
  - `ClusterController(..., ai=ai)`; `app.state.ai = ai`.
  - Khi tắt: `await ai.aclose()` sau `cluster.stop()`.
- **`desktop/qml/ManagementWindow.qml`:**
  - Trong dãy ô thống kê (~dòng 505, mẫu `{label, value, danger}`) thêm 1 ô:
    - label "AI đang dùng".
    - value dạng `"Công khai · gemini-2.5-flash"` / `"Nội bộ · bridge"` / `"Demo (offline)"`.
    - `danger` khi `state` là `"down"`.
    - Có `last_error_code` thì hiện thêm dòng nhỏ.
  - Snapshot đã có sẵn trong `win`; đọc từ trường `ai` mới.
  - **Không thêm nút** (khách chọn "Chỉ API").
- **`test/xem_giao_dien.py`:** thêm trường `ai` vào snapshot giả của bảng điều khiển để ảnh chụp có ô mới.

---

## 9. Thứ tự làm — mỗi bước xong phải chạy test

| # | Việc | Kiểm tra |
|---|---|---|
| 1 | `base.py` (`ChatContext`, `SuperdocError.code`, `normalize_history`, helper lỗi) + sửa chữ ký `mock` / `gemini` + `FakeProvider` trong `backend/tests/conftest.py` (`reply(history, context=None)`, `end_session(context, reason)` → lưu `context.session_id`) | backend pytest xanh |
| 2 | `settings.py` + `config.py` + test | `test_ai_settings.py` |
| 3 | `unavailable_provider.py`, `openai_provider.py`, `anthropic_provider.py`, `bridge_provider.py`, `bridge_reference.py` + test | test provider |
| 4 | `registry.py`, xoá `factory.py`, sửa `__init__.py` + test | `test_ai_registry.py` |
| 5 | `manager.py` + test | `test_ai_manager.py` |
| 6 | Nối `chat_session` / `cluster_controller` / `commands` / `schemas` / `main` | **toàn bộ** backend pytest xanh |
| 7 | `ai_routes.py` + test | `test_ai_routes.py` |
| 8 | Ô "AI đang dùng" trên bảng điều khiển + `xem_giao_dien.py` | qmllint sạch, `test\xem_giao_dien.py` 15/15, xem ảnh |
| 9 | Tài liệu + `.gitignore` + `TIEN_DO.md` | đọc lại |
| 10 | Chạy thật + đóng gói | mục Kiểm thử |

---

## 10. Kiểm thử

**Test tự động mới** (`backend/tests/`, theo mẫu `httpx.MockTransport` trong `test_superdoc.py` và `TestClient` trong `test_admin_routes.py`):

- **`test_superdoc.py` (sửa):** chữ ký mới. Đổi `test_factory_falls_back_to_mock_*` thành: cấu hình sai → `unavailable`, **không phải** `mock`.
- **`test_ai_settings.py`:**
  - Giá trị mặc định; `extra="forbid"`; `timeout_sec` ngoài 5–60 bị chặn; chuẩn hoá `base_url`.
  - Ánh xạ env cũ (`SUPERDOC_PROVIDER=gemini`).
  - Có file thì env không ghi đè; file hỏng thì dùng mặc định.
  - Ghi nguyên tử; **file lưu ra không chứa chuỗi key** (đặt env key giả, đọc lại file, kiểm không có).
- **`test_ai_providers.py`:**
  - OpenAI: URL `/chat/completions`, `Bearer`, message `system` đứng đầu, vai trò đúng, `base_url` tuỳ chỉnh, không có key thì không có header, `content_filter`, 401/429/500, mất mạng, rỗng.
  - Anthropic: `x-api-key`, `anthropic-version`, `system` ở cấp trên cùng, có `max_tokens`, nối khối text, `refusal`, 529.
  - Gemini: lấy prompt từ `context`.
  - `normalize_history`: gộp 2 user liền nhau, bỏ assistant đứng đầu.
- **`test_ai_bridge.py`:** `BridgeProvider` gọi **máy chủ mẫu thật trong tiến trình** qua `httpx.ASGITransport(app=bridge_app)`.
  - Trả lời đúng; `end_session` gửi đúng `reason`; token sai → 401 → `SuperdocError("http_401")`; phong bì lỗi; 404 khi end thì bỏ qua.
- **`test_ai_registry.py`:** đủ bảng quy tắc ở mục 4.
- **`test_ai_manager.py`:**
  - `apply` đổi AI cho phiên mới, **phiên đang giữ lease vẫn dùng provider cũ**; provider cũ `aclose` sau `release` cuối.
  - `build` lỗi thì giữ cái cũ; test thất bại thì giữ cái cũ và trả 424.
  - Khởi động với cấu hình sai → `unavailable` + `state=down`.
  - Chuyển trạng thái ok → degraded → down; reset đầu ngày.
  - `snapshot()` không chứa giá trị key.
- **`test_ai_routes.py`:**
  - Fixture ghi đè `require_local` (vì host của `TestClient` là `"testclient"`); thêm 1 test riêng cho `require_local` với scope giả → 403.
  - `GET` đúng hình dạng; `PUT` hợp lệ / 400 / 422 / 424; `POST /mode`; `POST /test`.
  - `admin_snapshot` có trường `ai`.

**Lệnh** (chạy trong `system/`):

```bat
cd backend && ..\.venv\Scripts\python -m pytest -q          :: hiện 176 → phải tăng, 0 lỗi
cd ..      && .venv\Scripts\python -m pytest desktop\tests -q :: 151 passed
.venv\Scripts\python -m ruff check .
.venv\Scripts\pyside6-qmllint -I desktop\qml desktop\qml\*.qml desktop\qml\PentaSync\*.qml
.venv\Scripts\python test\xem_giao_dien.py                  :: 15/15
```

**Chạy thật đầu-cuối** (PowerShell). Cổng mặc định là 8000; nếu 8000 bị chiếm thì `run.py` tự đổi cổng — xem dòng `PentaSync khởi động (backend http://127.0.0.1:PORT)` trong `desktop\pentasync_app_log.txt`:

1. Máy chủ mẫu: `cd backend; ..\.venv\Scripts\python -m app.superdoc.bridge_reference --port 9000`
2. App: `.venv\Scripts\python desktop\run.py`
3. `irm http://127.0.0.1:8000/api/ai` → `mode=demo`, `secrets` toàn `false` (nếu chưa đặt biến).
4. Chuyển sang nội bộ:
   ```powershell
   irm -Method Put http://127.0.0.1:8000/api/ai/settings -ContentType 'application/json; charset=utf-8' -Body '{"mode":"internal","internal":{"protocol":"bridge","base_url":"http://127.0.0.1:9000"}}'
   ```
   → `applied: true`, `test.ok: true`.
5. `.venv\Scripts\python test\kiem_tra_cham.py motman` → 23/23. Câu trả lời giờ đi qua bridge; log máy chủ mẫu có `/v1/chat` và `/v1/sessions/…/end`.
6. **Đổi giữa chừng:** mở chat ở màn 4 → `POST /api/ai/mode {"mode":"demo"}` → chat đang mở vẫn đi qua bridge, chat mới dùng mock; `pinned_sessions` về 0 sau khi chat cũ đóng.
7. Tắt máy chủ mẫu → `POST /api/ai/test` trả `ok: false, code: "network"`; `POST /api/ai/mode {"mode":"internal"}` → 424, AI không bị đổi.
8. **AI công khai (khách tự làm với key thật):**
   - `setx GEMINI_API_KEY "..."` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, mở lại app.
   - `PUT /api/ai/settings` với `{"mode":"public","public":{"provider":"openai","model":"<tên model>"}}` (tương tự với `anthropic`, `gemini`).
   - Kiểm: `test.ok: true`, chat trên màn có trả lời.
   - Thiếu key → 400 `field: secrets.OPENAI_API_KEY`.
9. **Bản đóng gói:** `.venv\Scripts\python packaging\build.py` → `test\kiem_tra_exe.py` 9/9 → gọi `irm http://127.0.0.1:<cổng exe>/api/ai`. Kiểm `data\ai_settings.json` được tạo sau lần `PUT` đầu và **không có key**.

---

## 11. Tài liệu phải cập nhật

- **Mới `docs/ai_api.md`:** bảng endpoint, ví dụ PowerShell (`irm`) cho từng thao tác, bảng mã lỗi `SuperdocError.code`, cách đặt key bằng `setx` (lưu trong biến môi trường tài khoản Windows, không phải file dự án; phải mở lại app), cảnh báo phải thêm xác thực khi đưa backend lên server.
- **Mới `docs/superdoc_bridge_api.md`:** mục 6 — viết cho IT công ty đọc.
- **Sửa:**
  - `README.md` (gốc và `system/`): mục "Chat AI" → 3 chế độ, trỏ sang `docs/ai_api.md`.
  - `descryption.md`: bảng file `superdoc/`, mục 11 "Chat AI", bảng "Muốn sửa X", route mới.
  - `docs/architecture.md`: mục 8.
  - `HUONG_DAN_TEST.md`: mục "Chat AI thật (Gemini)" → "Chat AI: nội bộ / công khai".
  - `TIEN_DO.md`: giai đoạn mới.

---

## Ngoài phạm vi (cố ý không làm)

- Nhập key qua giao diện / Windows Credential Manager (khách chọn chỉ biến môi trường).
- Nút đổi AI trên bảng điều khiển (khách chọn chỉ API; bảng điều khiển chỉ hiển thị).
- Trả lời dạng stream; tự chuyển sang AI dự phòng khi AI chính lỗi. Có thể thêm sau trong `AiManager`.
- Azure OpenAI (dùng header `api-key` khác chuẩn) và các SDK chính thức.
- Xác thực API quản lý — **bắt buộc làm khi tách backend lên server**.

## Lưu ý cho khách (không phải việc code)

Chế độ **công khai** gửi câu hỏi của người bệnh tới máy chủ nước ngoài (Google / OpenAI / Anthropic). Nên hỏi bộ phận pháp lý/CNTT bệnh viện theo quy định bảo vệ dữ liệu cá nhân của Việt Nam trước khi bật trên máy thật.

Hệ thống đã:
- Không gửi định danh màn/phiên cho AI công khai.
- Không log nội dung chat.
- Có system prompt dặn AI không hỏi thông tin cá nhân.
