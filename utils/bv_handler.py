import re
import webbrowser

BV_PATTERN = re.compile(r'BV[0-9a-zA-Z]+')


def is_bv_number(text: str) -> bool:
    """Check if the entire text is exactly a BV number."""
    return bool(BV_PATTERN.fullmatch(text.strip()))


def extract_bv_number(text: str) -> str | None:
    """Extract the first BV number found anywhere in the text."""
    m = BV_PATTERN.search(text.strip())
    return m.group(0) if m else None


def open_bv_video(bv_number: str):
    bn = bv_number.strip()
    webbrowser.open(f"https://www.bilibili.com/video/{bn}")
