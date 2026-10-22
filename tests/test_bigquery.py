"""Offline boundary tests; fake API rows are not evidence that BigQuery executed SQL."""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from gcp_ai_analytics import bigquery_pipeline as bq
from gcp_ai_analytics.contracts import Dataset
from gcp_ai_analytics.reporting import canonical_json

AS_OF = datetime(2026, 10, 22, tzinfo=UTC)
SETTINGS = bq.BigQuerySettings("synthetic-demo", "operations_insights")


def fixture():
    def event(name, **values):
        return {"event_id": name, "service_id": "server", **values}

    def ago(hours):
        return AS_OF - timedelta(hours=hours)

    return Dataset.model_validate(
        {
            "data_classification": "synthetic",
            "window_start": ago(4),
            "as_of": AS_OF,
            "services": [{"service_id": "server"}],
            "service_checks": [
                event(name, observed_at=ago(age), status=status)
                for name, age, status in [
                    ("first", 3.9, "up"),
                    ("replacement", 3.1, "down"),
                    ("unknown", 2, "unknown"),
                    ("latest", 1, "up"),
                ]
            ],
            "resource_samples": [
                event(
                    "resource",
                    observed_at=ago(1),
                    cpu_pct=85.555,
                    disk_used_bytes=90,
                    disk_total_bytes=100,
                )
            ],
            "backups": [
                event("success", completed_at=ago(50), outcome="success", verification="checksum"),
                event("failure", completed_at=ago(1), outcome="failed"),
            ],
            "restore_tests": [
                event("passed", completed_at=ago(31 * 24), outcome="passed"),
                event("failed", completed_at=ago(2), outcome="failed"),
            ],
            "job_runs": [
                event(
                    name,
                    job_id=name,
                    job_type="demo",
                    started_at=ago(start),
                    finished_at=ago(end) if end else None,
                    status=status,
                    attempts=attempts,
                    error_category="io" if status == "failed" else None,
                )
                for name, start, end, status, attempts in [
                    ("recovered", 10, 3, "succeeded", 3),
                    ("failed_job", 4, 1, "failed", 2),
                    ("blocked", 8, None, "blocked", 2),
                    ("running", 1, None, "running", 1),
                ]
            ],
        }
    )


def expected_rows():
    """Hand-calculated SQL-shaped response, deliberately independent of build_report."""

    def ago(hours):
        return AS_OF - timedelta(hours=hours)

    latest = {
        "latest_observed_at": ago(1),
        "latest_age_hours": 1.0,
        "is_fresh": True,
        "freshness_limit_seconds": 7200,
    }
    rows = {
        "checks": {
            "raw_observations": 4,
            "expected_slots": 4,
            "observed_slots": 3,
            "known_status_slots": 2,
            "up_slots": 1,
            "down_slots": 1,
            "unknown_slots": 1,
            "missing_slots": 1,
            "sampled_success_pct": 50.0,
            "monitoring_coverage_pct": 50.0,
            "latest_status": "up",
            "latest_latency_ms": None,
        },
        "freshness": {
            f"{name}_{key}": value
            for name in ("checks", "resources")
            for key, value in latest.items()
        },
        "resources": {
            **latest,
            "cpu_pct": 85.555,
            "memory_pct": None,
            "disk_used_bytes": 90,
            "disk_total_bytes": 100,
            "disk_used_pct": 90.0,
            "disk_free_inodes_pct": None,
            "pool_health": None,
            "disk_health": None,
            "measured_fields": ["cpu_pct", "disk_used_bytes", "disk_total_bytes"],
            "missing_fields": ["memory_pct", "disk_free_inodes_pct", "pool_health", "disk_health"],
        },
        "backups": {
            "max_age_hours": 48.0,
            "latest_attempt_at": ago(1),
            "latest_attempt_outcome": "failed",
            "last_success_at": ago(50),
            "last_success_age_hours": 50.0,
            "last_success_checksum_verified": True,
            "is_overdue": True,
        },
        "restore_tests": {
            "restore_max_age_days": 30.0,
            "latest_restore_at": ago(2),
            "latest_restore_outcome": "failed",
            "last_passed_restore_at": ago(31 * 24),
            "last_passed_restore_age_days": 31.0,
            "restore_is_overdue": True,
        },
        "jobs": {
            "completed_runs": 2,
            "succeeded_runs": 1,
            "failed_runs": 1,
            "success_pct": 50.0,
            "running_runs": 1,
            "blocked_runs": 1,
            "retries": 4,
            "completed_run_retries": 3,
            "pending_run_retries": 1,
            "failure_categories": [{"category": "io", "count": 1}],
            "slowest_completed_job_id": "recovered",
            "slowest_completed_duration_seconds": 25200.0,
            "oldest_pending_job_id": "blocked",
            "oldest_pending_age_hours": 8.0,
            "stale_pending_runs": 1,
            "pending_age_target_hours": 4.0,
        },
    }
    return {name: [{"service_id": "server", **row}] for name, row in rows.items()}


