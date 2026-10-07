# PentaSync

Hệ thống màn hình hành lang bệnh viện: **một máy tính điều khiển tối đa 5 màn hiển thị** — video chờ
chạy liền mạch qua các màn, trình chiếu thông tin bệnh viện, và chat với trợ lý ảo "Superdoc" trên các
màn cảm ứng.

Viết bằng Python: **PySide6 + QML** cho giao diện, **FastAPI** cho phần điều phối. Máy chạy không cần
cài Python (bản đóng gói `PentaSync.exe`), không cần mạng (AI mặc định chạy offline).

| Màn | Vai trò | Khi hệ thống thức |
|---|---|---|
| 1, 3, 5 | Trình chiếu, không nhận chạm | Slide thông tin bệnh viện |
| 2 | Điều khiển (cảm ứng) | Menu: Thông tin bệnh viện / Chat |
| 4 | Chat (cảm ứng) | "Chạm để bắt đầu" |

App **tự đếm số màn đang cắm** và gán vai trò tương ứng (1–5 màn đều chạy được; từ 6 màn thì màn chính
của Windows thành màn quản lý). Không ai tương tác trong 2 phút → mọi màn về video chờ.

## Cấu trúc

```
system/        ← CODE CHÍNH (bản đang dùng)
  desktop/       app màn hình: PySide6 + QML, đặt cửa sổ đúng từng màn
  backend/       FastAPI: máy trạng thái, chat, timer, database, cắt video
  packaging/     đóng gói PyInstaller → PentaSync.exe
  test/          script kiểm tra thủ công (chạm thật, giả lập nhiều màn)
old_system/    bản prototype cũ chạy bằng trình duyệt Edge — chỉ giữ làm dự phòng
design/        bản thiết kế giao diện đã duyệt (HTML)
descryption.txt đặc tả gốc của khách
```

Hai script lẻ ở thư mục gốc (`download.py` tải video mẫu, `test.py` nén ảnh) **không thuộc app**.

## Chạy từ mã nguồn

Cần Python 3.10+ trên Windows:

```bat
cd system
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt -r desktop\requirements.txt
.venv\Scripts\python desktop\run.py
```

App tự khởi động backend làm tiến trình con. Thoát bằng **Ctrl+Shift+Q**
(**Ctrl+Shift+M** bảng điều khiển · **Ctrl+Shift+I** nhận diện màn).

> Đang lập trình trên chính máy đó thì mọi lần gõ phím đều tính là "có người dùng" nên hệ thống không
> bao giờ về video chờ. Tắt tạm: `set PENTASYNC_HOST_ACTIVITY=0`.

## Những file KHÔNG có trong repo

Repo chỉ chứa mã nguồn. Các thứ nặng hoặc tự sinh đã bị loại (xem [.gitignore](.gitignore)):

| Thiếu | Cách có lại |
|---|---|
| `system/video/standby_wall.mp4` (video chờ, ~175 MB) | Đặt một video H.264 vào đúng đường dẫn đó (nên 3840×1080, ~30 fps). Thiếu video thì app vẫn chạy, chỉ không có màn hình chờ. |
| `system/dist/`, `system/build/` (bản đóng gói ~600 MB) | `.venv\Scripts\python packaging\build.py` |
| `system/backend/_cache/` (lát video đã cắt) | App tự cắt lại lần đầu (~4 phút) |
| `.venv/`, database, log | Tự sinh khi cài và chạy |

## Đóng gói

```bat
cd system
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\python packaging\build.py
```

Kết quả `system\dist\PentaSync\` — **chép nguyên thư mục** sang máy khác là chạy, không cần cài gì.

## Test

```bat
cd system\backend && ..\.venv\Scripts\python -m pytest -q          :: 301 passed
cd ..            && .venv\Scripts\python -m pytest desktop\tests -q :: 151 passed
                    .venv\Scripts\python -m ruff check .
```

Không cần mạng, API key hay nhiều màn hình. Các bài kiểm tra tay (chạm thật bằng `InjectTouchInput`,
giả lập 6 màn, kiểm bản đóng gói): [system/test/README.md](system/test/README.md).

## Cấu hình

| Muốn đổi | Ở đâu |
|---|---|
| Nội dung slide, tên bệnh viện | `system/backend/content_manifest/slides.json` |
| Video chờ | chép đè `system/video/standby_wall.mp4` |
| Thời gian chờ | biến môi trường `PENTASYNC_TIER1_WARNING_SEC`, `PENTASYNC_TIER1_CLEANUP_SEC`, `PENTASYNC_TIER2_CLUSTER_IDLE_SEC` |
| Chat AI (demo / nội bộ / Gemini · GPT · Claude) | API `/api/ai/*`, đổi lúc đang chạy — [system/docs/ai_api.md](system/docs/ai_api.md) |

> **Không bao giờ ghi API key vào file trong repo** — chỉ đặt qua biến môi trường. `ai_settings.json` (cấu hình AI
> lưu theo máy) đã nằm trong `.gitignore` và cũng không có chỗ nào để chứa khoá.

## Tài liệu

| File | Nội dung |
|---|---|
| [system/descryption.md](system/descryption.md) | **Giải thích từng file + hướng dẫn test + cấu hình chi tiết** |
| [system/HUONG_DAN_TEST.md](system/HUONG_DAN_TEST.md) | Chuẩn bị máy và test trên nhiều màn thật |
| [system/docs/ai_api.md](system/docs/ai_api.md) | Đổi AI (nội bộ / Gemini / GPT / Claude) bằng API |
| [system/docs/superdoc_bridge_api.md](system/docs/superdoc_bridge_api.md) | Chuẩn kết nối chatbot nội bộ (cho IT công ty) |
| [system/docs/architecture.md](system/docs/architecture.md) | Kiến trúc, máy trạng thái, các bẫy đã gỡ |
| [system/TIEN_DO.md](system/TIEN_DO.md) | Tiến độ, quyết định đã chốt, số đo thực tế |
| [descryption.txt](descryption.txt) | Đặc tả gốc của khách |

## Tình trạng

Đã kiểm chứng trên máy dev (1 màn 2560×1440 scale 150%): cửa sổ khớp đúng màn, giả lập 6 màn chạy trọn
luồng, chạm thật và 2 người chạm 2 màn cùng lúc, bản đóng gói tự phục hồi khi backend chết hoặc cổng bị
chiếm. **Chưa kiểm chứng:** nhiều màn vật lý khác độ phân giải/scale, màn cảm ứng thật, cắm/rút màn thật
— đang chờ buổi test trên máy khách.
