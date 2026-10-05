# PentaSync — Mô tả kiến trúc chi tiết

> Tài liệu này mô tả **code thực tế đã viết**. Phần nào chưa xây sẽ được ghi rõ.

## 1. Bối cảnh

Một máy tính chủ nối tối đa 5 màn hình treo ở hành lang bệnh viện (số màn thực tế và màn nào
giữ vai trò nào do app tự quyết — mục 11). Vai trò:

- **Màn 1, 3, 5** — thụ động, không nhận tương tác. Đây là 3 màn **duy nhất** trình chiếu slide.
- **Màn 2** — cảm ứng, điều khiển chính: menu 2 chế độ (Thông tin bệnh viện / Chat).
- **Màn 4** — cảm ứng, chỉ có chat: chạm là vào thẳng.

### 1.1 Ba điểm 2 file đặc tả nói khác nhau và cách đã chốt với khách

| Vấn đề | `descryption.txt` | `PentaSync_..._Flow.txt` | Đã chốt |
|---|---|---|---|
| Màn 2/4 có chiếu slide không? | "mỗi màn 2 slide → **6 nút**" (= 3 màn) | "cả 5 màn thành dải slide" | **Chỉ màn 1/3/5.** Màn 2 giữ bảng 6 nút, màn 4 giữ nút chat |
| Hết giờ Tier-1 thì về đâu? | "quay về **màn hình chọn chế độ** ban đầu" | "về màn hình chờ mặc định" | **Về màn chọn chế độ.** Tier-2 mới là tầng đưa cả cụm đi ngủ |
| Thức dậy thì màn 1/3/5 làm gì? | "**cả 5 màn** đều quay về chức năng vốn có của nó" | "các màn còn lại không có chức năng tương tác" | **Lên slide ngay** khi hệ thống thức |

Hệ quả của quyết định thứ nhất: **không còn khái niệm "màn 4 tách nhóm / nhập lại"** như Luồng D
mô tả — màn 4 vốn không bao giờ nằm trong dải slide, nên không có gì để tách ra.

Hệ quả của quyết định thứ ba: **thức dậy chính là lúc dải slide được bật**, chứ không phải lúc
bấm "Thông tin bệnh viện". Nút đó giờ chỉ mở bảng điều khiển 6 nút trên màn 2.

## 2. Kiến trúc tổng thể

Hai tiến trình trên cùng một máy. App màn hình (Qt) là **client**; backend giữ toàn bộ trạng thái
và luật chơi, nên sau này tách backend lên server riêng không phải viết lại giao diện.

```
┌─ App màn hình (desktop/, PySide6 + QML) ─────────────────────────────┐
│ main.py: khoá 1 bản · log · chọn card rời · giữ màn thức             │
│ BackendProcess ── chạy "run.py --backend" / "PentaSync.exe --backend"│
│                   /healthz mỗi 1 s · chết thì khởi động lại          │
│                   Job Object: app chết → backend chết theo           │
│ WindowManager                                                        │
│   monitors.read_screens() ─▶ layout.assign() ─▶ vai trò từng màn    │
│   1 DisplayWindow.qml / màn hiển thị ── ScreenClient (WS /ws/{vai})  │
│                                      └─ StandbySync (đồng bộ video)  │
│   ManagementWindow.qml ── AdminClient (WS /ws/admin)                 │
│   POST /api/layout mỗi khi bố cục đổi hoặc backend vừa khởi động lại │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ 127.0.0.1:8000
┌─ Backend (backend/app/, FastAPI) ─▼──────────────────────────────────┐
│ http_routes: /healthz · /api/layout · /standby-video[/{n}/{i}]       │
│              /media/{file}                                           │
│ ws_routes:   /ws/admin (đăng ký TRƯỚC) · /ws/{màn}                   │
│                     │ Command                                        │
│                     ▼                                                │
│ ClusterController — 1 asyncio.Queue duy nhất                         │
│   giữ: state 5 vai trò · ClusterLayout · cờ màn đen · kết nối        │
│        chat_sessions{} · Tier-2 timer · thống kê hôm nay             │
│   dùng: screen_fsm.transition() · SlideBand · VideoSlicer            │
│   gửi: ConnectionManager.send_to (màn) / send_admin (màn quản lý)    │
│ ChatSession × N ─ Tier-1 · lỗi · task AI · ChatStore (SQLite)        │
│ VideoSlicer ─ ffmpeg (tiến trình con, ưu tiên thấp) → cache lát      │
│ HostActivityMonitor ─ GetLastInputInfo mỗi 2 s                       │
└──────────────────────────────────────────────────────────────────────┘
```

Bản web cũ (`launcher/` mở 5 cửa sổ Edge, giao diện `frontend/`) đã chuyển nguyên trạng sang
`outsource/old_system/`, cùng route `/screen/{id}` và mount `/src` của nó — backend ở đây không còn
phục vụ giao diện web. Giữ làm phương án dự phòng, xem `old_system/README.md`.

## 3. Nguyên tắc cốt lõi: single-writer command queue

Mọi mutation state — dù đến từ WebSocket (chạm màn, gửi tin), từ 1 timer hết hạn, từ task gọi AI
trả về, hay từ thao tác chuột trên máy chủ — đều được quy về 1 `Command` rồi đẩy vào **một hàng
đợi duy nhất**. Chỉ **một coroutine** (`ClusterController.run()`) tiêu thụ hàng đợi đó, xử lý
tuần tự từng cái một. Vì vậy **không có lock nào trong toàn bộ hệ thống**.

Hệ quả bắt buộc phải giữ khi mở rộng: `ChatSession` không được tự sửa state màn hình. Timer của
nó và task gọi AI của nó chỉ được phép **đẩy Command** vào hàng đợi.

Ngoại lệ có chủ đích duy nhất: **task gọi AI chạy ngoài hàng đợi**. Nếu chờ AI ngay trong vòng
lặp xử lý command thì một phiên chat chậm sẽ làm đơ toàn bộ 5 màn.

## 4. State machine (`screen_fsm.py`)

