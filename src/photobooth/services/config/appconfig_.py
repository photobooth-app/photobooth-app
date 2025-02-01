"""
AppConfig class providing central config
file called appconfig_ to avoid conflicts with the singleton appconfig in __init__
"""

import logging
from datetime import datetime

from pydantic import PrivateAttr
from pydantic_settings import SettingsConfigDict

from ... import CONFIG_PATH
from .baseconfig import BaseConfig
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


class AppConfig(BaseConfig):
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

    model_config = SettingsConfigDict(json_file=f"{CONFIG_PATH}config.json")

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
