"""Bộ gõ tiếng Việt kiểu Telex cho bàn phím trên màn hình — hàm thuần.

Chỉ xử lý TỪ CUỐI của đoạn đang gõ (con trỏ luôn ở cuối — màn chat kiosk không cho di con trỏ).
Mỗi lần gõ 1 phím, từ cuối được biến đổi rồi đặt lại dấu thanh cho đúng vị trí, nên gõ dấu
trước hay sau đều ra cùng kết quả: "hoaf" + "n" → "hoàn", "tieengs" = "tiesng" = "tiếng".

    aa â   ee ê   oo ô   aw ă   ow ơ   uw ư   uow ươ   dd đ   w (đứng riêng) ư
    s sắc  f huyền  r hỏi  x ngã  j nặng  z bỏ dấu
    Gõ lặp phím để bỏ biến đổi: "aaa" → "aa", "ass" → "as", "ddd" → "dd".

Đặt dấu theo kiểu cũ (giống mặc định của Unikey): "hòa", "khỏe", "thủy".
"""

from __future__ import annotations

TONE_KEYS = {"s": 1, "f": 2, "r": 3, "x": 4, "j": 5}
REMOVE_TONE_KEY = "z"

# nguyên âm gốc → 6 dạng thanh: không dấu, sắc, huyền, hỏi, ngã, nặng
_TONED = {
    "a": "aáàảãạ", "ă": "ăắằẳẵặ", "â": "âấầẩẫậ",
    "e": "eéèẻẽẹ", "ê": "êếềểễệ",
    "i": "iíìỉĩị",
    "o": "oóòỏõọ", "ô": "ôốồổỗộ", "ơ": "ơớờởỡợ",
    "u": "uúùủũụ", "ư": "ưứừửữự",
    "y": "yýỳỷỹỵ",
}
# ký tự có dấu (cả hoa lẫn thường) → (nguyên âm gốc viết thường, thanh, là chữ hoa)
_SPLIT: dict[str, tuple[str, int, bool]] = {}
for _base, _forms in _TONED.items():
    for _tone, _ch in enumerate(_forms):
        _SPLIT[_ch] = (_base, _tone, False)
        _SPLIT[_ch.upper()] = (_base, _tone, True)

_VOWELS = set(_TONED)
_WITH_MARK = set("ăâêôơư")  # nguyên âm đã có mũ/móc/trăng — ưu tiên nhận dấu thanh

_CIRCUMFLEX = {"a": "â", "e": "ê", "o": "ô", "ă": "â", "ơ": "ô"}
_UNCIRCUMFLEX = {"â": "a", "ê": "e", "ô": "o"}
_BREVE_HORN = {"a": "ă", "o": "ơ", "u": "ư", "â": "ă", "ô": "ơ"}
_UNBREVE_HORN = {"ă": "a", "ơ": "o", "ư": "u"}

_LETTERS = set("abcdefghijklmnopqrstuvwxyzđ") | set(_SPLIT) | {"Đ"}


def _is_letter(ch: str) -> bool:
    return ch.lower() in _LETTERS or ch in _SPLIT


class _Word:
    """Từ đang gõ, tách thành các chữ (gốc thường + cờ hoa) và 1 dấu thanh chung."""

    def __init__(self, text: str):
        self.chars: list[str] = []
        self.upper: list[bool] = []
        self.tone = 0
        for ch in text:
            if ch in _SPLIT:
                base, tone, upper = _SPLIT[ch]
                if tone:
                    self.tone = tone
                self.chars.append(base)
                self.upper.append(upper)
            else:
                self.chars.append(ch.lower())
                self.upper.append(ch != ch.lower())

    def append(self, key: str) -> None:
        self.chars.append(key.lower())
        self.upper.append(key != key.lower())

    # ---------- cụm nguyên âm ----------

    def vowel_span(self) -> tuple[int, int] | None:
        """[đầu, cuối) của cụm nguyên âm chính. "qu" và "gi" đứng trước nguyên âm khác thì
        chữ u / i thuộc về phụ âm đầu."""
        chars = self.chars
        start = next((i for i, c in enumerate(chars) if c in _VOWELS), None)
        if start is None:
            return None
        end = start
        while end < len(chars) and chars[end] in _VOWELS:
            end += 1
        if end - start > 1 and start > 0:
            before = chars[start - 1]
            if (before == "q" and chars[start] == "u") or (before == "g" and chars[start] == "i"):
                start += 1
        return start, end

    def tone_position(self) -> int | None:
        span = self.vowel_span()
        if span is None:
            return None
        start, end = span
        vowels = self.chars[start:end]
        marked = [i for i, c in enumerate(vowels) if c in _WITH_MARK]
        if marked:
            # "ươ" → dấu nằm trên ơ
            return start + marked[-1] if vowels[marked[0]] == "ư" and len(marked) > 1 else start + marked[0]
        if len(vowels) == 1:
            return start
        if len(vowels) >= 3:
            return start + 1
        has_final_consonant = end < len(self.chars)
        return start + 1 if has_final_consonant else start

    def normalize(self) -> None:
        """"uơ" mà còn chữ đứng sau thì phải là "ươ": "duowng" gõ tới "w" mới là "duơ", tới
        "n" thì thành "dươn"."""
        span = self.vowel_span()
        if span is None:
            return
        start, end = span
        for i in range(start, end - 1):
            if self.chars[i] == "u" and self.chars[i + 1] == "ơ" and i + 2 < len(self.chars):
                self.chars[i] = "ư"

    # ---------- xuất ra ----------

    def render(self) -> str:
        pos = self.tone_position() if self.tone else None
        out = []
        for i, (c, up) in enumerate(zip(self.chars, self.upper, strict=True)):
            if i == pos:
                c = _TONED[c][self.tone]
            out.append(c.upper() if up else c)
        return "".join(out)