`transition(role, state, event) -> TransitionResult` là **hàm thuần túy** — không I/O, không
asyncio, không đọc state ngoài.

### 4.1 Màn 1, 3, 5 (PASSIVE)

| Từ | Sự kiện | Đến |
|---|---|---|
| STANDBY | BAND_ACTIVATE | SLIDE_MEMBER |
| bất kỳ | CLUSTER_RESET | STANDBY |

Slide nào đang chiếu **không phải là state** — nó nằm trong `SlideBand`, gửi kèm `state_update`.

### 4.2 Màn 2 (CONTROL)

| Từ | Sự kiện | Đến | Hiệu ứng |
|---|---|---|---|
| STANDBY | TOUCH_OWN / WAKE_PAIR | MENU | — |
| MENU | MENU_SELECT_INFO | SLIDE_CONTROL | `activate_band` |
| MENU | MENU_SELECT_CHAT | CHAT | `open_chat_session` |
| SLIDE_CONTROL | MENU_SELECT_CHAT | CHAT | `open_chat_session` (dải slide **không** tắt) |
| SLIDE_CONTROL | MENU_BACK | MENU | — |
| CHAT | MENU_SELECT_INFO | CHAT_CONFIRM_SWITCH | gửi `confirm_prompt` |
| CHAT_CONFIRM_SWITCH | CONFIRM_YES | SLIDE_CONTROL | `close_chat_session` + `activate_band` |
| CHAT_CONFIRM_SWITCH | CONFIRM_NO | CHAT | — |
| CHAT / CHAT_CONFIRM_SWITCH | CHAT_EXIT · TIER1_TIMEOUT · ERROR_TIMEOUT | **MENU** | `close_chat_session` |
| bất kỳ | CLUSTER_RESET | STANDBY | `close_chat_session` nếu đang chat |

`SLIDE_CONTROL` + `TOUCH_OWN` **không làm gì** — bảng điều khiển có nút "Quay lại menu" rõ ràng,
chạm lung tung không được làm mất bảng.

### 4.3 Màn 4 (CHAT)

| Từ | Sự kiện | Đến | Hiệu ứng |
|---|---|---|---|
| STANDBY | TOUCH_OWN | CHAT (thẳng) | `open_chat_session` |
| STANDBY | WAKE_PAIR / BAND_ACTIVATE | PROMPT_CHAT_BUTTON | — |
| PROMPT_CHAT_BUTTON | TOUCH_OWN | CHAT | `open_chat_session` |
| CHAT | BAND_ACTIVATE | *(không đổi — không ngắt chat đang diễn ra)* | — |
| CHAT | CHAT_EXIT · TIER1_TIMEOUT · ERROR_TIMEOUT | PROMPT_CHAT_BUTTON | `close_chat_session` |
| bất kỳ | CLUSTER_RESET | STANDBY | `close_chat_session` nếu đang chat |

3 đường thoát khỏi chat (chủ động / hết giờ / lỗi) được gom vào **một nhánh code duy nhất** trong
`transition()`: khác nhau về nguyên nhân nhưng giống hệt nhau về state đích. Tách ra 3 chỗ thì
sớm muộn cũng lệch nhau.

Đích đến lấy đúng chữ trong `descryption.txt` mục 3: *"quay về trạng thái ban đầu (màn 2 có 2 ô
là chế độ trình chiếu và chế độ chat còn màn 4 chỉ có 1 ô ghi chế độ chat)"* — nên màn 2 **luôn**
về MENU, không phụ thuộc dải slide có đang chạy hay không, và màn 1/3/5 không bị đụng đến.

## 5. Chế độ chờ: 1 video chia cho N màn

Đặc tả cấm rõ: *"5 màn cần đồng nhất khâu trình chiếu, ko được 5 màn 5 video độc lập"*.

Hệ thống nhận **một** video (`STANDBY_VIDEO_REL_PATH`) và chia nó thành N phần bằng nhau theo
chiều ngang, N = số màn hiển thị đang có, thứ tự theo **vị trí trên tường** (`wall_index`), không
theo số vai trò.

### 5.1 Hai cách hiện cùng một hình

Nhánh `standby` của `state_update` mang `video_src`, `crop_index`, `crop_count`:

| Tình huống | `video_src` | `crop` | Màn làm gì |
|---|---|---|---|
| Đã cắt lát xong (và N > 1) | `/standby-video/{N}/{i}` | 0 / 1 | Phát đúng lát của mình, kéo cho vừa màn |
| Chưa cắt xong, hoặc 1 màn | `/standby-video` | `wall_index` / N | Phát nguyên video, rộng N lần màn, đẩy sang trái `i` lần |

`StandbyView.qml` chỉ cần 1 công thức cho cả hai: `VideoOutput` rộng `crop_count × màn`, đặt ở
`x = −crop_index × màn`, `fillMode: Stretch`. Hai cách cho ra **cùng một hình**; cắt sẵn chỉ để nhẹ
máy — đo sạch 5 cửa sổ 1920×1080: nguyên video 6,9% CPU / 1562 MB, lát cắt sẵn 5,8% / 763 MB.

**`VideoSlicer` (`state/video_slicer.py`).** Mỗi lần bố cục đổi, controller gọi `ensure(N)`:

- Chạy `ffmpeg` đi kèm `imageio-ffmpeg` ở tiến trình con **ưu tiên thấp**, giải mã 1 lần rồi
  `split` ra N nhánh `crop` → mọi lát có cùng mốc thời gian từng khung. Khung khoá mỗi 2 giây để tua
  nhanh khi đồng bộ.
- Cắt xong → `SlicesReadyCommand(N)` → controller gửi lại `state_update` cho các màn đang chờ.
- Chỉ 1 việc cắt tại 1 thời điểm; đổi bố cục giữa chừng thì huỷ việc cũ.
- Cache theo **nội dung** video (kích thước + 1 MiB đầu + 1 MiB cuối) và N: chép cả thư mục sang máy
  khác vẫn dùng lại, thay video khác thì tự cắt lại và xoá lát của video cũ. Có file `done.json`
  mới tính là xong (cắt dở bị huỷ không bao giờ bị dùng nhầm).
