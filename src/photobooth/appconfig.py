"""
AppConfig class providing central config

"""

from pydantic import ValidationError

from .services.config.appconfig_ import AppConfig

try:
    appconfig = AppConfig()
except ValidationError as exc:
    print("")
    print("🛑 Your configuration has errors: 🛑")
    print("")
    print(exc)
    print("ℹ️  Check above errors and try to modify the config.json directly or delete it and start over.")
    print("")
    print("Sorry! 😔")
    print("")
    quit()
