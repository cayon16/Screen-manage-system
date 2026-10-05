import pytest

from desktop.telex import backspace, type_key


def typed(keys: str, start: str = "") -> str:
    text = start
    for key in keys:
        text = type_key(text, key)
    return text


@pytest.mark.parametrize(
    "keys, expected",
    [
        # dấu thanh
        ("as", "á"), ("af", "à"), ("ar", "ả"), ("ax", "ã"), ("aj", "ạ"),
        ("khams", "khám"), ("beenhj", "bệnh"), ("vieenj", "viện"),
        # mũ, trăng, móc
        ("aa", "â"), ("ee", "ê"), ("oo", "ô"), ("aw", "ă"), ("ow", "ơ"), ("uw", "ư"),
        ("dd", "đ"), ("ddaau", "đâu"), ("ddi", "đi"), ("did", "đi"),
        # dấu gõ trước hay sau đều ra cùng chữ
        ("tieengs", "tiếng"), ("tieesng", "tiếng"), ("tiengse", "tiếng"),
        ("vieejt", "việt"), ("vietej", "việt"),
        # vị trí dấu
        ("hoaf", "hòa"), ("hoafn", "hoàn"), ("toans", "toán"),
        ("khoer", "khỏe"), ("thuyr", "thủy"), ("huyfnh", "huỳnh"),
        ("muaf", "mùa"), ("kiaf", "kìa"), ("maif", "mài"),
        ("tuooir", "tuổi"), ("nguowif", "người"), ("nguwowif", "người"),
        ("duowngf", "dường"), ("duongwf", "dường"), ("ruowuj", "rượu"),
        ("thuowr", "thuở"), ("huwu", "hưu"), ("cuwus", "cứu"),
        ("muaw", "mưa"), ("guwir", "gửi"), ("guiwr", "gửi"),
        ("hoawjc", "hoặc"), ("khoas", "khóa"),
        # qu, gi
        ("quas", "quá"), ("quys", "quý"), ("quoocs", "quốc"), ("quyeenr", "quyển"),
        ("quawng", "quăng"), ("quow", "quơ"),
        ("gias", "giá"), ("gif", "gì"), ("giuwowngf", "giường"), ("gieengs", "giếng"),
        # w đứng riêng / sau phụ âm
        ("w", "ư"), ("tw", "tư"), ("nhwngx", "những"),
        # câu có nhiều từ
        ("beenhj vieenj mowr cuwar maays giowf", "bệnh viện mở cửa mấy giờ"),
        ("khoa caaps cuwus owr ddaau", "khoa cấp cứu ở đâu"),
        ("baor hieemr y tees", "bảo hiểm y tế"),
    ],
)
def test_common_words(keys, expected):
    assert typed(keys) == expected


def test_full_hospital_question():
    assert typed("baor hieemr y tees dduwowcj khoong?") == "bảo hiểm y tế được không?"


@pytest.mark.parametrize(
    "keys, expected",
    [
        ("aaa", "aa"), ("ooo", "oo"), ("ddd", "dd"),
        ("ass", "as"), ("aff", "af"),
        ("aww", "aw"), ("uww", "uw"),
        ("asz", "a"), ("az", "az"),
    ],
)
def test_repeating_a_key_undoes_the_transform(keys, expected):
    assert typed(keys) == expected


def test_changing_the_tone_replaces_it():
    assert typed("toans") == "toán"
    assert typed("toansf") == "toàn"


def test_uppercase_is_kept_through_transforms():
    assert typed("Vieejt") == "Việt"
    assert typed("DDaau") == "Đâu"
    assert typed("HOAF") == "HÒA"
    assert typed("Nguowif") == "Người"


def test_tone_keys_without_a_vowel_are_plain_letters():
    assert typed("s") == "s"
    assert typed("tr") == "tr"
    assert typed("x") == "x"


def test_numbers_and_punctuation_end_the_word():
    assert typed("12s") == "12s"
    assert typed("a.s") == "a.s"
    assert typed("giowf 7") == "giờ 7"


def test_only_the_last_word_changes():
    assert typed("s", start="bệnh viện ta") == "bệnh viện tá"
    assert typed("f", start="Chào ") == "Chào f"


def test_editing_after_backspace_places_the_tone_again():
    text = typed("hoafn")  # hoàn
    text = backspace(text)  # hoà — dấu vẫn nằm trên a
    assert text == "hoà"
    # gõ tiếp chữ khác, dấu được đặt lại theo quy tắc
    assert type_key(text, "i") == "hoài"


def test_backspace_on_empty_text_is_safe():
    assert backspace("") == ""
