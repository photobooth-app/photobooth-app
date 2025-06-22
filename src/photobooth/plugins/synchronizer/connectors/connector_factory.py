from ..config import (
    ConnectorConfig,
    FilesystemConnectorConfig,
    FtpConnectorConfig,
    NextcloudConnectorConfig,
)
from .abstractconnector import AbstractConnector
from .filesystem import FilesystemConnector
from .ftp import FtpConnector
from .nextcloud import NextcloudConnector


def connector_factory(connector_config: ConnectorConfig) -> AbstractConnector[ConnectorConfig]:
    connector_map: dict[type[ConnectorConfig], type[AbstractConnector]] = {
        FilesystemConnectorConfig: FilesystemConnector,
        FtpConnectorConfig: FtpConnector,
        NextcloudConnectorConfig: NextcloudConnector,
    }

    klass = connector_map[type(connector_config)]

    return klass(connector_config)
