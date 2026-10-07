from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.commands import AiChangedCommand, SlicesReadyCommand
from app.config import (
    AI_SETTINGS_PATH,
    HOST,
    HOST_ACTIVITY_ENABLED,
    PORT,
    STANDBY_SLICE_CACHE_DIR,
    STANDBY_VIDEO_PATH,
)
from app.logging_setup import get_logger
from app.routes.ai_routes import NotLocalError
from app.routes.ai_routes import router as ai_router
from app.routes.http_routes import router as http_router
from app.routes.ws_routes import router as ws_router
from app.state.cluster_controller import ClusterController
from app.state.host_activity import HostActivityMonitor
from app.state.video_slicer import VideoSlicer
from app.state.ws_manager import ConnectionManager
from app.superdoc.manager import AiManager

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    connection_manager = ConnectionManager()

    async def on_slices_ready(wall_count: int) -> None:
        await cluster.submit(SlicesReadyCommand(wall_count=wall_count))

    async def on_ai_changed() -> None:
        await cluster.submit(AiChangedCommand())

    slicer = VideoSlicer(STANDBY_VIDEO_PATH, STANDBY_SLICE_CACHE_DIR, on_ready=on_slices_ready)
    ai = AiManager(AI_SETTINGS_PATH, on_change=on_ai_changed)
    await ai.start()
    cluster = ClusterController(
        send=connection_manager.send_to,
        send_admin=connection_manager.send_admin,
        slicer=slicer,
        ai=ai,
    )
    app.state.connection_manager = connection_manager
    app.state.cluster = cluster
    app.state.slicer = slicer
    app.state.ai = ai

    background_tasks = [asyncio.create_task(cluster.run())]
    if HOST_ACTIVITY_ENABLED:
        background_tasks.append(asyncio.create_task(HostActivityMonitor(cluster.submit).run()))

    logger.info("PentaSync backend started")
    try:
        yield
    finally:
        cluster.stop()
        slicer.cancel()
        await ai.aclose()
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)
        logger.info("PentaSync backend stopped")


app = FastAPI(title="PentaSync", lifespan=lifespan)
app.include_router(http_router)
app.include_router(ai_router)
app.include_router(ws_router)


@app.exception_handler(NotLocalError)
async def _not_local(request: Request, exc: NotLocalError) -> JSONResponse:
    logger.warning("Tu choi goi API quan ly AI tu %s", exc)
    return JSONResponse({"error": "Chỉ gọi được từ chính máy chạy PentaSync"}, status_code=403)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
