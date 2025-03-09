"""
AppConfig class providing central config
file called appconfig_ to avoid conflicts with the singleton appconfig in __init__
"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import jsonref
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

SchemaTypes = Literal["default", "dereferenced"]
logger = logging.getLogger(__name__)


class JsonConfigSettingsSource(PydanticBaseSettingsSource):
    """
    A simple settings source class that loads variables from a JSON file
    at the project's root.

    Here we happen to choose to use the `env_file_encoding` from Config
    when reading `config.json`
    """

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        field_value = None
        try:
            file_content_json = json.loads(Path(str(self.config.get("json_file"))).read_text(self.config.get("env_file_encoding")))
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


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        # first in following list is least important; last .env file overwrites the other.
        env_file=[".env.installer", ".env.dev", ".env.test", ".env.prod"],
        env_nested_delimiter="__",
        case_sensitive=True,
        extra="ignore",
        json_file_encoding="utf-8",
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
        return (init_settings, JsonConfigSettingsSource(settings_cls), dotenv_settings, env_settings, file_secret_settings)

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

    def get_schema(self, schema_type: SchemaTypes = "default"):
        """Get schema to build UI. Schema is polished to the needs of UI"""
        schema = self.model_json_schema()
        self._fix_single_allof(schema)

        if schema_type == "dereferenced":
            # https://github.com/pydantic/pydantic/issues/889#issuecomment-1064688675

            return jsonref.loads(json.dumps(schema))

        else:
            return schema

    def get_current(self, secrets_is_allowed: bool = False):
        return self.model_dump(context={"secrets_is_allowed": secrets_is_allowed}, mode="json")

    def reset_defaults(self):
        self.__dict__.update(self.__class__())

    def persist(self):
        """Persist config to file"""

        # if a config exists, backup before overwriting
        self._backup_config()

        # write model to disk to persist
        with open(str(self.model_config.get("json_file")), mode="w", encoding=self.model_config.get("json_file_encoding")) as write_file:
            write_file.write(self.model_dump_json(context={"secrets_is_allowed": True}, indent=2))

        logger.debug(f"persisted config to {self.model_config.get('json_file')}")

        # remove old config to not clutter the config dir
        self._remove_old_configs()

    def deleteconfig(self):
        """Reset to defaults"""
        logger.debug("config reset to default")
        json_file = None

        try:
            json_file = str(self.model_config.get("json_file"))
            os.remove(json_file)
            logger.debug(f"deleted {json_file} file.")
        except (FileNotFoundError, PermissionError):
            logger.warning(f"delete {json_file} file failed.")

    def _backup_config(self):
        json_file = str(self.model_config.get("json_file"))
        if Path(json_file).exists():
            datetimestr = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(json_file, f"{json_file}_backup-{datetimestr}")

    def _remove_old_configs(self):
        KEEP_NO = 10
        json_file = Path(str(self.model_config.get("json_file")))
        json_file_name = json_file.name
        json_file_folder = json_file.parent
        paths = sorted(json_file_folder.glob(f"{json_file_name}_backup-*"), key=os.path.getmtime, reverse=True)

        if len(paths) > KEEP_NO:
            for path in paths[KEEP_NO:]:
                logging.debug(f"deleting old config {path}")
                os.remove(path)
