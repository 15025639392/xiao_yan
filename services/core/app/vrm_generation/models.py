from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class VrmGenerationStatus(StrEnum):
    QUEUED = "queued"
    VALIDATING_SPEC = "validating_spec"
    RUNNING_BLENDER = "running_blender"
    EXPORTING_VRM = "exporting_vrm"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VrmGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    input_model_path: str | None = None
    spec: dict[str, Any] | None = None


class VrmGenerationArtifacts(BaseModel):
    spec_path: str | None = None
    output_vrm_path: str | None = None
    log_path: str | None = None


class VrmGenerationJobList(BaseModel):
    items: list["VrmGenerationJob"]


class VrmGenerationJob(BaseModel):
    job_id: str = Field(default_factory=lambda: uuid4().hex)
    prompt: str
    status: VrmGenerationStatus = VrmGenerationStatus.QUEUED
    input_model_path: str | None = None
    artifacts: VrmGenerationArtifacts = Field(default_factory=VrmGenerationArtifacts)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def with_status(self, status: VrmGenerationStatus) -> "VrmGenerationJob":
        return self.model_copy(update={"status": status, "updated_at": datetime.now(timezone.utc)})

    def fail(self, *, code: str, message: str) -> "VrmGenerationJob":
        return self.model_copy(
            update={
                "status": VrmGenerationStatus.FAILED,
                "error_code": code,
                "error_message": message,
                "updated_at": datetime.now(timezone.utc),
            }
        )

