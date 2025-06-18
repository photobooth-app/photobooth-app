from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

from ..config import BaseConnectorConfig

T = TypeVar("T", bound=BaseConnectorConfig)


class AbstractConnector(ABC, Generic[T]):
    # class AbstractConnector(ABC):
    def __init__(self, config: T):
        ...
        # self._config: T = config

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

    @abstractmethod
    def __str__(self) -> str: ...
