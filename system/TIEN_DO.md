# TIẾN ĐỘ TRIỂN KHAI — đọc file này đầu tiên nếu phiên làm việc bị ngắt

> File này ghi lại **đang làm tới đâu** để phiên sau làm tiếp được ngay, không phải dò lại.
> Cập nhật sau mỗi bước có ý nghĩa. Dấu: `[x]` xong · `[~]` đang làm dở · `[ ]` chưa làm.

Kế hoạch gốc (đã duyệt): `C:\Users\ADMIN\.claude\plans\t-i-c-video-con-giggly-cat.md`
Bản thiết kế giao diện (đã duyệt, nền trắng): https://claude.ai/artifact/EXSKKbcoXpG9Mz345EPywD
— file nguồn thiết kế: `../design/*.dc.html`

---

## Mục tiêu

Biến PentaSync từ prototype (5 cửa sổ Edge do `launcher/` mở) thành **ứng dụng PySide6 + QML**:

1. **Căn chỉnh chuẩn từng màn** kể cả khác độ phân giải/scale (lỗi cũ: cửa sổ Edge tràn sang màn bên).
2. **Tự thích ứng số màn** theo quy tắc của khách (xem dưới).
3. **Giao diện mới** theo bản thiết kế nền trắng.
4. **Màn quản lý** khi có ≥ 6 màn.
5. Đóng gói thành `PentaSync.exe`, máy công ty không cần cài Python.

## Quyết định đã chốt (đừng bàn lại)

| Chủ đề | Quyết định |
|---|---|
| Công nghệ | **PySide6 + QML**, chỉ Python. Backend FastAPI giữ nguyên, app Qt là client WebSocket |
| Tên gói app | **`system/desktop/`** — KHÔNG đặt `app/` vì trùng tên gói `backend/app/` |
| Gán vai trò màn | N ≥ 6: màn Primary = quản lý, 5 màn còn lại hiển thị. N ≤ 5: tất cả hiển thị. Không màn nào cảm ứng → 1,2,3… trái→phải. Có cảm ứng → màn cảm ứng = 2,4; không cảm ứng = 1,3,5; thừa → số trống nhỏ nhất |
| Bàn phím chat | Dựng sẵn trong app, **hiện khi chạm ô chat, ẩn khi chạm ra ngoài** (như điện thoại), gõ Telex |
| Tắt trình chiếu | 2 nút: **Về video chờ** và **Tắt hẳn (màn đen, bỏ qua mọi chạm)** |
| Đổi nội dung | Chỉ **chọn slide đang chiếu** (không làm CMS) |
| Giao diện | **Nền trắng**, 1 màu nhấn xanh `#1668A8`, chữ Be Vietnam Pro, thiết kế ở khung 1920×1080 |
| Video chờ | Cắt thành N lát (N = số màn hiển thị), mỗi màn phát 1 lát, đồng bộ theo đồng hồ chung |

## Phần cứng thật (khách báo 2026-09-17)

Máy chính nối 5 màn qua **HDMI và DisplayPort**. Hệ quả phải xử lý:

- Màn DP/HDMI **tắt hoặc ngủ → Windows gỡ khỏi danh sách màn** và dồn cửa sổ sang màn khác.
  → App phải gọi `SetThreadExecutionState` giữ màn luôn thức, và **xếp lại cửa sổ khi màn
  biến mất/xuất hiện** (có chờ vài giây để khỏi xếp loạn khi màn chập chờn).
- Thứ tự trái→phải lấy theo **sắp xếp màn trong Windows Settings → Display**, không theo cổng cắm.
- TV qua HDMI hay bị **overscan** (cắt mép) → trông giống lỗi lệch màn. Sửa trong menu TV
  ("Just Scan"/"Screen Fit"/"PC") hoặc driver card đồ hoạ. Lớp "Nhận diện màn" lộ ra ngay.
- Nên để các màn **cùng tần số quét 60Hz**.
- Cảm ứng đi qua **cáp USB riêng** → phải chạy *Tablet PC Settings → Setup* để Windows biết
  cảm ứng nào thuộc màn nào.