def _split_last_word(text: str) -> tuple[str, str]:
    i = len(text)
    while i > 0 and _is_letter(text[i - 1]):
        i -= 1
    return text[:i], text[i:]


def _apply(word: _Word, key: str) -> bool:
    """Thử biến đổi từ theo phím Telex. Trả False nếu phím này chỉ là chữ thường."""
    k = key.lower()
    span = word.vowel_span()
    chars = word.chars

    if k in TONE_KEYS and span is not None:
        tone = TONE_KEYS[k]
        if word.tone == tone:
            word.tone = 0
            word.append(key)  # gõ lặp → bỏ dấu, giữ chữ
        else:
            word.tone = tone
        return True

    if k == REMOVE_TONE_KEY and word.tone:
        word.tone = 0
        return True

    if k == "d" and chars and chars[0] in ("d", "đ"):
        if chars[0] == "d":
            chars[0] = "đ"
        else:
            chars[0] = "d"
            word.append(key)
        return True

    if k in ("a", "e", "o") and span is not None:
        start, end = span
        for i in range(end - 1, start - 1, -1):
            c = chars[i]
            if _UNCIRCUMFLEX.get(c) == k:
                chars[i] = k
                word.append(key)  # "aaa" → "aa"
                return True
            if c in _CIRCUMFLEX and (c == k or _UNCIRCUMFLEX.get(_CIRCUMFLEX[c]) == k):
                chars[i] = _CIRCUMFLEX[c]
                return True
        return False

    if k == "w":
        return _apply_w(word, key, span)

    return False


def _apply_w(word: _Word, key: str, span: tuple[int, int] | None) -> bool:
    chars = word.chars
    if span is None:
        # "w" đứng sau phụ âm (hoặc đứng riêng) là chữ ư: "tw" → "tư"
        word.append("U" if key == "W" else "u")
        chars[-1] = "ư"
        return True

    start, end = span
    cluster = "".join(chars[start:end])

    pair = cluster.find("uo")
    if pair >= 0:
        u, o = start + pair, start + pair + 1
        # "thuở", "huơ" không có gì sau ơ; "dương", "người" thì có → ươ. Nếu ươ chưa đủ điều
        # kiện ngay lúc này, normalize() sẽ đổi khi gõ tiếp chữ sau.
        chars[o] = "ơ"
        if o + 1 < len(chars):
            chars[u] = "ư"
        return True
    for pair_text in ("ưo", "uơ"):
        pair = cluster.find(pair_text)
        if pair >= 0:
            chars[start + pair], chars[start + pair + 1] = "ư", "ơ"
            return True

    if any(c in _UNBREVE_HORN for c in chars[start:end]):
        # gõ lặp → trả lại chữ gốc, thêm chữ w
        for i in range(start, end):
            chars[i] = _UNBREVE_HORN.get(chars[i], chars[i])
        word.append(key)
        return True

    # "ua" (không đứng sau q — span đã bỏ chữ u của "qu") là "ưa": "muaw" → "mưa"
    if cluster.startswith("ua"):
        chars[start] = "ư"
        return True
    for targets in (("a", "â"), ("o", "ô"), ("u",)):
        for i in range(start, end):
            if chars[i] in targets:
                chars[i] = _BREVE_HORN[chars[i]]
                return True
    return False


def type_key(text: str, key: str) -> str:
    """Kết quả sau khi gõ 1 phím `key` vào cuối `text`."""
    if len(key) != 1:
        return text + key
    if not key.isalpha():
        return text + key
    head, last = _split_last_word(text)

    word = _Word(last)
    if not _apply(word, key):
        word.append(key)
    word.normalize()
    return head + word.render()


def backspace(text: str) -> str:
    return text[:-1]
