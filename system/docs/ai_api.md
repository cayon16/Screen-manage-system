# API quản lý kết nối AI

Đổi AI mà Superdoc dùng **ngay lúc đang chạy**, không cần khởi động lại app. Gọi bằng PowerShell hoặc
curl; bảng điều khiển (`Ctrl+Shift+M`) chỉ **hiển thị** AI đang dùng và tình trạng, không có nút đổi.

## 1. Ba chế độ

| Chế độ | Dùng khi | Nối tới |
|---|---|---|
| `demo` | Chạy thử, không có AI thật | Trả lời theo từ khoá, chạy offline |
| `internal` | **Chatbot nội bộ của công ty** | `bridge` (chuẩn riêng của PentaSync, xem `superdoc_bridge_api.md`) hoặc `openai_compatible` (bot nội bộ nói chuẩn OpenAI: vLLM, Ollama, LiteLLM, Dify…) |
| `public` | AI công khai | `gemini` (Google), `openai` (GPT), `anthropic` (Claude) |

Đổi chế độ chỉ ảnh hưởng **cuộc chat mới**. Cuộc chat đang dở giữ AI cũ tới khi kết thúc (chatbot nội bộ
có thể đang giữ phiên phía nó); `pinned_sessions` trong `GET /api/ai` cho biết còn mấy cuộc chat như vậy.

> **Cấu hình AI sai KHÔNG lùi về `demo`.** Màn hình bệnh viện mà trả lời bằng dữ liệu giả còn nguy hiểm
> hơn là báo thẳng "chưa kết nối được". Lúc đó mọi câu hỏi báo lỗi chung trên màn hình, còn lý do thật
> nằm ở `GET /api/ai` (mục `problems`) và trong log backend.

## 2. Khoá API — chỉ nằm trong biến môi trường

API quản lý **không nhận và không trả** khoá. Khoá không được ghi vào file dự án, file cấu hình, log hay git.

| Cần cho | Biến môi trường |
|---|---|
| Gemini | `GEMINI_API_KEY` |
| GPT (OpenAI) | `OPENAI_API_KEY` |
| Claude (Anthropic) | `ANTHROPIC_API_KEY` |
| Chatbot nội bộ (tuỳ chọn) | `SUPERDOC_INTERNAL_TOKEN` |

Đặt một lần cho tài khoản Windows (Windows lưu riêng cho tài khoản đó, không nằm trong thư mục dự án):

```bat
setx OPENAI_API_KEY "sk-..."
```

`setx` chỉ có hiệu lực với chương trình mở **sau đó**: **tắt app (Ctrl+Shift+Q) rồi mở lại**. Xem khoá nào
đã có: `GET /api/ai` → `secrets` (chỉ `true/false`).

Khoá đã lỡ lộ (dán vào chat, commit lên git…) phải **thu hồi và tạo lại** ở trang quản lý của nhà cung cấp.

## 3. Địa chỉ

```powershell
$api = "http://127.0.0.1:8000"
```

Cổng mặc định 8000. Nếu 8000 bị chương trình khác chiếm, app tự chọn cổng khác — xem dòng
`PentaSync khởi động (backend http://127.0.0.1:PORT)` trong `pentasync_app_log.txt`. API **chỉ gọi được
từ chính máy chạy PentaSync** (máy khác nhận 403).

## 4. Các lệnh

### Xem tình trạng — `GET /api/ai`

```powershell
irm $api/api/ai | ConvertTo-Json -Depth 6
```

Trả về: `active` (chế độ/nhà cung cấp/model đang dùng), `settings` (cấu hình đã lưu), `secrets` (khoá nào
đã có), `status` (tình trạng kết nối), `problems` (cấu hình đang thiếu gì), `pinned_sessions`, `catalog`
(mọi lựa chọn có thể dùng và mỗi cái cần gì).

