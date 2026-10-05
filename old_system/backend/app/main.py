from __future__ import annotations

import asyncio
import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.commands import SlicesReadyCommand
from app.config import HOST, HOST_ACTIVITY_ENABLED, PORT, STANDBY_SLICE_CACHE_DIR, STANDBY_VIDEO_PATH
from app.logging_setup import get_logger
from app.routes.http_routes import FRONTEND_DIR
from app.routes.http_routes import router as http_router
from app.routes.ws_routes import router as ws_router
from app.state.cluster_controller import ClusterController
from app.state.host_activity import HostActivityMonitor
from app.state.video_slicer import VideoSlicer
from app.state.ws_manager import ConnectionManager

logger = get_logger()

# Registry MIME type cua Windows doi khi khong co .js -> co the khien trinh duyet tu choi
# <script type="module"> vi sai Content-Type. Ep dung tuong minh, khong phu thuoc OS registry.
mimetypes.add_type("application/javascript", ".js")


@asynccontextmanager
async def lifespan(app: FastAPI):
    connection_manager = ConnectionManager()

    async def on_slices_ready(wall_count: int) -> None:
        await cluster.submit(SlicesReadyCommand(wall_count=wall_count))

    slicer = VideoSlicer(STANDBY_VIDEO_PATH, STANDBY_SLICE_CACHE_DIR, on_ready=on_slices_ready)
    cluster = ClusterController(
        send=connection_manager.send_to,
        send_admin=connection_manager.send_admin,
        slicer=slicer,
    )
    app.state.connection_manager = connection_manager
    app.state.cluster = cluster
    app.state.slicer = slicer

    background_tasks = [asyncio.create_task(cluster.run())]
    if HOST_ACTIVITY_ENABLED:
        background_tasks.append(asyncio.create_task(HostActivityMonitor(cluster.submit).run()))

    logger.info("PentaSync backend started")
    try:
        yield
    finally:
        cluster.stop()
        slicer.cancel()
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)
        logger.info("PentaSync backend stopped")


app = FastAPI(title="PentaSync", lifespan=lifespan)
app.include_router(http_router)
app.include_router(ws_router)
# Chi mount thu muc that su co file. Truoc day co mount them "/assets" tro toi 1 thu muc RONG:
# StaticFiles nem RuntimeError ngay luc import neu thu muc khong ton tai, ma nen zip thi bo thu
# muc rong -> backend chet ngay khi giai nen sang may khac. Khong mount thu khong dung toi.
# Giao dien web cu (launcher/ + frontend/) chi co khi chay tu ma nguon; ban dong goi khong kem.
if (FRONTEND_DIR / "src").is_dir():
    app.mount("/src", StaticFiles(directory=str(FRONTEND_DIR / "src")), name="src")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