- Không có ffmpeg / không có video → chỉ ghi log, các màn dùng cách "nguyên video".

Số đo: video 600 s 3840×1080 → 5 lát mất 228 s trên laptop dev, tổng ~200 MB. `packaging/build.py`
chép sẵn cache lát vào bản đóng gói.

### 5.2 Về chuyện hình bị giãn ngang

5 màn 16:9 ghép lại thành một khung ~**8.9:1**, video thường là **1.78:1** (video hiện tại 3.56:1).
Không có cách nào vừa phủ kín vừa giữ đúng tỉ lệ:

| Cách | Kết quả |
|---|---|
| Kéo giãn cho vừa các màn *(đang dùng)* | Cá bị giãn ngang |
| Giữ tỉ lệ, cắt lấy dải ngang | Chỉ thấy một dải mỏng của video |
| Giữ tỉ lệ, thu vừa chiều cao | Video chỉ rộng bằng 1–2 màn, các màn còn lại đen |

Khách đã chốt tạm chấp nhận giãn ngang. **Đây không phải thứ phải sửa code sau này:** `Stretch`
chỉ giãn đúng bằng mức chênh giữa tỉ lệ video và tỉ lệ tường — đưa vào một video siêu rộng đúng
tỉ lệ là tự khớp 1:1.

### 5.3 Đồng bộ các màn (`desktop/standby_sync.py`)

Không truyền frame. Backend cấp mốc `t0` dùng chung (`sync_clock.py`), mỗi màn tự tính:

```
target = (now + lệch_đồng_hồ − t0) mod duration
```

`StandbySync` (Python, mỗi cửa sổ 1 cái) chỉnh `QMediaPlayer` của QML mỗi 500 ms:

- `|lệch| > 0.3 s` **hai nhịp liền** → tua thẳng tới `target`.
- còn lại → chỉnh mượt `playbackRate` trong 0.85–1.15; `|lệch| < 0.02 s` → về 1.
- Phép trừ theo **vòng tròn** (lúc video vừa lặp lại).
- `lệch_đồng_hồ = server_now − received_at`, trong đó `received_at` là lúc `ScreenClient`
  **nhận** message — không phải lúc view dựng xong.

Đo trên máy thật: lệch giữa mốc chung và đầu phát 0,02–0,06 s ở trạng thái ổn định.

## 6. Dải slide (`slide_band.py` + `content_manifest/`)

3 nội dung **độc lập**, không liên quan nhau. "Đồng bộ" ở đây chỉ nghĩa là bật/tắt cùng lúc.

- Nội dung nằm hoàn toàn trong `slides.json` — sửa nội dung không phải đụng vào code.
- Mỗi slide có `kind`: `text` (chữ gõ thẳng), `image` hoặc `video` (file trong `media/`).
- Kiểm tra lúc nạp: thiếu màn → lỗi; `id` trùng nhau giữa 2 màn → lỗi (id trùng sẽ khiến bấm nút
  của màn này lại nhảy nội dung sang màn khác); `kind` lạ → lỗi; `src` chứa đường dẫn thay vì tên
  file → lỗi. Nhưng **file media thiếu chỉ ghi cảnh báo**: mất 1 file nội dung không được phép
  làm cả 5 màn hình của bệnh viện không khởi động được.
- Bấm 1 trong 6 nút → `SelectSlideCommand` → chỉ **đúng màn phụ trách** nhận `state_update` mới.
  Không có auto-rotate: người dùng chọn gì thì màn giữ nguyên nội dung đó.

## 7. Hai tầng timer

**Tier-1 (per-chat, trong `ChatSession`)** — riêng cho từng phiên của Màn 2 và Màn 4:

1. Im lặng `TIER1_WARNING_SEC` → gửi `confirm_prompt{kind: tier1_warning}` và bật đồng hồ dọn dẹp.
2. Im lặng thêm `TIER1_CLEANUP_SEC` → `Tier1CleanupFiredCommand` → hủy task AI đang chạy → xóa
   lịch sử trong bộ nhớ → báo cho AI kết thúc phiên → đóng bản ghi trong database → về màn chọn chế độ.
3. Bất kỳ dấu hiệu nào của người dùng (chạm màn, gửi tin, bấm "Tôi vẫn ở đây") đều reset về bước 0.

Hai chi tiết quan trọng, cả hai đều nằm trong `ChatSession.mark_activity()` để mọi nơi gọi đều
đúng mà không phải nhớ tự kiểm tra:

- **Trong lúc đang chờ AI trả lời thì đồng hồ Tier-1 dừng hẳn** — chờ AI không phải là người dùng
  bỏ đi.
- **Chạm màn cũng hủy đồng hồ dọn-dẹp-sau-lỗi.** Đồng hồ đó sinh ra để dọn màn hình đang treo
  thông báo lỗi mà *không có ai* đứng đó; nếu người dùng vẫn đang chạm thì không được phép đóng
  phiên chat của họ giữa chừng.

**Tier-2 (cluster)** — reset khi có `touch_event` từ Màn 2/4, khi 1 phiên chat vừa đóng, hoặc
khi có thao tác trên máy chủ. Bị **hủy** khi còn bất kỳ phiên chat nào đang mở. Hết hạn → cả 5
màn về STANDBY.

⚠️ Sau khi bắn, Tier-2 **không tự khởi động lại** — nó chỉ chạy lại khi có tương tác thật tiếp
theo. (Bug này từng bị bắt bởi `test_tier2_timer_does_not_restart_itself_immediately_after_firing`;
nếu sửa `cluster_controller.py` thì chạy lại test đó.)

`config.py` có `assert` ngay lúc nạp: `TIER1_WARNING + TIER1_CLEANUP < TIER2`. Nếu vi phạm, phiên
chat im lặng sẽ không bao giờ tự đóng, mà Tier-2 lại bị gate bởi "còn phiên chat đang mở" → cả
hệ thống kẹt mãi ở trạng thái thức.

## 8. Chat với Superdoc