`status.state`: `unknown` (chưa có lượt hỏi nào) · `ok` · `degraded` (1–2 lần lỗi liên tiếp) · `down`
(từ 3 lần lỗi liên tiếp, hoặc cấu hình thiếu).

### Đổi chế độ nhanh — `POST /api/ai/mode`

```powershell
irm -Method Post $api/api/ai/mode -ContentType 'application/json' -Body '{"mode":"demo"}'
```

Giữ nguyên phần cấu hình còn lại, nên chuyển qua lại giữa các chế độ đã cấu hình chỉ cần 1 lệnh.

### Đổi toàn bộ cấu hình — `PUT /api/ai/settings`

Chatbot nội bộ chuẩn Bridge:

```powershell
$body = '{"mode":"internal","internal":{"protocol":"bridge","base_url":"http://10.0.0.20:9000"}}'
irm -Method Put $api/api/ai/settings -ContentType 'application/json' -Body $body
```

Chatbot nội bộ nói chuẩn OpenAI:

```powershell
$body = '{"mode":"internal","internal":{"protocol":"openai_compatible","base_url":"http://10.0.0.20:8000/v1","model":"ten-model"}}'
irm -Method Put $api/api/ai/settings -ContentType 'application/json' -Body $body
```

GPT / Claude / Gemini:

```powershell
$body = '{"mode":"public","public":{"provider":"openai","model":"<ten model OpenAI>"}}'
irm -Method Put $api/api/ai/settings -ContentType 'application/json' -Body $body

$body = '{"mode":"public","public":{"provider":"anthropic"}}'     # model mac dinh claude-opus-5-5
$body = '{"mode":"public","public":{"provider":"gemini"}}'        # model mac dinh gemini-2.5-flash
```

Mặc định **thử kết nối trước khi đổi**: thử hỏng thì giữ nguyên AI cũ (HTTP 424). Thêm `?test=false`
để ép đổi dù AI chưa trả lời được.

Cấu hình đã đổi được **lưu vào `ai_settings.json`** (cạnh `pentasync.db`; không chứa khoá) và dùng lại
những lần mở app sau. Có file này thì biến môi trường `SUPERDOC_PROVIDER` không còn ghi đè.

### Thử kết nối — `POST /api/ai/test`

```powershell
irm -Method Post $api/api/ai/test                                              # thử AI dang chay
irm -Method Post $api/api/ai/test -ContentType 'application/json' -Body $body  # thử cau hinh moi, chua doi
```

Lần thử không tính vào số cuộc gọi/lỗi trong ngày. Kết quả `ok: false` vẫn trả HTTP 200 (việc thử đã chạy
xong); xem `error.code` và `error.message`.

> Nếu body có chữ tiếng Việt (vd `system_prompt`) và dùng Windows PowerShell 5.1, gửi dạng byte để khỏi hỏng dấu:
> `-Body ([Text.Encoding]::UTF8.GetBytes($body))`.

## 5. Các trường cấu hình (`AiSettings`)

| Trường | Ý nghĩa |
|---|---|
| `mode` | `demo` · `internal` · `public` |
| `internal.protocol` | `bridge` (mặc định) · `openai_compatible` |
| `internal.base_url` | Địa chỉ chatbot nội bộ, bắt buộc khi `mode=internal` |
| `internal.model` | Tên model, chỉ cho `openai_compatible` (bắt buộc khi đó) |
| `public.provider` | `gemini` · `openai` · `anthropic` |
| `public.model` | Bỏ trống = mặc định của nhà cung cấp. **OpenAI không có mặc định**: tên model của họ đổi liên tục, phải chọn |
| `public.base_url` | Chỉ cho `openai`; bỏ trống = `https://api.openai.com/v1` (đổi để dùng cổng trung gian/dịch vụ chuẩn OpenAI khác) |
| `timeout_sec` | 5–60 giây, mặc định 30. Quá hạn coi như lỗi |
| `system_prompt` | Bỏ trống = lời dặn mặc định (`SUPERDOC_SYSTEM_PROMPT` trong `config.py`) |

