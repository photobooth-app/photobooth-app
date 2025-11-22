import asyncio
import logging
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, WebSocket, status
from fastapi.responses import FileResponse, StreamingResponse
from starlette.websockets import WebSocketDisconnect

from ...appconfig import appconfig
from ...container import container
from ...utils.helper import filenames_sanitize

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/aquisition", tags=["aquisition"])


async def wrap_iter(iterable: Generator[bytes, Any, None]) -> AsyncGenerator[bytes]:
    """
    convert sync function in async generator
    https://stackoverflow.com/questions/57835872/send-data-via-websocket-from-synchronous-iterator-in-starlette
    """

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
        next_item = await asyncio.to_thread(get_next_item)
        if next_item is None:
            break

        yield next_item


@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket, index_device: int = 0, index_subdevice: int = 0):
    await websocket.accept()

    async for frame in wrap_iter(container.acquisition_service.gen_stream(index_device, index_subdevice)):
        try:
            await websocket.send_bytes(frame)
        except WebSocketDisconnect as exc:
            logger.debug(f"client disconnected code: {exc.code}, reason: {exc.reason}")
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
def video_stream(index_device: int = 0, index_subdevice: int = 0):
    if not appconfig.backends.enable_livestream:
        raise HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED, "preview not enabled")

    def gen_multipart():
        for jpeg_bytes in container.acquisition_service.gen_stream(index_device, index_subdevice):
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n\r\n")

    try:
        headers = {"Age": "0", "Cache-Control": "no-cache, private", "Pragma": "no-cache"}
        return StreamingResponse(content=gen_multipart(), headers=headers, media_type="multipart/x-mixed-replace; boundary=frame")
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"preview failed: {exc}") from exc


@router.get("/still")
def api_still_get():
    try:
        file = container.acquisition_service.wait_for_still_file()
        return FileResponse(file, filename=file.name)
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/multicam")
def api_multicam_get() -> list[Path]:
    try:
        return container.acquisition_service.wait_for_multicam_files()
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/multicam/{file_path:path}")
def api_multicam_loadfile_get(file_path: Path):
    filepath_sanitized = filenames_sanitize(file_path)
    return FileResponse(filepath_sanitized, filename=filepath_sanitized.name)  # cannot catch exceptions here since async internally.


@router.get("/mode/{mode}", status_code=status.HTTP_202_ACCEPTED)
def api_cmd_aquisition_capturemode_get(mode: Literal["preview", "capture", "video", "idle"] = "preview"):
    """set backends to preview or capture mode (usually automatically switched as needed by processingservice)"""
    if mode == "capture":
        container.acquisition_service.signalbackend_configure_optimized_for_hq_capture()
    elif mode == "preview":
        container.acquisition_service.signalbackend_configure_optimized_for_hq_preview()
    elif mode == "video":
        container.acquisition_service.signalbackend_configure_optimized_for_video()
    elif mode == "idle":
        container.acquisition_service.signalbackend_configure_optimized_for_idle()
