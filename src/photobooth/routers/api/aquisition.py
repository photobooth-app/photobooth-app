import asyncio
import logging
from collections.abc import AsyncGenerator, Generator
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, WebSocket, status
from fastapi.responses import FileResponse, StreamingResponse
from starlette.websockets import WebSocketDisconnect

from ...appconfig import appconfig
from ...container import container

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/aquisition", tags=["aquisition"])


async def wrap_iter(iterable: Generator[bytes, Any, None]) -> AsyncGenerator[bytes]:
    """
    convert sync function in async generator
    https://stackoverflow.com/questions/57835872/send-data-via-websocket-from-synchronous-iterator-in-starlette
    """
    loop = asyncio.get_event_loop()

    def get_next_item():
        # Get the next item synchronously.  We cannot call next(it) directly because StopIteration cannot be transferred
        # across an "await". So we detect StopIteration and convert it to a sentinel object.
        try:
            return next(iter(iterable))
        except StopIteration:
            return None

    while True:
        # Submit execution of next(it) to another thread and resume when it's done. await will suspend the coroutine and
        # allow other tasks to execute while waiting.
        next_item = await loop.run_in_executor(None, get_next_item)
        if next_item is None:
            break

        yield next_item


@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    async for frame in wrap_iter(container.aquisition_service.gen_stream()):
        try:
            await websocket.send_bytes(frame)
        except WebSocketDisconnect as exc:
            logger.info(f"client disconnected code: {exc.code}, reason: {exc.reason}")
            break
        except Exception as exc:
            logger.info(f"error sending data: {exc}")
            break
    else:
        # when for ends (None is returned/stream break), close the connection server side so client can retry connecting)
        try:
            await websocket.close(code=1001, reason="backend stopped delivering")
        except Exception as exc:
            logger.warning(f"websocket failed closing: {exc}")


@router.get("/stream.mjpg")
def video_stream():
    headers = {"Age": "0", "Cache-Control": "no-cache, private", "Pragma": "no-cache"}

    if not appconfig.backends.enable_livestream:
        raise HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED, "preview not enabled")

    def gen_multipart():
        for jpeg_bytes in container.aquisition_service.gen_stream():
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n\r\n")

    try:
        return StreamingResponse(content=gen_multipart(), headers=headers, media_type="multipart/x-mixed-replace; boundary=frame")
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"preview failed: {exc}") from exc


@router.get("/still")
def api_still_get():
    try:
        file = container.aquisition_service.wait_for_still_file()
        return FileResponse(file, filename=file.name)
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/mode/{mode}", status_code=status.HTTP_202_ACCEPTED)
def api_cmd_aquisition_capturemode_get(mode: Literal["preview", "capture", "video", "idle"] = "preview"):
    """set backends to preview or capture mode (usually automatically switched as needed by processingservice)"""
    if mode == "capture":
        container.aquisition_service.signalbackend_configure_optimized_for_hq_capture()
    elif mode == "preview":
        container.aquisition_service.signalbackend_configure_optimized_for_hq_preview()
    elif mode == "video":
        container.aquisition_service.signalbackend_configure_optimized_for_video()
    elif mode == "idle":
        container.aquisition_service.signalbackend_configure_optimized_for_idle()
