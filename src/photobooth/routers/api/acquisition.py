import asyncio
import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, WebSocket, status
from fastapi.responses import FileResponse, StreamingResponse
from starlette.websockets import WebSocketDisconnect

from ...appconfig import appconfig
from ...container import container
from ...services.sse import sse_service
from ...services.sse.sse_ import SseEventTranslateableFrontendNotification
from ...utils.exceptions import BackendNotRunning
from ...utils.helper import filenames_sanitize

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/aquisition", tags=["aquisition"])


@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket, index_device: int | None = None, index_subdevice: int = 0):
    if not appconfig.backends.enable_livestream:
        raise HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED, "preview not enabled")

    await websocket.accept()

    retries = 3

    while True:
        try:
            msg = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)

        except WebSocketDisconnect:
            logger.debug("client disconnected while waiting for the ready signal to send the next frame")
            return  # return because disconnected already and below would handle disconnect otherwise again which fails for sure.
        except TimeoutError:
            # logger.debug("timed out while waiting for the ready signal to send the next frame, continue waiting...")
            continue

        if msg != "ready":
            logger.warning(f"invalid message from client: {msg}")
            continue

        jpeg_bytes = None

        for attempt in range(retries):
            try:
                jpeg_bytes = await asyncio.to_thread(container.acquisition_service.wait_for_lores_image, index_device, index_subdevice)
                break  # success, don't execute for...else:

            except TimeoutError:  # backend timeout (mode switching, ...)
                logger.debug(f"camera timeout ({attempt + 1}/{retries})")
                continue  # retry
            except BackendNotRunning:
                logger.info("backend stopped, closing stream")

                await websocket.close(code=1001, reason="backend stopped")
                return  # stop
            except Exception as exc:
                logger.error(exc)
                continue  # retry, but likely to fail and then exchaust the retry loop crit
        else:
            # retry loop exhausted
            logger.error("failed to get frame after max retries, closing stream")
            sse_service.dispatch_event(SseEventTranslateableFrontendNotification(color="negative", message_key="acquisition.stream_error"))

            await websocket.close(code=1011, reason="camera failed")
            return

        # print(time.monotonic())

        if jpeg_bytes:
            try:
                await websocket.send_bytes(jpeg_bytes)
            except WebSocketDisconnect:
                logger.debug("client disconnected while sending a frame")
                return  # return because disconnected already and below would handle disconnect otherwise again which fails for sure.
            except Exception as exc:
                logger.info(f"error sending data: {exc}")
                break

    # when while ends, close the connection server side so client can retry connecting)
    try:
        await websocket.close(code=1001, reason="backend stopped delivering")
    except Exception as exc:
        logger.warning(f"websocket failed closing: {exc}")


@router.get("/stream.mjpg")
def video_stream(index_device: int = 0, index_subdevice: int = 0):
    if not appconfig.backends.enable_livestream:
        raise HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED, "preview not enabled")

    def gen_multipart():

        while True:
            try:
                jpeg_bytes = container.acquisition_service.wait_for_lores_image(index_device, index_subdevice)
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n\r\n")
            except TimeoutError:
                # a timeouterror can occur during mode switches of the backend - the frontend will just wait for another frame
                continue
            except BackendNotRunning:
                logger.info("stop streaming because backend is not running")
                break
            except Exception as exc:
                logger.warning(exc)
                sse_service.dispatch_event(SseEventTranslateableFrontendNotification(color="negative", message_key="acquisition.stream_error"))

                break

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


@router.get("/mode/{backend_index}/{mode}", status_code=status.HTTP_202_ACCEPTED)
def api_cmd_aquisition_capturemode_get(backend_index: int = 0, mode: Literal["capture", "video", "standby"] = "video"):
    """set backends to preview or capture mode (usually automatically switched as needed by processingservice)"""
    if mode == "capture":
        container.acquisition_service._backends[backend_index]._mode_machine.request_still()
    elif mode == "video":
        container.acquisition_service._backends[backend_index]._mode_machine.request_video()
    elif mode == "standby":
        container.acquisition_service._backends[backend_index]._mode_machine.request_standby()