class FakeJob:
    def __init__(self, *, rows=None, output_rows=None, estimate=10, error=None):
        self.rows = rows
        self.output_rows = output_rows
        self.total_bytes_processed = estimate
        self.total_bytes_billed = estimate
        self.cache_hit = False
        self.error = error

    def result(self, **kwargs):
        assert kwargs["retry"] is None
        assert kwargs["timeout"] == bq.JOB_TIMEOUT_SECONDS
        if self.error:
            raise self.error
        return self.rows if self.rows is not None else self


class FakeClient:
    def __init__(self, *, rows=None, estimate=10, load_error=None, query_error=None):
        self.rows = rows if rows is not None else expected_rows()
        self.estimate = estimate
        self.load_error = load_error
        self.query_error = query_error
        self.calls = []
        self.tables = []

    def create_dataset(self, dataset, **kwargs):
        self.calls.append(("dataset", kwargs))
        return dataset

    def create_table(self, table, **kwargs):
        self.tables.append(table)
        self.calls.append(("table", kwargs))
        return table

    def load_table_from_file(self, stream, destination, **kwargs):
        self.calls.append(("load", kwargs))
        assert kwargs["num_retries"] == 0
        raw = stream.read()
        assert len(raw) == kwargs["size"]
        return FakeJob(output_rows=len(raw.splitlines()), error=self.load_error)

    def query(self, sql, **kwargs):
        config = kwargs["job_config"]
        self.calls.append(("dry_run" if config.dry_run else "query", kwargs))
        assert kwargs["retry"] is kwargs["job_retry"] is None
        name = next(name for name in bq.QUERY_NAMES if kwargs["job_id"].endswith("_" + name))
        return FakeJob(
            rows=self.rows[name],
            estimate=self.estimate,
            error=None if config.dry_run else self.query_error,
        )


def runner(tmp_path, client=None):
    data = fixture()
    bundle = bq.export_dataset(data, tmp_path / "export")
    return bq.BigQueryRunner(
        SETTINGS,
        data,
        bundle,
        execute=True,
        client=client or FakeClient(),
        record_dir=tmp_path / "private",
    )


def test_export_schemas_hashes_classification_and_reproducibility(tmp_path):
    data = fixture()
    bundle = bq.export_dataset(data, tmp_path)
    assert bq.export_dataset(data, tmp_path).manifest == bundle.manifest
    assert set(bundle.paths) == set(bq.TABLE_FIELDS)
    assert (
        bundle.source_sha256
        == hashlib.sha256(canonical_json(data.model_dump(mode="json")).encode()).hexdigest()
    )
    total_bytes = 0
    for name, path in bundle.paths.items():
        raw = path.read_bytes()
        rows = [json.loads(row) for row in raw.splitlines()]
        metadata = bundle.manifest["tables"][name]
        assert metadata["sha256"] == hashlib.sha256(raw).hexdigest()
        assert metadata["row_count"] == len(rows)
        assert metadata["bytes"] == len(raw)
        assert set(rows[0]) == {field["name"] for field in metadata["schema"]}
        total_bytes += len(raw)
    assert total_bytes == bundle.manifest["total_jsonl_bytes"]
    assert bundle.manifest["data_classification"] == "synthetic"
    assert len(list(tmp_path.glob("*.jsonl"))) == 5


