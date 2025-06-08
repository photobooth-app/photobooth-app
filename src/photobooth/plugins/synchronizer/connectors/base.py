from abc import ABC, abstractmethod
from pathlib import Path

# T = TypeVar("T", bound=BaseClientConfig)


# class BaseClient(ABC,Generic[T]):
class BaseConnector(ABC):
    # def __init__(self):
    #     self._config: T

    @abstractmethod
    def connect(self): ...
    @abstractmethod
    def disconnect(self): ...
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def get_remote_samefile(self, local_path: Path, remote_path: Path) -> bool: ...

    @abstractmethod
    def do_upload(self, local_path: Path, remote_path: Path): ...
    @abstractmethod
    def do_delete_remote(self, remote_path: Path): ...

    # @abstractmethod
    # def mediaitem_link(self, remote_path: Path) -> str | None: ...

    def __str__(self):
        return f"{self.__class__.__name__}"


class BaseMediashare:
    def __init__(self, media_url: str):
        super().__init__()

        self._media_url: str = media_url

    def mediaitem_link(self, remote_path: Path) -> str | None:
        if not self._media_url:
            return None

        # mediaitem_url = f"{self._media_url.rstrip('/')}/{remote_path.as_posix()}"
        mediaitem_url = self._media_url.replace("{remote_path}", remote_path.as_posix())
        return mediaitem_url
