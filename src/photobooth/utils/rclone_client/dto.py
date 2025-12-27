from dataclasses import dataclass
from typing import Any


@dataclass
class CoreVersion:
    version: str

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return CoreVersion(version=d.get("version", "unknown"))


@dataclass
class JobList:
    executeId: str
    jobids: list[int]
    runningIds: list[int]
    finishedIds: list[int]

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return JobList(
            executeId=str(d.get("executeId", "")),
            jobids=d.get("jobids", []),
            runningIds=d.get("runningIds", []),
            finishedIds=d.get("finishedIds", []),
        )


@dataclass
class ConfigListremotes:
    remotes: list[str]

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return ConfigListremotes(remotes=d.get("remotes", []))


@dataclass
class AsyncJobResponse:
    jobid: int
    executeId: str

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return AsyncJobResponse(
            jobid=d["jobid"],
            executeId=d["executeId"],
        )


@dataclass
class JobStatus:
    finished: bool
    duration: float
    endTime: str | None
    error: str | None
    id: int
    executeId: int | None
    startTime: str | None
    success: bool
    output: Any
    progress: Any

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return JobStatus(
            finished=d.get("finished", False),
            duration=d.get("duration", 0.0),
            endTime=d.get("endTime"),
            error=d.get("error"),
            id=d.get("id", 0),
            executeId=d.get("executeId"),
            startTime=d.get("startTime"),
            success=d.get("success", False),
            output=d.get("output"),
            progress=d.get("progress"),
        )


@dataclass
class TransferEntry:
    bytes: int
    eta: float | None
    name: str
    percentage: float
    speed: float
    speedAvg: float
    size: int

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return TransferEntry(
            bytes=d.get("bytes", 0),
            eta=d.get("eta"),  # may be None
            name=d.get("name", ""),
            percentage=d.get("percentage", 0.0),
            speed=d.get("speed", 0.0),
            speedAvg=d.get("speedAvg", 0.0),
            size=d.get("size", 0),
        )


@dataclass
class CoreStats:
    bytes: int
    checks: int
    deletes: int
    elapsedTime: float
    errors: int
    eta: float | None
    fatalError: bool
    lastError: str | None
    renames: int
    listed: int
    retryError: bool

    serverSideCopies: int
    serverSideCopyBytes: int
    serverSideMoves: int
    serverSideMoveBytes: int

    speed: float

    totalBytes: int
    totalChecks: int
    totalTransfers: int
    transferTime: float
    transfers: int

    transferring: list[TransferEntry]
    checking: list[str]

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return CoreStats(
            bytes=d.get("bytes", 0),
            checks=d.get("checks", 0),
            deletes=d.get("deletes", 0),
            elapsedTime=d.get("elapsedTime", 0.0),
            errors=d.get("errors", 0),
            eta=d.get("eta"),
            fatalError=d.get("fatalError", False),
            lastError=d.get("lastError"),
            renames=d.get("renames", 0),
            listed=d.get("listed", 0),
            retryError=d.get("retryError", False),
            serverSideCopies=d.get("serverSideCopies", 0),
            serverSideCopyBytes=d.get("serverSideCopyBytes", 0),
            serverSideMoves=d.get("serverSideMoves", 0),
            serverSideMoveBytes=d.get("serverSideMoveBytes", 0),
            speed=d.get("speed", 0.0),
            totalBytes=d.get("totalBytes", 0),
            totalChecks=d.get("totalChecks", 0),
            totalTransfers=d.get("totalTransfers", 0),
            transferTime=d.get("transferTime", 0.0),
            transfers=d.get("transfers", 0),
            transferring=[TransferEntry.from_dict(x) for x in d.get("transferring", [])],
            checking=d.get("checking", []),
        )
