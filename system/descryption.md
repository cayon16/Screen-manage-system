# PentaSync — giải thích từng file và cách test

File này là **bản giải thích chi tiết**: mỗi file trong `system/` làm gì, vì sao nó tồn tại, và cách
tự kiểm tra mọi thứ. `README.md` chỉ là bản tóm tắt ngắn để chạy cho nhanh.

Đọc theo nhu cầu:

| Bạn muốn | Đọc mục |
|---|---|
| Hiểu hệ thống chạy thế nào trong 2 phút | [1. Toàn cảnh](#1-toàn-cảnh) |
| Biết file nào làm gì | [3](#3-desktop--ứng-dụng-màn-hình)–[9](#9-test--script-kiểm-tra-thủ-công) |
| Tự test lại toàn bộ | [10. Hướng dẫn test](#10-hướng-dẫn-test) |
| Đổi thời gian chờ, slide, video, AI | [11. Cấu hình chi tiết](#11-cấu-hình-chi-tiết) |
| Sửa một thứ cụ thể trong code | [12. Muốn sửa X thì vào đâu](#12-muốn-sửa-x-thì-vào-đâu) |
| Tránh làm hỏng những chỗ đã khó khăn mới xong | [13. Đừng sửa bừa](#13-đừng-sửa-bừa) |

Tài liệu khác: `HUONG_DAN_TEST.md` (cầm theo khi test trên máy thật, có cả phần chuẩn bị Windows),
`docs/architecture.md` (kiến trúc sâu, dành cho người viết code mới), `TIEN_DO.md` (tiến độ, quyết
định đã chốt).

---

## 1. Toàn cảnh

Hệ thống có **2 tiến trình** chạy cùng lúc, nhưng người dùng chỉ bấm **1 file** `PentaSync.exe`:

```
        ┌──────────────────────────── PentaSync.exe (app) ────────────────────────────┐
        │  desktop/  —  PySide6 + QML                                                 │
        │                                                                             │
        │  đọc màn hình thật ──► gán vai trò ──► mở 1 cửa sổ toàn màn hình / màn       │
        │  (monitors.py)        (layout.py)      (window_manager.py + qml/)           │
        │                                             │                               │
        │                                   mỗi cửa sổ 1 WebSocket                    │
        └─────────────────────────────────────────────│───────────────────────────────┘
                                                      │  ws://127.0.0.1:8000/ws/{số màn}
        ┌─────────────────────────────────────────────▼───────────────────────────────┐
        │  backend/ — FastAPI (tiến trình con, app tự khởi động và tự canh)           │
        │                                                                             │
        │  mọi sự kiện ──► 1 hàng đợi duy nhất ──► máy trạng thái ──► gửi view cho màn │
        │  (chạm, chat,      (cluster_controller)    (screen_fsm)                      │
        │   timer, admin)                                                             │
        └─────────────────────────────────────────────────────────────────────────────┘
```

Vì sao tách 2 tiến trình: theo đặc tả, sau này backend có thể chuyển lên server thật, app màn hình
vẫn chỉ là client WebSocket — không phải viết lại. Backend chết thì app tự dựng lại (≤ 10 s) mà màn
hình không tắt.

**Nguyên tắc quan trọng nhất:** app màn hình **không tự quyết định** gì về trạng thái. Chạm vào màn
→ gửi lên backend → backend trả về "màn 2 giờ hiện MENU" → app hiện MENU. Nhờ vậy 5 màn không bao
giờ lệch nhau, và toàn bộ luật (timer, đóng chat, đánh thức theo cặp) chỉ nằm ở **một chỗ**.

---

## 2. Bản đồ thư mục

```
system/
  descryption.md           ← file này
  README.md                tóm tắt: cách chạy, cấu hình
  HUONG_DAN_TEST.md         cầm theo khi test máy thật (chuẩn bị Windows, danh sách kiểm)
  TIEN_DO.md                tiến độ + quyết định đã chốt (đọc trước khi làm tiếp)
  docs/architecture.md      kiến trúc chi tiết cho người viết code
  ruff.toml                 cấu hình dò lỗi tĩnh

  desktop/                  ỨNG DỤNG MÀN HÌNH (PySide6 + QML) — mục 3, 4
  backend/                  ĐIỀU PHỐI (FastAPI) — mục 5
  video/                    video chờ — mục 6
  packaging/                đóng gói ra .exe — mục 7
  test/                     script kiểm tra thủ công (cần mở cửa sổ thật) — mục 9

  .venv/                    môi trường Python (không chép đi đâu)
  dist/, build/             kết quả đóng gói (máy tự sinh)
```

Không có trong `system/` nữa: code cũ chạy bằng trình duyệt Edge đã chuyển sang
`outsource/old_system/` (chỉ để dự phòng, xem `old_system/README.md`).

---

## 3. `desktop/` — ứng dụng màn hình

### Khởi động

**`run.py`** (62 dòng) — **điểm chạy duy nhất**. Luôn gọi file này, đừng gọi `main.py` trực tiếp.
- Thêm `backend/` và `system/` vào đường dẫn import.
- **Chọn cổng trước khi import cấu hình:** thử nối `127.0.0.1:8000`; nếu có ai đang chiếm (thường là
  bản PentaSync cũ chưa tắt, hoặc chương trình khác) thì xin cổng trống của hệ điều hành và đặt biến
  môi trường `PENTASYNC_PORT`. Thứ tự này quan trọng: `config.py` đọc biến đó **lúc import**, nên
  chọn cổng muộn hơn là vô nghĩa.
- `run.py --backend` → chỉ chạy backend (dùng cho tiến trình con).

**`backend_entry.py`** (23 dòng) — chạy uvicorn với `app.main:app`, host/port lấy từ config. Tách
riêng để bản đóng gói (`PentaSync.exe --backend`) và bản mã nguồn dùng chung một đường.

**`main.py`** (161 dòng) — dựng môi trường rồi bàn việc cho `WindowManager`:
- **Log** ra file có xoay vòng (5 MB), bắt cả lỗi không ai đỡ (`sys.excepthook`) và thông báo của Qt.
  Tiếng ồn lúc tắt máy phát video bị hạ xuống DEBUG để log không đầy lỗi giả.
- **Chỉ cho chạy 1 bản** (`QLockFile` trong thư mục tạm) — 2 bản cùng chạy sẽ tranh cổng và tranh màn.
- **`_prefer_discrete_gpu()`** — ghi `HKCU\...\DirectX\UserGpuPreferences` để Windows luôn vẽ bằng
  card rời. Máy có cả đồ hoạ tích hợp lẫn card rời hay chọn sai, làm video chờ giật.
- **`_keep_displays_awake()`** — `SetThreadExecutionState`: màn hình hành lang không được tự ngủ.
- Nạp font Be Vietnam Pro từ `fonts/` (máy khách có thể không có font này).
- **Phím tắt toàn cục**: `Ctrl+Shift+M` bảng điều khiển · `Ctrl+Shift+I` nhận diện màn ·
  `Ctrl+Shift+Q` thoát. Đăng ký ở cấp hệ điều hành nên ăn cả khi app không được chọn — cửa sổ toàn
  màn hình không có nút đóng, không có phím tắt là không thoát được.
- Tắt `quitOnLastWindowClosed`: rút màn làm đóng cửa sổ, không được hiểu là "thoát app".

### Đặt cửa sổ đúng màn (phần đã gây lỗi ở bản cũ)

**`monitors.py`** (203 dòng) — đọc màn hình thật, trả về danh sách `ScreenEntry`:
- Từ Qt: tên (`\\.\DISPLAY1`), khung hình, độ phân giải, scale, màn nào là màn chính.
- Từ Windows: `QScreen` → `HMONITOR` (qua `nativeInterface`), toạ độ **pixel vật lý**
  (`GetMonitorInfoW`), tên card đang xuất hình (`EnumDisplayDevicesW`).
- **`touch_devices()`** — `GetPointerDevices`: liệt kê thiết bị cảm ứng và `HMONITOR` mà Windows gán
  cho nó → biết chính xác màn nào có cảm ứng.
- **`touch_problem()`** — phát hiện trường hợp hay gặp: có cảm ứng nhưng Windows gán tất cả vào màn
  chính, tức là **chưa chạy hiệu chỉnh** (Control Panel → Tablet PC Settings → Setup). Chưa hiệu
  chỉnh thì chạm màn 4 có thể bấm sang màn khác — lỗi của Windows, không phải của app, nhưng app
  phải cảnh báo chứ không im lặng gán sai vai trò.

**`layout.py`** (106 dòng) — **hàm thuần** (không đụng Qt, không đụng Windows), nên test được toàn bộ
bằng bảng ca. Nhận danh sách màn → trả về: màn nào là màn quản lý, màn nào mang vai trò 1–5, thứ tự
trái→phải để cắt video.

Luật gán vai trò (chốt với khách):

```
Số màn ≥ 6 : màn chính của Windows = MÀN QUẢN LÝ, 5 màn còn lại trái→phải = màn hiển thị
Số màn ≤ 5 : tất cả là màn hiển thị

Trong các màn hiển thị:
  không màn nào cảm ứng → đánh số 1,2,3,4,5 lần lượt trái→phải
  có màn cảm ứng        → màn cảm ứng nhận 2, 4 (trái→phải)
                          màn không cảm ứng nhận 1, 3, 5 (trái→phải)
                          thừa ra thì nhận số trống nhỏ nhất còn lại
```

**`win32.py`** (168 dòng) — những việc Qt không làm được, gọi trực tiếp Windows:
- `window_rect`, `monitor_of_window`, `rect_matches` — **đo vị trí thật** của cửa sổ bằng toạ độ vật
  lý để tự kiểm "cửa sổ này có đúng nằm trọn trong màn của nó không".
- `force_rect` — nếu lệch thì ép về đúng chỗ (`SetWindowPos`), không cần Qt đồng ý.
- `raise_window` — nâng cửa sổ lên trên **mà không lấy focus**. Dùng cho màn chính: thứ khác nổi đè
  lên (hộp thoại Windows, thanh taskbar) sẽ ăn mất chạm.
- `set_topmost` — giữ trên cùng, dùng cho các màn không phải màn chính.
- `disable_touch_feedback` — tắt vòng tròn xanh Windows vẽ khi chạm; màn hành lang không cần.
- `GlobalHotkeys` — `RegisterHotKey` + lọc `WM_HOTKEY`. Nếu tổ hợp bị chương trình khác giữ thì tự
  đổi sang `Ctrl+Alt+Shift+…` và ghi log tổ hợp thật, chứ không âm thầm mất phím tắt.

**`window_manager.py`** (473 dòng) — trái tim phần hiển thị:
- Mỗi màn hiển thị = 1 cửa sổ QML: gán `setScreen()` → `setGeometry(screen.geometry())` →
  `showFullScreen()`. Không tự nhân scale — đây chính là lỗi của bản cũ (bản cũ tự tính toạ độ nên
  màn scale 150% bị cửa sổ to gấp rưỡi, lấn sang màn bên).
- **Tự canh mỗi 5 giây** (và 0,7 s + 2,5 s sau khi vừa mở): đo vị trí thật; lệch thì đặt lại rồi ép
  bằng `force_rect`; màn không phải màn chính giữ topmost, màn chính thì `raise_window`.
- Cắm/rút màn → chờ cho Windows ổn định (3 s) → gán lại vai trò → mở lại cửa sổ → `POST /api/layout`
  cho backend biết số màn mới (để cắt lại video và bật/tắt vai trò).
- **`_WakeOnPress`** — bắt chạm/bấm chuột trên màn 2/4 để đánh thức. Phải tự nhận ra "điểm vừa nhấn
  xuống" cả trong `TouchBegin` **và** `TouchUpdate`: Windows gộp mọi màn cảm ứng thành **một** thiết
  bị, nên khi 2 người chạm gần nhau thì chạm thứ hai đến dưới dạng `TouchUpdate`.
- **`TelexBridge`** — QML gửi từng phím lên, Python trả lại chuỗi tiếng Việt đã ghép dấu.
- Mở/đóng bảng điều khiển, lớp "nhận diện màn", reset hệ thống (đóng chat + tạo lại cửa sổ).

### Nói chuyện với backend

**`screen_client.py`** (268 dòng) — mỗi màn hiển thị 1 cái. `QWebSocket` tự nối lại (1→5 s), phơi
cho QML: view đang phải hiện, dữ liệu kèm theo, lịch sử chat (`ChatModel` cho `ListView`), trạng thái
"đang chờ AI". Ghi lại **thời điểm nhận** gói đồng bộ video — không đo lúc tạo view, vì máy phát
video mất khoảng nửa giây để nạp, đo sai thời điểm là 5 màn lệch nhau.

**`admin_client.py`** (86 dòng) — WebSocket `/ws/admin` cho bảng điều khiển: nhận ảnh chụp trạng thái
toàn cụm, gửi lệnh (chọn slide, về video chờ, màn đen, reset).

**`standby_sync.py`** (106 dòng) — giữ video chờ của mọi màn khớp nhau theo đồng hồ chung của backend:
lệch > 0,3 s thì nhảy thẳng, lệch nhỏ thì chỉnh tốc độ phát 0,85–1,15 cho mượt. Yêu cầu **2 lần đo
liên tiếp** đều lệch xa mới nhảy — một lần đọc vị trí lỗi của QtMultimedia từng gây nhảy oan.

**`telex.py`** (244 dòng) — bộ gõ Telex tiếng Việt, **hàm thuần** (`type_key(text, key) -> text`),
nên test được hàng loạt từ bằng pytest. Xử lý dấu thanh (s f r x j), `z` xoá dấu, `aa â`, `aw ă`,
`ow ơ`, `dd đ`, và đặt dấu đúng nguyên âm khi từ có 2–3 nguyên âm.

**`backend_process.py`** (228 dòng) — chạy backend làm tiến trình con và canh cho nó sống:
- Hỏi `/healthz` mỗi giây. Backend chết → khởi động lại, giãn dần tới 10 s.
- Mỗi lần backend vừa sẵn sàng thì phát `ready`; app **gửi lại bố cục màn** (backend mới sinh ra
  không biết đang có mấy màn).
- Gắn tiến trình con vào **Job Object** của Windows với cờ `KILL_ON_JOB_CLOSE`: app bị tắt kiểu gì
  (kể cả Task Manager) thì backend chết theo, không để lại tiến trình mồ côi giữ cổng 8000.

**`config.py`** (44 dòng) — đường dẫn, địa chỉ backend, tên bệnh viện (đọc từ
`content_manifest/slides.json`), thời gian chờ ổn định khi cắm/rút màn, chu kỳ đồng bộ video.

---

## 4. `desktop/qml/` — giao diện

Giao diện dựng theo bản thiết kế đã duyệt, **nền trắng, chữ to, ít chi tiết**. Mọi màn vẽ trong khung
cố định 1920×1080 rồi co giãn cho vừa — nên màn 4K hay màn 1080p đều ra đúng tỷ lệ.

**Cửa sổ**

| File | Dòng | Làm gì |
|---|---|---|
| `DisplayWindow.qml` | 97 | 1 cửa sổ toàn màn hình của 1 màn hiển thị. `Loader` đổi view theo lệnh backend. Không viền, **không nhận focus** (`WindowDoesNotAcceptFocus`) — chi tiết này là cái cứu việc 2 người chạm 2 màn cùng lúc, xem mục 12. Tự ẩn con trỏ chuột khi không ai cử động. |
| `ManagementWindow.qml` | 635 | Bảng điều khiển: sơ đồ màn + trạng thái từng màn, chọn slide cho màn 1/3/5, "Đưa về video chờ", "Tắt hẳn (màn đen)", "Reset hệ thống", "Nhận diện màn", số liệu chat trong ngày. Có màn thứ 6 thì chiếm trọn màn chính, ít hơn thì mở dạng cửa sổ 1280×720. |

**Các view (một view = một thứ người đi hành lang nhìn thấy)**

| File | Dòng | Hiện khi |
|---|---|---|
| `StandbyView.qml` | 74 | Chế độ chờ — mỗi màn phát đúng phần của mình trong một khung hình chung. |
| `MenuView.qml` | 167 | Màn 2 vừa được đánh thức: "Thông tin bệnh viện" / "Chat". |
| `SlideControlView.qml` | 221 | Màn 2 chọn slide cho các màn trình chiếu. |
| `SlideView.qml` | 204 | Màn 1/3/5 — slide chữ, hoặc ảnh/video lấp cả màn. |
| `PromptChatView.qml` | 100 | Màn 4 khi hệ thống thức: chạm đâu cũng vào chat. |
| `ChatView.qml` | 410 | Khung chat với Superdoc + bàn phím trên màn. |
| `BlackoutView.qml` | 6 | "Tắt hẳn" từ bảng điều khiển: đen hoàn toàn, **dừng hẳn** máy phát video cho máy nghỉ. |
| `ConnectingView.qml` | 57 | Chưa nối được backend. Chờ 2 giây mới hiện, để lần backend khởi động lại nhanh không nhấp nháy. |

**Thành phần dùng lại**

| File | Dòng | Làm gì |
|---|---|---|
| `Stage.qml` | 22 | Khung vẽ 1920×1080 co giãn đều — nền tảng của toàn bộ việc "màn nào cũng đúng tỷ lệ". |
| `Theme.qml` | 41 | Bảng màu + cỡ chữ (singleton). Sửa màu toàn hệ thống chỉ ở đây. |
| `AppButton.qml` | 70 | Nút chạm: primary / secondary / danger. |
| `OnScreenKeyboard.qml` | 126 | Bàn phím QWERTY trên màn. Chỉ phát tín hiệu phím, việc ghép dấu do `telex.py` làm. |
| `KeyButton.qml` | 57 | 1 phím — nhận **ngay lúc chạm xuống** để gõ nhanh không sót. |
| `ChatBubble.qml` | 46 | 1 lượt hội thoại (người dùng bên phải, Superdoc bên trái). |
| `TypingDots.qml` | 37 | "Superdoc đang soạn câu trả lời" — 3 chấm nhấp nháy. |
| `Tier1Dialog.qml` | 134 | "Bạn còn muốn tiếp tục trò chuyện không?" — đếm ngược, chạm đâu cũng là "còn". |
| `ConfirmSwitchDialog.qml` | 111 | Đang chat mà bấm sang xem thông tin → xác nhận, vì chat sẽ bị xoá. |
| `IdentifyOverlay.qml` | 150 | Lớp nhận diện màn: số màn thật to, độ phân giải, scale, có cảm ứng hay không, **viền ôm sát 4 mép** — nhìn viền là biết cửa sổ có khớp màn hay không. |
| `Icon.qml`, `Icons.qml`, `IconTile.qml`, `HospitalMark.qml` | 31/22/24/29 | Biểu tượng nét vẽ từ path SVG và ô nền cho chúng. |
| `qmldir` | — | Khai báo module `PentaSync` để các file trên import được nhau. |

`fonts/` — Be Vietnam Pro (giấy phép OFL, đã kèm `OFL.txt`).

---

## 5. `backend/` — điều phối

### `app/` — nền

| File | Dòng | Làm gì |
|---|---|---|
| `main.py` | 62 | Dựng FastAPI: mở database, chọn AI, khởi động vòng lặp điều phối, bắt đầu cắt video, bật theo dõi thao tác máy chủ. Tắt thì dọn ngược lại. |
| `config.py` | 112 | **Mọi hằng số ở đây**: cổng, vai trò màn, thời gian timer (đọc được từ biến môi trường để test nhanh), đường dẫn video/database/log, chọn AI + câu lệnh hệ thống cho AI. Bản đóng gói thì nội dung sửa được nằm cạnh file exe, còn database/log vào `data\`. |
| `logging_setup.py` | 19 | Log ra file xoay vòng 10 MB. |
| `schemas.py` | 152 | **Toàn bộ giao thức WebSocket** bằng Pydantic: app gửi lên (chạm, tin chat, xác nhận, chọn slide, lệnh admin) và backend gửi xuống (đổi trạng thái, hỏi xác nhận, lỗi, phiên đã đóng, ảnh chụp trạng thái). Sai kiểu là bị chặn ngay ở cửa. |
| `commands.py` | 156 | 17 loại lệnh nội bộ — **từ vựng duy nhất** mà vòng lặp điều phối hiểu. Mọi thứ (chạm, timer, AI trả lời, admin, cắm rút màn) đều phải biến thành một lệnh trong danh sách này. |
| `db.py` | 152 | SQLite 2 bảng (`chat_sessions`, `chat_messages`): lưu **toàn bộ** lịch sử chat theo yêu cầu đặc tả, cộng số liệu trong ngày cho bảng điều khiển. Chạy trong luồng riêng để không chặn vòng lặp. |

### `app/routes/` — cửa ra vào

| File | Dòng | Làm gì |
|---|---|---|
| `ws_routes.py` | 120 | `/ws/{số màn}` cho từng màn, `/ws/admin` cho bảng điều khiển. Đổi tin nhắn thành lệnh. **`/ws/admin` phải khai báo trước `/ws/{screen_id}`**, nếu không route kia bắt mất chữ "admin" rồi từ chối. |
| `http_routes.py` | 96 | `/healthz` (app dùng để canh backend), `/standby-video` + `/standby-video/{số màn}/{lát}`, `POST /api/layout` (báo bố cục màn), `/media/{tên file}` (ảnh/video của slide). |

### `app/state/` — luật vận hành

| File | Dòng | Làm gì |
|---|---|---|
| `cluster_controller.py` | 744 | **Người viết duy nhất** vào trạng thái. Một vòng lặp asyncio đọc hàng đợi lệnh và làm theo thứ tự, nên không bao giờ có 2 việc sửa trạng thái cùng lúc. Ở đây có: đánh thức theo cặp 2↔4, mở/đóng phiên chat, gọi AI, timer, màn đen, reset, ảnh chụp trạng thái cho bảng điều khiển. |
| `screen_fsm.py` | 136 | **Bảng chuyển trạng thái thuần** `transition(vai trò, trạng thái, sự kiện)`. Không mạng, không thời gian, không I/O → test cực nhanh và chắc. Đây là chỗ trả lời "chạm vào lúc này thì màn chuyển sang gì". |
| `layout.py` | 72 | `ClusterLayout`: vai trò nào đang có, nằm thứ mấy trái→phải. Mặc định đủ 5 màn. |
| `chat_session.py` | 211 | 1 phiên chat: lịch sử, lượt đang chờ AI, timer Tier‑1, ghi database. |
| `slide_band.py` | 163 | Dải slide đọc từ `content_manifest/slides.json`; chỉ trả nút của những màn trình chiếu **đang có**; `reset()` về slide mặc định. |
| `timers.py` | 45 | `ResettableTimer` — hẹn giờ có thể lùi lại từ đầu (dùng cho Tier‑1/Tier‑2). |
| `sync_clock.py` | 30 | Đồng hồ chung để 5 màn phát video chờ khớp nhau. |
| `video_slicer.py` | 198 | Cắt 1 video ngang thành N lát bằng ffmpeg (`imageio-ffmpeg`, không cần cài gì thêm). Cắt xong nhớ lại theo **nội dung file** (kích thước + 1 MiB đầu/cuối) nên chép video sang chỗ khác không phải cắt lại. Chạy ở ưu tiên thấp để không làm giật video đang chiếu. |
| `host_activity.py` | 62 | Người đang ngồi máy chủ dùng chuột/bàn phím (`GetLastInputInfo`) → coi như có người, không đưa màn về chế độ chờ. Đang màn đen thì bỏ qua. |
| `ws_manager.py` | 53 | Giữ danh sách kết nối, gửi tin cho 1 màn hoặc tất cả. |

### `app/superdoc/` — AI

| File | Dòng | Làm gì |
|---|---|---|
| `base.py` | 50 | Khuôn giao tiếp (`Protocol`) + kiểu lỗi. Đổi nhà cung cấp AI chỉ cần viết 1 class theo khuôn này. |
| `factory.py` | 30 | Chọn nhà cung cấp theo biến môi trường `SUPERDOC_PROVIDER`. |
| `mock_provider.py` | 109 | **Mặc định**: AI giả, không cần mạng, không cần API key — chạy và test được trọn luồng. |
| `gemini_provider.py` | 89 | Gọi Gemini thật. Key **chỉ** lấy từ biến môi trường `GEMINI_API_KEY`, không bao giờ ghi vào file trong dự án. |

---

## 6. Nội dung và dữ liệu

| Đường dẫn | Là gì | Sửa được? |
|---|---|---|
| `video/standby_wall.mp4` | Video chờ (1 khung hình chung, app tự cắt cho N màn) | Chép đè file cùng tên |
| `backend/content_manifest/slides.json` | Nội dung slide + `hospital_name` | Có — mở lại app là áp dụng |
| `backend/content_manifest/media/` | Ảnh/video của slide | Có |
| `backend/pentasync.db` | Lịch sử chat (SQLite) | Máy tự sinh, đừng sửa tay |
| `backend/pentasync_log.txt` | Log backend | Máy tự sinh |
| `desktop/pentasync_app_log.txt` | Log app | Máy tự sinh |
| `backend/_cache/standby_slices/` | Lát video đã cắt (~225 MB) | Xoá được, app cắt lại (~4 phút) |

Ở **bản đóng gói**, database/log/lát video nằm trong `dist\PentaSync\data\`, còn
`content_manifest\` và `video\` nằm cạnh `PentaSync.exe` để người vận hành sửa được.

---

## 7. `packaging/` — đóng gói

| File | Làm gì |
|---|---|
| `build.py` (76 dòng) | Chạy PyInstaller rồi chép kèm `content_manifest/`, `video/`, lát video đã cắt cho 5 màn, `chay_thu_nhanh.bat`. Ra `dist/PentaSync/` (~600 MB), **chép cả thư mục** sang máy khách. |
| `PentaSync.spec` (72 dòng) | Cấu hình PyInstaller: một-thư-mục, không cửa sổ console, gói QML + font + backend. |
| `chay_thu_nhanh.bat` | Chạy exe với thời gian chờ **rút ngắn** (10 s / 10 s / 30 s) để test timer mà không phải đợi 2 phút mỗi lần. |

---

## 8. Test tự động — file nào kiểm gì

### `backend/tests/` — 176 test

| File | Kiểm |
|---|---|
| `conftest.py` | Dựng sẵn controller/AI giả cho các test khác. |
| `test_screen_fsm.py` | Bảng chuyển trạng thái của từng vai trò màn (nhiều ca nhất, chạy nhanh nhất). |
| `test_cluster_controller.py` | Luồng thật: đánh thức theo cặp, đóng chat, thao tác máy chủ, Tier‑2. |
| `test_chat_flow.py` | Trọn vòng hỏi–đáp: gửi, chờ AI, trả lời, lỗi AI, Tier‑1 nhắc rồi dọn. |
| `test_layout_admin.py` | Bố cục 1–5 màn + lệnh bảng điều khiển + màn đen + reset. |
| `test_ws_protocol.py` | Tin nhắn sai kiểu/không phải JSON/`screen_id` không khớp **không được** làm sập kết nối. |
| `test_admin_routes.py` | `/ws/admin`, `POST /api/layout`, route lát video. |
| `test_slide_band.py` | Đọc `slides.json`, chọn slide, chỉ hiện nút của màn đang có. |
| `test_timers.py`, `test_host_activity.py` | Hẹn giờ lùi được; đọc thao tác máy chủ. |
| `test_superdoc.py` | AI giả + xử lý lỗi của nhà cung cấp. |
| `test_video_slicer.py` | Dựng lệnh ffmpeg đúng, nhớ theo nội dung file, không cắt lại vô ích. |

### `desktop/tests/` — 151 test

| File | Kiểm |
|---|---|
| `test_layout.py` | **Luật gán vai trò** — bảng ca 1→7 màn, 0/1/2/3 màn cảm ứng, màn chính nằm giữa dãy. |
| `test_telex.py` | Gõ Telex: từ thường gặp, đặt dấu đúng nguyên âm, xoá dấu, xoá lùi. |
| `test_standby_sync.py` | Thuật toán đồng bộ video: khi nào nhảy, khi nào chỉnh tốc độ, vòng qua cuối video. |
| `test_screen_client.py` | Nhận tin backend → đổi view/lịch sử chat đúng; tự nối lại. |
| `test_monitors.py` | Đọc màn + phát hiện cảm ứng chưa hiệu chỉnh. |
| `test_win32.py` | So khung cửa sổ, dung sai, tổ hợp phím tắt. |
| `test_wake_filter.py` | Nhận ra "vừa chạm xuống" trong cả `TouchBegin` và `TouchUpdate` (ca 2 người chạm cùng lúc). |
| `test_run.py` | Chọn cổng khi 8000 bị chiếm. |

---

## 9. `test/` — script kiểm tra thủ công

Đây **không phải** pytest. Là các bài cần **mở cửa sổ thật, chạm thật** — pytest không làm được.

| File | Dòng | Làm gì |
|---|---|---|
| `chung.py` | 185 | Phần dùng chung: ghi kết quả từng mục, chạy các bước tuần tự, tìm phần tử trong cây QML, đổi sang toạ độ pixel thật để chạm, chụp ảnh cửa sổ, lớp `MayCham`. |
| `gia_lap_cham.py` | 138 | **Thiết bị cảm ứng ảo của Windows** (`InitializeTouchInjection` / `InjectTouchInput`): chạm thật mà không cần màn cảm ứng. Mỗi tiến trình chỉ tạo được 1 thiết bị → muốn giả lập 2 màn cảm ứng thì chạy 2 tiến trình, đúng như 2 màn thật. |
| `kiem_tra_cham.py` | 294 | Bài chạm: `motman` (1 màn, 23 mục: đánh thức → menu → chat → gõ Telex → xoá → gửi → hộp "còn ở đây" → giữ lâu → 2 ngón), `chuagan` (cảm ứng chưa hiệu chỉnh), `haiman` (**2 người chạm 2 màn cùng lúc**). |
| `gia_lap_nhieu_man.py` | 195 | Giả lập N màn trên 1 màn thật, chạy trọn luồng: đánh thức, slide, chat, màn đen, reset, bảng điều khiển. `--do-tai-nguyen` thì đo thêm CPU/RAM. |
| `xem_giao_dien.py` | 255 | Dựng từng view với dữ liệu giả rồi chụp ảnh — xem giao diện mà không cần backend. |
| `kiem_tra_exe.py` | 102 | Kiểm bản đóng gói: 2 tiến trình lên, cửa sổ khớp màn, cổng 8000 bị chiếm thì tự đổi, giết backend thì tự dựng lại và nhận lại bố cục, phím tắt thoát, không sót tiến trình, log không có lỗi lạ. |

---

## 10. Hướng dẫn test

Chạy **từ thư mục `system`**, dùng Python trong `.venv`. Trên Windows dùng dấu `\`.

### Bước 0 — chuẩn bị (làm 1 lần)

```bat
cd system
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
.venv\Scripts\python -m pip install -r desktop\requirements.txt
.venv\Scripts\python -m pip install pytest ruff psutil pyinstaller
```

Không cần mạng, không cần API key, không cần nhiều màn hình cho các bước 1–4.

### Bước 1 — test tự động (30 giây) ⟵ *luôn chạy bước này trước*

```bat
cd backend
..\.venv\Scripts\python -m pytest -q      :: kỳ vọng: 176 passed
cd ..
.venv\Scripts\python -m pytest desktop\tests -q   :: kỳ vọng: 151 passed
```

Có dòng đỏ thì **dừng lại sửa**, đừng chạy tiếp các bước sau.

### Bước 2 — dò lỗi tĩnh (5 giây)

```bat
.venv\Scripts\python -m ruff check .
.venv\Scripts\pyside6-qmllint -I desktop\qml desktop\qml\*.qml desktop\qml\PentaSync\*.qml
```

Kỳ vọng: `All checks passed!` và qmllint không in gì. Bắt được: import thừa, biến không dùng, code
chết, lỗi cú pháp QML, thuộc tính QML gán 2 lần.

### Bước 3 — xem giao diện bằng mắt (1 phút)

```bat
.venv\Scripts\python test\xem_giao_dien.py
```

Dựng 15 view với dữ liệu giả và chụp ảnh vào `test\anh\`. Mở thư mục đó xem: chữ có bị tràn, bàn phím
có che khung chat, màu có đúng. Kỳ vọng `15/15 muc dat`.

### Bước 4 — chạy trọn luồng không cần nhiều màn (2 phút)

```bat
.venv\Scripts\python test\gia_lap_nhieu_man.py
.venv\Scripts\python test\gia_lap_nhieu_man.py --do-tai-nguyen   :: thêm đo CPU/RAM
```

Giả lập 6 màn, đi hết: đánh thức → menu → slide → chat → hỏi "còn ở đây" → màn đen → reset → bảng
điều khiển. Kỳ vọng `15/15 muc dat`. Đo tài nguyên: **đóng hết game/ứng dụng nặng** trước khi đo,
nếu không số CPU sai.

### Bước 5 — chạm thật (3 phút)

```bat
.venv\Scripts\python test\kiem_tra_cham.py motman     :: kỳ vọng 23/23
.venv\Scripts\python test\kiem_tra_cham.py chuagan    :: kỳ vọng  9/9
.venv\Scripts\python test\kiem_tra_cham.py haiman     :: kỳ vọng 10/10
```

Dùng thiết bị cảm ứng ảo của Windows nên **không cần màn cảm ứng**. `haiman` là bài quan trọng nhất:
2 người chạm và gõ chồng thời gian trên 2 màn — nên chạy **2–3 lần** vì đây là loại lỗi thỉnh thoảng
mới lộ.

Trong lúc chạy **đừng dùng chuột/bàn phím**: chạm giả lập và chạm thật lẫn vào nhau sẽ ra kết quả sai.

### Bước 6 — bản đóng gói (10 phút)

```bat
.venv\Scripts\python packaging\build.py
.venv\Scripts\python test\kiem_tra_exe.py                  :: kỳ vọng 9/9
.venv\Scripts\python test\kiem_tra_exe.py D:\PentaSync     :: kiểm bản vừa chép sang USB
```

Bài này cố tình phá: chiếm trước cổng 8000, giết backend giữa chừng, thoát bằng phím tắt — rồi kiểm
app có tự phục hồi và tắt sạch không.

### Bước 7 — máy thật, nhiều màn

Những thứ **không thể** kiểm ở máy 1 màn: nhiều màn khác độ phân giải/scale, màn cảm ứng thật, cắm
rút màn thật, card 4070 Ti Super + đồ hoạ tích hợp. Làm theo `HUONG_DAN_TEST.md` — có sẵn phần chuẩn
bị Windows (quan trọng nhất: **sắp xếp màn** và **hiệu chỉnh cảm ứng**) và danh sách kiểm 11 nhóm.

### Bảng tóm tắt

| Bước | Lệnh | Mất | Kỳ vọng |
|---|---|---|---|
| 1 | `pytest -q` (backend, rồi desktop) | 30 s | 176 + 151 passed |
| 2 | `ruff check .` + `pyside6-qmllint` | 5 s | sạch |
| 3 | `test\xem_giao_dien.py` | 1 ph | 15/15 |
| 4 | `test\gia_lap_nhieu_man.py` | 2 ph | 15/15 |
| 5 | `test\kiem_tra_cham.py motman / chuagan / haiman` | 3 ph | 23/23 · 9/9 · 10/10 |
| 6 | `packaging\build.py` + `test\kiem_tra_exe.py` | 10 ph | 9/9 |
| 7 | `HUONG_DAN_TEST.md` | 60–75 ph | trên máy thật |

### Hỏng thì đọc ở đâu

1. **Log app**: `desktop\pentasync_app_log.txt` (bản exe: `data\pentasync_app_log.txt`) — cửa sổ, màn
   hình, phím tắt, backend sống/chết.
2. **Log backend**: `backend\pentasync_log.txt` (bản exe: `data\pentasync_log.txt`) — trạng thái từng
   màn, chat, timer, bố cục.
3. Tìm chữ `ERROR` trong 2 file trên trước tiên. Dòng `Backend dừng bất thường` **lúc đang tắt app**
   là bình thường (chính app giết backend).
4. Cửa sổ lệch màn: log app có dòng ghi rõ khung mong đợi và khung thật của từng cửa sổ.

### Chạy thẳng từ mã nguồn (không đóng gói)

```bat
.venv\Scripts\python desktop\run.py
```

Thoát bằng `Ctrl+Shift+Q`. Muốn test timer nhanh thì đặt biến môi trường trước khi chạy:
`PENTASYNC_TIER1_WARNING_SEC=10`, `PENTASYNC_TIER1_CLEANUP_SEC=10`,
`PENTASYNC_TIER2_CLUSTER_IDLE_SEC=30`.

---

## 11. Cấu hình chi tiết

### Thời gian chờ

Sửa trong `backend/app/config.py`, hoặc đặt biến môi trường trước khi chạy (dùng được cả với bản exe,
không phải sửa code):

| Hằng số / biến môi trường | Mặc định | Ý nghĩa |
|---|---|---|
| `TIER1_WARNING_SEC` / `PENTASYNC_TIER1_WARNING_SEC` | 30 | Im lặng bao lâu thì hỏi "bạn còn muốn tiếp tục không?" |
| `TIER1_CLEANUP_SEC` / `PENTASYNC_TIER1_CLEANUP_SEC` | 30 | Hỏi xong chờ thêm bao lâu thì tự kết thúc chat |
| `TIER2_CLUSTER_IDLE_SEC` / `PENTASYNC_TIER2_CLUSTER_IDLE_SEC` | 120 | Bao lâu không ai tương tác thì mọi màn về video chờ |

Ràng buộc: `TIER1_WARNING + TIER1_CLEANUP < TIER2` — backend kiểm lúc khởi động và báo lỗi nếu sai.

Biến môi trường khác: `PENTASYNC_PORT` (cổng backend), `PENTASYNC_HOST_ACTIVITY=0` (bỏ tính chuột/bàn
phím máy chủ là "có người" — **cần khi đang lập trình trên chính máy đó**, nếu không hệ thống không
bao giờ về video chờ).

### Video chờ

App nhận **một** video, tự cắt thành N lát dọc bằng nhau (N = số màn hiển thị), mỗi màn phát một lát,
đồng bộ theo đồng hồ chung. Việc cắt chạy nền bằng ffmpeg đi kèm (`imageio-ffmpeg`, không cần cài
thêm), ưu tiên thấp, kết quả được nhớ lại theo nội dung file nên chép sang máy khác vẫn dùng được.
Trong lúc đang cắt, các màn phát nguyên video và tự lấy đúng phần của mình — cùng một hình, chỉ nặng
máy hơn. Video 10 phút 3840×1080 mất ~4 phút để cắt thành 5 lát.

- **Mã nguồn:** đổi video = sửa `STANDBY_VIDEO_REL_PATH` trong `backend/app/config.py` (đường dẫn
  tương đối từ thư mục `system/`).
- **Bản exe:** chép đè `video\standby_wall.mp4` cạnh `PentaSync.exe`.

> **Hình đang bị giãn ngang.** 5 màn 16:9 ghép lại thành khung ~8,9:1 còn video là 16:9–32:9, nên mỗi
> lát bị kéo cho vừa màn. Đây là lựa chọn tạm đã thống nhất với khách. Đưa vào một video siêu rộng
> đúng tỉ lệ là hết méo — **không phải sửa code**.

Video nên là H.264, ~30 fps, cao 1080. Lệnh làm nhẹ một video 4K (máy có ffmpeg):

```bash
ffmpeg -i "<file gốc>.mp4" -vf "scale=3840:1080,setsar=1" -r 30 \
       -c:v libx264 -preset veryfast -crf 28 -g 60 -pix_fmt yuv420p -an standby_wall.mp4
```

### Nội dung slide và tên bệnh viện

Sửa `content_manifest/slides.json` (mã nguồn: `backend/content_manifest/`; bản exe: cạnh
`PentaSync.exe`), mở lại app để áp dụng.

- `"hospital_name"` — tên hiện ở đầu màn menu, màn chờ chat và chân các slide.
- Mỗi màn `1`, `3`, `5` có 2 slide; `id` phải duy nhất. Slide có thể là **chữ**, **ảnh** hoặc **video**:

```jsonc
// chữ: title = dòng nhỏ phía trên, subtitle = tiêu đề lớn, bullets = danh sách đánh số
{ "id": "noi_quy", "title": "Nội quy bệnh viện", "subtitle": "...", "bullets": ["...", "..."] }

// ảnh / video: bỏ file vào content_manifest/media/ rồi ghi tên file
{ "id": "noi_quy", "kind": "image", "title": "Nội quy bệnh viện", "src": "noi_quy.png" }
{ "id": "gioi_thieu", "kind": "video", "title": "Giới thiệu", "src": "gioi_thieu.mp4" }
```

`src` là **tên file** trong `content_manifest/media/`. Video slide phát lặp, tắt tiếng. Khai báo file
không tồn tại thì app vẫn chạy, màn đó hiện thông báo thiếu file.

### Chat AI

Mặc định dùng AI giả (`mock`) — trả lời theo từ khoá, chạy offline, đủ để test trọn luồng. Gọi Gemini
thật:

```bat
set SUPERDOC_PROVIDER=gemini
set GEMINI_API_KEY=<khoá của bạn>
set GEMINI_MODEL=gemini-2.5-flash        :: tuỳ chọn
```

> **Đừng ghi API key vào bất kỳ file nào trong dự án**, kể cả file ví dụ. Chỉ đặt qua biến môi
> trường. Khoá đã lỡ ghi vào file phải thu hồi và tạo lại ở Google AI Studio.

Thiếu khoá hoặc lỗi khởi tạo → tự lùi về `mock` và ghi log. Khi có tài liệu API Superdoc thật, thêm 1
file trong `backend/app/superdoc/` theo khuôn trong `base.py`.

### Card đồ hoạ

Máy có cả card rời lẫn đồ hoạ tích hợp: lúc khởi động app tự đặt **High performance** cho file đang
chạy (đúng thiết lập của Windows Settings → Display → Graphics, chỉ đặt khi chưa có lựa chọn nào) để
mọi màn vẽ bằng card rời. Chạy từ mã nguồn thì thiết lập áp cho `python.exe`. Muốn đổi lại: Windows
Settings → Display → Graphics.

### Đọc lịch sử chat

Database SQLite 2 bảng `chat_sessions`, `chat_messages`, không lưu thông tin định danh. Kết thúc phiên
thì lịch sử bị xoá khỏi màn hình và bộ nhớ, **bản ghi trong database vẫn giữ** (đúng yêu cầu đặc tả).
Xem nhanh:

```bat
python -c "import sqlite3; c=sqlite3.connect('pentasync.db'); [print(r) for r in c.execute('SELECT role, substr(text,1,60) FROM chat_messages ORDER BY id DESC LIMIT 20')]"
```

Số lượt chat, thời gian trả lời trung bình và số lỗi AI trong ngày có sẵn trên bảng điều khiển
(`Ctrl+Shift+M`).

---

## 12. Muốn sửa X thì vào đâu

| Muốn | Sửa ở |
|---|---|
| Thời gian chờ (Tier‑1/Tier‑2) | `backend/app/config.py` — hoặc đặt biến môi trường để không phải sửa code |
| Nội dung slide, tên bệnh viện | `backend/content_manifest/slides.json` |
| Video chờ | chép đè `video/standby_wall.mp4` (xoá `backend/_cache/` nếu muốn cắt lại ngay) |
| Màu sắc, cỡ chữ | `desktop/qml/PentaSync/Theme.qml` |
| Chữ trên nút, tiêu đề | file view tương ứng trong `desktop/qml/PentaSync/` |
| Cách sắp phím trên bàn phím | `desktop/qml/PentaSync/OnScreenKeyboard.qml` |
| Luật gõ tiếng Việt | `desktop/telex.py` (có test — thêm ca vào `desktop/tests/test_telex.py`) |
| Luật gán vai trò màn | `desktop/layout.py` (có test — `desktop/tests/test_layout.py`) |
| Màn nào chuyển trạng thái gì | `backend/app/state/screen_fsm.py` |
| Thêm lệnh cho bảng điều khiển | `schemas.py` → `commands.py` → `cluster_controller.py` → `ManagementWindow.qml` |
| Đổi sang AI khác | viết 1 class theo khuôn `backend/app/superdoc/base.py`, khai báo ở `factory.py` |
| Phím tắt | `desktop/main.py` (đăng ký) + `desktop/win32.py` (`GlobalHotkeys`) |

---

## 13. Đừng sửa bừa

Những chỗ dưới đây trông vô lý nhưng **đang giữ hệ thống chạy đúng**. Sửa thì phải chạy lại đúng bài
test ghi kèm.

1. **`Qt.WindowDoesNotAcceptFocus` trong `DisplayWindow.qml`.** Bỏ ra là 2 người chạm 2 màn cùng lúc
   sẽ mất chạm: cửa sổ được kích hoạt làm Windows/Qt **huỷ** chạm đang dở ở cửa sổ khác.
   → `test\kiem_tra_cham.py haiman`

2. **`_is_press()` trong `window_manager.py` phải xét cả `TouchUpdate`.** Windows gộp mọi màn cảm ứng
   thành một thiết bị, nên chạm của người thứ hai đến trong `TouchUpdate`, không phải `TouchBegin`.
   → `test\kiem_tra_cham.py haiman`, `desktop/tests/test_wake_filter.py`

3. **`raise_window()` mỗi 5 giây cho cửa sổ trên màn chính.** Không có nó, thứ gì nổi đè lên (hộp
   thoại Windows, thông báo) sẽ ăn mất chạm mà người dùng không biết vì sao. Màn chính **không** dùng
   topmost vì sẽ che cả bảng điều khiển.

4. **Không tự nhân scale khi đặt cửa sổ.** Chỉ `setScreen` → `setGeometry(screen.geometry())` →
   `showFullScreen()`. Tự tính toạ độ là đúng nguyên nhân lỗi lấn màn của bản cũ.
   → `Ctrl+Shift+I` nhìn viền, và log tự kiểm mỗi 5 s

5. **Chọn cổng trong `run.py` phải xảy ra trước khi import `config`.** `config.py` đọc
   `PENTASYNC_PORT` lúc import; đổi sau thì app vẫn nối cổng cũ.
   → `desktop/tests/test_run.py`, `test\kiem_tra_exe.py`

6. **`/ws/admin` khai báo trước `/ws/{screen_id}`** trong `ws_routes.py`, không thì bị route kia bắt.
   → `backend/tests/test_admin_routes.py`

7. **Đồng bộ video dùng thời điểm *nhận* gói tin, và cần 2 lần đo liên tiếp mới nhảy.** Đo lúc tạo
   view thì sai ~0,5 s (máy phát video nạp chậm); nhảy theo 1 lần đo thì video giật oan.
   → `desktop/tests/test_standby_sync.py`

8. **Nhớ lát video theo *nội dung* file, không theo đường dẫn.** Nếu không thì mỗi lần chép thư mục
   sang chỗ khác là cắt lại 4 phút.
   → `backend/tests/test_video_slicer.py`

9. **Mọi thay đổi trạng thái phải đi qua hàng đợi lệnh của `cluster_controller`.** Gọi tắt vào trạng
   thái từ route hay từ timer sẽ tạo ra tranh chấp mà test khó bắt.

10. **API key Gemini chỉ nằm ở biến môi trường `GEMINI_API_KEY`.** Không ghi vào bất kỳ file nào
    trong dự án, kể cả file ví dụ.