**Adapter (`app/superdoc/`).** Chatbot Superdoc thật của khách chưa có tài liệu API. Toàn bộ hệ
thống chỉ nói chuyện qua giao diện `SuperdocProvider` trong `base.py`:

- `reply(history) -> str` — trả lời lượt cuối, ném `SuperdocError` khi hỏng.
- `end_session(session_id)` — **báo cho AI biết đoạn chat đã kết thúc**, đúng yêu cầu
  `descryption.txt` mục 3. Provider hiện tại đều stateless nên đây là no-op, nhưng chatbot
  Superdoc thật có thể là loại giữ phiên phía nó; khi đó đây chính là chỗ gọi endpoint đóng
  phiên, không phải sửa `ChatSession` hay `ClusterController`.

Khi có API thật: thêm 1 file provider, đổi `SUPERDOC_PROVIDER`.

- `mock` (mặc định) — trả lời theo từ khóa, chạy offline, không cần API key.
  Kiểm tra "câu hỏi y tế" chạy **trước** bảng từ khóa: *"tôi bị đau bụng uống thuốc gì"* có chứa
  chữ "thuốc" nên nếu tra từ khóa trước sẽ trả ra vị trí nhà thuốc, trong khi đúng ra phải từ
  chối tư vấn và hướng người bệnh tới quầy tiếp đón. (Lỗi này đã bị test bắt được.)
- `gemini` — gọi `generateContent`. Lưu ý vai trò của AI trong Gemini tên là `model`, không phải
  `assistant` như dùng nội bộ.
- Khởi tạo provider thật thất bại (thiếu key...) → **tự lùi về mock** và ghi log.

**Chống nhầm phiên.** Mọi message liên quan tới chat đều đi qua `_session_for(screen_id, session_id)`
và bị bỏ nếu `session_id` không khớp. Đây là lá chắn cho cả một họ bug: câu trả lời của AI về
muộn sau khi người trước đã bỏ đi sẽ **không** hiện lên màn hình của người kế tiếp.

**Không cho gửi khi AI chưa trả lời xong.** Ô nhập bị khóa ở app màn hình, và backend chặn lần nữa.
Nếu lọt, lịch sử sẽ có 2 lượt `user` liên tiếp — Gemini thật từ chối payload dạng đó.

**Lỗi mạng/AI.** Thất bại → chỉ màn đó nhận `error` + bật đồng hồ `ERROR_CLEANUP_SEC` tự dọn dẹp.
Màn còn lại (nếu đang chat) hoàn toàn không bị ảnh hưởng. Người dùng hỏi lại thành công, hoặc chỉ
cần chạm màn, đều hủy đồng hồ đó.

## 9. Database (`db.py`)

SQLite (thư viện chuẩn, không thêm dependency). 2 bảng: `chat_sessions`, `chat_messages`.
Không lưu bất kỳ thông tin định danh nào — mọi phiên chat đều coi là khách lạ.

Mỗi thao tác mở 1 connection riêng rồi đóng ngay: SQLite gắn connection với thread tạo ra nó, mà
các lệnh ở đây chạy qua `asyncio.to_thread`. Với khối lượng thật (vài tin nhắn/phiên) chi phí này
không đáng kể, đổi lại không phải tự quản lý lock.

Lỗi ghi database **được log nhưng không ném tiếp**: mất 1 bản ghi lịch sử không được phép làm
sập phiên chat của người đang đứng trước màn hình.

## 10. Thao tác trên máy chủ (`host_activity.py`)

Đặc tả yêu cầu hệ thống chỉ ngủ khi *"không có ai tương tác ở màn 2/4 **và** ở máy chủ không có
ai thao tác gì"*. Chạm màn hình đã có WebSocket báo về, nhưng gõ phím/di chuột trực tiếp trên máy
chủ thì giao diện không hề biết — nên phải hỏi thẳng Windows qua `GetLastInputInfo` mỗi 2 giây,
và chỉ đẩy command khi mốc thời gian thực sự đổi. Trên hệ điều hành khác, tính năng tự tắt.

Bản `video_sleep.py` cũ (prototype đầu tiên, nằm ngoài thư mục này) làm việc này bằng cách dùng
`mss` + `cv2` **chụp màn hình và so sánh pixel mỗi 5 giây**. Cách đó vừa nặng vừa không chính xác;
`GetLastInputInfo` là một syscall, không chụp ảnh, không giải mã, không phụ thuộc OpenCV.

## 11. Bố cục màn động

### 11.1 Gán vai trò (`desktop/layout.py`, hàm thuần)

```
N ≥ 6 : màn Primary của Windows = MÀN QUẢN LÝ, các màn còn lại hiển thị
N ≤ 5 : tất cả hiển thị
không màn nào cảm ứng → 1, 2, 3, 4, 5 trái → phải
có cảm ứng            → màn cảm ứng 2, 4; màn thường 1, 3, 5 (trái → phải);
                        màn thừa nhận số còn trống nhỏ nhất; hết số → không dùng
```

Trái → phải = toạ độ `rcMonitor` của Windows (theo sơ đồ trong Settings → Display, **không** theo
cổng cắm). `wall_index` là vị trí trong dãy màn **được dùng** (bỏ màn quản lý và màn thừa) — video
chờ chia theo `wall_index`, không theo vai trò.

`monitors.read_screens()` đọc từ Qt + Win32: `QScreen.nativeInterface().handle()` trả thẳng
HMONITOR → `GetMonitorInfoW` (tên `\\.\DISPLAYn`, toạ độ vật lý, cờ Primary);
`GetPointerDevices` (thiết bị loại TOUCH kèm HMONITOR) → màn nào cảm ứng;
`EnumDisplayDevicesW` → tên card đồ hoạ đang xuất ra màn đó.

### 11.2 Backend chỉ xét vai trò đang có

`POST /api/layout {"displays":[{role, wall_index}]}` → `ClusterLayout.from_displays` (kiểm chặt:
không rỗng, vai trò hợp lệ, không trùng, vị trí 0..n−1; sai → 400 kèm lý do) → `LayoutCommand`.
Chưa ai gửi thì mặc định đủ 5 màn theo thứ tự vai trò.

