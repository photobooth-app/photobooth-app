"""
AppConfig class providing central config

"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonref
from pydantic import PrivateAttr
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .groups.actions import GroupActions
from .groups.backends import GroupBackends
from .groups.common import GroupCommon
from .groups.filetransfer import GroupFileTransfer
from .groups.hardwareinputoutput import GroupHardwareInputOutput
from .groups.mediaprocessing import GroupMediaprocessing
from .groups.misc import GroupMisc
from .groups.qrshare import GroupQrShare
from .groups.share import GroupShare
from .groups.uisettings import GroupUiSettings

logger = logging.getLogger(__name__)

CONFIG_DIR = "./config/"
CONFIG_FILENAME = "config.json"
CONFIG_FILEPATH = f"{CONFIG_DIR}{CONFIG_FILENAME}"


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
            file_content_json = json.loads(Path(CONFIG_FILEPATH).read_text(encoding))
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
    actions: GroupActions = GroupActions()
    share: GroupShare = GroupShare()
    qrshare: GroupQrShare = GroupQrShare()
    filetransfer: GroupFileTransfer = GroupFileTransfer()
    mediaprocessing: GroupMediaprocessing = GroupMediaprocessing()
    uisettings: GroupUiSettings = GroupUiSettings()
    backends: GroupBackends = GroupBackends()
    hardwareinputoutput: GroupHardwareInputOutput = GroupHardwareInputOutput()
    misc: GroupMisc = GroupMisc()

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

    @classmethod
    def _fix_single_allof(cls, dictionary):
        """Remove allof that would interfere with the normal processing of jsonforms
        Despite there is a bugfix in pydantic, it seems it applies only on first level, nested
        BaseModels still have the allof with just 1 item.

        References:
        - https://github.com/pydantic/pydantic/issues/1209
        - https://github.com/flexcompute/Flow360/pull/90/files#diff-1552b8f7a48149f4361b20a50d6c8a0f79856de26b0765626abc5d54093a7f99
        Args:
            dictionary (_type_): _description_

        Raises:
            ValueError: _description_

        Returns:
            _type_: _description_
        """
        if not isinstance(dictionary, dict):
            raise ValueError("Input must be a dictionary")

        for key, value in list(dictionary.items()):
            if key == "allOf" and len(value) == 1 and isinstance(value[0], dict):
                for allOfKey, allOfValue in list(value[0].items()):
                    dictionary[allOfKey] = allOfValue
                del dictionary["allOf"]
            elif isinstance(value, dict):
                cls._fix_single_allof(value)

        return dictionary

    @classmethod
    def get_schema(cls, schema_type: str = "default"):
        """Get schema to build UI. Schema is polished to the needs of UI"""
        schema = cls.model_json_schema()
        cls._fix_single_allof(schema)
        if schema_type == "dereferenced":
            # https://github.com/pydantic/pydantic/issues/889#issuecomment-1064688675
            return jsonref.loads(json.dumps(schema))
        else:
            return schema

    def reset_defaults(self):
        self.__dict__.update(__class__())

    def update_field(self, field_path: str, value: Any):
        """
        Update a specific field in the configuration JSON file.
        Args:
            field_path (str): The dotted path to the field to update (e.g., "share.max_shares" or "share.items[0].name").
            value (Any): The new value to set for the field.
        """
        import re

        # Regex to match array indices
        array_index_pattern = re.compile(r"(\w+)\[(\d+)\]")

        # Split the field path into parts, considering array indices
        parts = []
        for part in field_path.split("."):
            match = array_index_pattern.match(part)
            if match:
                parts.append(match.group(1))
                parts.append(int(match.group(2)))
            else:
                parts.append(part)

        # Traverse the dictionary to find the specific field
        config = self
        for part in parts[:-1]:
            if isinstance(part, int):  # If the part is an integer, it means it's an index in a list
                config = config[part]
            else:
                config = getattr(config, part, None)
                if config is None:
                    raise KeyError(f"Field path '{field_path}' is invalid.")

        # Update the field
        if isinstance(parts[-1], int):
            config[parts[-1]] = value
        else:
            setattr(config, parts[-1], value)

        # Persist the updated configuration
        self.persist()

    def persist(self):
        """Persist config to file"""
        logger.debug("persist config to json file")

        # if a config exists, backup before overwriting
        self.backup_config()

        # write model to disk to persist
        with open(CONFIG_FILEPATH, mode="w", encoding="utf-8") as write_file:
            write_file.write(self.model_dump_json(context={"secrets_is_allowed": True}, indent=2))

        # remove old config to not clutter the config dir
        self.remove_old_configs()

    def deleteconfig(self):
        """Reset to defaults"""
        logger.debug("config reset to default")

        try:
            os.remove(CONFIG_FILEPATH)
            logger.debug(f"deleted {CONFIG_FILEPATH} file.")
        except (FileNotFoundError, PermissionError):
            logger.warning(f"delete {CONFIG_FILEPATH} file failed.")

    def backup_config(self):
        if Path(CONFIG_FILEPATH).exists():
            datetimestr = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(CONFIG_FILEPATH, f"{CONFIG_FILEPATH}_backup-{datetimestr}")

    def remove_old_configs(self):
        KEEP_NO = 10

        paths = sorted(Path(CONFIG_DIR).glob("*_backup*"), key=os.path.getmtime, reverse=True)

        if len(paths) > KEEP_NO:
            for path in paths[KEEP_NO:]:
                logging.debug(f"deleting old config {path}")
                os.remove(path)