**Cấu hình cụ thể:** card **RTX 4070 Ti Super** (1 HDMI + 3 DP) + **1 HDMI trên mainboard** → 4 màn
chạy card rời, màn thứ 5 chạy chip đồ hoạ tích hợp (iGPU) của CPU. GeForce xuất tối đa 4 màn nên
cách cắm này là bắt buộc. Việc phải làm trên máy đó:
- BIOS: bật iGPU khi có card rời ("iGPU Multi-Monitor"/"IGD Multi-Monitor" – Intel;
  "Integrated Graphics: Forces" – AMD), màn chính (Primary Display) = PCIe/PEG. CPU phải có iGPU
  (Intel đuôi F không có → cổng HDMI mainboard không lên hình). Cài driver iGPU.
- Windows Settings → Display → Graphics: đặt **PentaSync.exe** (và `.venv\Scripts\python.exe` khi
  chạy mã nguồn) = **High performance** → cả 5 cửa sổ vẽ + giải mã video trên card NVIDIA, Windows
  tự chép hình sang màn cắm mainboard (tốn thêm chút ít cho đúng 1 màn đó).
- App hiện tên card của từng màn (lớp "Nhận diện màn", màn quản lý, log) và ghi card Qt dùng để
  vẽ (`QSG_INFO=1` → dòng `[qt]` trong `desktop/pentasync_app_log.txt`) để kiểm tra tại chỗ.

→ Tất cả phải vào `HUONG_DAN_TEST.md` ở giai đoạn 6.

## Số đo từ thử nghiệm kỹ thuật (đã xong)

Đo sạch (máy rảnh, chỉ tính cây tiến trình của app + dwm.exe, có bằng chứng video đang phát),
5 cửa sổ 1920×1080:

| Cách | CPU | RAM |
|---|---|---|
| Edge + H.264 (hệ thống cũ) | 5.1% | 1618 MB |
| **QML + H.264 cắt sẵn 5 lát** | **5.8%** | **763 MB** ← chọn |
| QML + H.264 đầy đủ + dịch khung | 6.9% | 1562 MB ← dùng tạm khi chưa cắt xong |
| QtWebEngine + VP9 | 14.1% | 1650 MB |

- Cửa sổ Qt `showFullScreen()` khớp CHÍNH XÁC màn ở scale 150%.
- `QScreen.name()` trả **tên model màn**, không phải `\\.\DISPLAYn` → khớp với Win32 bằng
  `MonitorFromWindow(window.winId())`.
- QtMultimedia (PySide6 6.11.2) phát được H.264. QtWebEngine KHÔNG phát được H.264.
- ⚠️ Lần đo đầu bị sai hoàn toàn vì máy đang chạy game. Đo CPU phải đo **cây tiến trình của app**,
  không đo toàn máy. Script đo nằm ở scratchpad (`measure.py`), không phải trong dự án.

---

## Danh sách việc

### Giai đoạn 0 — Thiết kế giao diện
- [x] 11 màn thiết kế, khách duyệt bản nền trắng

### Giai đoạn 1 — Thử nghiệm kỹ thuật
- [x] Căn chỉnh cửa sổ Qt · [x] H.264 · [x] đo tài nguyên · [x] khớp QScreen ↔ HMONITOR

### Giai đoạn 2 — Backend (`backend/app/`)
- [x] `state/layout.py` (ClusterLayout), lệnh mới trong `commands.py`, schema admin/layout
- [x] `SlideBand.buttons(screens)` + `reset()`, `ChatStore.stats_since()`
- [x] Viết lại `cluster_controller.py`: bố cục động, kết nối theo conn_id, admin, blackout, reset
- [x] Bố cục màn động: `POST /api/layout`, chỉ xét vai trò đang có
- [x] Kênh quản lý `WS /ws/admin`: ảnh chụp trạng thái + lệnh (`ws_manager.send_admin`)
- [x] Màn đen (blackout), Reset hệ thống, về video chờ
- [x] Thống kê hôm nay cho màn quản lý (số phiên, thời lượng TB, lỗi AI)
- [x] Cắt video chờ thành N lát (`state/video_slicer.py`), route `/standby-video/{n}/{i}`
- [x] Test: `test_layout_admin.py` (33), `test_video_slicer.py` (9), `test_admin_routes.py` (7) → **177 test xanh**

