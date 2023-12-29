"""
AppConfig class providing central config

"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonref
from pydantic import PrivateAttr
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from .groups.backends import GroupBackends
from .groups.common import GroupCommon
from .groups.filetransfer import GroupFileTransfer
from .groups.hardwareinputoutput import GroupHardwareInputOutput
from .groups.mediaprocessing import (
    GroupMediaprocessing,
    GroupMediaprocessingPipelineAnimation,
    GroupMediaprocessingPipelineCollage,
    GroupMediaprocessingPipelinePrint,
    GroupMediaprocessingPipelineSingleImage,
)
from .groups.misc import GroupMisc
from .groups.sharing import GroupSharing
from .groups.uisettings import GroupUiSettings

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "./config/config.json"


class JsonConfigSettingsSource(PydanticBaseSettingsSource):
    """
    A simple settings source class that loads variables from a JSON file
    at the project's root.

    Here we happen to choose to use the `env_file_encoding` from Config
    when reading `config.json`
    """

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        encoding = self.config.get("env_file_encoding")
        field_value = None
        try:
            file_content_json = json.loads(Path(CONFIG_FILENAME).read_text(encoding))
            field_value = file_content_json.get(field_name)
        except FileNotFoundError:
            # ignore file not found, because it could have been deleted or not yet initialized
            # using defaults
            pass

        return field_value, field_name, False

    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        return value

    def __call__(self) -> dict[str, Any]:
        d: dict[str, Any] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, value_is_complex = self.get_field_value(field, field_name)
            field_value = self.prepare_field_value(field_name, field, field_value, value_is_complex)
            if field_value is not None:
                d[field_key] = field_value

        return d


class AppConfig(BaseSettings):
    """
    AppConfig class glueing all together

    In the case where a value is specified for the same Settings field in multiple ways, the selected value is determined as follows
    (in descending order of priority):

    1 Arguments passed to the Settings class initialiser.
    2 Environment variables, e.g. my_prefix_special_function as described above.
    3 Variables loaded from a dotenv (.env) file.
    4 Variables loaded from the secrets directory.
    5 The default field values for the Settings model.
    """

    _processed_at: datetime = PrivateAttr(default_factory=datetime.now)  # private attributes

    # groups -> setting items
    common: GroupCommon = GroupCommon()
    sharing: GroupSharing = GroupSharing()
    filetransfer: GroupFileTransfer = GroupFileTransfer()
    mediaprocessing: GroupMediaprocessing = GroupMediaprocessing()
    mediaprocessing_pipeline_singleimage: GroupMediaprocessingPipelineSingleImage = GroupMediaprocessingPipelineSingleImage()
    mediaprocessing_pipeline_collage: GroupMediaprocessingPipelineCollage = GroupMediaprocessingPipelineCollage()
    mediaprocessing_pipeline_animation: GroupMediaprocessingPipelineAnimation = GroupMediaprocessingPipelineAnimation()
    mediaprocessing_pipeline_printing: GroupMediaprocessingPipelinePrint = GroupMediaprocessingPipelinePrint()
    uisettings: GroupUiSettings = GroupUiSettings()
    backends: GroupBackends = GroupBackends()
    hardwareinputoutput: GroupHardwareInputOutput = GroupHardwareInputOutput()
    misc: GroupMisc = GroupMisc()

    # TODO[pydantic]: We couldn't refactor this class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        # first in following list is least important; last .env file overwrites the other.
        env_file=[".env.installer", ".env.dev", ".env.test", ".env.prod"],
        env_nested_delimiter="__",
        case_sensitive=True,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """customize sources"""
        return (
            init_settings,
            JsonConfigSettingsSource(settings_cls),
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    def get_schema(self, schema_type: str = "default"):
        """Get schema to build UI. Schema is polished to the needs of UI"""
        if schema_type == "dereferenced":
            # https://github.com/pydantic/pydantic/issues/889#issuecomment-1064688675
            return jsonref.loads(json.dumps(self.model_json_schema()))

        return self.model_json_schema()

    def reset_defaults(self):
        self.__dict__.update(__class__())

    def persist(self):
        """Persist config to file"""
        logger.debug("persist config to json file")

        with open(CONFIG_FILENAME, mode="w", encoding="utf-8") as write_file:
            write_file.write(self.model_dump_json(indent=2))

    def deleteconfig(self):
        """Reset to defaults"""
        logger.debug("config reset to default")

        try:
            os.remove(CONFIG_FILENAME)
            logger.debug(f"deleted {CONFIG_FILENAME} file.")
        except (FileNotFoundError, PermissionError):
            logger.info(f"delete {CONFIG_FILENAME} file failed.")
