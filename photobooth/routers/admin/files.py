import io
import logging
import logging.config
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

from ...utils.helper import filenames_sanitize

logger = logging.getLogger(__name__)
admin_files_router = APIRouter(
    prefix="/admin/files",
    tags=["admin", "files"],
)


@dataclass
class PathListItem:
    """ """

    name: str
    filepath: str
    is_dir: bool
    size: int


def zipfiles(paths: list[Path]):
    zip_filename = f"photobooth_archive_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}.zip"

    # create in memory zip file. TODO: improve to lower memory consumption use zip streaming.
    zip_io = io.BytesIO()
    zip_file = zipfile.ZipFile(zip_io, "w")

    for path in paths:
        if path.is_dir():
            files = [f for f in path.rglob("*")]  # walks also through subdirs to get all files

            for file in files:
                zip_file.write(file.relative_to(Path.cwd()))

        else:
            # is file
            zip_file.write(path.relative_to(Path.cwd()))

    # Must close zip for all contents to be written
    zip_file.close()

    logger.info(f"created {zip_filename}, added {len(zip_file.filelist)}, size {round(len(zip_io.getvalue())/1024**2,2)} MB")
    # logger.debug(zip.namelist())

    # Grab ZIP file from in-memory, make response with correct MIME-type
    return StreamingResponse(
        iter([zip_io.getvalue()]),
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}.zip"},
    )


@admin_files_router.get("/list{dir:path}")
async def get_list(dir: str = "/"):
    """ """

    dir_path = filenames_sanitize([dir], check_exists=False)[0].relative_to(Path.cwd())

    if not dir_path.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "folder does not exist!")

    folders = [f for f in dir_path.iterdir() if f.is_dir()]
    files = [f for f in dir_path.iterdir() if f.is_file()]

    output = []
    for f in folders:
        folder_size = sum(os.path.getsize(os.path.join(dirpath, filename)) for dirpath, dirnames, filenames in os.walk(f) for filename in filenames)
        output.append(PathListItem(f.name, f.as_posix(), f.is_dir(), folder_size))
    for f in files:
        output.append(PathListItem(f.name, f.as_posix(), f.is_dir(), f.stat().st_size))

    return output


@admin_files_router.get("/file{file:path}")
async def get_file(file: str = "/"):
    """ """
    try:
        path = filenames_sanitize([file], check_exists=False)[0]
    except Exception as exc:
        raise HTTPException(500, f"failed to get file: {exc}") from exc

    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{file} is not a file!")

    return FileResponse(path)


@admin_files_router.post("/file/upload")
def create_upload_file(upload_target_folder: Annotated[str, Body()], uploaded_files: list[UploadFile]):
    logger.info(f"file upload started, upload to folder '{upload_target_folder}'")

    # check for files uploaded
    if not uploaded_files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no files uploaded")

    # check target directory
    try:
        upload_target_folder_path = filenames_sanitize([upload_target_folder], check_exists=True)[0]
        if not upload_target_folder_path.is_dir():
            raise ValueError(f"{upload_target_folder_path=} is no directory")

    except Exception as exc:
        raise HTTPException(500, f"{upload_target_folder=} does not exist or is no folder! {exc}") from exc

    try:
        for uploaded_file in uploaded_files:
            file_location = upload_target_folder_path.joinpath(uploaded_file.filename)
            with open(file_location, "wb+") as file_object:
                shutil.copyfileobj(uploaded_file.file, file_object)

            logger.info(f"file {uploaded_file.filename} stored successfully in {upload_target_folder_path}")

    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(500, f"upload failed: {exc}") from exc

    return {"uploaded_files": [file.filename for file in uploaded_files]}


@admin_files_router.post("/folder/new", status_code=status.HTTP_201_CREATED)
async def post_folder_new(new_folder_name: Annotated[str, Body()]):
    """need to provide full path starting from CWD."""

    logger.info(f"post_folder_new requested, {new_folder_name=}")

    if not new_folder_name:
        logger.warning(f"no new folder name provided {new_folder_name=}")

    try:
        new_path = filenames_sanitize([new_folder_name], check_exists=False)[0]
        new_path.mkdir(exist_ok=False, parents=True)
        logger.debug(f"folder {new_path=} created")

    except FileExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"folder {new_path} already exists!") from exc

    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(500, f"folder creation failed: {exc}") from exc


@admin_files_router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def post_delete(selected_paths: list[PathListItem] = None):
    """ """
    filenames_to_process = [selected_path.filepath for selected_path in selected_paths]
    logger.info(f"request delete, {filenames_to_process=}")

    def rmdir(directory: Path):
        for item in directory.iterdir():
            if item.is_dir():
                rmdir(item)
            else:
                item.unlink()
        directory.rmdir()

    try:
        paths = filenames_sanitize(filenames_to_process)
        for path in paths:
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


@admin_files_router.post("/zip")
def post_zip(selected_paths: list[PathListItem] = None):
    filenames_to_process = [selected_path.filepath for selected_path in selected_paths]
    logger.info(f"requested zip, {filenames_to_process=}")

    try:
        return zipfiles(filenames_sanitize(filenames_to_process))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"selected file not found {exc}") from exc
