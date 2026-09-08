from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings


TEST_TYPES = Literal[
    "seq_read_128k", "seq_write_128k", "rand_read_4k", "rand_write_4k",
    "randrw_70_30", "randrw_50_50", "qd_scan", "stress_rand_write", "stress_seq_write",
]


class FioParameters(BaseModel):
    block_size: Optional[str] = None
    queue_depth: int = Field(default=32, ge=1, le=1024)
    num_jobs: int = Field(default=1, ge=1, le=128)
    runtime_seconds: int = Field(default=60, ge=1, le=604800)
    size: str = "100%"
    precondition: bool = False
    queue_depths: List[int] = Field(default_factory=lambda: [1, 2, 4, 8, 16, 32, 64, 128, 256])

    @field_validator("block_size")
    @classmethod
    def valid_bs(cls, value: Optional[str]):
        if value is not None and not __import__("re").fullmatch(r"[1-9]\d*[kKmMgG]?", value):
            raise ValueError("块大小格式无效，例如 4k、128k、1m")
        return value

    @field_validator("size")
    @classmethod
    def valid_size(cls, value: str):
        if value != "100%" and not __import__("re").fullmatch(r"[1-9]\d*(?:[kKmMgGtT]|[kKmMgGtT]i?[bB])", value):
            raise ValueError("测试容量格式无效，例如 10G、10GiB 或 100%")
        return value

    @field_validator("queue_depths")
    @classmethod
    def valid_qds(cls, value: List[int]):
        if not value or len(value) > 32 or any(v < 1 or v > 1024 for v in value):
            raise ValueError("QD 列表必须包含 1-32 个 1..1024 的整数")
        return value


class TestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    device: str = Field(min_length=1, max_length=255)
    test_type: TEST_TYPES
    parameters: FioParameters = Field(default_factory=FioParameters)
    destructive_confirmed: bool = False
    confirmation_device: Optional[str] = None

    @model_validator(mode="after")
    def stress_default_runtime(self):
        if self.test_type.startswith("stress_") and "runtime_seconds" not in self.parameters.model_fields_set:
            self.parameters.runtime_seconds = settings.default_stress_seconds
        return self


class TestStart(BaseModel):
    destructive_confirmed: bool = False
    confirmation_device: Optional[str] = None


class TestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    device: str
    test_type: str
    status: str
    progress: float
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: Optional[float]
    error_message: Optional[str]
    result_dir: Optional[str]