Trường lạ (ví dụ `api_key`) bị từ chối với HTTP 422 — cấu hình không có chỗ nào để chứa khoá.

## 6. Mã trả về

| HTTP | Khi nào |
|---|---|
| 200 | Thành công |
| 400 | Cấu hình đang chọn còn thiếu: `{"error": "...", "field": "secrets.OPENAI_API_KEY"}` (`field` chỉ ra thiếu gì: `secrets.<TÊN BIẾN>`, `public.model`, `internal.base_url`, `internal.model`) |
| 403 | Gọi từ máy khác |
| 422 | Sai cấu trúc (chế độ lạ, trường lạ, `timeout_sec` ngoài 5–60…) |
| 424 | Thử kết nối thất bại nên **chưa đổi**: `{"error": "...", "test": {...}}` |

## 7. Mã lỗi AI (`status.last_error.code`, `test.error.code`)

| Mã | Thường do |
|---|---|
| `http_401` | Khoá API / token sai hoặc hết hạn |
| `http_403` | Khoá không có quyền với model này |
| `http_404` | Tên model hoặc địa chỉ sai (thông báo kèm lý do nhà cung cấp trả về) |
| `http_429` | Hết hạn mức hoặc gọi quá nhanh |
| `http_5xx` / `http_529` | Nhà cung cấp lỗi / đang quá tải (529 là của Anthropic) |
| `timeout` | Quá `timeout_sec` |
| `network` | Không nối được (mất mạng, sai địa chỉ, tường lửa) |
| `bad_response` | Trả về dữ liệu không đúng chuẩn |
| `empty_reply` | Trả về câu rỗng |
| `filtered` | Bị bộ lọc an toàn của nhà cung cấp chặn |
| `not_configured` | Cấu hình thiếu (xem `problems`) |
| `error` | Lỗi không lường trước (xem log) |

Người dùng đứng trước màn hình **không thấy các mã này**: họ chỉ thấy thông báo chung ("Hiện chưa kết nối
được tới Superdoc…" hoặc "Superdoc phản hồi quá lâu…").

## 8. Quyền riêng tư và bảo mật

- Chế độ `public` gửi câu hỏi của người bệnh tới máy chủ của Google / OpenAI / Anthropic. Cần được bộ phận
  pháp lý/CNTT bệnh viện đồng ý theo quy định bảo vệ dữ liệu cá nhân trước khi bật trên máy thật.
- AI công khai chỉ nhận nội dung hội thoại và lời dặn hệ thống — **không** nhận mã phiên hay số màn. Chỉ chatbot
  nội bộ (mạng nội bộ) nhận chúng.
- Log không ghi nội dung chat, không ghi body request/response, không ghi khoá.
- **Khi tách backend lên server thật phải thêm xác thực (token) cho `/api/ai/*`** — hiện chỉ kiểm địa chỉ
  máy gọi, đủ cho backend chỉ nghe `127.0.0.1`.

## 9. Thêm một nhà cung cấp mới

1. Viết `backend/app/superdoc/<ten>_provider.py` theo `SuperdocProvider` (`base.py`): `name`, `model`,
   `reply(history, context)`, `end_session(context, reason)`, `aclose()`. Lỗi đi qua
   `http_common.to_superdoc_error`, câu trả lời rỗng/bị chặn ném `SuperdocError` có `code`.
2. Khai báo trong `registry.py`: `problems()` (cần gì), `build()`, `describe()`, một dòng trong `CATALOG`.
   Nếu là nhà cung cấp công khai mới thì thêm vào `Literal` của `PublicSettings.provider` (`settings.py`).
3. Viết test bằng `httpx.MockTransport` như `backend/tests/test_ai_providers.py`.

Không cần sửa `ClusterController`, `ChatSession` hay giao diện.
