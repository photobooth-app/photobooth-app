from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from ...database.types import MediaitemTypes

eventHooksService = Literal["init", "start", "stop"]
eventHooksStatemachine = Literal["counting", "capture", "captured", "finished"]
eventHooksAcquisition = Literal["capture_still", "capture_multicam", "capture_video"]
eventHooks = Literal[eventHooksService, eventHooksStatemachine, eventHooksAcquisition]
requestMethods = Literal["get", "post", "patch", "put", "delete"]
locationOfAdditionalParameters = Literal["query", "body"]


class HttpRequestParameters(BaseModel):
    key: str = Field(
        description="Key name for the http request to make the parameter list.",
    )
    value: str = Field(
        description="Value assigned to the key in the request (key=value). The placeholder {event} is replaced by the actual event.",
    )
    where: locationOfAdditionalParameters = Field(
        description="Parameters can be sent in the URL as query parameter (usually for get requests like ?key=value) or "
        "in the request body (usually when method is POST)",
        default="query",
    )


class TaskBase(BaseModel):
    enabled: bool = Field(
        description="Enable to invoke the request when the event occurs.",
        default=True,
    )
    name: str = Field(
        description="Name chosen by the user to distinguish between multiple tasks. Used for display only.",
        default="default task",
    )
    event: list[eventHooks] = Field(
        description="Task is run for every selected event.",
        default=["finished"],
    )
    filter_mediaitem_types: list[MediaitemTypes] = Field(
        description="During job-related events (counting, capture, captured, finished), the task execution can be filtered by types. "
        "If nothing is selected, the task is executed for all types, otherwise only for the chosen ones.",
        default=[],
    )

    @field_validator("event", mode="before")
    def _map_deprecated_record(cls, v):
        return ["capture_video" if x == "record" else x for x in v]

    delay_before: float = Field(
        description="Seconds to delay the execution of the task after the event occured. Please note, that the delay is not cancellable.",
        default=0,
        ge=0,
        le=10,
    )

    wait_until_completed: bool = Field(
        description="Suspend the process calling the event until the task completed or failed. "
        "Usually not recommended to avoid slowing down the apps responsiveness.",
        default=False,
    )
    timeout: int = Field(
        description="Abort task after timeout.",
        default=5,
    )


class TaskHttpRequest(TaskBase):
    url: HttpUrl = Field(
        description="URL to send the request to.",
    )
    method: requestMethods = Field(
        description="Method to send the request.",
        default="get",
    )
    body_parameters_as_json: bool = Field(
        description="If enabled, the parameters with location 'body' are sent as json, otherwise as normal body data.",
        default=True,
    )
    parameter: list[HttpRequestParameters] = Field(
        description="Add additional paramters to the request. Parameter can be added to the query url (?key=val) or in the body.",
        default=[],
    )


class TaskCommand(TaskBase):
    command: str = Field(
        description="Command to run. The placeholder {event} is replaced by the actual event.",
    )
