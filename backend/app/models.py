from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, validator


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BruteforceConfig(BaseModel):
    enabled: bool = False
    wordlist: Optional[str] = None
    resolvers: Optional[str] = None
    threads: Optional[int] = Field(default=None, ge=1)
    tools: List[str] = Field(default_factory=list)


class JobRequest(BaseModel):
    targets: List[str] = Field(..., description="List of domains or scopes to scan")
    tools: Optional[List[str]] = Field(None, description="Explicit list of tools to run")
    exclude_tools: List[str] = Field(default_factory=list)
    static_bruteforce: BruteforceConfig = Field(default_factory=BruteforceConfig)
    dynamic_bruteforce: BruteforceConfig = Field(default_factory=BruteforceConfig)
    environment: Dict[str, str] = Field(default_factory=dict)
    options: Dict[str, str | int | float | bool] = Field(default_factory=dict)

    @validator("targets")
    def _ensure_targets(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("At least one target must be provided")
        return value


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    message: Optional[str] = None


class JobDetail(JobResponse):
    targets: List[str]
    tools: List[str]
    data_path: Path
    artifacts: List[str]


class JobListResponse(BaseModel):
    jobs: List[JobResponse]


class ArtifactList(BaseModel):
    files: List[str]


class LogEntry(BaseModel):
    timestamp: datetime
    message: str


class ToolResult(BaseModel):
    tool: str
    return_code: Optional[int]
    output_file: Optional[str]
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    error: Optional[str] = None


class JobRunSummary(BaseModel):
    job_id: str
    results: List[ToolResult]
    merged_file: Optional[str]
    probe_file: Optional[str]