Trong `ClusterController`:
- Chạm từ vai trò không có trong bố cục bị bỏ qua; đánh thức cặp 2↔4 chỉ khi màn kia có mặt;
  `_all_standby` / `_activate_band` chỉ xét vai trò đang có; bảng 6 nút chỉ còn nút của màn slide đang có.
- Vai trò bị rút ra → phiên chat của nó đóng với lý do `screen_removed`, state về STANDBY.
- Vai trò mới cắm vào lúc hệ thống đang thức → nhận ngay `WAKE_PAIR` + `BAND_ACTIVATE` (vào đúng
  trạng thái "đang thức" như các màn khác).
- Mọi màn nhận lại `state_update` (vị trí tường có thể đã đổi) và `VideoSlicer.ensure(N)`.

### 11.3 Cắm / rút màn (`window_manager.py`)

`screenAdded` / `screenRemoved` / `primaryScreenChanged` và `geometryChanged` /
`logicalDotsPerInchChanged` của từng màn → chờ yên **3 giây** (màn HDMI/DP chập chờn báo liên tục)
→ `rebuild()`: gán lại vai trò; cửa sổ nào vẫn giữ (màn, vai trò) cũ thì **giữ nguyên** và chỉ đặt
lại lên màn; còn lại đóng / mở mới; gửi bố cục cho backend.

Đặt cửa sổ: `setScreen(screen)` → `setGeometry(screen.geometry())` → `showFullScreen()`. Qt tự lo
DPI từng màn — **không tự tính toạ độ**. (Bản Edge cũ lấy toạ độ vật lý từ `screeninfo` rồi đưa cho
Edge vốn hiểu là toạ độ logic → ở scale 150% cửa sổ to gấp rưỡi màn và lấn sang màn bên.)

`SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)` suốt thời gian
chạy: màn DisplayPort ngủ là Windows gỡ nó khỏi danh sách màn.

## 12. App màn hình (`desktop/`)

**Giao diện.** Mọi view (trừ video chờ, slide ảnh/video, màn đen) vẽ trong khung cố định
1920×1080 (`Stage.qml`) rồi co giãn đều theo cửa sổ — đúng kích thước bản thiết kế
(`../design/*.dc.html`, nền trắng, màu nhấn `#1668A8`, phông Be Vietnam Pro đi kèm). Màu và đường
vẽ biểu tượng tập trung ở `Theme.qml`, `Icons.qml`. `DisplayWindow.qml` chọn view theo
`client.view`; chưa kết nối được thì hiện "Đang kết nối" (chờ 2 s mới hiện để backend khởi động lại
nhanh không làm màn chớp).

**Chạm để đánh thức.** Màn 2/4: `_WakeOnPress` (event filter Python trên cửa sổ) gửi
`generic_wake` cho **mọi** lần chạm — kể cả chạm trúng nút hay phím — rồi để sự kiện đi tiếp tới
nút. FSM chỉ dùng `TOUCH_OWN` ở STANDBY (màn 2/4) và PROMPT_CHAT_BUTTON (màn 4), các trạng thái khác
bỏ qua nên không đổi gì ngoài ý muốn; còn phía chat thì mỗi lần chạm (kể cả gõ phím) đều hoãn Tier-1.

**Bàn phím trên màn + Telex.** Không dùng ô nhập thật của Qt: Windows chỉ cho **một** cửa sổ giữ
bàn phím, trong khi màn 2 và màn 4 có thể được gõ cùng lúc. Chữ đang gõ là thuộc tính `draft` của
`ChatView`; phím gọi `telex.type_key(draft, phím)` (`desktop/telex.py`, hàm thuần: chỉ biến đổi từ
cuối, đặt lại dấu thanh sau mỗi phím, kiểu cũ "hòa/thủy", gõ lặp để bỏ biến đổi). Bàn phím hiện khi
chạm ô nhập, ẩn khi chạm vùng hội thoại / phím Ẩn / đổi phiên / hiện hộp thoại; gửi xong vẫn mở.

**Lịch sử chat trên màn** nằm trong `ScreenClient` (`ChatModel`) gắn với `session_id`: đổi phiên,
rời view chat hoặc nhận `session_closed` là xoá sạch. Câu hỏi được thêm ngay khi gửi và ô nhập khoá
ngay (không chờ backend) để bấm gửi 2 lần không thành 2 lượt hỏi.

**Nhận diện màn** (`IdentifyOverlay.qml`, 10 giây): viền 14 px + 4 góc vẽ theo pixel thật của cửa
sổ, số vai trò, độ phân giải, scale, cảm ứng, thiết bị, card đồ hoạ — kiểm căn chỉnh, overscan và gán
cảm ứng ngay tại chỗ.

**Card đồ hoạ.** Máy test có card rời (4 màn) + đồ hoạ tích hợp (1 màn). Mặc định Windows hay đưa
đồ hoạ tích hợp lên đầu danh sách DXGI → Qt vẽ + giải mã cả 5 màn bằng chip yếu. `main.py` ghi
`GpuPreference=2;` cho file đang chạy vào `HKCU\Software\Microsoft\DirectX\UserGpuPreferences`
(đúng thứ Windows Settings → Graphics ghi, có hiệu lực ngay nếu ghi trước khi Qt khởi tạo; đã có
giá trị thì giữ nguyên). `QSG_INFO=1` + bộ lọc log giữ lại dòng `Adapter … using this adapter`.

**Màn hiển thị không bao giờ nhận kích hoạt** (`Qt.WindowDoesNotAcceptFocus` → WS_EX_NOACTIVATE).
Chạm vào 1 cửa sổ mà kích hoạt nó thì cửa sổ đang được chạm khác bị mất kích hoạt, và Qt huỷ thao
tác chạm dở ở đó — 2 người dùng màn 2 và màn 4 cùng lúc sẽ mất chạm / mất phím (đã đo). Đã thử trên
Windows 11: cửa sổ toàn màn hình không kích hoạt vẫn phủ kín vùng taskbar. Hệ quả: app không có nút
trên taskbar, không có trong Alt+Tab, và cửa sổ hiển thị không nhận bàn phím.