### Giai đoạn 3 — Ứng dụng Qt (`desktop/`)
- [x] Môi trường: `system/.venv` (backend + PySide6 6.11.2), `desktop/requirements.txt` (CHỈ ASCII — pip 21 đọc cp1252), phông Be Vietnam Pro + OFL trong `desktop/fonts/`
- [x] `layout.py` (hàm thuần) + `tests/test_layout.py`
- [x] `monitors.py` — `QScreen.nativeInterface().handle()` trả thẳng HMONITOR (không cần mở cửa sổ dò)
- [x] `telex.py` + `tests/test_telex.py` → 107 test desktop xanh (`cd system/desktop && python -m pytest -q`)
- [x] `backend_process.py` (QProcess + /healthz + tự khởi động lại + Job Object kill-on-close)
- [x] `screen_client.py` (+ ChatModel), `admin_client.py`, `standby_sync.py` (+ test)
- [x] `window_manager.py` (xếp cửa sổ, chờ 3 s khi cắm/rút, màn quản lý, nhận diện, reset, POST layout), `main.py`, `run.py`, `backend_entry.py`, `config.py` (HOSPITAL_NAME)
- [x] QML: Theme, Icons, components, 7 view, bàn phím Telex, 2 hộp thoại, IdentifyOverlay, DisplayWindow, ManagementWindow — ảnh chụp khớp bản thiết kế
- [x] Chạy thật 1 màn: cửa sổ khớp mép (FullScreen, 150%), backend lên/tắt theo, video chờ phát + đồng bộ (lệch 0.02–0.06 s)
- [x] Test: `test_standby_sync.py` (có đầu phát giả), `test_screen_client.py` → 130 test desktop xanh
- [x] Chạy giả lập 6 màn (vá `read_screens`, script `sim6.py` ở scratchpad) trọn luồng: đánh thức, slide (màn 2 + màn quản lý), chạm màn 4 qua bộ lọc → chat → AI trả lời, màn đen bỏ qua chạm, bật lại, reset tạo lại cửa sổ — ĐẠT
- [x] Sửa lỗi lộ ra: nút X cửa sổ quản lý (`closing` → `visibleChanged`), nối tín hiệu màn 1 lần, log giả khi đóng, log nhiễu FFmpeg khi rời màn chờ
- [x] Đo: 5 cửa sổ phát lát + màn quản lý + backend (+dwm) = **CPU 4.4%, RAM 1268 MB** (cửa sổ 2560×1440)
- [x] Tên card đồ hoạ từng màn (EnumDisplayDevicesW) → nhận diện + màn quản lý + log; `QSG_INFO=1` (chỉ giữ dòng Adapter)
- [x] App tự đặt "High performance" cho file đang chạy (HKCU `DirectX\UserGpuPreferences`, chỉ khi chưa có giá trị).
  Thử trên laptop lai AMD+NVIDIA: Qt đổi từ AMD sang NVIDIA, màn gắn chip AMD vẫn lên hình, video chạy.
  Chạy mã nguồn thì giá trị ghi cho python.exe GỐC (python.exe của venv chỉ là trình khởi chạy).
  Đã xoá giá trị thử trên laptop dev. `test_admin_routes` giờ dùng cache lát tạm (không phụ thuộc cache thật).
- [ ] Chưa thử được: nhiều màn thật khác độ phân giải/scale, cảm ứng thật, cắm/rút màn, 2 card → test ở công ty

### Giai đoạn 4 — Dọn phần bị thay thế
- [x] Chuyển `launcher/`, `frontend/` và `backend` bản cũ sang `outsource/old_system/` (kèm README nói rõ
  chỉ dùng dự phòng + hạn chế scale 100% + phải chép video tay). `system/` chỉ còn code mới.
- [x] Xoá route `/screen/{id}`, mount `/src` và test liên quan → backend không còn phục vụ giao diện web
- [x] Xoá rác còn lại trong `system/backend`: `_edge_profile_screen_1|2` (196 MB profile Edge của bản cũ),
  `launcher_log.txt` — không còn code nào tham chiếu

