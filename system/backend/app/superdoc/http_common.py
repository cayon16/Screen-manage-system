from __future__ import annotations

import httpx

from app.superdoc.base import SuperdocError

# Ma loi nay thuong do cau hinh sai (model sai ten, dia chi sai...) nen noi them ly do nha cung
# cap tra ve de nguoi van hanh sua duoc. Ma khac (401, 429, 5xx) khong can.
_DETAIL_STATUSES = frozenset({400, 402, 403, 404, 422})


def to_superdoc_error(exc: Exception, provider_name: str) -> SuperdocError:
    """Doi loi httpx sang SuperdocError dung chung cho moi provider. Khong dua noi dung nguoi
    dung vua go vao thong bao — chi lay ly do cua nha cung cap khi no la loi cau hinh."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        message = f"{provider_name} trả về HTTP {status}"
        if status in _DETAIL_STATUSES:
            detail = _error_detail(exc.response)
            if detail:
                message = f"{message}: {detail}"
        return SuperdocError(message, code=f"http_{status}")
    if isinstance(exc, httpx.TimeoutException):
        return SuperdocError(f"{provider_name} không trả lời kịp", code="timeout")
    if isinstance(exc, ValueError):
        # response.json() gap noi dung khong phai JSON.
        return SuperdocError(f"{provider_name} trả về dữ liệu không đọc được", code="bad_response")
    return SuperdocError(f"Không gọi được {provider_name}: {type(exc).__name__}", code="network")


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    error = body.get("error") if isinstance(body, dict) else None
    message = error.get("message") if isinstance(error, dict) else error
    return message.strip()[:200] if isinstance(message, str) else ""