**Phím tắt toàn cục** (`win32.GlobalHotkeys`: `RegisterHotKey` + `QAbstractNativeEventFilter`, bắt
`WM_HOTKEY` ở cả `windows_generic_MSG` lẫn `windows_dispatcher_MSG`): Ctrl+Shift+M / I / Q; bị chương
trình khác giữ thì dùng Ctrl+Alt+Shift. Bảng điều khiển có thêm nút Thoát (hỏi xác nhận).

**Canh vị trí thật** (`WindowManager._check_placement`, sau 0,7 s, 2,5 s và mỗi 5 s): hỏi Windows
`GetWindowRect` + `MonitorFromWindow` của từng cửa sổ toàn màn hình, so với `rcMonitor` của màn.
Lệch → đặt lại bằng Qt (thoát toàn màn hình → `setScreen` → `setGeometry` → `showFullScreen`);
lệch lần nữa → ép bằng `SetWindowPos`. Bị thu nhỏ / thoát toàn màn hình → mở lại. Lần 2,5 s ghi
`Màn N khớp …` cho từng màn vào log. Màn hiển thị **không phải màn chính** được đặt topmost và đặt
lại mỗi 5 s (bấm phím Windows xong là taskbar của màn đó lại nổi lên trên); màn chính không topmost
để người vận hành còn mở được Task Manager. Cửa sổ mới tắt hiệu ứng phản hồi chạm của Windows
(`SetWindowFeedbackSetting`).

**Bộ lọc đánh thức** (`_is_press`): Qt gộp mọi màn cảm ứng thành **một** thiết bị. Khi màn 2 đang có
ngón tay đặt mà màn 4 bị chạm, màn 4 nhận `TouchUpdate` có điểm `Pressed` (không phải `TouchBegin`),
màn 2 nhận `TouchUpdate` có điểm `Released` (không phải `TouchEnd`). Qt Quick xử lý theo trạng thái
từng điểm nên nút vẫn ăn; bộ lọc cũng phải nhìn trạng thái điểm, không nhìn loại sự kiện.

**Cổng backend**: `run.py` thử kết nối 127.0.0.1:8000 trước khi nạp cấu hình; có ai nghe thì chọn
cổng trống và đặt `PENTASYNC_PORT` (backend con nhận lại qua biến môi trường).

**Cảnh báo cảm ứng** (`monitors.touch_problem`): thiết bị cảm ứng chưa gắn màn nào, nhiều thiết bị
gắn chung 1 màn, hoặc mọi cảm ứng dồn vào màn chính → ghi log + dòng đỏ trên bảng điều khiển.

## 13. Màn quản lý, màn đen, reset

`WS /ws/admin`: mỗi command làm thay đổi gì đó thì controller gửi **một** `admin_snapshot` trọn gói
(màn đen, giờ khởi động, số màn, 5 thẻ vai trò: có mặt / vị trí / đã kết nối / state / view /
có chat + giờ bắt đầu / slide đang chiếu; danh sách slide; thống kê hôm nay: số phiên, thời lượng
trung bình từ SQLite, số lỗi AI). Dữ liệu nhỏ nên gửi cả gói, không tính phần chênh.

Lệnh `admin_command`:

| `action` | Việc |
|---|---|
| `select_slide` | Chọn slide cho bất kỳ màn slide nào đang có, không cần màn 2 ở bảng 6 nút |
| `force_standby` | Như Tier-2 hết hạn (đóng chat với lý do `cluster_reset`), rồi huỷ Tier-2 |
| `blackout_on` | Đóng mọi chat (`blackout`), mọi vai trò về STANDBY, view `blackout`; **bỏ qua** chạm, thao tác máy chủ, chọn slide; huỷ Tier-2 |
| `blackout_off` | Hết màn đen → mọi màn về video chờ |
| `reset` | Đóng mọi chat (`system_reset`), slide về mặc định, tắt màn đen, về STANDBY. App tạo lại toàn bộ cửa sổ hiển thị |
| `refresh` | Tính lại thống kê |

Kết nối mỗi màn có `conn_id` riêng: tin "ngắt" đến muộn của kết nối cũ không xoá nhầm kết nối mới
(màn vừa mở lại) khỏi trạng thái "đã kết nối" trên bảng.

Màn đen trong QML là một hình chữ nhật đen — không có đầu phát nào sống, máy được nghỉ.

## 14. Đóng gói (`packaging/`)

`PentaSync.spec` (PyInstaller, 1 thư mục, không console) gói `desktop/` + `backend/app` + QML +
phông + ffmpeg của `imageio-ffmpeg`, bỏ các phần Qt không dùng (WebEngine, 3D, Charts, Controls…).
Cùng một exe chạy cả hai vai: `PentaSync.exe` (app) và `PentaSync.exe --backend` (`run.py` rẽ nhánh).

`app/config.py` nhận biết `sys.frozen`: thứ người vận hành sửa được (`content_manifest/`,
`video/`) nằm **cạnh exe**; thứ máy tự sinh (database, log, cache lát) nằm trong `data/`. Chạy từ mã
nguồn thì giữ bố cục thư mục `system/`. Tên bệnh viện nằm trong `slides.json` (`hospital_name`) và
thời gian chờ đổi được qua biến môi trường `PENTASYNC_*` — để bản exe vẫn cấu hình được mà không
sửa code. `build.py` chạy PyInstaller rồi chép nội dung, video, cache lát, tài liệu,
`chay_thu_nhanh.bat`.

## 15. Test

**Backend — 176 test** (`cd backend && ..\.venv\Scripts\python -m pytest -q`):