### Giai đoạn 5 — Đóng gói
- [x] `app/config.py` biết chạy từ exe (`FROZEN`): `content_manifest/`, `video/` cạnh exe; db/log/lát trong `data/`
- [x] Mount `/src` chỉ khi có `frontend/`; `backend_entry` chịu stdout=None; tên bệnh viện → `slides.json` (`hospital_name`)
- [x] Khoá cache lát video theo NỘI DUNG (size + 1 MiB đầu/cuối) → chép thư mục sang máy khác vẫn dùng lại (+ test)
- [x] `packaging/PentaSync.spec` + `packaging/build.py` (bỏ QtWebEngine/3D/Charts…; chép nội dung, video, lát, tài liệu)
- [x] Build: chương trình 219 MB + video 175 MB + lát 204 MB → `system/dist/PentaSync/`
- [x] Thời gian chờ đổi được bằng biến môi trường `PENTASYNC_TIER1_WARNING_SEC`, `PENTASYNC_TIER1_CLEANUP_SEC`,
  `PENTASYNC_TIER2_CLUSTER_IDLE_SEC`; `packaging/chay_thu_nhanh.bat` (ASCII, CRLF) đi kèm exe = 10/10/30 giây
- [x] Thử từ thư mục chép sang chỗ khác: chạy không cần Python, backend = `PentaSync.exe --backend`, dùng lát
  có sẵn, chọn NVIDIA, video chờ lên hình; **tắt cưỡng bức exe → backend chết theo, cổng 8000 đóng**

### Giai đoạn 6 — Tài liệu
- [x] `HUONG_DAN_TEST.md` viết lại: build exe, BIOS/iGPU, sắp xếp màn, Tablet PC Settings, overscan, nguồn,
  phím tắt, quy tắc vai trò, nhận diện màn, 11 nhóm kiểm tra (căn chỉnh, chờ, đánh thức, slide, chat 2 người,
  đổi chế độ, timer, bảng điều khiển, cắm/rút, tự phục hồi, tài nguyên), sự cố, Gemini, dự phòng Edge
- [x] `README.md` viết lại (chạy exe/mã nguồn, cấu hình, đóng gói, cấu trúc, log, tình trạng)
- [x] `docs/architecture.md`: kiến trúc 2 tiến trình, video chờ N lát, bố cục động, app Qt, quản lý/màn đen/reset, đóng gói, test, bẫy mới
- [x] Build lại `dist/PentaSync` (có tài liệu + `chay_thu_nhanh.bat`); thử bat từ bản copy: biến thời gian chờ tới cả app lẫn backend

---

## Đang làm dở

**Giai đoạn 7 — rà soát lần cuối trước khi test (khách yêu cầu 2026-09-17) — XONG:** không lệch màn, 5 màn
hiển thị trọn vẹn, chạy đúng với màn cảm ứng. Việc:
- [x] Rà toàn bộ code tìm lỗi tiềm ẩn
- [x] `desktop/win32.py`: đo/sửa vị trí cửa sổ bằng Win32, topmost, tắt phản hồi chạm, phím tắt toàn cục
- [x] `window_manager`: kiểm vị trí sau 0,7 s / 2,5 s / mỗi 5 s (lệch → đặt lại Qt → lần 2 ép Win32; thu nhỏ → mở lại),
  log "Màn N khớp …"; đặt lại cửa sổ đang toàn màn hình đúng quy trình (showNormal trước); rebuild bọc try
- [x] Màn phụ topmost + đặt lại định kỳ (taskbar); màn chính không topmost (còn mở được Task Manager)
- [x] **Màn hiển thị KHÔNG nhận kích hoạt** (`Qt.WindowDoesNotAcceptFocus`): kích hoạt màn này làm Qt huỷ chạm dở ở màn kia.
  Đã thử: cửa sổ toàn màn hình không kích hoạt vẫn phủ kín taskbar (Windows 11, taskbar luôn hiện)
- [x] Phím tắt toàn cục (RegisterHotKey, dự phòng Ctrl+Alt+Shift); bỏ Shortcut trong DisplayWindow
- [x] Cổng 8000 bị chiếm → `run.py` chọn cổng trống, truyền `PENTASYNC_PORT` cho backend
- [x] `sys.excepthook` → log; cảnh báo cảm ứng gán sai (`monitors.touch_problem`) → log + bảng điều khiển
- [x] Bảng điều khiển: nút "Thoát ứng dụng" (hỏi xác nhận); chữ chat PlainText; prompt AI không markdown; ẩn con trỏ khi đứng yên
- [x] **Bộ lọc đánh thức bắt điểm "Pressed" trong cả TouchUpdate** (Qt gộp các màn cảm ứng thành 1 thiết bị → chạm
  chồng thời gian ở màn khác đến dạng TouchUpdate, không phải TouchBegin) + test
