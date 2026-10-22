"""Reproducible server observations; no live collectors or private inputs."""

import random
from datetime import UTC, datetime, timedelta

from .contracts import Dataset

DEFAULT_AS_OF = datetime(2026, 10, 19, tzinfo=UTC)


def generate_dataset(seed: int = 42) -> Dataset:
    rng = random.Random(seed)
    as_of = DEFAULT_AS_OF
    start = as_of - timedelta(days=28)
    services = ["compute", "documents", "photos"]
    data = {
        "schema_version": 1,
        "data_classification": "synthetic",
        "window_start": start,
        "as_of": as_of,
        "seed": seed,
        "generator_version": "1",
        "services": [{"service_id": name} for name in services],
        "service_checks": [],
        "resource_samples": [],
        "backups": [],
        "restore_tests": [],
        "job_runs": [],
    }
    for hour in range(28 * 24):
        observed_at = start + timedelta(hours=hour)
        for name in services:
            missing = (name == "photos" and hour >= 660) or (name == "documents" and hour % 29 == 0)
            if not missing:
                status = "up"
                if name == "documents" and (hour % 79 == 0 or hour == 671):
                    status = "down"
                elif hour % 53 == 0:
                    status = "unknown"
                data["service_checks"].append(
                    {
                        "event_id": f"check-{name}-{hour:04d}",
                        "service_id": name,
                        "observed_at": observed_at,
                        "status": status,
                        "latency_ms": round(rng.uniform(15, 90), 2) if status == "up" else None,
                    }
                )
            if hour % 6 != 0 and hour != 671:
                continue
            if name == "photos" and hour >= 664:
                continue
            disk_pct = 60 + hour * 36 / 671 if name == "photos" else 45 + hour * 4 / 671
            data["resource_samples"].append(
                {
                    "event_id": f"resource-{name}-{hour:04d}",
                    "service_id": name,
                    "observed_at": observed_at,
                    "cpu_pct": round(rng.uniform(15, 55), 2),
                    "memory_pct": 94 if name == "documents" and hour >= 600 else 45,
                    "disk_used_bytes": int(1_000_000_000_000 * disk_pct / 100),
                    "disk_total_bytes": 1_000_000_000_000,
                    "disk_free_inodes_pct": 4 if name == "documents" and hour == 671 else 55,
                    "pool_health": "degraded" if name == "compute" and hour == 671 else "online",
                    "disk_health": "passed",
                }
            )
    for day in range(28):
        for name in services:
            if name == "photos" and day >= 25:
                continue
            failed = name == "documents" and day == 27
            data["backups"].append(
                {
                    "event_id": f"backup-{name}-{day:02d}",
                    "service_id": name,
                    "completed_at": start + timedelta(days=day, hours=2),
                    "outcome": "failed" if failed else "success",
                    "verification": "none" if failed else "checksum",
                }
            )
        for name in ("documents", "photos"):
            for run in range(2):
                number = day * 2 + run
                started_at = start + timedelta(days=day, hours=run * 6 + 4)
                status = "failed" if number % 17 == 0 else "succeeded"
                if day == 27 and run == 0:
                    status = "blocked" if name == "documents" else "running"
                duration = timedelta(minutes=rng.randint(5, 80))
                data["job_runs"].append(
                    {
                        "event_id": f"job-event-{name}-{number:03d}",
                        "service_id": name,
                        "job_id": f"job-{name}-{number:03d}",
                        "job_type": "index" if name == "documents" else "thumbnail",
                        "started_at": started_at,
                        "finished_at": started_at + duration
                        if status in {"succeeded", "failed"}
                        else None,
                        "status": status,
                        "attempts": 3 if number % 5 == 0 else 1,
                        "error_category": "dependency_unavailable"
                        if status in {"failed", "blocked"}
                        else None,
                    }
                )
    for name, age, outcome in (
        ("compute", 40, "passed"),
        ("documents", 10, "passed"),
        ("photos", 2, "failed"),
    ):
        data["restore_tests"].append(
            {
                "event_id": f"restore-{name}",
                "service_id": name,
                "completed_at": as_of - timedelta(days=age),
                "outcome": outcome,
            }
        )
    return Dataset.model_validate(data)
