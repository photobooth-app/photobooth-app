from typing import Any

from pydantic import SerializationInfo


def contextual_serializer_password(value: Any, info: SerializationInfo):
    if info.context:
        if info.context.get("secrets_is_allowed", False):
            return value.get_secret_value()

    return "************"
