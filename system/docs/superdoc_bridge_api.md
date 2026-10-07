# Superdoc Bridge v1 — chuẩn kết nối chatbot nội bộ

Tài liệu cho **bộ phận IT của công ty / bệnh viện**. Chatbot nội bộ chưa có tài liệu API nên PentaSync tự
định nghĩa một chuẩn kết nối rất nhỏ. Bên chatbot chỉ cần dựng (hoặc bọc ngoài bot hiện có) một máy chủ
HTTP nói đúng chuẩn này, rồi nhập địa chỉ vào PentaSync.

> Bot nội bộ **đã nói chuẩn OpenAI** (`POST /v1/chat/completions`) thì **không cần tài liệu này** — dùng
> `internal.protocol = "openai_compatible"`, xem `ai_api.md`.

## Tổng quan

```
Màn hình hành lang ──► PentaSync ──HTTP/JSON──► (máy chủ Bridge) ──► chatbot nội bộ
```

- Chỉ 2 endpoint bắt buộc/tuỳ chọn + 1 endpoint giám sát. Mọi thứ là JSON UTF-8.
- PentaSync gọi chatbot, không ngược lại. Một cuộc chat trên màn hình = một `session_id`.
- Địa chỉ gốc (`base_url`) do người vận hành cấu hình, ví dụ `http://10.0.0.20:9000`.

## Xác thực (tuỳ chọn)

Nếu PentaSync có biến môi trường `SUPERDOC_INTERNAL_TOKEN` thì **mọi request** kèm header:

```
Authorization: Bearer <token>
X-PentaSync-Bridge: 1
```

(Header `X-PentaSync-Bridge: 1` luôn được gửi, để bên nhận nhận ra request của PentaSync.) Sai/thiếu token
thì trả **401**.

## `POST /v1/chat` — hỏi một câu (bắt buộc)

Request:

```json
{
  "session_id": "9b2f0c11-5d2e-4e0a-9c1c-6f3a1b2c3d4e",
  "screen": 4,
  "locale": "vi-VN",
  "system_prompt": "Bạn là Superdoc — trợ lý ảo đặt tại màn hình hành lang bệnh viện. ...",
  "messages": [
    {"role": "user", "content": "Khoa cấp cứu ở đâu?"},
    {"role": "assistant", "content": "Khoa Cấp cứu ở Khu A, Tầng 1."},
    {"role": "user", "content": "Mở cửa mấy giờ?"}
  ]
}
```

| Trường | Ý nghĩa |
|---|---|
| `session_id` | Mã ngẫu nhiên của cuộc chat, **đổi mỗi cuộc chat**, không gắn với danh tính ai |
| `screen` | Số màn (2 hoặc 4); `0` = lần kiểm tra kết nối |
| `locale` | Luôn `vi-VN` |
| `system_prompt` | Lời dặn nên đưa cho model (không bắt buộc phải dùng) |
| `messages` | Lịch sử gần nhất (tối đa 20 lượt), xen kẽ `user` / `assistant`. **Lượt cuối luôn là `user`** |

Bot **không lưu trạng thái**: dùng `messages` làm ngữ cảnh. Bot **có lưu phiên**: dùng `session_id` và chỉ
cần lượt cuối.

Response **200**:

```json
{"reply": "Khoa Cấp cứu mở cửa 24/7."}
```

- `reply`: chữ thường, **không markdown** (màn hình hiện nguyên văn), nên ngắn (≤ 600 ký tự, 2–4 câu).
- Phải trả lời trong thời gian PentaSync cấu hình (`timeout_sec`, mặc định 30 giây), nếu không bị coi là lỗi.

Lỗi: mã khác 2xx, nên kèm phong bì sau — PentaSync hiện **thông báo chung** cho người dùng và ghi
`message` vào log/bảng quản lý:

```json
{"error": {"code": "unauthorized", "message": "Sai hoặc thiếu token"}}
```

## `POST /v1/sessions/{session_id}/end` — báo kết thúc cuộc chat (không bắt buộc)

Gọi khi cuộc chat đóng, để bot nào giữ phiên phía nó biết mà dọn.

```json
{"reason": "user_exit"}
```

Trả **204** (không nội dung). Bot không hỗ trợ có thể trả 404/405 — PentaSync **bỏ qua**, không coi là lỗi.

`reason` là một trong:

| Giá trị | Nghĩa |
|---|---|
| `user_exit` | Người dùng chủ động thoát chat |
| `tier1_timeout` | Im lặng quá lâu, hệ thống tự kết thúc |
| `error_timeout` | Lỗi rồi không ai thao tác nên tự dọn |
| `mode_switch` | Chuyển sang xem thông tin bệnh viện |
| `cluster_reset` | Cả cụm về chế độ chờ |
| `blackout` | Quản lý tắt hẳn màn hình |
| `system_reset` | Quản lý reset hệ thống |
| `screen_removed` | Màn bị rút |
| `connection_test` | Phiên thử kết nối (do `/api/ai/test`), `session_id` dạng `test-...` |

## `GET /v1/health` — giám sát (không bắt buộc)

```json
{"status": "ok"}
```

Để IT giám sát máy chủ Bridge. PentaSync không dùng.

## Máy chủ mẫu để tham khảo và thử

Trong mã nguồn PentaSync có sẵn một máy chủ mẫu chạy đúng chuẩn này (trả lời bằng AI giả theo từ khoá):

```bat
cd backend
..\.venv\Scripts\python -m app.superdoc.bridge_reference --port 9000
..\.venv\Scripts\python -m app.superdoc.bridge_reference --port 9000 --token mat-khau   :: kiem tra xac thuc
```

Mã nguồn: `backend/app/superdoc/bridge_reference.py` (≈100 dòng, FastAPI). Thử bằng curl:

```bat
curl -s -X POST http://127.0.0.1:9000/v1/chat -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"s1\",\"screen\":4,\"locale\":\"vi-VN\",\"system_prompt\":\"x\",\"messages\":[{\"role\":\"user\",\"content\":\"may gio kham?\"}]}"
```

## Kiểm tra máy chủ của bạn có đúng chuẩn

1. `POST /v1/chat` với lịch sử 1 lượt → 200 + `{"reply": "..."}` (chuỗi, không rỗng).
2. Lịch sử nhiều lượt → trả lời đúng ngữ cảnh.
3. (Nếu dùng token) sai token → 401.
4. `POST /v1/sessions/{id}/end` → 204 (hoặc 404/405 nếu không hỗ trợ).
5. Nối vào PentaSync rồi chạy `POST /api/ai/test` (xem `ai_api.md`) → `ok: true`.

## Đổi phiên bản

Thay đổi phá vỡ tương thích sẽ ra `/v2`. Bản v1 sẽ không đổi nghĩa các trường đã có; trường mới (nếu có)
sẽ chỉ được **thêm** vào — máy chủ Bridge nên bỏ qua trường lạ.
