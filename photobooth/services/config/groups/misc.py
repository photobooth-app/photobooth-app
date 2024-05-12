"""
AppConfig class providing central config

"""

from pydantic import BaseModel, ConfigDict


class GroupMisc(BaseModel):
    """
    Quite advanced or experimental, usually not necessary to touch. Can change any time.
    """

    model_config = ConfigDict(title="Miscellaneous Config")