- [x] Chạm vào danh sách tin nhắn không ẩn bàn phím (ListView nuốt chạm) → thêm TapHandler trong ListView
- [x] Test chạm THẬT (InjectTouchInput, scratchpad `touch_injector.py`):
  `touch_e2e.py mapped` 25/25 · `touch_e2e.py raw` 10/10 · `touch_dual.py` (2 thiết bị, 2 người cùng lúc) 11/11 × 3 lần.
  Thử WM_TOUCH (`windows:nowmpointer`) → tệ hơn (mất chạm) → giữ WM_POINTER mặc định.
- [x] Test mới: test_monitors, test_win32, test_run, test_wake_filter → 151 test desktop (176 backend)
- [x] Giả lập 6 màn vẫn đạt; build lại exe; `exe_check.py` 10/10 (cổng bị chiếm, giết backend, phím tắt, thoát sạch);
  tài liệu cập nhật (B7 lớp phủ/vuốt mép/khoá máy, phím tắt toàn cục, 0.4–0.5, 4.6b–c, 9.3, sự cố); đã xoá giá trị GPU thử

### Giai đoạn 8 — Dọn dẹp + tài liệu giải thích (khách yêu cầu 2026-09-30) — XONG
- [x] `ruff.toml`: chỉ bật luật bắt lỗi thật (F, E4/E7/E9, B, SIM, RUF), tắt luật phong cách và các
  luật báo sai với chữ tiếng Việt (RUF001–003) → `ruff check .` sạch; qmllint 0 cảnh báo
- [x] Chuyển bài kiểm tra tay từ scratchpad vào `system/test/` (giữ được giữa các phiên):
  `chung.py`, `gia_lap_cham.py`, `kiem_tra_cham.py` (motman/chuagan/haiman), `gia_lap_nhieu_man.py`,
  `xem_giao_dien.py`, `kiem_tra_exe.py` + `test/README.md`
- [x] `descryption.md`: giải thích từng file trong `system/`, hướng dẫn test 7 bước, cấu hình chi tiết,
  bảng "muốn sửa X thì vào đâu", 10 chỗ "đừng sửa bừa" kèm bài test tương ứng
- [x] `README.md` rút thành bản tóm tắt (chi tiết trỏ sang `descryption.md`); cập nhật
  `HUONG_DAN_TEST.md`, `docs/architecture.md` theo cấu trúc mới

Sau giai đoạn 8:
1. Khách mang `system/dist/PentaSync` đi test ở công ty theo `HUONG_DAN_TEST.md` → chờ kết quả, sửa theo báo cáo.
2. Build lại bằng `packaging/build.py` sau mỗi lần sửa code (để `dist/` mang tài liệu mới nhất).

Ghi nhớ cấu trúc QML: module `PentaSync` ở `desktop/qml/PentaSync/`, 2 cửa sổ gốc
`DisplayWindow.qml`, `ManagementWindow.qml`. Kiểm giao diện bằng `qml_load.py` (scratchpad, dữ liệu giả).
Cửa sổ nhận `client` (ScreenClient), `sync` (StandbySync), `manager` (WindowManager: identifying,
displays, hospitalName, telex.typeKey/erase, toggleManagement, identify, resetSystem, quit), `role`, `info`.
Màn quản lý nhận `admin` (AdminClient: snapshot, command, selectSlide), `manager`, `windowed`.
Mọi lần chạm màn 2/4 đã tự gửi `generic_wake` (event filter trong Python) — QML chỉ gửi target riêng.

## Giao thức backend ↔ app Qt (chốt ở giai đoạn 2)

- `POST /api/layout` `{"displays":[{"role":2,"wall_index":0}, ...]}` → 200 / 400 (lý do) / 422.
- `WS /ws/{role}`: như cũ. `state_update.view` thêm `"blackout"`. Nhánh `standby` có
  `video_src`, `crop_index`, `crop_count` (lát cắt sẵn thì `crop` = 0/1), `t0`, `server_now` (giây epoch).
