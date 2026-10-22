"""Hand-calculated fixtures for denominators, time boundaries, and evidence."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from gcp_ai_analytics.analytics import build_report
from gcp_ai_analytics.contracts import Dataset

AS_OF = datetime(2026, 10, 22, tzinfo=UTC)
START = AS_OF - timedelta(hours=4)


def dataset(**overrides) -> Dataset:
    data = {
        "data_classification": "synthetic",
        "window_start": START,
        "as_of": AS_OF,
        "services": [{"service_id": "server"}],
    }
    data.update(overrides)
    return Dataset.model_validate(data)


def check(event_id, hours_ago, status="up"):
    return {
        "event_id": event_id,
        "service_id": "server",
        "observed_at": AS_OF - timedelta(hours=hours_ago),
        "status": status,
    }


def resource(hours_ago=0.5, **values):
    return {
        "event_id": "resource",
        "service_id": "server",
        "observed_at": AS_OF - timedelta(hours=hours_ago),
        **values,
    }


def backup(event_id="backup", hours_ago=1, outcome="success", verification="none"):
    return {
        "event_id": event_id,
        "service_id": "server",
        "completed_at": AS_OF - timedelta(hours=hours_ago),
        "outcome": outcome,
        "verification": verification,
    }


def restore(event_id="restore", days_ago=1, outcome="passed"):
    return {
        "event_id": event_id,
        "service_id": "server",
        "completed_at": AS_OF - timedelta(days=days_ago),
        "outcome": outcome,
    }


def job(event_id, hours_ago=2, finish_hours_ago=1, status="succeeded", attempts=1, **extra):
    return {
        "event_id": event_id,
        "service_id": "server",
        "job_id": event_id,
        "job_type": "document_import",
        "started_at": AS_OF - timedelta(hours=hours_ago),
        "finished_at": (
            AS_OF - timedelta(hours=finish_hours_ago) if finish_hours_ago is not None else None
        ),
        "status": status,
        "attempts": attempts,
        **extra,
    }


def service(report):
    return report["services"][0]


def codes(report):
    return {item["code"] for item in report["findings"]}


def test_gaps_and_unknown_do_not_count_as_healthy():
    report = build_report(
        dataset(
            service_checks=[
                check("up", 4),
                check("down", 3, "down"),
                check("unknown", 1, "unknown"),
            ]
        )
    )
    metrics = service(report)["checks"]
    assert metrics["expected_slots"] == 4
    assert metrics["observed_slots"] == 3
    assert metrics["known_status_slots"] == 2
    assert metrics["missing_slots"] == 1
    assert metrics["unknown_slots"] == 1
    assert metrics["up_slots"] == metrics["down_slots"] == 1
    assert metrics["sampled_success_pct"] == 50
    assert metrics["monitoring_coverage_pct"] == 50
    assert "latest_check_unknown" in codes(report)


def test_clustered_checks_use_latest_per_slot_without_inflating_coverage():
    report = build_report(
        dataset(
            service_checks=[
                check("first", 4),
                check("second", 3.8),
                check("third", 3.2, "down"),
                check("fourth", 1, "up"),
            ]
        )
    )
    metrics = service(report)["checks"]
    assert metrics["raw_observations"] == 4
    assert metrics["observed_slots"] == metrics["known_status_slots"] == 2
    assert metrics["monitoring_coverage_pct"] == 50
    assert metrics["sampled_success_pct"] == 50
    assert metrics["down_slots"] == 1


def test_unknown_latest_check_replaces_earlier_known_check_in_same_slot():
    report = build_report(
        dataset(
            service_checks=[
                check("known", 1),
                check("unknown", 0.5, "unknown"),
            ]
        )
    )
    metrics = service(report)["checks"]
    assert metrics["known_status_slots"] == 0
    assert metrics["sampled_success_pct"] is None
    assert metrics["monitoring_coverage_pct"] == 0


def test_partial_final_monitoring_slot_is_expected():
    report = build_report(dataset(window_start=AS_OF - timedelta(hours=4.5)))
    assert service(report)["checks"]["expected_slots"] == 5


def test_empty_inputs_do_not_claim_perfect_health():
    report = build_report(dataset())
    metrics = service(report)
    assert metrics["checks"]["sampled_success_pct"] is None
    assert metrics["checks"]["monitoring_coverage_pct"] == 0
    assert metrics["resources"]["is_fresh"] is None
    assert metrics["jobs"]["success_pct"] is None
    assert metrics["jobs"]["slowest_completed_duration_seconds"] is None
    assert metrics["backups"]["last_success_checksum_verified"] is None
    assert {"checks_missing", "resources_missing", "backup_success_missing"} <= codes(report)


@pytest.mark.parametrize(
    "collection,row",
    [
        ("service_checks", check("boundary", 0)),
        ("resource_samples", resource(0)),
        ("backups", backup(hours_ago=0)),
        ("restore_tests", restore(days_ago=0)),
        ("job_runs", job("boundary", finish_hours_ago=0)),
    ],
)
def test_events_at_exclusive_end_boundary_are_rejected(collection, row):
    with pytest.raises(ValidationError, match="exclusive as_of"):
        dataset(**{collection: [row]})


def test_checks_before_window_are_not_in_window_denominator():
    report = build_report(dataset(service_checks=[check("old", 5, "down")]))
    metrics = service(report)["checks"]
    assert metrics["raw_observations"] == metrics["observed_slots"] == 0
    assert metrics["latest_status"] == "down"
    assert metrics["is_fresh"] is False
    assert "checks_stale" in codes(report)
    assert "latest_check_down" not in codes(report)


def test_latest_fresh_down_observation_is_critical():
    report = build_report(dataset(service_checks=[check("recent_down", 1, "down")]))
    finding = next(item for item in report["findings"] if item["code"] == "latest_check_down")
    assert finding["severity"] == "critical"
    assert finding["evidence"]["event_id"] == "recent_down"
    assert finding["evidence"]["age_hours"] == 1


def test_stale_high_resource_values_do_not_create_current_resource_alerts():
    report = build_report(
        dataset(
            resource_samples=[
                resource(
                    3,
                    cpu_pct=100,
                    memory_pct=99,
                    disk_used_bytes=990,
                    disk_total_bytes=1000,
                    disk_free_inodes_pct=1,
                    pool_health="faulted",
                    disk_health="failed",
                )
            ]
        )
    )
    metrics = service(report)["resources"]
    assert metrics["cpu_pct"] == 100
    assert metrics["disk_used_pct"] == 99
    assert metrics["latest_age_hours"] == 3
    assert metrics["is_fresh"] is False
    assert "resources_stale" in codes(report)
    assert not (
        {
            "cpu_high",
            "memory_high",
            "disk_capacity_high",
            "free_inodes_low",
            "pool_faulted",
            "disk_health_failed",
        }
        & codes(report)
    )


def test_fresh_empty_resource_sample_reports_absent_measurements():
    report = build_report(dataset(resource_samples=[resource()]))
    metrics = service(report)["resources"]
    assert metrics["is_fresh"] is True
    assert metrics["measured_fields"] == []
    assert metrics["missing_fields"] == [
        "cpu_pct",
        "memory_pct",
        "disk_used_bytes",
        "disk_total_bytes",
        "disk_free_inodes_pct",
        "pool_health",
        "disk_health",
    ]
    finding = next(item for item in report["findings"] if item["code"] == "resources_empty")
    assert finding["severity"] == "warning"
    assert finding["evidence"]["event_id"] == "resource"
    assert finding["evidence"]["observed_at"] == (AS_OF - timedelta(hours=0.5)).isoformat()
    assert finding["evidence"]["missing_fields"] == metrics["missing_fields"]


def test_resource_thresholds_and_observation_evidence():
    report = build_report(
        dataset(
            resource_samples=[
                resource(
                    cpu_pct=85,
                    memory_pct=95,
                    disk_used_bytes=950,
                    disk_total_bytes=1000,
                    disk_free_inodes_pct=5,
                    pool_health="degraded",
                    disk_health="failed",
                )
            ]
        )
    )
    findings = {item["code"]: item for item in report["findings"]}
    assert findings["cpu_high"]["severity"] == "warning"
    for code in [
        "memory_high",
        "disk_capacity_high",
        "free_inodes_low",
        "pool_degraded",
        "disk_health_failed",
    ]:
        assert findings[code]["severity"] == "critical"
        assert findings[code]["evidence"]["event_id"] == "resource"
        assert findings[code]["evidence"]["age_hours"] == 0.5


def test_disk_rounding_does_not_trigger_threshold_early():
    report = build_report(
        dataset(
            resource_samples=[
                resource(
                    disk_used_bytes=84999,
                    disk_total_bytes=100000,
                )
            ]
        )
    )
    assert service(report)["resources"]["disk_used_pct"] == 85
    assert "disk_capacity_high" not in codes(report)


def test_backup_checksum_is_not_a_restore_test():
    report = build_report(dataset(backups=[backup(verification="checksum")]))
    metrics = service(report)["backups"]
    assert metrics["last_success_checksum_verified"] is True
    assert metrics["last_passed_restore_at"] is None
    assert metrics["is_overdue"] is False
    assert "restore_success_missing" in codes(report)
    assert "backup_success_missing" not in codes(report)


def test_historical_backup_and_restore_success_do_not_hide_latest_failure():
    report = build_report(
        dataset(
            backups=[backup("good_backup", 50), backup("bad_backup", 1, "failed")],
            restore_tests=[restore("good_restore", 31), restore("bad_restore", 1, "failed")],
        )
    )
    metrics = service(report)["backups"]
    assert metrics["last_success_age_hours"] == 50
    assert metrics["is_overdue"] is True
    assert metrics["latest_attempt_outcome"] == "failed"
    assert metrics["last_passed_restore_age_days"] == 31
    assert metrics["restore_is_overdue"] is True
    assert metrics["latest_restore_outcome"] == "failed"
    assert {
        "backup_overdue",
        "latest_backup_failed",
        "restore_test_overdue",
        "latest_restore_failed",
    } <= codes(report)


def test_backup_target_boundary_uses_unrounded_age():
    at_target = build_report(dataset(backups=[backup(hours_ago=48)]))
    assert service(at_target)["backups"]["is_overdue"] is False
    just_over = backup(hours_ago=48)
    just_over["completed_at"] -= timedelta(microseconds=1)
    over_target = build_report(dataset(backups=[just_over]))
    assert service(over_target)["backups"]["is_overdue"] is True


def test_disabled_backup_and_restore_targets_do_not_assert_missing_requirements():
    report = build_report(
        dataset(
            services=[
                {
                    "service_id": "server",
                    "backup_max_age_hours": None,
                    "restore_max_age_days": None,
                }
            ]
        )
    )
    assert "backup_success_missing" not in codes(report)
    assert "restore_success_missing" not in codes(report)
    assert service(report)["backups"]["is_overdue"] is None


def test_eventually_successful_retries_are_not_final_failures():
    report = build_report(
        dataset(
            job_runs=[
                job("recovered", hours_ago=3, finish_hours_ago=1, attempts=3),
                job(
                    "failed",
                    hours_ago=2,
                    finish_hours_ago=1.5,
                    status="failed",
                    attempts=2,
                    error_category="timeout",
                ),
                job("blocked", hours_ago=10, finish_hours_ago=None, status="blocked", attempts=2),
                job("running", hours_ago=1, finish_hours_ago=None, status="running"),
            ]
        )
    )
    metrics = service(report)["jobs"]
    assert metrics["completed_runs"] == 2
    assert metrics["succeeded_runs"] == metrics["failed_runs"] == 1
    assert metrics["success_pct"] == 50
    assert metrics["blocked_runs"] == metrics["running_runs"] == 1
    assert metrics["retries"] == 4
    assert metrics["completed_run_retries"] == 3
    assert metrics["pending_run_retries"] == 1
    assert metrics["slowest_completed_duration_seconds"] == 7200
    assert metrics["slowest_completed_job_id"] == "recovered"
    assert metrics["oldest_pending_age_hours"] == 10
    assert metrics["stale_pending_runs"] == 1
    assert metrics["failure_categories"] == {"timeout": 1}


def test_job_window_uses_finish_time_and_pending_carry_in():
    report = build_report(
        dataset(
            job_runs=[
                job("old", hours_ago=10, finish_hours_ago=5, status="failed", attempts=5),
                job("carry_in", hours_ago=10, finish_hours_ago=4, attempts=2),
                job("pending_carry_in", hours_ago=20, finish_hours_ago=None, status="running"),
            ]
        )
    )
    metrics = service(report)["jobs"]
    assert metrics["completed_runs"] == metrics["succeeded_runs"] == 1
    assert metrics["failed_runs"] == 0
    assert metrics["success_pct"] == 100
    assert metrics["running_runs"] == 1
    assert metrics["retries"] == 1
    assert metrics["oldest_pending_age_hours"] == 20
    assert metrics["slowest_completed_duration_seconds"] == 6 * 3600


def test_pending_age_target_boundary_uses_unrounded_age():
    at_target = job("at_target", hours_ago=4, finish_hours_ago=None, status="running")
    just_over = job("just_over", hours_ago=4, finish_hours_ago=None, status="running")
    just_over["started_at"] -= timedelta(microseconds=1)
    report = build_report(dataset(job_runs=[at_target, just_over]))
    metrics = service(report)["jobs"]
    assert metrics["running_runs"] == 2
    assert metrics["stale_pending_runs"] == 1
    finding = next(item for item in report["findings"] if item["code"] == "pending_jobs_old")
    assert finding["evidence"]["job_ids"] == ["just_over"]


def test_exact_duplicate_events_are_counted_once():
    row = job("deduplicated", attempts=3)
    report = build_report(dataset(job_runs=[row, dict(row)]))
    assert report["duplicates_removed"] == 1
    assert service(report)["jobs"]["completed_runs"] == 1
    assert service(report)["jobs"]["retries"] == 2


def test_report_is_deterministic_for_reordered_input():
    first = dataset(
        services=[{"service_id": "z_service"}, {"service_id": "server"}],
        service_checks=[check("early", 3), check("late", 1, "down")],
        job_runs=[job("first"), job("second", status="failed")],
    )
    second = first.model_dump()
    second["services"].reverse()
    second["service_checks"].reverse()
    second["job_runs"].reverse()
    assert build_report(first) == build_report(Dataset.model_validate(second))
