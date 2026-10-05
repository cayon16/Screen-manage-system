# PentaSync — hệ thống màn hình hành lang bệnh viện

Một máy tính điều khiển tối đa 5 màn hiển thị: video chờ chạy liền mạch qua các màn, trình chiếu thông
tin bệnh viện, và chat với trợ lý ảo Superdoc (các phiên chat độc lập tuyệt đối với nhau). Viết bằng
Python: **PySide6 + QML** cho giao diện, **FastAPI** cho phần điều phối.

File này là **bản tóm tắt**. Chi tiết nằm ở các file dưới đây:

| Tài liệu | Dùng khi nào |
|---|---|
| **`descryption.md`** | **Giải thích từng file + cách test lại toàn bộ + cấu hình chi tiết** |
| **`HUONG_DAN_TEST.md`** | **Chuẩn bị máy và test trên màn thật — cầm theo file này** |
| `docs/architecture.md` | Viết code mới: kiến trúc, state machine, timer, các bẫy đã gỡ |
| `TIEN_DO.md` | Nhật ký triển khai, quyết định đã chốt, số đo |
| `test/README.md` | Danh sách script kiểm tra thủ công |
| `../descryption.txt` | Đặc tả gốc của khách |

## Vai trò các màn

App tự đếm màn đang cắm và gán vai trò (thứ tự trái → phải lấy theo sơ đồ màn trong Windows Settings →
Display):

- **6 màn trở lên:** màn chính của Windows là **màn quản lý**, các màn còn lại hiển thị.
- **5 màn trở xuống:** tất cả là màn hiển thị; bảng quản lý mở bằng **Ctrl+Shift+M**.
- Không màn nào cảm ứng → đánh số 1, 2, 3… trái → phải. Có màn cảm ứng → màn cảm ứng nhận **2, 4**,
  màn thường nhận **1, 3, 5**; màn thừa nhận số còn trống nhỏ nhất.

| Màn | Vai trò | Khi hệ thống thức |
|---|---|---|
| 1, 3, 5 | Trình chiếu, không nhận chạm | Slide (mỗi màn 2 slide) |
| 2 | Điều khiển (cảm ứng) | Menu: Thông tin bệnh viện / Chat |
| 4 | Chat (cảm ứng) | "Chạm để bắt đầu" |

Ít màn hơn thì chỉ những vai trò có mặt hoạt động (vd 1 màn cảm ứng duy nhất = màn 2).

Không ai tương tác trong 120 giây → mọi màn về **video chờ**. Chạm màn 2/4 **hoặc động vào chuột/bàn
phím máy chính** là cả hệ thống thức dậy.

**Phím tắt toàn cục** (bàn phím máy chính, bấm lúc nào cũng được): **Ctrl+Shift+M** bảng điều khiển ·
**Ctrl+Shift+I** nhận diện màn · **Ctrl+Shift+Q** thoát. Tổ hợp bị chương trình khác giữ thì app dùng
Ctrl+Alt+Shift + cùng chữ (log ghi rõ). Bảng điều khiển có thêm nút **Thoát ứng dụng**.

## Chạy

