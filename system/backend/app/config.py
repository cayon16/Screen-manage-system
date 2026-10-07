import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Bản đóng gói (PentaSync.exe): mã nguồn nằm trong _internal/, còn những thứ người vận hành sửa
# được (nội dung slide, video chờ) nằm NGAY CẠNH file exe; thứ máy tự sinh (database, log, lát
# video) nằm trong data/ cạnh exe. Chạy từ mã nguồn thì giữ nguyên bố cục thư mục system/.
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    APP_HOME = Path(sys.executable).resolve().parent
    PROJECT_DIR = APP_HOME
    CONTENT_MANIFEST_DIR = APP_HOME / "content_manifest"
    DATA_DIR = APP_HOME / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
else:
    PROJECT_DIR = BACKEND_DIR.parent  # thư mục system/
    CONTENT_MANIFEST_DIR = BACKEND_DIR / "content_manifest"
    DATA_DIR = BACKEND_DIR

HOST = "127.0.0.1"
# App màn hình tự chọn cổng khác (và truyền cho backend qua biến này) nếu 8000 đang bị chiếm.
PORT = int(os.environ.get("PENTASYNC_PORT", "8000"))

# Danh sách screen_id hợp lệ và vai trò từng màn (trái sang phải theo đặc tả khách hàng)
PASSIVE_SCREENS = (1, 3, 5)   # chỉ thụ động, không nhận input
CONTROL_SCREEN = 2            # menu: Thông tin bệnh viện / Chat
CHAT_SCREEN = 4               # chỉ chat, chạm là vào thẳng CHAT
TOUCH_SCREENS = (CONTROL_SCREEN, CHAT_SCREEN)
ALL_SCREENS = (1, 2, 3, 4, 5)

# Chỉ 3 màn thụ động mới trình chiếu slide. Màn 2 giữ bảng điều khiển 6 nút, màn 4 giữ nút
# "Chạm để chat" — chốt theo descryption.txt ("mỗi màn 2 slide --> tương đương 6 nút").
SLIDE_SCREENS = PASSIVE_SCREENS

# Mỗi thời gian chờ dưới đây đổi tạm được bằng biến môi trường cùng tên có tiền tố PENTASYNC_
# (vd PENTASYNC_TIER2_CLUSTER_IDLE_SEC=30) — dùng khi test nhanh, kể cả với bản PentaSync.exe.
def _seconds(name: str, default: int) -> int:
    return int(os.environ.get(f"PENTASYNC_{name}", default))


# ---- Tier-1: per-chat timer (riêng cho Màn 2 và Màn 4) ----
# Sau bao nhiêu giây im lặng (không gửi tin/không nhận phản hồi mới) thì hiện cảnh báo "còn chat không?"
TIER1_WARNING_SEC = _seconds("TIER1_WARNING_SEC", 30)
# Sau cảnh báo, chờ thêm bao nhiêu giây không phản hồi thì tự dọn dẹp (xóa lịch sử, đóng phiên, về Standby)
TIER1_CLEANUP_SEC = _seconds("TIER1_CLEANUP_SEC", 30)

# ---- Tier-2: cluster timer (toàn hệ thống) ----
# Khi không còn phiên chat nào mở, không lỗi nào treo, và đã qua ngần này giây không có touch_event
# từ Màn 2/4 thì đưa cả 5 màn về Standby.
TIER2_CLUSTER_IDLE_SEC = _seconds("TIER2_CLUSTER_IDLE_SEC", 120)

# Bất biến bắt buộc theo đặc tả: 1 phiên chat im lặng phải tự dọn dẹp TRƯỚC khi cả cụm ngủ,
# nếu không Tier-2 sẽ không bao giờ chạy được (nó bị gate bởi "còn phiên chat đang mở").
assert TIER1_WARNING_SEC + TIER1_CLEANUP_SEC < TIER2_CLUSTER_IDLE_SEC, (
    "TIER1_WARNING_SEC + TIER1_CLEANUP_SEC phải nhỏ hơn TIER2_CLUSTER_IDLE_SEC"
)

# Lỗi mạng/AI: đếm ngược tự dọn dẹp cục bộ cho đúng màn bị lỗi
ERROR_CLEANUP_SEC = 15

