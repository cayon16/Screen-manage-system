from __future__ import annotations

from typing import Awaitable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.schemas import AiModeRequest
from app.superdoc.manager import AiManager, AiTestFailed
from app.superdoc.registry import ProviderConfigError
from app.superdoc.settings import AiSettings

# API quan ly ket noi AI. Backend chi nghe 127.0.0.1, day la lop phong thu them. Khi tach backend len
# server THAT thi phai thay bang xac thuc (token) — chi kiem dia chi may la khong du.
_LOCAL_HOSTS = frozenset({"127.0.0.1", "::1"})


class NotLocalError(Exception):
    """Goi tu may khac — main.py doi thanh 403."""


def require_local(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in _LOCAL_HOSTS:
        raise NotLocalError(host)


router = APIRouter(prefix="/api/ai", dependencies=[Depends(require_local)])


def _ai(request: Request) -> AiManager:
    return request.app.state.ai


async def _respond(call: Awaitable[dict]) -> JSONResponse:
    """Doi cac loi cua AiManager thanh ma HTTP: 400 cau hinh thieu, 424 thu ket noi hong."""
    try:
        return JSONResponse(await call)
    except ProviderConfigError as exc:
        return JSONResponse({"error": exc.message, "field": exc.field}, status_code=400)
    except AiTestFailed as exc:
        return JSONResponse({"error": "Thử kết nối thất bại — chưa đổi", "test": exc.result}, status_code=424)


@router.get("")
async def get_ai(request: Request) -> JSONResponse:
    """AI dang dung, cau hinh, khoa nao da co (chi co/chua, khong bao gio gia tri), tinh trang."""
    return JSONResponse(_ai(request).snapshot())


@router.put("/settings")
async def put_settings(body: AiSettings, request: Request, test: bool = True) -> JSONResponse:
    """Doi toan bo cau hinh AI. Mac dinh thu ket noi truoc: hong thi giu nguyen AI cu (424).
    `?test=false` de ep doi du AI chua tra loi duoc."""
    return await _respond(_ai(request).apply(body, test_first=test))


@router.post("/mode")
async def post_mode(body: AiModeRequest, request: Request, test: bool = True) -> JSONResponse:
    """Chi doi che do (demo / internal / public), giu nguyen phan cau hinh con lai."""
    return await _respond(_ai(request).set_mode(body.mode, test_first=test))


@router.post("/test")
async def post_test(request: Request, body: AiSettings | None = None) -> JSONResponse:
    """Thu 1 cau. Khong co body = thu AI dang chay; co body = thu cau hinh ung vien ma khong doi.
    Ket qua `ok: false` van la 200 (viec thu da chay xong); chi cau hinh thieu moi tra 400."""
    return await _respond(_ai(request).test(body))
