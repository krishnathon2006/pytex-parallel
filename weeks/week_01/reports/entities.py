from enum import StrEnum


class JobStatus(StrEnum):
    STARTED = "started"
    RUNNING = "running"
    ERROR = "error"
    DONE = "done"