def test_export_rejects_tampering_and_unsafe_model_construct(tmp_path):
    data = fixture()
    bundle = bq.export_dataset(data, tmp_path)
    bundle.paths["jobs"].write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        bq.verify_export(data, bundle)
    with pytest.raises(ValueError, match="differs"):
        bq.export_dataset(data, tmp_path)
    with pytest.raises(ValueError):
        bq.export_dataset(data.model_copy(update={"data_classification": "private"}), tmp_path)


def test_export_combined_limit_checked_before_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(bq, "MAX_EXPORT_BYTES", 100)
    with pytest.raises(ValueError, match="5 MiB"):
        bq.export_dataset(fixture(), tmp_path / "too_large")
    assert not (tmp_path / "too_large").exists()


def test_export_rejects_measurements_outside_bigquery_integer_range(tmp_path):
    data = fixture().model_dump(mode="json")
    data["resource_samples"][0]["disk_total_bytes"] = 2**63
    with pytest.raises(ValueError, match="INT64"):
        bq.export_dataset(Dataset.model_validate(data), tmp_path)


def test_empty_service_retains_unknown_health_and_explicit_missing_coverage(tmp_path):
    data = Dataset.model_validate(
        {
            "data_classification": "synthetic",
            "window_start": AS_OF - timedelta(hours=4),
            "as_of": AS_OF,
            "services": [{"service_id": "server"}],
        }
    )
    rows = expected_rows()
    checks = rows["checks"][0]
    for name in (
        "raw_observations",
        "observed_slots",
        "known_status_slots",
        "up_slots",
        "down_slots",
        "unknown_slots",
        "monitoring_coverage_pct",
    ):
        checks[name] = 0
    checks.update(missing_slots=4, sampled_success_pct=None, latest_status=None)
    for name in rows["freshness"][0]:
        if name != "service_id" and not name.endswith("freshness_limit_seconds"):
            rows["freshness"][0][name] = None
    resources = rows["resources"][0]
    resources["measured_fields"] = []
    resources["missing_fields"] = [
        "cpu_pct",
        "memory_pct",
        "disk_used_bytes",
        "disk_total_bytes",
        "disk_free_inodes_pct",
        "pool_health",
        "disk_health",
    ]
    for name in resources:
        if name not in {
            "service_id",
            "measured_fields",
            "missing_fields",
            "freshness_limit_seconds",
        }:
            resources[name] = None
    for query, policy in (("backups", "max_age_hours"), ("restore_tests", "restore_max_age_days")):
        for name in rows[query][0]:
            if name not in {"service_id", policy}:
                rows[query][0][name] = None
    jobs = rows["jobs"][0]
    for name in jobs:
        if name.endswith("runs") or name.endswith("retries"):
            jobs[name] = 0
        elif name in {"failure_categories"}:
            jobs[name] = []
        elif name not in {"service_id", "pending_age_target_hours"}:
            jobs[name] = None
    bundle = bq.export_dataset(data, tmp_path)
    assert all(path.stat().st_size == 0 for path in bundle.paths.values())
    assert bq.compare_query_results(data, rows)["matches"] is True


@pytest.mark.parametrize(
    "project,dataset,location",
    [
        ("bad`id", "safe", "US"),
        ("valid-project", "a.b", "US"),
        ("valid-project", "safe`; DELETE", "US"),
        ("valid-project", "safe", "US'; DROP"),
    ],
)
def test_identifiers_cannot_inject_sql(project, dataset, location):
    with pytest.raises(ValueError):
        bq.BigQuerySettings(project, dataset, location)