- `WS /ws/admin`: server gửi `admin_snapshot` (blackout, started_at, wall_count, screens[role,
  active, wall_index, connected, state, view, chat_open, chat_started_at, slide_title], slides,
  stats{chats_today, avg_chat_seconds, ai_errors_today}); client gửi
  `{"type":"admin_command","action":"select_slide|force_standby|blackout_on|blackout_off|reset|refresh","slide_id":...}`.
- `GET /standby-video/{n}/{i}`: lát i trong n lát (404 nếu chưa cắt xong). Cache ở
  `backend/_cache/standby_slices/`.

## Cách chạy nhanh để kiểm tra

```bash
cd system/backend && ../.venv/Scripts/python -m pytest -q    # test backend (177)
cd system/desktop && ../.venv/Scripts/python -m pytest -q    # test app (152)
system/.venv/Scripts/python system/desktop/run.py            # chạy app (Ctrl+Shift+Q để thoát)
cd system && .venv/Scripts/python packaging/build.py         # đóng gói → dist/PentaSync (cần pyinstaller)
```

Bài học khi chạy thật:
- Đo lệch đồng hồ phải dùng thời điểm NHẬN message (`received_at`), không phải lúc view dựng xong
  (lần đầu nạp QtMultimedia mất ~0.5 s → mọi màn chậm nửa giây).
- Giao diện khựng 1 nhịp làm `position()` cũ → chỉ tua khi lệch lớn 2 nhịp liền.
- `grabWindow()` 2560×1440 làm treo vòng sự kiện ~0.5 s — đừng tin số đo đồng bộ ngay sau khi chụp.

## Nhật ký

- 2026-09-16: tạo file tiến độ, bắt đầu giai đoạn 2.
- 2026-09-17: khách báo nối màn qua HDMI/DP. Viết lại controller + admin + slicer + routes.
  Giai đoạn 2 xong, 177 test xanh. Bắt đầu giai đoạn 3.
- 2026-09-17: cắt thật video chờ 600 s 3840×1080 thành 5 lát: **228 giây** (ưu tiên thấp),
  tổng ~200 MB. Giai đoạn 5 nên chép sẵn cache lát vào bản đóng gói để máy công ty khỏi chờ.
- 2026-09-17: app Qt chạy thật 1 màn + giả lập 6 màn đạt. Khách báo máy test: RTX 4070 Ti S
  (1 HDMI + 3 DP) + 1 HDMI mainboard. Hoãn giai đoạn 4 (giữ bản Edge dự phòng).
- 2026-09-17: thêm tên card từng màn + tự chọn card rời; giai đoạn 5 (exe) và 6 (tài liệu) xong.
  178 test backend + 130 test app xanh. Chờ khách test trên máy thật.
- 2026-09-30: giai đoạn 4 + 8 xong — code cũ sang `old_system/`, xoá 196 MB profile Edge còn sót,
  ruff/qmllint sạch, bài kiểm tra tay dọn vào `system/test/`, viết `descryption.md` (giải thích từng
  file + hướng dẫn test), README thành bản tóm tắt.
  Sửa thêm: in chữ có dấu ra cmd (cp1252) làm `build.py` và script test chết → reconfigure stdout
  utf-8 ở `test/chung.py`, `packaging/build.py`, `desktop/main.py` (cả StreamHandler của log).
  Test: 176 backend + 151 desktop xanh, ruff + qmllint sạch; motman 23/23, chuagan 9/9,
  haiman 10/10 × 2, xem_giao_dien 15/15, gia_lap_nhieu_man 15/15, kiem_tra_exe 9/9 (exe build lại).
- 2026-09-17: giai đoạn 7 xong — canh vị trí Win32, topmost, cửa sổ không kích hoạt, phím tắt toàn cục,
  tự đổi cổng, bộ lọc chạm theo trạng thái điểm; test chạm thật (InjectTouchInput) 25/25, 10/10, 11/11×3;
  exe 10/10. 178 test backend + 152 test app xanh. Script test ở scratchpad phiên này
  (touch_injector.py, touch_e2e.py, touch_dual.py, exe_check.py, sim6.py, qml_load.py).
