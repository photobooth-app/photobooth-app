from abc import ABC, abstractmethod
from pathlib import Path


class BaseBackend(ABC):
    pass

    @abstractmethod
    def connect(self): ...
    @abstractmethod
    def disconnect(self): ...

    @abstractmethod
    def get_remote_samefile(self, local_path: Path, remote_path: Path) -> bool: ...

    @abstractmethod
    def do_upload(self, local_path: Path, remote_path: Path): ...
    @abstractmethod
    def do_delete_remote(self, remote_path: Path): ...

    # @abstractmethod
    # def get_share_link(self, remote_path: Path): ...
