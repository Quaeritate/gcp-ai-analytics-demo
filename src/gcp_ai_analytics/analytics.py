"""Deterministic offline server analytics over a validated synthetic dataset.

All ages are measured at the dataset's exclusive ``as_of`` boundary. Findings
describe observations, not causes, outage durations, or promises of recoverability.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from typing import Any

from gcp_ai_analytics.contracts import Dataset, ServiceSpec


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _percentage(numerator: int | float, denominator: int | float) -> float | None:
    return round(100 * numerator / denominator, 2) if denominator else None


def _hours(later: datetime, earlier: datetime) -> float:
    return round((later - earlier).total_seconds() / 3600, 4)


def _latest(records: list[Any], time_field: str) -> Any | None:
    return max(records, key=lambda item: (getattr(item, time_field), item.event_id), default=None)


def _finding(
    findings: list[dict[str, Any]],
    service_id: str,
    severity: str,
    code: str,
    summary: str,
    **evidence: Any,
) -> None:
    findings.append(
        {
            "severity": severity,
            "service_id": service_id,
            "code": code,
            "summary": summary,
            "evidence": evidence,
        }
    )


def _checks(dataset: Dataset, service: ServiceSpec, findings: list) -> dict[str, Any]:
    history = [item for item in dataset.service_checks if item.service_id == service.service_id]
    observations = [item for item in history if dataset.window_start <= item.observed_at]
    expected = math.ceil(
        (dataset.as_of - dataset.window_start).total_seconds() / service.check_interval_seconds
    )
    slots: dict[int, Any] = {}
    for item in sorted(observations, key=lambda item: (item.observed_at, item.event_id)):
        slot = int(
            (item.observed_at - dataset.window_start).total_seconds()
            // service.check_interval_seconds
        )
        slots[slot] = item
    statuses = Counter(item.status for item in slots.values())
    known = statuses["up"] + statuses["down"]
    latest = _latest(history, "observed_at")
    age_seconds = (dataset.as_of - latest.observed_at).total_seconds() if latest else None
    is_fresh = age_seconds <= 2 * service.check_interval_seconds if latest else None
    result = {
        "raw_observations": len(observations),
        "expected_slots": expected,
        "observed_slots": len(slots),
        "known_status_slots": known,
        "up_slots": statuses["up"],
        "down_slots": statuses["down"],
        "unknown_slots": statuses["unknown"],
        "missing_slots": expected - len(slots),
        "sampled_success_pct": _percentage(statuses["up"], known),
        "monitoring_coverage_pct": _percentage(known, expected),
        "latest_observed_at": _iso(latest.observed_at) if latest else None,
        "latest_status": latest.status if latest else None,
        "latest_latency_ms": latest.latency_ms if latest else None,
        "latest_age_hours": _hours(dataset.as_of, latest.observed_at) if latest else None,
        "is_fresh": is_fresh,
        "freshness_limit_seconds": 2 * service.check_interval_seconds,
    }
    if known < expected:
        _finding(
            findings,
            service.service_id,
            "warning",
            "monitoring_coverage_gap",
            "Some expected monitoring slots have no known up/down observation.",
            expected_slots=expected,
            known_status_slots=known,
            missing_slots=result["missing_slots"],
            unknown_slots=statuses["unknown"],
            monitoring_coverage_pct=result["monitoring_coverage_pct"],
        )
    if latest is None:
        _finding(
            findings,
            service.service_id,
            "warning",
            "checks_missing",
            "No service check is available before the report cutoff.",
            available_checks=0,
        )
    elif not is_fresh:
        _finding(
            findings,
            service.service_id,
            "warning",
            "checks_stale",
            "The latest service check is too old to describe current status.",
            event_id=latest.event_id,
            observed_at=_iso(latest.observed_at),
            age_hours=result["latest_age_hours"],
            freshness_limit_seconds=result["freshness_limit_seconds"],
            observed_status=latest.status,
        )
    elif latest.status in {"down", "unknown"}:
        _finding(
            findings,
            service.service_id,
            "critical" if latest.status == "down" else "warning",
            "latest_check_down" if latest.status == "down" else "latest_check_unknown",
            f"The latest fresh service check reports {latest.status}.",
            event_id=latest.event_id,
            observed_at=_iso(latest.observed_at),
            age_hours=result["latest_age_hours"],
            observed_status=latest.status,
        )
    return result


def _resources(dataset: Dataset, service: ServiceSpec, findings: list) -> dict[str, Any]:
    latest = _latest(
        [item for item in dataset.resource_samples if item.service_id == service.service_id],
        "observed_at",
    )
    limit_seconds = 2 * service.check_interval_seconds
    measurement_fields = (
        "cpu_pct",
        "memory_pct",
        "disk_used_bytes",
        "disk_total_bytes",
        "disk_free_inodes_pct",
        "pool_health",
        "disk_health",
    )
    measured_fields = [
        field for field in measurement_fields if latest and getattr(latest, field) is not None
    ]
    result: dict[str, Any] = {
        "latest_observed_at": _iso(latest.observed_at) if latest else None,
        "latest_age_hours": _hours(dataset.as_of, latest.observed_at) if latest else None,
        "is_fresh": (
            (dataset.as_of - latest.observed_at).total_seconds() <= limit_seconds
            if latest
            else None
        ),
        "freshness_limit_seconds": limit_seconds,
        "measured_fields": measured_fields,
        "missing_fields": [field for field in measurement_fields if field not in measured_fields],
        "cpu_pct": latest.cpu_pct if latest else None,
        "memory_pct": latest.memory_pct if latest else None,
        "disk_used_bytes": latest.disk_used_bytes if latest else None,
        "disk_total_bytes": latest.disk_total_bytes if latest else None,
        "disk_used_pct": (
            _percentage(latest.disk_used_bytes, latest.disk_total_bytes)
            if latest and latest.disk_used_bytes is not None and latest.disk_total_bytes
            else None
        ),
        "disk_free_inodes_pct": latest.disk_free_inodes_pct if latest else None,
        "pool_health": latest.pool_health if latest else None,
        "disk_health": latest.disk_health if latest else None,
    }
    if latest is None:
        _finding(
            findings,
            service.service_id,
            "warning",
            "resources_missing",
            "No resource sample is available before the report cutoff.",
            available_samples=0,
        )
        return result
    observation = {
        "event_id": latest.event_id,
        "observed_at": _iso(latest.observed_at),
        "age_hours": result["latest_age_hours"],
    }
    if not measured_fields:
        _finding(
            findings,
            service.service_id,
            "warning",
            "resources_empty",
            "The latest resource sample has no measurements; freshness alone does not show health.",
            **observation,
            measured_fields=measured_fields,
            missing_fields=result["missing_fields"],
        )
    if not result["is_fresh"]:
        _finding(
            findings,
            service.service_id,
            "warning",
            "resources_stale",
            "The latest resource sample is too old for current resource alerts.",
            **observation,
            freshness_limit_seconds=limit_seconds,
        )
        return result
    thresholds = [
        ("cpu_pct", "cpu_high", "CPU utilization", 85, 95),
        ("memory_pct", "memory_high", "Memory utilization", 85, 95),
        ("disk_used_pct", "disk_capacity_high", "Disk capacity used", 85, 95),
    ]
    for field, code, label, warning, critical in thresholds:
        value = result[field]
        if field == "disk_used_pct" and latest.disk_total_bytes:
            value = 100 * latest.disk_used_bytes / latest.disk_total_bytes
        if value is not None and value >= warning:
            _finding(
                findings,
                service.service_id,
                "critical" if value >= critical else "warning",
                code,
                f"{label} exceeds the demonstration threshold in the latest sample.",
                **observation,
                metric=field,
                value_pct=value,
                warning_threshold_pct=warning,
                critical_threshold_pct=critical,
            )
    free_inodes = latest.disk_free_inodes_pct
    if free_inodes is not None and free_inodes <= 10:
        _finding(
            findings,
            service.service_id,
            "critical" if free_inodes <= 5 else "warning",
            "free_inodes_low",
            "Free inodes are low in the latest sample.",
            **observation,
            free_inodes_pct=free_inodes,
            warning_threshold_pct=10,
            critical_threshold_pct=5,
        )
    if latest.pool_health in {"degraded", "faulted", "unknown"}:
        _finding(
            findings,
            service.service_id,
            "critical" if latest.pool_health in {"degraded", "faulted"} else "warning",
            f"pool_{latest.pool_health}",
            f"The latest storage pool observation reports {latest.pool_health}.",
            **observation,
            pool_health=latest.pool_health,
        )
    if latest.disk_health in {"failed", "unknown"}:
        _finding(
            findings,
            service.service_id,
            "critical" if latest.disk_health == "failed" else "warning",
            f"disk_health_{latest.disk_health}",
            f"The latest disk health observation reports {latest.disk_health}.",
            **observation,
            disk_health=latest.disk_health,
        )
    return result


def _backups(dataset: Dataset, service: ServiceSpec, findings: list) -> dict[str, Any]:
    attempts = [item for item in dataset.backups if item.service_id == service.service_id]
    restores = [item for item in dataset.restore_tests if item.service_id == service.service_id]
    latest = _latest(attempts, "completed_at")
    success = _latest([item for item in attempts if item.outcome == "success"], "completed_at")
    latest_restore = _latest(restores, "completed_at")
    passed_restore = _latest(
        [item for item in restores if item.outcome == "passed"], "completed_at"
    )
    backup_age = _hours(dataset.as_of, success.completed_at) if success else None
    restore_age_days = (
        (dataset.as_of - passed_restore.completed_at).total_seconds() / 86400
        if passed_restore
        else None
    )
    backup_overdue = (
        (dataset.as_of - success.completed_at).total_seconds() > service.backup_max_age_hours * 3600
        if success and service.backup_max_age_hours is not None
        else None
    )
    restore_overdue = (
        restore_age_days > service.restore_max_age_days
        if passed_restore and service.restore_max_age_days is not None
        else None
    )
    result = {
        "max_age_hours": service.backup_max_age_hours,
        "latest_attempt_at": _iso(latest.completed_at) if latest else None,
        "latest_attempt_outcome": latest.outcome if latest else None,
        "last_success_at": _iso(success.completed_at) if success else None,
        "last_success_age_hours": backup_age,
        "last_success_checksum_verified": success.verification == "checksum" if success else None,
        "is_overdue": backup_overdue,
        "restore_max_age_days": service.restore_max_age_days,
        "latest_restore_at": _iso(latest_restore.completed_at) if latest_restore else None,
        "latest_restore_outcome": latest_restore.outcome if latest_restore else None,
        "last_passed_restore_at": _iso(passed_restore.completed_at) if passed_restore else None,
        "last_passed_restore_age_days": (
            round(restore_age_days, 4) if restore_age_days is not None else None
        ),
        "restore_is_overdue": restore_overdue,
    }
    if service.backup_max_age_hours is not None and not success:
        _finding(
            findings,
            service.service_id,
            "warning",
            "backup_success_missing",
            "No successful backup is recorded for this service.",
            recorded_attempts=len(attempts),
            max_age_hours=service.backup_max_age_hours,
        )
    elif backup_overdue:
        _finding(
            findings,
            service.service_id,
            "warning",
            "backup_overdue",
            "The most recent successful backup exceeds its configured age target.",
            event_id=success.event_id,
            last_success_at=_iso(success.completed_at),
            age_hours=backup_age,
            max_age_hours=service.backup_max_age_hours,
        )
    if latest and latest.outcome == "failed":
        _finding(
            findings,
            service.service_id,
            "warning",
            "latest_backup_failed",
            "The latest recorded backup attempt failed.",
            event_id=latest.event_id,
            completed_at=_iso(latest.completed_at),
            last_success_at=result["last_success_at"],
        )
    if service.restore_max_age_days is not None and not passed_restore:
        _finding(
            findings,
            service.service_id,
            "warning",
            "restore_success_missing",
            "No successful restore test is recorded; backup success alone does not prove recovery.",
            recorded_restore_tests=len(restores),
            max_age_days=service.restore_max_age_days,
        )
    elif restore_overdue:
        _finding(
            findings,
            service.service_id,
            "warning",
            "restore_test_overdue",
            "The most recent successful restore test exceeds its configured age target.",
            event_id=passed_restore.event_id,
            completed_at=_iso(passed_restore.completed_at),
            age_days=result["last_passed_restore_age_days"],
            max_age_days=service.restore_max_age_days,
        )
    if latest_restore and latest_restore.outcome == "failed":
        _finding(
            findings,
            service.service_id,
            "critical",
            "latest_restore_failed",
            "The latest recorded restore test failed.",
            event_id=latest_restore.event_id,
            completed_at=_iso(latest_restore.completed_at),
            last_passed_restore_at=result["last_passed_restore_at"],
        )
    return result


def _jobs(dataset: Dataset, service: ServiceSpec, findings: list) -> dict[str, Any]:
    history = [item for item in dataset.job_runs if item.service_id == service.service_id]
    completed = [
        item
        for item in history
        if item.status in {"succeeded", "failed"} and item.finished_at >= dataset.window_start
    ]
    pending = [item for item in history if item.status in {"running", "blocked"}]
    succeeded = [item for item in completed if item.status == "succeeded"]
    failed = [item for item in completed if item.status == "failed"]
    stale = [
        item
        for item in pending
        if (dataset.as_of - item.started_at).total_seconds() > service.job_stale_after_hours * 3600
    ]
    slowest = max(
        completed,
        key=lambda item: ((item.finished_at - item.started_at).total_seconds(), item.event_id),
        default=None,
    )
    oldest_pending = min(pending, key=lambda item: (item.started_at, item.event_id), default=None)
    completed_retries = sum(item.attempts - 1 for item in completed)
    pending_retries = sum(item.attempts - 1 for item in pending)
    categories = dict(
        sorted(Counter(item.error_category or "unspecified" for item in failed).items())
    )
    result = {
        "completed_runs": len(completed),
        "succeeded_runs": len(succeeded),
        "failed_runs": len(failed),
        "success_pct": _percentage(len(succeeded), len(completed)),
        "running_runs": sum(item.status == "running" for item in pending),
        "blocked_runs": sum(item.status == "blocked" for item in pending),
        "retries": completed_retries + pending_retries,
        "completed_run_retries": completed_retries,
        "pending_run_retries": pending_retries,
        "failure_categories": categories,
        "slowest_completed_job_id": slowest.job_id if slowest else None,
        "slowest_completed_duration_seconds": (
            (slowest.finished_at - slowest.started_at).total_seconds() if slowest else None
        ),
        "oldest_pending_job_id": oldest_pending.job_id if oldest_pending else None,
        "oldest_pending_age_hours": (
            _hours(dataset.as_of, oldest_pending.started_at) if oldest_pending else None
        ),
        "stale_pending_runs": len(stale),
        "pending_age_target_hours": service.job_stale_after_hours,
    }
    if failed:
        _finding(
            findings,
            service.service_id,
            "warning",
            "failed_job_runs",
            "Some job runs completed with a final failure during the reporting window.",
            failed_runs=len(failed),
            completed_runs=len(completed),
            failure_categories=categories,
        )
    if result["blocked_runs"]:
        _finding(
            findings,
            service.service_id,
            "warning",
            "blocked_job_runs",
            "Some job runs are blocked at the report cutoff.",
            blocked_runs=result["blocked_runs"],
        )
    if stale:
        _finding(
            findings,
            service.service_id,
            "warning",
            "pending_jobs_old",
            "Some pending job runs exceed the configured pending-age target.",
            stale_pending_runs=len(stale),
            oldest_pending_age_hours=result["oldest_pending_age_hours"],
            age_target_hours=service.job_stale_after_hours,
            job_ids=sorted(item.job_id for item in stale),
        )
    if result["retries"]:
        _finding(
            findings,
            service.service_id,
            "info",
            "job_retries",
            "Recorded job attempts include retries; retries are separate from final failures.",
            retries=result["retries"],
            completed_runs=len(completed),
            pending_runs=len(pending),
            final_failed_runs=len(failed),
        )
    return result


def build_report(dataset: Dataset) -> dict[str, Any]:
    """Calculate an auditable report from validated data without I/O or cloud calls."""
    findings: list[dict[str, Any]] = []
    services = [
        {
            "service_id": service.service_id,
            "checks": _checks(dataset, service, findings),
            "resources": _resources(dataset, service, findings),
            "backups": _backups(dataset, service, findings),
            "jobs": _jobs(dataset, service, findings),
        }
        for service in sorted(dataset.services, key=lambda item: item.service_id)
    ]
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(
        key=lambda item: (severity_order[item["severity"]], item["service_id"], item["code"])
    )
    return {
        "schema_version": dataset.schema_version,
        "data_classification": dataset.data_classification,
        "window_start": _iso(dataset.window_start),
        "as_of": _iso(dataset.as_of),
        "duplicates_removed": dataset.duplicates_removed,
        "services": services,
        "findings": findings,
        "limitations": [
            "All input is synthetic; these findings do not describe an actual server.",
            "The reporting window is [window_start, as_of), in UTC; as_of is exclusive.",
            "Monitoring cadence slots start at window_start; a partial final slot is expected. "
            "Only the latest check per slot counts. Known coverage excludes missing and unknown "
            "slots. Sampled success uses only known up/down slots and is not continuous uptime.",
            "Freshness uses at most twice the configured check cadence for checks and resources. "
            "Latest observations use available history before as_of. Stale resource values remain "
            "visible as historical evidence and do not produce current threshold alerts.",
            "Resource warnings use demonstration thresholds: CPU, memory and disk used at "
            "85%/95%; free inodes at 10%/5%. Single samples do not establish sustained load. "
            "No storage exhaustion forecast or cause is inferred.",
            "Backup and restore history may predate window_start. A successful or checksum "
            "verified backup does not prove a restore will succeed. Restore records do not "
            "identify which backup was tested; no latest-backup restore claim is made.",
            "Completed job runs count by finished_at within the window. Pending runs include "
            "carry-in runs and are observed at as_of. Retries are attempts minus one for those "
            "included runs, not individual retry events timed within the window. Pending age "
            "measures elapsed time since start, not time since last progress.",
            "Missing measurements and empty outcome denominators remain null; no observation "
            "is not evidence of health. Configured targets are demonstration assumptions.",
        ],
    }
