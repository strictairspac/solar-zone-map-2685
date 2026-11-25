from pydantic import BaseModel, Field, field_validator

from src.constants.purge_state import PurgeState
from src.utils.serial import canonical_json


class CaseInput(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=420)
    payload: dict
    expires_at: int | None = Field(default=None, ge=0)

    @field_validator("title")
    @classmethod
    def check_title(cls, title):
        if len(title.strip()) < 2:
            raise ValueError("请输入至少两个字符的名称")
        return title.strip()

    @field_validator("payload")
    @classmethod
    def check_size(cls, payload):
        if len(canonical_json(payload)) > 750_000:
            raise ValueError("样本数据不能超过 750 KB")
        return payload


class PurgeProgress(BaseModel):
    state: PurgeState
    expired: bool
    expires_at: int | None
    started_at: int | None
    purged_at: int | None
    accepted_runs: int
    pending_runs: int
    readings_retained: bool
    copies_retained: bool


class CaseEntry(BaseModel):
    id: int
    code: str
    title: str
    description: str
    payload: dict | None
    created_by: str
    progress: PurgeProgress | None = None


class PurgeEntry(BaseModel):
    id: int
    progress: PurgeProgress
