import io
import logging
import os
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, UploadFile, status
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from ... import RECYCLE_PATH
from ...utils.helper import filenames_sanitize

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["admin", "files"])


@dataclass
class PathListItem:
    """ """

    name: str
    filepath: str
    is_dir: bool
    size: int


class ZipStream(io.RawIOBase):
    """An unseekable stream for the ZipFile to write to,
    reference: https://github.com/pR0Ps/zipstream-ng
    """

    def __init__(self):
        self._buffer = bytearray()
        self._closed = False

    def close(self):
        self._closed = True

    def write(self, b):
        if self._closed:
            raise ValueError("Can't write to a closed stream")
        self._buffer += b
        return len(b)

    def readall(self):
        chunk = bytes(self._buffer)
        self._buffer.clear()
        return chunk


def iter_files(paths: list[Path]):
    for path in paths:
        if path.is_dir():
            files = [f for f in path.rglob("*")]  # walks also through subdirs to get all files

            for file in files:
                yield file.relative_to(Path.cwd())

        else:
            # is file
            yield path.relative_to(Path.cwd())


def read_file(path):
    with open(path, "rb") as fp:
        while True:
            buf = fp.read(1024 * 64)
            if not buf:
                break
            yield buf


def generate_zipstream(paths: list[Path]):
    try:
        stream = ZipStream()

        with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED) as zf:
            for path in iter_files(paths):
                arcname = None  # path.absolute()
                zinfo = zipfile.ZipInfo.from_file(path, arcname)

                # Write data to the zip file then yield the stream content
                with zf.open(zinfo, mode="w") as fp:
                    if zinfo.is_dir():
                        continue
                    for buf in read_file(path):
                        fp.write(buf)
                        yield stream.readall()

        yield stream.readall()

    except Exception as exc:
        # this generator is called by fastapi in separate background taskgroup. an exception cannot be
        # raised and catched in the actual route because the output has started to the client during generation
        # this one is just to catch the error in the backend - the resulting ZIP download is probably trash.
        logger.exception(exc)
        logger.error(f"error creating the compressed data: {exc}")


@router.get("/list/{dir:path}", response_model=list[PathListItem])
async def get_list(dir: str = "/"):
    """ """
    try:
        path = filenames_sanitize(dir).relative_to(Path.cwd())
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"failed to get file: {exc}") from exc
    if not path.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{dir} is not a file / does not exist!")

    output: list[PathListItem] = []

    folders = [f for f in sorted(path.iterdir()) if f.is_dir()]
    for f in folders:
        try:
            folder_size = sum(
                os.path.getsize(os.path.join(dirpath, filename)) for dirpath, dirnames, filenames in os.walk(f) for filename in filenames
            )
            output.append(PathListItem(f.name, f.as_posix(), f.is_dir(), folder_size))
        except Exception as exc:
            logger.warning(f"skipped folder {f.name}, due to error: {exc}")

    files = [f for f in sorted(path.iterdir()) if f.is_file()]
    for f in files:
        try:
            output.append(PathListItem(f.name, f.as_posix(), f.is_dir(), f.stat().st_size))
        except Exception as exc:
            logger.warning(f"skipped file {f.name}, due to error: {exc}")

    return output


@router.get("/file/{file:path}")
async def get_file(file: str = ""):
    """ """
    try:
        logger.info(file)
        path = filenames_sanitize(file)
        logger.info(path)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"failed to get file: {exc}") from exc
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{file} is not a file/does not exist!")

    return FileResponse(path, filename=path.name)


@router.post("/file/upload", status_code=status.HTTP_201_CREATED)
def create_upload_file(upload_target_folder: Annotated[str, Body()], uploaded_files: list[UploadFile]):
    logger.info(f"file upload started, upload to folder '{upload_target_folder}'")

    # check for files uploaded
    if not uploaded_files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no files uploaded")

    # check target directory
    try:
        upload_target_folder_path = filenames_sanitize(upload_target_folder)
        if not upload_target_folder_path.is_dir():
            raise ValueError(f"{upload_target_folder_path=} is no directory / does not exist")

    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{upload_target_folder=} does not exist or is no folder! {exc}") from exc

    try:
        for uploaded_file in uploaded_files:
            assert uploaded_file.filename
            file_location = upload_target_folder_path.joinpath(uploaded_file.filename)
            with open(file_location, "wb+") as file_object:
                shutil.copyfileobj(uploaded_file.file, file_object)

            logger.info(f"file {uploaded_file.filename} stored successfully in {upload_target_folder_path}")

    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(500, f"upload failed: {exc}") from exc

    return {"uploaded_files": [file.filename for file in uploaded_files]}


@router.post("/folder/new", status_code=status.HTTP_201_CREATED)
async def post_folder_new(new_folder_name: Annotated[str, Body()]):
    """need to provide full path starting from CWD."""

    logger.info(f"post_folder_new requested, {new_folder_name=}")

    if not new_folder_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no new_folder_name given")

    new_path = None

    try:
        new_path = filenames_sanitize(new_folder_name)
        new_path.mkdir(exist_ok=False, parents=True)
        logger.debug(f"folder {new_path=} created")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"failed to create folder: {new_folder_name}") from exc
    except FileExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"folder {new_path} already exists!") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(500, f"folder creation failed: {exc}") from exc


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def post_delete(selected_paths: list[PathListItem]):
    """ """
    filenames_to_process = [filenames_sanitize(selected_path.filepath) for selected_path in selected_paths]
    logger.info(f"request delete, {filenames_to_process=}")

    def rmdir(directory: Path):
        for item in directory.iterdir():
            if item.is_dir():
                rmdir(item)
            else:
                item.unlink()
        directory.rmdir()

    try:
        for path in filenames_to_process:
            # filter main data dir.
            if path == Path.cwd():
                logger.warning("delete cwd skipped, need to explicit select all items to clear data dir")
                continue

            # recursively delete all files.
            if path.is_dir():
                logger.info(f"delete {path} recursively")
                rmdir(path)
            else:
                logger.info(f"delete {path}")
                path.unlink()

    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(500, f"deleting failed: {exc}") from exc


@router.post("/zip")
def post_zip(selected_paths: list[PathListItem]):
    zip_filename = f"photobooth_archive_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}.zip"

    try:
        filenames_to_process = [filenames_sanitize(selected_path.filepath) for selected_path in selected_paths]
        # preflight check if selected paths exist, otherwise raise error here because in generator there is no ability to
        # raise exceptions since output started already.
        for path in filenames_to_process:
            if not path.exists():
                raise FileNotFoundError(f"{path} not found")

        logger.info(f"requested zip, {filenames_to_process=}")

        response = StreamingResponse(
            generate_zipstream(filenames_to_process),
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"},
        )
        return response
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"selected file not found {exc}") from exc


@router.get("/clearrecycledir", status_code=status.HTTP_204_NO_CONTENT)
def api_clearrecycledir():
    """Warning: deletes all files permanently without any further confirmation

    Raises:
        HTTPException: _description_
    """

    try:
        for file in Path(f"{RECYCLE_PATH}").glob("*.*"):
            os.remove(file)

    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(500, f"clearing recycle directory failed, error: {exc}") from exc