**Bản đóng gói (máy không cần Python):** bấm `PentaSync.exe` trong `dist\PentaSync\`, hoặc
`chay_thu_nhanh.bat` để test với thời gian chờ ngắn. Chuẩn bị máy (BIOS, sắp xếp màn, cảm ứng, card đồ
hoạ): `HUONG_DAN_TEST.md` phần B.

**Từ mã nguồn (máy dev, Python 3.10+):**

```bat
cd system
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt -r desktop\requirements.txt
.venv\Scripts\python desktop\run.py
```

App tự khởi động backend làm tiến trình con, tự dựng lại nếu backend chết, và tắt backend theo khi app
thoát (kể cả bị tắt ngang từ Task Manager).

> Khi ngồi lập trình trên chính máy đó, mọi lần gõ phím đều được tính là "có người dùng" nên hệ thống
> không bao giờ về video chờ. Tắt tạm: `set PENTASYNC_HOST_ACTIVITY=0` trước khi chạy.

## Cấu hình nhanh

| Muốn đổi | Ở đâu |
|---|---|
| Nội dung slide, tên bệnh viện | `content_manifest\slides.json` → mở lại app |
| Video chờ | chép đè `video\standby_wall.mp4` |
| Thời gian chờ | biến môi trường `PENTASYNC_TIER1_WARNING_SEC`, `PENTASYNC_TIER1_CLEANUP_SEC`, `PENTASYNC_TIER2_CLUSTER_IDLE_SEC` |
| Chat AI thật | `set SUPERDOC_PROVIDER=gemini` + `set GEMINI_API_KEY=…` (**không ghi khoá vào file trong dự án**) |

Đầy đủ (định dạng slides.json, lệnh nén video, đổi nhà cung cấp AI, card đồ hoạ): `descryption.md`
mục 11.

## Đóng gói

```bat
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\python packaging\build.py
```

Kết quả `dist\PentaSync\` (~600 MB, có kèm video và lát video đã cắt cho 5 màn). **Chép nguyên thư
mục** sang máy khác là chạy.

## Log và lịch sử chat

| | Mã nguồn | Bản exe |
|---|---|---|
| Log app | `desktop\pentasync_app_log.txt` | `data\pentasync_app_log.txt` |
| Log backend | `backend\pentasync_log.txt` | `data\pentasync_log.txt` |
| Lịch sử chat (SQLite) | `backend\pentasync.db` | `data\pentasync.db` |

## Test

```bat
cd backend && ..\.venv\Scripts\python -m pytest -q          :: 176 passed
cd ..     && .venv\Scripts\python -m pytest desktop\tests -q :: 151 passed
             .venv\Scripts\python -m ruff check .            :: All checks passed!
```

Không cần mạng, API key hay nhiều màn hình. Các bài kiểm tra tay (chạm thật, giả lập nhiều màn, kiểm
bản exe) và cách đọc kết quả: `descryption.md` mục 10 và `test\README.md`.

## Tình trạng

**Đã kiểm chứng trên máy dev** (1 màn 2560×1440 scale 150%, laptop có cả AMD tích hợp + NVIDIA):

| Chức năng | Kết quả |
|---|---|
| Cửa sổ khớp đúng màn (nguyên nhân lỗi lấn màn của bản cũ) | Khớp tuyệt đối ở scale 150% |
| Giả lập 6 màn: đánh thức, slide, chat, màn đen, reset, bảng điều khiển | 15/15 |
| Video chờ cắt lát + đồng bộ | Lệch 0,02–0,06 s |
| Tài nguyên: 5 cửa sổ video + bảng điều khiển + backend | CPU ~4,4%, RAM ~1,3 GB |
| Vẽ bằng card rời, xuất ra màn gắn đồ hoạ tích hợp | Lên hình, video chạy |
| Cố tình làm lệch 1 cửa sổ | Tự sửa về đúng màn trong ≤ 5 s |
| **Chạm thật của Windows**: đánh thức, menu, chat, gõ Telex, xoá, gửi, hỏi "còn ở đây", giữ lâu, 2 ngón | 23/23 × 3 lần |
| **2 người dùng 2 màn cảm ứng cùng lúc** (2 thiết bị chạm, chạm và gõ chồng thời gian) | 10/10 × 2 lần |
| Cảm ứng chưa gán màn | Có cảnh báo, màn không bị nhận nhầm là màn cảm ứng |
| Bản exe từ thư mục khác: cổng 8000 bị chiếm, giết backend giữa chừng, phím tắt, thoát sạch | 9/9 |

**Chưa thử được / còn phụ thuộc bên ngoài:**

- Nhiều màn **vật lý** khác độ phân giải/scale, màn cảm ứng thật, cắm/rút màn thật, card 4070 Ti S +
  đồ hoạ tích hợp — mục tiêu của buổi test, xem `HUONG_DAN_TEST.md`.
- API Superdoc thật (chưa có tài liệu); nội dung slide thật; video chờ siêu rộng hết méo.

Code cũ chạy bằng trình duyệt Edge đã chuyển sang `..\old_system\` — chỉ dùng làm phương án dự phòng.
