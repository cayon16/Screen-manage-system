from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from app.commands import LayoutCommand
from app.config import STANDBY_VIDEO_PATH, STANDBY_VIDEO_REL_PATH
from app.logging_setup import get_logger
from app.schemas import LayoutRequest
from app.state.layout import ClusterLayout, LayoutError
from app.state.slide_band import MEDIA_DIR

logger = get_logger()

router = APIRouter()

@router.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@router.get("/standby-video")
async def standby_video():
    """Video phát ở chế độ chờ, lấy từ STANDBY_VIDEO_REL_PATH trong config.

    Dùng route co dinh chu KHONG di qua /media/{filename}: video nam o system/video/ (ngoai
    content_manifest), va ten file that co dau cach lan emoji — de tren URL thi phai ma hoa,
    de sinh loi vat. Route co dinh thi ten file khong bao gio xuat hien tren URL.

    FileResponse tu ho tro HTTP Range nen the <video> tua/phat muot binh thuong.
    """
    if not STANDBY_VIDEO_PATH.is_file():
        logger.warning("Khong tim thay video cho: %s", STANDBY_VIDEO_PATH)
        return JSONResponse(
            {
                "error": "Khong tim thay video cho",
                "duong_dan_dang_tro_toi": str(STANDBY_VIDEO_PATH),
                "sua_o": f"STANDBY_VIDEO_REL_PATH trong backend/app/config.py (dang la {STANDBY_VIDEO_REL_PATH!r})",
            },
            status_code=404,
        )
    return FileResponse(STANDBY_VIDEO_PATH, media_type="video/mp4")


@router.get("/standby-video/{wall_count}/{index}")
async def standby_video_slice(wall_count: int, index: int, request: Request):
    """1 lat da cat san cua video cho (lat thu `index` trong `wall_count` lat, trai -> phai).

    Chi co khi backend da bao lat san sang (state_update cua man cho tro toi day). 404 thi
    man cho quay ve phat nguyen video.
    """
    slicer = getattr(request.app.state, "slicer", None)
    path = slicer.slice_path(wall_count, index) if slicer is not None else None
    if path is None or not path.is_file():
        return JSONResponse({"error": "lat video chua san sang"}, status_code=404)
    return FileResponse(path, media_type="video/mp4")


@router.post("/api/layout")
async def set_layout(body: LayoutRequest, request: Request) -> JSONResponse:
    """App Qt bao bo cuc man thuc te: vai tro nao dang co va nam o vi tri nao tren tuong."""
    try:
        layout = ClusterLayout.from_displays(
            [(d.role, d.wall_index) for d in body.displays]
        )
    except LayoutError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    await request.app.state.cluster.submit(LayoutCommand(layout=layout))
    return JSONResponse({"ok": True, **layout.as_dict()})


@router.get("/media/{filename}")
async def serve_media(filename: str):
    """Phuc vu anh/video cua slide tu content_manifest/media/.

    Co tinh dung route thuong chu KHONG dung StaticFiles: StaticFiles nem loi ngay luc khoi dong
    neu thu muc khong ton tai, ma nen zip thi bo thu muc rong -> backend chet ngay khi giai nen
    sang may khac. Route nay chi tra 404 kem thong bao ro rang.

    FileResponse tu ho tro HTTP Range nen the <video> tua/phat muot binh thuong.
    """
    # Chan path traversal: chi chap nhan ten file tran, khong thu muc con, khong "..".
    candidate = (MEDIA_DIR / filename).resolve()
    if Path(filename).name != filename or MEDIA_DIR.resolve() not in candidate.parents:
        logger.warning("Tu choi duong dan media khong hop le: %r", filename)
        return JSONResponse({"error": "invalid media path"}, status_code=404)

    if not candidate.is_file():
        logger.warning("Khong tim thay file media: %s", candidate)
        return JSONResponse(
            {"error": f"Khong tim thay {filename} trong content_manifest/media/"}, status_code=404
        )
    return FileResponse(candidate)
