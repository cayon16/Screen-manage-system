# old_system — bản cũ chạy bằng trình duyệt Edge (chỉ để dự phòng)

Đây là **bản lưu trữ** của hệ thống PentaSync đời đầu: backend FastAPI + 5 cửa sổ Microsoft Edge do
`launcher/launcher.py` mở. Bản đang dùng là ứng dụng Qt ở thư mục `../system/` — xem
`../system/README.md`.

Giữ thư mục này chỉ để **chiếu tạm** nếu ứng dụng mới gặp sự cố không sửa kịp trên máy thật.
Sau buổi test ở công ty mà bản mới chạy đạt thì xoá cả thư mục này đi.

## Nhược điểm đã biết (lý do bị thay thế)

- **Lệch màn khi tỉ lệ hiển thị (scale) khác 100%.** Launcher lấy toạ độ theo pixel vật lý, còn Edge
  hiểu tham số theo pixel logic → ở scale 150%, cửa sổ to gấp rưỡi màn và lấn sang màn bên.
  Muốn dùng bản này thì đặt **mọi màn về scale 100%**.
- Không tự nhận số màn, không có màn quản lý, không có bàn phím tiếng Việt trên màn, giao diện nền tối cũ.
- Mỗi cửa sổ giải mã **toàn bộ** video chờ rồi chỉ hiện 1/5 → nặng máy hơn bản mới.

## Cách chạy

Cần **Python 3.10+** và **Microsoft Edge** trên máy.

```bat
cd old_system\backend
pip install -r requirements.txt

rem Video chờ không được chép kèm (175 MB). Chép file vào đúng đường dẫn sau:
rem     old_system\video\standby_wall.mp4
rem (lấy từ system\video\standby_wall.mp4 hoặc từ USB)

cd ..\launcher
python launcher.py --dry-run     rem in thứ tự màn, KHÔNG mở gì — đối chiếu với màn thật
python launcher.py               rem chạy thật, dừng bằng Ctrl+C
```

Thứ tự màn sai thì sửa `MONITOR_INDEX_OVERRIDE` trong `launcher/launcher.py` rồi chạy lại `--dry-run`.

## Có gì trong này

| Thư mục | Nội dung |
|---|---|
| `backend/` | Bản sao backend tại thời điểm tách ra — còn route `/screen/{id}` và mount `/src` phục vụ giao diện web (bản mới đã bỏ 2 thứ này) |
| `frontend/` | Giao diện web cũ: `public/index.html` + `src/*.js` (ws_client, state_router, các view) |
| `launcher/` | `launcher.py` — dò màn bằng thư viện `screeninfo` rồi mở 5 cửa sổ Edge đúng vị trí |

Không chép kèm: video chờ, database, log, thư mục `.venv`, bản đóng gói.
