from pydantic import Field, HttpUrl
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH

from ...services.config.baseconfig import BaseConfig
from .models import HttpRequestParameters, TaskCommand, TaskHttpRequest


class CommanderConfig(BaseConfig):
    model_config = SettingsConfigDict(title="Commander Plugin Config", json_file=f"{CONFIG_PATH}plugin_commander.json")

    enable_tasks_processing: bool = Field(
        default=False,
        description="Enable to process any of the defined tasks at all.",
    )

    tasks_httprequests: list[TaskHttpRequest] = Field(
        description="Send HTTP requests.",
        default=[
            TaskHttpRequest(
                name="demo http request to index page",
                url=HttpUrl("http://127.0.0.1/"),
                parameter=[
                    HttpRequestParameters(key="event_key", value="{event}"),
                    HttpRequestParameters(key="demoparameter", value="demovalue"),
                ],
            ),
        ],
    )
    tasks_commands: list[TaskCommand] = Field(
        description="Run commands on the system the app is running on.",
        default=[
            TaskCommand(
                enabled=True,
                name="demo command",
                command="echo this echoed on event {event}!",
            )
        ],
    )
