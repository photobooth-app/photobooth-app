import logging
import logging.config
import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, status
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse

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


@admin_files_router.get("/list{dir_path:path}")
async def get_list(dir_path: str = "/"):
    """ """

    list_path = Path("./" + dir_path).relative_to(Path("./"))

    if not list_path.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "folder does not exist!")

    folders = [f for f in list_path.iterdir() if f.is_dir()]
    files = [f for f in list_path.iterdir() if f.is_file()]

    output = []
    for f in folders:
        folder_size = sum(os.path.getsize(os.path.join(dirpath, filename)) for dirpath, dirnames, filenames in os.walk(f) for filename in filenames)
        output.append(PathListItem(f.name, f.as_posix(), f.is_dir(), folder_size))
    for f in files:
        output.append(PathListItem(f.name, f.as_posix(), f.is_dir(), f.stat().st_size))

    return output


@admin_files_router.get("/file{file_path:path}")
async def get_file(file_path: str = "/"):
    """ """

    file_path = Path("./" + file_path).relative_to(Path("./"))

    if not file_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file does not exist!")

    return FileResponse(file_path)
