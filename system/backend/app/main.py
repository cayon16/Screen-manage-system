from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.commands import SlicesReadyCommand
from app.config import HOST, HOST_ACTIVITY_ENABLED, PORT, STANDBY_SLICE_CACHE_DIR, STANDBY_VIDEO_PATH
from app.logging_setup import get_logger
from app.routes.http_routes import router as http_router
from app.routes.ws_routes import router as ws_router
from app.state.cluster_controller import ClusterController
from app.state.host_activity import HostActivityMonitor
from app.state.video_slicer import VideoSlicer
from app.state.ws_manager import ConnectionManager

logger = get_logger()


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