| File | Nội dung |
|---|---|
| `test_screen_fsm.py` | Mọi cạnh transition của cả 3 vai trò màn |
| `test_cluster_controller.py` | Đánh thức, dải slide, 6 nút, chat song song, hành vi chéo, Tier-2, kết nối lại |
| `test_chat_flow.py` | Hỏi–đáp AI, lịch sử, lưu database, Tier-1 2 tầng, lỗi AI cục bộ |
| `test_layout_admin.py` | Bố cục 1–5 màn, cắm/rút giữa chừng, lát video, ảnh chụp quản lý, conn_id, mọi lệnh quản lý, màn đen, reset, thống kê |
| `test_video_slicer.py` | Lệnh ffmpeg; cắt thật video tí hon và so từng lát với đúng phần của video gốc; cache theo nội dung; huỷ việc cũ; thiếu ffmpeg/video |
| `test_admin_routes.py` | `/ws/admin`, `POST /api/layout` (200/400/422), route lát video |
| `test_slide_band.py` | 6 nút, chọn slide, slide ảnh/video, chặn manifest sai |
| `test_superdoc.py` | Mock, factory fallback, shape request Gemini + các đường lỗi (không chạm mạng) |
| `test_host_activity.py` | Chỉ báo khi mốc input thật sự đổi; tự tắt khi OS không hỗ trợ |
| `test_timers.py` | ResettableTimer: bắn đúng hạn, cancel, reset |
| `test_ws_protocol.py` | Round-trip WebSocket thật, route media, chống path traversal, payload hỏng |

**App — 151 test** (`cd desktop && ..\.venv\Scripts\python -m pytest -q`): `test_layout.py`
(bảng ca 1–7 màn, cảm ứng 0–3, màn quản lý ở giữa dãy, toạ độ âm), `test_telex.py` (từ thường gặp,
gõ lặp, chữ hoa, vị trí dấu sau khi xoá), `test_standby_sync.py` (công thức + đầu phát giả: không
tua vì 1 lần đọc cũ), `test_screen_client.py` (lịch sử theo phiên, khoá ô nhập, Tier-1, lỗi),
`test_wake_filter.py` (điểm Pressed trong TouchUpdate), `test_monitors.py` (cảnh báo gán cảm ứng),
`test_win32.py` (so khung, phím tắt toàn cục), `test_run.py` (tự đổi cổng).

**Dò lỗi tĩnh:** `.venv\Scripts\python -m ruff check .` (cấu hình `ruff.toml` — chỉ bật luật bắt lỗi
thật, không bật luật thuần phong cách) và
`.venv\Scripts\pyside6-qmllint -I desktop\qml desktop\qml\*.qml desktop\qml\PentaSync\*.qml`.

**Bài kiểm tra tay** (`test/`, cần cửa sổ thật nên pytest không làm được): `xem_giao_dien.py` dựng
từng view với dữ liệu giả rồi chụp ảnh; `gia_lap_nhieu_man.py` giả lập 6 màn chạy trọn luồng;
`kiem_tra_cham.py` chạm thật bằng `InjectTouchInput` (1 màn / cảm ứng chưa gắn màn / 2 người 2 màn);
`kiem_tra_exe.py` kiểm bản đóng gói. Chi tiết và kỳ vọng từng bài: `descryption.md` mục 10.

## 16. Đã kiểm chứng chạy thật (ngoài pytest)

Trên laptop dev (1 màn 2560×1440, scale 150%, AMD tích hợp + NVIDIA rời):

- Cửa sổ khớp tuyệt đối màn (`FullScreen`, hình học cửa sổ = hình học màn).
- Ảnh chụp mọi view (dữ liệu giả) khớp bản thiết kế; không cảnh báo QML.
- **Giả lập 6 màn** (vá `read_screens` trả 6 màn trên cùng 1 màn thật, backend thật, AI giả): đánh
  thức qua bộ lọc chạm, bảng 6 nút, chọn slide từ màn 2 và từ bảng quản lý, chạm màn 4 → chat → có
  trả lời, màn đen bỏ qua chạm, bật lại, reset tạo lại cửa sổ — đạt từng bước.
- Tài nguyên 5 cửa sổ phát lát + bảng quản lý + backend (+ dwm): CPU 4,4%, RAM ~1,3 GB.
- Vẽ bằng NVIDIA trong khi màn gắn chip AMD: lên hình, video chạy.
- Bản exe chép sang thư mục khác: chạy không cần Python, dùng lát có sẵn, tắt ngang app → backend
  tắt theo, cổng 8000 đóng.

- **Chạm thật của Windows** (`InjectTouchInput` — Windows cho giả lập cảm ứng không cần phần cứng;
  thiết bị giả hiện trong `GetPointerDevices` là loại TOUCH chưa gắn màn):
  1 màn cảm ứng 23/23 bước (đánh thức, menu, giữ lâu 1,2 s, gõ Telex, xoá, gửi, ẩn bàn phím, hỏi
  "còn ở đây", 2 ngón); cảm ứng chưa gắn màn 9/9 (có cảnh báo, không nhận nhầm vai trò);
  **2 thiết bị chạm cho 2 cửa sổ cạnh nhau, chạm và gõ chồng thời gian** 10/10 × 2 lần.
  Các bài này nằm ở `test/kiem_tra_cham.py` (`motman` / `chuagan` / `haiman`), chạy lại được.
- Cố tình làm lệch cửa sổ → tự về đúng màn. Chiếm cổng 8000 → tự đổi cổng. Bản exe: giết backend
  giữa chừng → dựng lại + gửi lại bố cục; Ctrl+Shift+Q thoát sạch.

Chưa kiểm chứng được: nhiều màn **vật lý** khác độ phân giải/scale, cảm ứng thật (phần cứng), cắm/rút màn thật,
card 4070 Ti S + đồ hoạ tích hợp — xem `HUONG_DAN_TEST.md`.

## 17. Những cái bẫy đã gỡ, đừng dựng lại

**App Qt / đóng gói**
- **Cửa sổ hiển thị nhận kích hoạt** — 2 người chạm 2 màn cùng lúc làm Qt huỷ chạm dở của nhau.
  Giữ `Qt.WindowDoesNotAcceptFocus`.
