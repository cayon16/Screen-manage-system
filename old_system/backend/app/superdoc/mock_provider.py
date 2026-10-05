from __future__ import annotations

import asyncio
from typing import Sequence

from app.superdoc.base import SuperdocError, Turn

# Provider mac dinh: khong goi mang, khong can API key. Muc dich la de chay va test toan bo
# luong chat (go tin -> hien "dang tra loi" -> nhan cau tra loi -> reset Tier-1 timer) ma khong
# phu thuoc internet hay quota. Cau tra loi la co dinh theo tu khoa, khong phai AI that.

_KEYWORD_ANSWERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("giờ", "mấy giờ", "thời gian", "lịch"),
        "Bệnh viện khám từ 07:00 đến 16:30 các ngày thứ 2 đến thứ 6, thứ 7 khám buổi sáng "
        "đến 12:00. Khoa Cấp cứu trực 24/7 kể cả chủ nhật và ngày lễ.",
    ),
    (
        ("cấp cứu", "khẩn", "gấp"),
        "Khoa Cấp cứu ở Khu A, Tầng 1, ngay bên phải cổng chính và trực 24/7. "
        "Trường hợp khẩn cấp bạn có thể gọi 115.",
    ),
    (
        ("bảo hiểm", "bhyt", "thẻ"),
        "Bạn mang thẻ BHYT còn hạn cùng giấy tờ tùy thân tới quầy tiếp đón Tầng 1 để đăng ký. "
        "Nếu khám trái tuyến, mức chi trả sẽ thấp hơn — nhân viên quầy sẽ tư vấn cụ thể.",
    ),
    (
        ("đăng ký", "khám", "quy trình", "thủ tục"),
        "Bạn lấy số thứ tự tại quầy tiếp đón Tầng 1, đăng ký khám, rồi chờ gọi số vào phòng khám. "
        "Sau khi khám xong, bạn đóng viện phí và nhận thuốc cũng tại Tầng 1.",
    ),
    (
        ("nhà thuốc", "thuốc", "lãnh thuốc"),
        "Nhà thuốc bệnh viện ở Khu A, Tầng 1, mở cửa cùng giờ khám bệnh. "
        "Bạn xuất trình đơn thuốc của bác sĩ để được cấp phát.",
    ),
    (
        ("ở đâu", "chỗ nào", "đường", "sơ đồ", "tầng"),
        "Khu A là tiếp đón và cấp cứu, Khu B là khám ngoại trú và xét nghiệm, Khu C là khu nội trú, "
        "Khu D là chẩn đoán hình ảnh. Sơ đồ chi tiết đang hiển thị trên màn hình bên phải.",
    ),
    (
        ("thăm", "người nhà", "nuôi bệnh"),
        "Giờ thăm bệnh là 11:00 - 12:30 và 17:00 - 19:00 hằng ngày. "
        "Mỗi bệnh nhân chỉ bố trí 01 người nhà ở lại chăm sóc.",
    ),
)

# Cac dau hieu cho thay nguoi dung dang hoi ve tinh trang suc khoe CUA CHINH HO. Phai giu that
# cu the: tu chung chung nhu "benh" xuat hien trong gan het cau hoi ("benh vien may gio mo cua?")
# se lam moi cau hoi hanh chinh binh thuong deu bi tu choi tra loi.
_MEDICAL_HINTS = (
    "tôi bị",
    "em bị",
    "cháu bị",
    "bị bệnh",
    "đau",
    "sốt",
    "triệu chứng",
    "thuốc gì",
    "chẩn đoán",
    "chữa",
)

_DEFAULT_ANSWER = (
    "Xin lỗi, tôi chưa có thông tin cho câu hỏi này. Bạn có thể hỏi tôi về giờ khám, "
    "quy trình đăng ký, bảo hiểm y tế, hoặc vị trí các khoa phòng trong bệnh viện."
)

_MEDICAL_ANSWER = (
    "Tôi không thể chẩn đoán bệnh hay tư vấn thuốc. Bạn vui lòng tới quầy tiếp đón Tầng 1 "
    "để được đăng ký khám với bác sĩ chuyên khoa nhé."
)


class MockSuperdocProvider:
    """Provider gia lap — tra loi theo tu khoa, tre nhan tao 0.4s cho giong goi mang that."""

    name = "mock"

    def __init__(self, latency_sec: float = 0.4):
        self._latency_sec = latency_sec

    async def reply(self, history: Sequence[Turn]) -> str:
        if not history:
            raise SuperdocError("history rong — khong co gi de tra loi")

        await asyncio.sleep(self._latency_sec)

        question = history[-1].text.lower()

        # Kiem tra y te PHAI di truoc bang tu khoa: "toi bi dau bung uong thuoc gi" co chua tu
        # "thuoc" nen neu tra cuu tu khoa truoc se tra ra vi tri nha thuoc — dung ra phai tu choi
        # tu van va huong nguoi benh toi quay tiep don.
        if any(h in question for h in _MEDICAL_HINTS):
            return _MEDICAL_ANSWER

        for keywords, answer in _KEYWORD_ANSWERS:
            if any(k in question for k in keywords):
                return answer
        return _DEFAULT_ANSWER

    async def end_session(self, session_id: str) -> None:
        # Provider nay khong giu trang thai gi phia server -> khong co gi de dong.
        return None

    async def aclose(self) -> None:
        return None
