# Script kiểm tra thủ công

Đây **không phải** pytest. Là các bài cần mở cửa sổ thật / chạm thật — chạy tay khi cần.
Test tự động nằm ở `backend/tests/` và `desktop/tests/`.

Chạy từ thư mục `system`:

| Lệnh | Kiểm gì | Kỳ vọng |
|---|---|---|
| `.venv\Scripts\python test\xem_giao_dien.py` | dựng từng view với dữ liệu giả, chụp ảnh vào `test\anh\giao_dien\` (~10 s) | 15/15 |
| `.venv\Scripts\python test\gia_lap_nhieu_man.py` | giả lập 6 màn, chạy trọn luồng (thêm `--do-tai-nguyen` để đo CPU/RAM) | 15/15 |
| `.venv\Scripts\python test\kiem_tra_cham.py motman` | chạm thật 1 màn: đánh thức → chat → gõ Telex → gửi | 23/23 |
| `.venv\Scripts\python test\kiem_tra_cham.py chuagan` | cảm ứng chưa hiệu chỉnh trong Windows | 9/9 |
| `.venv\Scripts\python test\kiem_tra_cham.py haiman` | **2 người chạm 2 màn cùng lúc** — chạy 2–3 lần | 10/10 |
| `.venv\Scripts\python test\kiem_tra_exe.py [thư mục]` | bản đóng gói: đổi cổng, backend bị giết, phím tắt, thoát sạch | 9/9 |

Trong lúc chạy bài chạm, **đừng dùng chuột/bàn phím** — chạm giả lập lẫn với chạm thật sẽ ra kết quả
sai.

File dùng chung: `chung.py` (ghi kết quả, tìm phần tử QML, toạ độ thật, lớp `MayCham`) và
`gia_lap_cham.py` (thiết bị cảm ứng ảo của Windows — mỗi tiến trình 1 thiết bị, nên `haiman` chạy 2
tiến trình).

Giải thích chi tiết từng file: `../descryption.md` mục 9 và 10.
