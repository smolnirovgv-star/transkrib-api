"""Enums for task state and source type."""

from enum import Enum


class TaskState(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    LOADING_MODEL = "loading_model"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    ASSEMBLING = "assembling"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceType(str, Enum):
    FILE = "file"
    URL = "url"
