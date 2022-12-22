from .ConfigSettings import settings
from typing import Annotated
from pydantic import BaseModel, BaseSettings, Field
import os
import json
import logging
logger = logging.getLogger(__name__)


class ConfigService():
    '''Actions on configsettings class'''

    def __init__(self, ee):
        self._ee = ee

    def reset_default_values(self):
        pass

    def load(self):
        pass

    def update_internal_config(self):
        pass

    def save(self):
        pass

    def get_schema(self):
        '''get json schema for UI'''
        return (self.schema_json(indent=2))

    def _publishSSEInitial(self):
        self._publishSSE_currentconfig()

    def _publishSSE_currentconfig(self):
        self._ee.emit("publishSSE", sse_event="config/currentconfig",
                      sse_data=settings.json())