# ---- Video chế độ chờ ----
# ĐỔI VIDEO CHỜ = SỬA ĐÚNG DÒNG NÀY. Đường dẫn tính TƯƠNG ĐỐI từ thư mục system/ (bản đóng gói:
# thư mục chứa PentaSync.exe — ở đó chỉ cần chép đè file video/standby_wall.mp4), nên copy cả
# thư mục sang máy khác (hoặc đổi ổ đĩa, đổi tên user) vẫn chạy được, không phải sửa gì thêm.
#
# Hệ thống chỉ làm đúng một việc: cắt video thành 5 phần bằng nhau theo chiều ngang, mỗi màn 1
# phần. Không có phép co giãn nào phức tạp.
#
# Về tỉ lệ: 5 màn 16:9 ghép ngang lại thành một khung ~8.9:1.
#   - Video có tỉ lệ ~8.9:1 (vd 9600x1080) -> cắt 5 phần khớp 1:1, KHÔNG méo chút nào.
#   - Video 16:9 thông thường -> bị giãn ngang ~5 lần cho vừa tường. Chấp nhận tạm.
# Muốn hết méo thì đổi sang video siêu rộng, không phải sửa code.
STANDBY_VIDEO_REL_PATH = "video/standby_wall.mp4"
STANDBY_VIDEO_PATH = PROJECT_DIR / STANDBY_VIDEO_REL_PATH
# Nơi lưu các lát video đã cắt sẵn (mỗi màn 1 lát). Tự tạo lại được, xoá thoải mái.
STANDBY_SLICE_CACHE_DIR = DATA_DIR / "_cache" / "standby_slices"

# ---- Superdoc (AI) ----
# AI dang dung (chế độ demo / nội bộ / công khai) đổi lúc đang chạy qua API /api/ai — xem docs/ai_api.md.
# Lần đầu chưa có file cấu hình thì lấy từ biến môi trường SUPERDOC_PROVIDER (xem superdoc/settings.py).
# Cấu hình AI đang dùng (chế độ, nhà cung cấp, model...) lưu ở file này và đổi lúc đang chạy qua
# API /api/ai. File KHÔNG chứa API key: key chỉ nằm trong biến môi trường có tên dưới đây.
AI_SETTINGS_PATH = DATA_DIR / "ai_settings.json"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
INTERNAL_TOKEN_ENV = "SUPERDOC_INTERNAL_TOKEN"
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"
ANTHROPIC_DEFAULT_MODEL = "claude-opus-5-5"
# Quá thời gian này mà AI chưa trả lời -> coi như lỗi, màn đó tự dọn dẹp (không treo cả hệ thống).
SUPERDOC_TIMEOUT_SEC = 30.0
# Số lượt hội thoại gần nhất gửi kèm làm ngữ cảnh (giới hạn để không phình payload theo thời gian).
SUPERDOC_HISTORY_LIMIT = 20
SUPERDOC_SYSTEM_PROMPT = (
    "Bạn là Superdoc — trợ lý ảo đặt tại màn hình hành lang bệnh viện. "
    "Trả lời ngắn gọn, dễ hiểu, bằng tiếng Việt, tối đa 4 câu. "
    "Bạn KHÔNG được chẩn đoán bệnh hay kê đơn thuốc; với câu hỏi y tế cá nhân, "
    "hãy hướng dẫn người dùng tới quầy tiếp đón hoặc bác sĩ trực. "
    "Chỉ viết văn bản thường: không dùng markdown, không dùng dấu * hay # để định dạng."
)

# ---- Database ----
# SQLite (thư viện chuẩn, không thêm dependency). Lưu toàn bộ lịch sử chat, coi mọi người
# chat là khách lạ — không lưu bất kỳ thông tin định danh nào.
DB_PATH = DATA_DIR / "pentasync.db"

# ---- Thao tác trên máy chủ ----
# Chu kỳ hỏi Windows xem lần cuối có input (chuột/phím) là bao giờ. Có thao tác trên máy chủ
# cũng được tính là "hệ thống đang được dùng" -> reset Tier-2 và đánh thức khỏi Standby.
HOST_ACTIVITY_POLL_SEC = 2.0
# Đặt PENTASYNC_HOST_ACTIVITY=0 để tắt. Cần khi ngồi lập trình trên chính máy chạy backend:
# gõ phím liên tục sẽ khiến hệ thống không bao giờ vào được Standby để kiểm tra.
HOST_ACTIVITY_ENABLED = os.environ.get("PENTASYNC_HOST_ACTIVITY", "1") != "0"

LOG_FILE = DATA_DIR / "pentasync_log.txt"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB, xoay vòng giữ 1 bản backup
