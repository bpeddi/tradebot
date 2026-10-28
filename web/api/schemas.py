import re

from pydantic import BaseModel, field_validator


class AuthRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def min_length(cls, v):
        if len(v) < 8:
            raise ValueError("new_password must be at least 8 characters")
        return v


class ConfigModel(BaseModel):
    symbols: list[str]
    candle_interval: str = "4h"
    short_window: int
    long_window: int
    lookback_days: int = 100
    max_investment: float
    max_slots: int
    rotation_weakness_pct: float = 1.0
    rotation_enabled: bool = True

    @field_validator("symbols")
    @classmethod
    def uppercase_symbols(cls, v):
        return [s.strip().upper() for s in v if s.strip()]

    @field_validator("max_slots")
    @classmethod
    def positive_slots(cls, v):
        if v < 1:
            raise ValueError("max_slots must be at least 1")
        return v


_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class ScheduleModel(BaseModel):
    time1: str = "10:00"
    time2: str = "15:00"
    timezone: str = "America/Chicago"
    enabled: bool = False

    @field_validator("time1", "time2")
    @classmethod
    def validate_time(cls, v):
        if not _TIME_RE.match(v):
            raise ValueError("time must be HH:MM (24-hour)")
        return v