def test_offline_plan_does_not_construct_client_and_includes_empty_service(tmp_path, monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("Offline planning constructed a cloud client")

    monkeypatch.setattr(bq.bigquery, "Client", forbidden)
    data = fixture().model_dump(mode="json")
    data["services"].append({"service_id": "empty", "backup_max_age_hours": None})
    data = Dataset.model_validate(data)
    bundle = bq.export_dataset(data, tmp_path)
    plan = bq.plan_bigquery(data, SETTINGS, bundle)
    assert plan["limits"]["max_load_submissions"] == 5
    assert plan["limits"]["max_query_submissions"] == 6
    policy = bq.query_parameters(data)[2].to_api_repr()
    assert len(policy["parameterValue"]["arrayValues"]) == 2
    values = policy["parameterValue"]["arrayValues"][0]["structValues"]
    assert values["service_id"]["value"] == "empty"
    assert values["backup_max_age_hours"]["value"] is None
    for name in bq.QUERY_NAMES:
        sql = bq.query_sql(name, SETTINGS, bundle.source_sha256)
        assert "UNNEST(@services)" in sql
        assert "@as_of" in sql and "{{" not in sql
        assert len(plan["queries"][name]["sql_sha256"]) == 64
    with pytest.raises(ValueError, match="execute=True"):
        bq.BigQueryRunner(SETTINGS, data, bundle)


def test_compare_independent_expected_metrics_and_detect_wrong_semantics():
    rows = expected_rows()
    comparison = bq.compare_query_results(fixture(), rows)
    assert comparison["matches"] is True
    assert comparison["metrics_compared"] > 60
    rows["checks"][0]["monitoring_coverage_pct"] = 75
    rows["jobs"][0]["retries"] = 3
    rows["restore_tests"][0]["restore_is_overdue"] = False
    comparison = bq.compare_query_results(fixture(), rows)
    assert {item["metric"] for item in comparison["mismatches"]} == {
        "monitoring_coverage_pct",
        "retries",
        "restore_is_overdue",
    }


def test_comparison_rejects_missing_rows_and_missing_null_columns():
    rows = expected_rows()
    rows["checks"][0].pop("latest_latency_ms")
    rows["resources"] = []
    result = bq.compare_query_results(fixture(), rows)
    assert {item["metric"] for item in result["mismatches"]} == {
        "latest_latency_ms",
        "service_membership",
    }


def test_comparison_preserves_configured_policy_precision():
    data = fixture().model_dump(mode="json")
    data["services"][0].update(backup_max_age_hours=48.123456, restore_max_age_days=30.123456)
    rows = expected_rows()
    rows["backups"][0]["max_age_hours"] = 48.123456
    rows["restore_tests"][0]["restore_max_age_days"] = 30.123456
    assert bq.compare_query_results(Dataset.model_validate(data), rows)["matches"] is True


def test_successful_batch_uses_limits_and_never_overwrites(tmp_path):
    client = FakeClient()
    batch = runner(tmp_path, client)
    output = batch.run()
    assert output["comparison"]["matches"] is True
    assert batch.counts == {"load": 5, "dry_run": 6, "query": 6}
    assert [kind for kind, _ in client.calls][-12:] == ["dry_run", "query"] * 6
    for kind, kwargs in client.calls:
        if kind == "load":
            config = kwargs["job_config"]
            assert config.write_disposition == "WRITE_EMPTY"
            assert config.create_disposition == "CREATE_NEVER"
            assert config.autodetect is False and config.ignore_unknown_values is False
        elif kind in {"query", "dry_run"}:
            config = kwargs["job_config"]
            assert config.maximum_bytes_billed == 100_000_000
            assert config.use_query_cache is False
        elif kind == "table":
            assert kwargs["exists_ok"] is False
    for table in client.tables:
        assert table.project == SETTINGS.project_id and table.dataset_id == SETTINGS.dataset_id
        assert timedelta(days=6.9) < table.expires - datetime.now(UTC) < timedelta(days=7.1)
    with pytest.raises(ValueError, match="already started"):
        batch.run()
    with pytest.raises(FileExistsError):
        runner(tmp_path)


@pytest.mark.parametrize("failure_kind", ["load", "query"])
def test_uncertain_timeout_consumes_budget_and_preserves_job_id(tmp_path, failure_kind):
    client = FakeClient(**{f"{failure_kind}_error": TimeoutError("private error details")})
    batch = runner(tmp_path, client)
    with pytest.raises(TimeoutError):
        batch.run()
    assert batch.counts[failure_kind] == 1
    ledger = json.loads(batch.ledger_path.read_text())
    last = ledger["records"][-1]
    assert last["kind"] == failure_kind and last["state"] == "submission_outcome_unknown"
    assert last["job_id"].startswith("ops_")
    assert last["error_type"] == "TimeoutError"
    assert "private error details" not in batch.ledger_path.read_text()
    assert len([kind for kind, _ in client.calls if kind == failure_kind]) == 1
    with pytest.raises(ValueError, match="already started"):
        batch.run()


@pytest.mark.parametrize("estimate", [None, bq.MAX_BYTES_BILLED + 1])
def test_dry_run_blocks_execution_if_estimate_unknown_or_over_budget(tmp_path, estimate):
    client = FakeClient(estimate=estimate)
    batch = runner(tmp_path, client)
    with pytest.raises(ValueError, match="estimate|limit"):
        batch.run()
    assert batch.counts == {"load": 5, "dry_run": 1, "query": 0}


def test_existing_dataset_scope_mismatch_stops_before_tables_or_loads(tmp_path):
    client = FakeClient()
    client.create_dataset = lambda *args, **kwargs: SimpleNamespace(
        project=SETTINGS.project_id, dataset_id=SETTINGS.dataset_id, location="EU", labels={}
    )
    batch = runner(tmp_path, client)
    with pytest.raises(ValueError, match="scope/location"):
        batch.run()
    assert not client.tables
    assert batch.counts["load"] == 0


def test_bad_cloud_metrics_are_saved_but_cannot_be_treated_as_verified(tmp_path):
    rows = copy.deepcopy(expected_rows())
    rows["jobs"][0]["failed_runs"] = 0
    batch = runner(tmp_path, FakeClient(rows=rows))
    with pytest.raises(ValueError, match="differ from the local reference"):
        batch.run()
    saved = json.loads(next(batch.record_dir.glob("results-*.json")).read_text())
    assert saved["comparison"]["matches"] is False


def test_explicit_submission_budget_includes_failures(tmp_path):
    batch = runner(tmp_path)

    def failure(_):
        raise TimeoutError()

    for _ in range(5):
        with pytest.raises(TimeoutError):
            batch._attempt("load", "test", failure)
    with pytest.raises(ValueError, match="budget exhausted"):
        batch._attempt("load", "test", failure)
    assert batch.counts["load"] == 5


def test_verified_report_uses_returned_aggregates_and_removes_local_only_facts(tmp_path):
    rows = expected_rows()
    # SQL floating arithmetic may differ below comparison tolerance. Preserve its actual value.
    returned_cpu = 85.55500000001
    rows["resources"][0]["cpu_pct"] = returned_cpu
    batch = runner(tmp_path, FakeClient(rows=rows))
    result = batch.run()
    report = bq.build_verified_report(fixture(), result)
    cpu_finding = next(item for item in report["findings"] if item["code"] == "cpu_high")
    assert cpu_finding["evidence"]["cpu_pct"] == returned_cpu
    assert report["services"][0]["resources"]["cpu_pct"] == returned_cpu
    assert "event_id" not in cpu_finding["evidence"]
    assert all(
        "event_id" not in item["evidence"] and "job_ids" not in item["evidence"]
        for item in report["findings"]
    )
    overdue = next(item for item in report["findings"] if item["code"] == "backup_overdue")
    assert overdue["evidence"]["last_success_age_hours"] == 50.0
    assert report["provenance"]["execution"] == "bigquery_aggregates_verified"
    assert "Python rules" in report["provenance"]["finding_selection"]


def test_verified_report_rechecks_metrics_and_source_instead_of_trusting_pass_flag(tmp_path):
    result = runner(tmp_path).run()
    changed_hash = copy.deepcopy(result)
    changed_hash["source_dataset_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="provenance"):
        bq.build_verified_report(fixture(), changed_hash)
    result["query_results"]["jobs"][0]["failed_runs"] = 0
    assert result["comparison"]["matches"] is True
    with pytest.raises(ValueError, match="matching BigQuery"):
        bq.build_verified_report(fixture(), result)