- **Bộ lọc chạm chỉ nghe `TouchBegin`** — chạm chồng thời gian ở màn khác đến dạng `TouchUpdate`.
- **Bắt chạm ở vùng cha của `ListView`** — Flickable nuốt chạm; TapHandler phải nằm trong ListView.
- **Chuyển sang cảm ứng kiểu cũ `QT_QPA_PLATFORM=windows:nowmpointer`** — đã thử, mất chạm nhiều hơn.
- **Giả lập 2 người bằng 1 thiết bị chạm 2 ngón** — Windows gộp cả 2 ngón vào 1 khung, không giống 2 màn
  cảm ứng thật (2 thiết bị). Mỗi màn cảm ứng giả phải là 1 tiến trình `InitializeTouchInjection` riêng.
- **Tin Qt đặt cửa sổ đúng mà không đo lại** — đo bằng `GetWindowRect` và tự sửa (mục 12).
- **Đưa toạ độ vật lý cho cửa sổ hiểu toạ độ logic** — nguyên nhân lỗi lấn màn của bản Edge. Dùng
  `setScreen` + `screen.geometry()` + `showFullScreen()`, không tự tính.
- **`QScreen.name()` là tên model màn**, không phải `\\.\DISPLAYn` — khớp với Win32 qua
  `nativeInterface().handle()`.
- **QtWebEngine không phát được H.264** (bản PySide6 dựng sẵn) — vì vậy video dùng QtMultimedia.
- **Tín hiệu `closing` của cửa sổ QML** không nối được vào slot Python (PySide không chuyển được
  `QQuickCloseEvent`) — dùng `visibleChanged`.
- **Đo lệch đồng hồ lúc view dựng xong** thay vì lúc nhận message — lần đầu nạp QtMultimedia mất
  ~0,5 s nên mọi màn chậm nửa giây mà bộ đồng bộ tưởng đã khớp.
- **Tua ngay khi thấy lệch lớn một lần** — giao diện khựng một nhịp (vd chụp màn hình) làm
  `position()` cũ, tua nhầm gây giật. Phải lệch lớn 2 nhịp liền.
- **Tin số đo đồng bộ ngay sau `grabWindow()`** — chụp 2560×1440 làm treo vòng sự kiện ~0,5 s.
- **Qt tự chọn đồ hoạ tích hợp** trên máy lai — xem mục 12 "Card đồ hoạ". Chạy từ `.venv` thì
  tiến trình thật là `python.exe` gốc (python.exe của venv chỉ là trình khởi chạy) — thiết lập
  card phải ghi cho đường dẫn đó.
- **`requirements.txt` có chữ tiếng Việt có dấu** — pip 21 đọc theo cp1252 và lỗi. Giữ file ASCII.
  Tương tự `.bat`: chỉ ASCII, xuống dòng CRLF.
- **In chữ tiếng Việt ra cửa sổ lệnh** — cmd mặc định là cp1252, `print` ném `UnicodeEncodeError` và
  làm script chết giữa bài (đã gặp ở `packaging/build.py` và các script trong `test/`). Mọi entry
  point in ra console phải `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`; `main.py`
  làm việc này cho cả `StreamHandler` của log.
- **Mount `/src` khi không có `frontend/`** — `StaticFiles` ném lỗi lúc import, backend bản exe
  chết ngay. Mount này (và route `/screen/{id}`) đã bỏ cùng giao diện web; bài học vẫn đúng cho mọi
  `StaticFiles` mới: chỉ mount khi thư mục chắc chắn tồn tại.
- **Test đọc cache lát video thật của máy** — kết quả đổi theo máy. Test route dùng thư mục tạm.
- **Khoá cache theo đường dẫn file** — chép sang máy khác là phải cắt lại vài phút. Khoá theo nội dung.

**Backend**
- **Mount `/assets` trỏ tới thư mục rỗng.** `StaticFiles` ném `RuntimeError` ngay lúc import nếu
  thư mục không tồn tại, mà nén zip thì bỏ thư mục rỗng. Route `/media/{filename}` cố tình **không**
  dùng `StaticFiles` vì lý do này, và `media/` có sẵn `README.txt` để không bao giờ rỗng.
- **Trừ thời gian video theo đường thẳng thay vì theo vòng tròn** — lúc video vừa lặp lại, sai số
  bằng gần hết độ dài video.
- **`/ws/admin` đăng ký sau `/ws/{screen_id}`** — bị route kia bắt mất và từ chối vì "admin"
  không phải số.
- **Dùng thẳng video 4K60** — bộ giải mã quá tải, rớt khung, các màn trôi khỏi nhau dù CPU trông
  nhàn. Video chờ nên là H.264 ~30 fps, cao 1080.

**Bản web cũ (còn giữ làm dự phòng)**
- `MONITOR_INDEX_OVERRIDE` gán trùng `screen_id` → 1 cửa sổ thành "xác sống"; launcher chặn ở `--dry-run`.
- `standby_view.js` phải tự dừng vòng đồng bộ và `pause()` video khi rời DOM.
- Đo hiệu năng phải dùng 5 **cửa sổ**, không phải 5 **tab** (tab ẩn bị Chromium tiết lưu).

## 18. Nguyên tắc giữ giao thức gọn

Không khai báo trước trường hay loại message "để dành cho sau này". Đã có một lượt cắt bỏ toàn bộ
lớp phòng xa không ai dùng: `ping`/`pong`, `hello`, `chat_cancel`, `TouchEventMsg.payload`,
`ChatMessageAckMsg.streaming`/`done`/`message_id`, `ErrorMsg.recoverable`/`cleanup_in_sec`,
`ConfirmPromptMsg.options`/`prompt_id`, `CONFIRM_DIALOG_TIMEOUT_SEC`, `MUTE_AMBIENT_AUDIO`,
`STANDBY_CLOCK_RESYNC_SEC`, `/api/clock`, `STANDBY_CYCLE_SEC`.

Thừa một trường là thừa một thứ để hiểu nhầm và để lệch giữa backend với app.

*(Route phục vụ video chờ từng bị xoá ở lượt đó vì bản canvas không dùng tới. Nay quay lại dưới
tên `/standby-video` vì có lý do thật — nguyên tắc là xoá thứ **hiện không ai dùng**, không phải
cấm vĩnh viễn.)*
