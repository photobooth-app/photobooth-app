"""
AppConfig class providing central config

"""

from pydantic import ValidationError

from .services.config.appconfig_ import AppConfig

try:
    appconfig = AppConfig()
except ValidationError as exc:
    print(
        "\n\nYour configuration has errors:\n"
        f"{exc}\n"
        "Check above errors and try to modify the config.json directly or delete it and start over.\n"
        "\nSorry!\n"
    )

    raise SystemExit from exc
