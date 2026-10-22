"""Versioned, content-free operational contracts for the synthetic demonstration."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,95}$")]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Percentage = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    @field_validator(
        "observed_at",
        "completed_at",
        "started_at",
        "finished_at",
        "window_start",
        "as_of",
        check_fields=False,
    )
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    @field_validator(
        "cpu_pct",
        "memory_pct",
        "disk_free_inodes_pct",
        "disk_used_bytes",
        "disk_total_bytes",
        "latency_ms",
        "backup_max_age_hours",
        "restore_max_age_days",
        "job_stale_after_hours",
        check_fields=False,
        mode="before",
    )
    @classmethod
    def numeric_not_boolean(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Boolean values are not measurements")
        return value


class ServiceSpec(Contract):
    service_id: Identifier
    check_interval_seconds: Annotated[int, Field(strict=True, ge=60)] = 3600
    backup_max_age_hours: Positive | None = 48
    restore_max_age_days: Positive | None = 30
    job_stale_after_hours: Positive = 4


class Event(Contract):
    event_id: Identifier
    service_id: Identifier


class ServiceCheck(Event):
    observed_at: AwareDatetime
    status: Literal["up", "down", "unknown"]
    latency_ms: Nonnegative | None = None


class ResourceSample(Event):
    observed_at: AwareDatetime
    cpu_pct: Percentage | None = None
    memory_pct: Percentage | None = None
    disk_used_bytes: Annotated[int, Field(strict=True, ge=0)] | None = None
    disk_total_bytes: Annotated[int, Field(strict=True, gt=0)] | None = None
    disk_free_inodes_pct: Percentage | None = None
    pool_health: Literal["online", "degraded", "faulted", "unknown"] | None = None
    disk_health: Literal["passed", "failed", "unknown"] | None = None

    @model_validator(mode="after")
    def disk_bounds(self) -> "ResourceSample":
        if (self.disk_used_bytes is None) != (self.disk_total_bytes is None):
            raise ValueError("Disk used/total bytes must be supplied together")
        if self.disk_used_bytes is not None and self.disk_used_bytes > self.disk_total_bytes:
            raise ValueError("Disk usage exceeds capacity")
        return self


class BackupRecord(Event):
    completed_at: AwareDatetime
    outcome: Literal["success", "failed"]
    verification: Literal["none", "checksum"] = "none"

    @model_validator(mode="after")
    def verification_requires_success(self) -> "BackupRecord":
        if self.outcome == "failed" and self.verification != "none":
            raise ValueError("Failed backups cannot have successful verification")
        return self


class RestoreTest(Event):
    completed_at: AwareDatetime
    outcome: Literal["passed", "failed"]


class JobRun(Event):
    job_id: Identifier
    job_type: Identifier
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    status: Literal["succeeded", "failed", "running", "blocked"]
    attempts: Annotated[int, Field(strict=True, ge=1)] = 1
    error_category: Identifier | None = None

    @model_validator(mode="after")
    def lifecycle(self) -> "JobRun":
        terminal = self.status in {"succeeded", "failed"}
        if terminal != (self.finished_at is not None):
            raise ValueError("Only terminal jobs must have a finish timestamp")
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("Job finishes before it starts")
        return self


class Dataset(Contract):
    schema_version: Literal[1] = 1
    data_classification: Literal["synthetic"]
    window_start: AwareDatetime
    as_of: AwareDatetime
    seed: Annotated[int, Field(strict=True)] | None = None
    generator_version: Literal["1"] | None = None
    services: list[ServiceSpec] = Field(min_length=1, max_length=100)
    service_checks: list[ServiceCheck] = Field(default_factory=list, max_length=100_000)
    resource_samples: list[ResourceSample] = Field(default_factory=list, max_length=100_000)
    backups: list[BackupRecord] = Field(default_factory=list, max_length=100_000)
    restore_tests: list[RestoreTest] = Field(default_factory=list, max_length=100_000)
    job_runs: list[JobRun] = Field(default_factory=list, max_length=100_000)
    _duplicates_removed: int = PrivateAttr(default=0)

    @property
    def duplicates_removed(self) -> int:
        return self._duplicates_removed

    @model_validator(mode="after")
    def relationships(self) -> "Dataset":
        if self.window_start >= self.as_of:
            raise ValueError("Reporting window must start before the exclusive as_of cutoff")
        service_ids = {service.service_id for service in self.services}
        if len(service_ids) != len(self.services):
            raise ValueError("Duplicate service definition")
        seen: dict[str, tuple[str, dict]] = {}
        fields = ("service_checks", "resource_samples", "backups", "restore_tests", "job_runs")
        if sum(len(getattr(self, name)) for name in fields) > 100_000:
            raise ValueError("Dataset exceeds 100,000 events")
        for name in fields:
            normalized = []
            observation_keys = set()
            for event in getattr(self, name):
                if event.service_id not in service_ids:
                    raise ValueError("Event refers to an undefined service")
                for value in event.model_dump().values():
                    if isinstance(value, datetime) and value >= self.as_of:
                        raise ValueError("Events must precede the exclusive as_of cutoff")
                fingerprint = (name, event.model_dump(mode="json"))
                if event.event_id in seen:
                    if seen[event.event_id] != fingerprint:
                        raise ValueError("Conflicting event ID")
                    self._duplicates_removed += 1
                    continue
                seen[event.event_id] = fingerprint
                if name == "job_runs":
                    observation_key = (event.service_id, event.job_id)
                else:
                    timestamp = getattr(event, "observed_at", None)
                    if timestamp is None:
                        timestamp = event.completed_at
                    observation_key = (event.service_id, timestamp)
                if observation_key in observation_keys:
                    raise ValueError(f"Conflicting observation key in {name}")
                observation_keys.add(observation_key)
                normalized.append(event)
            setattr(self, name, normalized)
        return self
