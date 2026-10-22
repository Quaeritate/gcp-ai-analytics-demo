"""Bounded BigQuery export and execution; planning never constructs a cloud client."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Any

from google.cloud import bigquery

from .analytics import build_report
from .contracts import Dataset
from .reporting import canonical_json

MAX_EXPORT_BYTES = 5 * 1024 * 1024
MAX_BYTES_BILLED = 100_000_000
TABLE_EXPIRY_DAYS = 7
REQUEST_TIMEOUT_SECONDS = 30
JOB_TIMEOUT_SECONDS = 120
TABLE_FIELDS = {
    "checks": "service_checks",
    "resources": "resource_samples",
    "backups": "backups",
    "restore_tests": "restore_tests",
    "jobs": "job_runs",
}
QUERY_NAMES = ("checks", "freshness", "resources", "backups", "restore_tests", "jobs")
_BASE = [("event_id", "STRING", "REQUIRED"), ("service_id", "STRING", "REQUIRED")]
SCHEMAS = {
    "checks": _BASE
    + [
        ("observed_at", "TIMESTAMP", "REQUIRED"),
        ("status", "STRING", "REQUIRED"),
        ("latency_ms", "FLOAT64", "NULLABLE"),
    ],
    "resources": _BASE
    + [("observed_at", "TIMESTAMP", "REQUIRED")]
    + [(name, "FLOAT64", "NULLABLE") for name in ("cpu_pct", "memory_pct")]
    + [(name, "INT64", "NULLABLE") for name in ("disk_used_bytes", "disk_total_bytes")]
    + [
        ("disk_free_inodes_pct", "FLOAT64", "NULLABLE"),
        ("pool_health", "STRING", "NULLABLE"),
        ("disk_health", "STRING", "NULLABLE"),
    ],
    "backups": _BASE
    + [
        ("completed_at", "TIMESTAMP", "REQUIRED"),
        ("outcome", "STRING", "REQUIRED"),
        ("verification", "STRING", "REQUIRED"),
    ],
    "restore_tests": _BASE
    + [("completed_at", "TIMESTAMP", "REQUIRED"), ("outcome", "STRING", "REQUIRED")],
    "jobs": _BASE
    + [
        ("job_id", "STRING", "REQUIRED"),
        ("job_type", "STRING", "REQUIRED"),
        ("started_at", "TIMESTAMP", "REQUIRED"),
        ("finished_at", "TIMESTAMP", "NULLABLE"),
        ("status", "STRING", "REQUIRED"),
        ("attempts", "INT64", "REQUIRED"),
        ("error_category", "STRING", "NULLABLE"),
    ],
}


@dataclass(frozen=True)
class BigQuerySettings:
    project_id: str
    dataset_id: str
    location: str = "US"

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", self.project_id):
            raise ValueError("Project ID must be a 6–30 character Google Cloud project ID")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,1023}", self.dataset_id):
            raise ValueError("Dataset ID must contain only letters, digits and underscores")
        if not re.fullmatch(r"(?:US|EU|[a-z]+(?:-[a-z0-9]+)+)", self.location):
            raise ValueError("Location must be an explicit BigQuery region or US/EU")

    @property
    def dataset_ref(self) -> str:
        return f"{self.project_id}.{self.dataset_id}"


@dataclass(frozen=True)
class ExportBundle:
    directory: Path
    manifest: dict[str, Any]

    @property
    def source_sha256(self) -> str:
        return self.manifest["source_dataset_sha256"]

    @property
    def paths(self) -> dict[str, Path]:
        return {name: self.directory / f"{name}.jsonl" for name in TABLE_FIELDS}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validated(dataset: Dataset) -> Dataset:
    # Revalidation also protects callers that used model_construct/model_copy.
    validated = Dataset.model_validate(dataset.model_dump(mode="json"))
    for name, field in TABLE_FIELDS.items():
        integer_fields = [n for n, kind, _ in SCHEMAS[name] if kind == "INT64"]
        for event in getattr(validated, field):
            if any(
                getattr(event, key) is not None and getattr(event, key) > 2**63 - 1
                for key in integer_fields
            ):
                raise ValueError("Measurement exceeds BigQuery INT64 range")
    if any(service.check_interval_seconds > (2**63 - 1) // 2 for service in validated.services):
        raise ValueError("Check interval exceeds the BigQuery freshness calculation range")
    if sum(job.attempts - 1 for job in validated.job_runs) > 2**63 - 1:
        raise ValueError("Combined retries exceed BigQuery INT64 range")
    return validated


def _export_content(dataset: Dataset) -> tuple[dict[str, bytes], dict[str, Any]]:
    dataset = _validated(dataset)
    content: dict[str, bytes] = {}
    tables = {}
    for name, field in TABLE_FIELDS.items():
        rows = sorted(getattr(dataset, field), key=lambda row: row.event_id)
        raw = "".join(
            json.dumps(
                row.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            + "\n"
            for row in rows
        ).encode()
        content[f"{name}.jsonl"] = raw
        tables[name] = {
            "row_count": len(rows),
            "bytes": len(raw),
            "sha256": _sha(raw),
            "schema": [{"name": n, "type": t, "mode": m} for n, t, m in SCHEMAS[name]],
        }
    manifest = {
        "export_version": 1,
        "data_classification": "synthetic",
        "source_dataset_sha256": _sha(canonical_json(dataset.model_dump(mode="json")).encode()),
        "window_start": dataset.window_start.isoformat(),
        "as_of": dataset.as_of.isoformat(),
        "services": [
            s.model_dump(mode="json")
            for s in sorted(dataset.services, key=lambda service: service.service_id)
        ],
        "total_jsonl_bytes": sum(len(value) for value in content.values()),
        "tables": tables,
    }
    content["manifest.json"] = canonical_json(manifest).encode()
    if sum(len(value) for value in content.values()) > MAX_EXPORT_BYTES:
        raise ValueError("Normalized export and manifest exceed the combined 5 MiB limit")
    return content, manifest


def export_dataset(dataset: Dataset, output_dir: Path) -> ExportBundle:
    """Write stable JSONL and provenance, rejecting changed existing output."""
    content, manifest = _export_content(dataset)
    output_dir = Path(output_dir)
    for name, raw in content.items():
        path = output_dir / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"Existing export differs: {path}; choose a new directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, raw in content.items():
        path = output_dir / name
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(raw)
    return ExportBundle(output_dir, manifest)


def verify_export(dataset: Dataset, bundle: ExportBundle) -> None:
    content, manifest = _export_content(dataset)
    if bundle.manifest != manifest:
        raise ValueError("Export manifest does not match the validated source dataset")
    for name, raw in content.items():
        path = bundle.directory / name
        if path.stat().st_size != len(raw) or path.read_bytes() != raw:
            raise ValueError(f"Export integrity check failed: {name}")


def query_sql(name: str, settings: BigQuerySettings, source_sha256: str) -> str:
    if name not in QUERY_NAMES or not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("Unknown fixed query or invalid source hash")
    sql = files("gcp_ai_analytics").joinpath("sql", f"{name}.sql").read_text(encoding="utf-8")
    for table in TABLE_FIELDS:
        sql = sql.replace("{{" + table + "}}", table_ref(settings, source_sha256, table))
    return sql


def table_ref(settings: BigQuerySettings, source_sha256: str, name: str) -> str:
    if name not in TABLE_FIELDS or not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("Invalid table name or source hash")
    return f"{settings.dataset_ref}.ops_{source_sha256[:24]}_{name}"


def query_parameters(dataset: Dataset) -> list[Any]:
    """All services are parameters, so services without any events remain visible."""
    policies = [
        bigquery.StructQueryParameter(
            None,
            bigquery.ScalarQueryParameter("service_id", "STRING", service.service_id),
            bigquery.ScalarQueryParameter(
                "check_interval_seconds", "INT64", service.check_interval_seconds
            ),
            bigquery.ScalarQueryParameter(
                "backup_max_age_hours", "FLOAT64", service.backup_max_age_hours
            ),
            bigquery.ScalarQueryParameter(
                "restore_max_age_days", "FLOAT64", service.restore_max_age_days
            ),
            bigquery.ScalarQueryParameter(
                "job_stale_after_hours", "FLOAT64", service.job_stale_after_hours
            ),
        )
        for service in sorted(dataset.services, key=lambda service: service.service_id)
    ]
    return [
        bigquery.ScalarQueryParameter("window_start", "TIMESTAMP", dataset.window_start),
        bigquery.ScalarQueryParameter("as_of", "TIMESTAMP", dataset.as_of),
        bigquery.ArrayQueryParameter("services", "STRUCT", policies),
    ]


def plan_bigquery(dataset: Dataset, settings: BigQuerySettings, bundle: ExportBundle) -> dict:
    """Produce an approval-ready plan locally; this performs no cloud operation."""
    verify_export(dataset, bundle)
    return {
        "execution": "planned_only",
        "data_classification": "synthetic",
        "project_id": settings.project_id,
        "dataset_id": settings.dataset_id,
        "location": settings.location,
        "source_dataset_sha256": bundle.source_sha256,
        "dataset_labels": {
            "application": "server-ops-insights",
            "data_classification": "synthetic",
        },
        "table_expiry_days": TABLE_EXPIRY_DAYS,
        "tables": {
            name: {"table_id": table_ref(settings, bundle.source_sha256, name), **metadata}
            for name, metadata in bundle.manifest["tables"].items()
        },
        "queries": {
            name: {"sql_sha256": _sha(query_sql(name, settings, bundle.source_sha256).encode())}
            for name in QUERY_NAMES
        },
        "limits": {
            "combined_export_bytes": MAX_EXPORT_BYTES,
            "max_load_submissions": 5,
            "max_query_submissions": 6,
            "max_dry_run_submissions": 6,
            "maximum_bytes_billed_per_query": MAX_BYTES_BILLED,
            "maximum_total_bytes_billed": MAX_BYTES_BILLED * 6,
            "use_query_cache": False,
            "automatic_retries": 0,
            "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "job_timeout_seconds": JOB_TIMEOUT_SECONDS,
        },
        "cost_basis": {
            "currency": "USD",
            "on_demand_example_per_tib": 6.25,
            "analysis_upper_bound_before_free_tier": MAX_BYTES_BILLED * 6 / 2**40 * 6.25,
            "notes": "Illustrative on-demand US analysis only; verify project pricing, "
            "region, reservations and storage before approval. Free tier not assumed.",
            "source": "https://cloud.google.com/bigquery/pricing",
        },
        "approval_required": True,
        "verification": "SQL is prepared but has not been executed by this local plan.",
    }


def _normalize(value: Any, key: str = "") -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, list):
        if key == "failure_categories":
            return {item["category"]: item["count"] for item in value}
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {name: _normalize(item, name) for name, item in value.items()}
    # Presentation rounding matches Python's reference; SQL comparisons use raw durations.
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        if key in {
            "sampled_success_pct",
            "monitoring_coverage_pct",
            "disk_used_pct",
            "success_pct",
        }:
            return round(value, 2)
        if key in {
            "latest_age_hours",
            "last_success_age_hours",
            "last_passed_restore_age_days",
            "oldest_pending_age_hours",
            "checks_latest_age_hours",
            "resources_latest_age_hours",
        }:
            return round(value, 4)
    return value


def compare_query_results(dataset: Dataset, results: dict[str, list[dict]]) -> dict:
    """Compare every returned metric against the independently computed local reference."""
    reference = {row["service_id"]: row for row in build_report(dataset)["services"]}
    mismatches = []
    checked = 0
    for name in QUERY_NAMES:
        rows = results.get(name, [])
        ids = [row.get("service_id") for row in rows]
        if set(ids) != set(reference) or len(ids) != len(reference):
            mismatches.append(
                {
                    "query": name,
                    "metric": "service_membership",
                    "expected": sorted(reference),
                    "actual": ids,
                }
            )
        for raw in rows:
            row = _normalize(dict(raw))
            service_id = row.get("service_id")
            if service_id not in reference:
                continue
            local = reference[service_id]
            if name == "freshness":
                expected = {
                    f"{section}_{key}": local[section][key]
                    for section in ("checks", "resources")
                    for key in (
                        "latest_observed_at",
                        "latest_age_hours",
                        "is_fresh",
                        "freshness_limit_seconds",
                    )
                }
            elif name == "checks":
                expected = {
                    key: value
                    for key, value in local[name].items()
                    if key
                    not in (
                        "latest_observed_at",
                        "latest_age_hours",
                        "is_fresh",
                        "freshness_limit_seconds",
                        "latest_status",
                        "latest_latency_ms",
                    )
                }
                expected.update(
                    {key: local[name][key] for key in ("latest_status", "latest_latency_ms")}
                )
            elif name in ("backups", "restore_tests"):
                expected = {
                    key: value
                    for key, value in local["backups"].items()
                    if ("restore" in key) == (name == "restore_tests")
                }
            else:
                expected = local[name]
            for key, value in expected.items():
                checked += 1
                actual = row.get(key)
                equal = actual == value and isinstance(actual, bool) == isinstance(value, bool)
                if (
                    isinstance(value, float)
                    and isinstance(actual, (float, int))
                    and not isinstance(actual, bool)
                ):
                    equal = math.isclose(actual, value, rel_tol=1e-12, abs_tol=1e-9)
                if key not in row or not equal:
                    mismatches.append(
                        {
                            "query": name,
                            "service_id": service_id,
                            "metric": key,
                            "expected": value,
                            "actual": actual,
                        }
                    )
    return {"matches": not mismatches, "metrics_compared": checked, "mismatches": mismatches}


def build_verified_report(dataset: Dataset, result: dict) -> dict:
    """Use verified SQL aggregates as evidence, with deterministic local rule selection.

    The comparison covers aggregate metrics, not individual event identity. Consequently
    findings here contain only selected SQL columns; local event IDs and event lists never
    become cloud evidence. A caller must supply the actual result of an approved batch.
    """
    source = _validated(dataset)
    expected_hash = _sha(canonical_json(source.model_dump(mode="json")).encode())
    if (
        result.get("execution") != "bigquery_observed"
        or result.get("source_dataset_sha256") != expected_hash
    ):
        raise ValueError("BigQuery result provenance does not match this synthetic source")
    results = result.get("query_results", {})
    comparison = compare_query_results(source, results)
    if not result.get("comparison", {}).get("matches") or not comparison["matches"]:
        raise ValueError("Verified report requires matching BigQuery and local metrics")
    rows = {
        name: {row["service_id"]: _normalize(dict(row)) for row in results[name]}
        for name in QUERY_NAMES
    }
    report = build_report(source)
    services = {}
    for service in report["services"]:
        service_id = service["service_id"]
        checks = {
            **rows["checks"][service_id],
            **{
                key.removeprefix("checks_"): value
                for key, value in rows["freshness"][service_id].items()
                if key.startswith("checks_")
            },
        }
        candidates = {
            "checks": checks,
            "resources": rows["resources"][service_id],
            "backups": {**rows["backups"][service_id], **rows["restore_tests"][service_id]},
            "jobs": rows["jobs"][service_id],
        }
        for section, candidate in candidates.items():
            service[section] = {key: candidate[key] for key in service[section]}
        services[service_id] = service
    fields = {
        "monitoring_coverage_gap": (
            "checks",
            [
                "expected_slots",
                "known_status_slots",
                "missing_slots",
                "unknown_slots",
                "monitoring_coverage_pct",
            ],
        ),
        "checks_missing": ("checks", ["latest_observed_at", "latest_status", "observed_slots"]),
        "checks_stale": (
            "checks",
            [
                "latest_observed_at",
                "latest_age_hours",
                "latest_status",
                "is_fresh",
                "freshness_limit_seconds",
            ],
        ),
        "latest_check_down": (
            "checks",
            ["latest_observed_at", "latest_age_hours", "latest_status", "is_fresh"],
        ),
        "latest_check_unknown": (
            "checks",
            ["latest_observed_at", "latest_age_hours", "latest_status", "is_fresh"],
        ),
        "resources_missing": ("resources", ["latest_observed_at", "measured_fields"]),
        "resources_empty": (
            "resources",
            ["latest_observed_at", "measured_fields", "missing_fields"],
        ),
        "resources_stale": (
            "resources",
            ["latest_observed_at", "latest_age_hours", "is_fresh", "freshness_limit_seconds"],
        ),
        "backup_success_missing": (
            "backups",
            ["last_success_at", "max_age_hours", "latest_attempt_at", "latest_attempt_outcome"],
        ),
        "backup_overdue": (
            "backups",
            ["last_success_at", "last_success_age_hours", "max_age_hours", "is_overdue"],
        ),
        "latest_backup_failed": (
            "backups",
            ["latest_attempt_at", "latest_attempt_outcome", "last_success_at"],
        ),
        "restore_success_missing": (
            "backups",
            [
                "last_passed_restore_at",
                "restore_max_age_days",
                "latest_restore_at",
                "latest_restore_outcome",
            ],
        ),
        "restore_test_overdue": (
            "backups",
            [
                "last_passed_restore_at",
                "last_passed_restore_age_days",
                "restore_max_age_days",
                "restore_is_overdue",
            ],
        ),
        "latest_restore_failed": (
            "backups",
            ["latest_restore_at", "latest_restore_outcome", "last_passed_restore_at"],
        ),
        "failed_job_runs": ("jobs", ["failed_runs", "completed_runs", "failure_categories"]),
        "blocked_job_runs": ("jobs", ["blocked_runs"]),
        "pending_jobs_old": (
            "jobs",
            [
                "stale_pending_runs",
                "oldest_pending_age_hours",
                "oldest_pending_job_id",
                "pending_age_target_hours",
            ],
        ),
        "job_retries": (
            "jobs",
            [
                "retries",
                "completed_run_retries",
                "pending_run_retries",
                "completed_runs",
                "running_runs",
                "blocked_runs",
                "failed_runs",
            ],
        ),
    }
    resource_metrics = {
        "cpu_high": ["cpu_pct"],
        "memory_high": ["memory_pct"],
        "disk_capacity_high": ["disk_used_pct", "disk_used_bytes", "disk_total_bytes"],
        "free_inodes_low": ["disk_free_inodes_pct"],
        "pool_degraded": ["pool_health"],
        "pool_faulted": ["pool_health"],
        "pool_unknown": ["pool_health"],
        "disk_health_failed": ["disk_health"],
        "disk_health_unknown": ["disk_health"],
    }
    fields.update(
        {
            code: ("resources", ["latest_observed_at", "latest_age_hours", "is_fresh", *keys])
            for code, keys in resource_metrics.items()
        }
    )
    for finding in report["findings"]:
        if finding["code"] not in fields:
            raise ValueError(f"No SQL evidence mapping for finding: {finding['code']}")
        section, selected = fields[finding["code"]]
        metrics = services[finding["service_id"]][section]
        finding["evidence"] = {key: metrics[key] for key in selected}
    report["provenance"] = {
        "dataset_sha256": expected_hash,
        "execution": "bigquery_aggregates_verified",
        "metrics_compared": comparison["metrics_compared"],
        "finding_selection": "deterministic Python rules over the identical validated source",
        "finding_evidence": "selected returned BigQuery aggregate columns only",
    }
    report["limitations"].append(
        "Finding selection, summaries and severity use deterministic Python rules. "
        "Supporting values here come from SQL aggregates checked against the local reference. "
        "Individual local event IDs, recorded-attempt counts and stale-job lists are not SQL proof."
    )
    return report


class BigQueryRunner:
    """One explicitly approved batch. Never retries uncertain submissions or overwrites tables.

    The private ledger is reserved before client construction. Reusing its directory fails,
    including after a crash. Inspect recorded job IDs manually before a new approval/batch.
    """

    def __init__(
        self,
        settings: BigQuerySettings,
        dataset: Dataset,
        bundle: ExportBundle,
        *,
        execute: bool = False,
        client: Any = None,
        record_dir: Path | None = None,
    ):
        if execute is not True:
            raise ValueError("Cloud execution requires explicit execute=True after owner approval")
        self.settings = settings
        self.dataset = _validated(dataset)
        self.bundle = bundle
        self.plan = plan_bigquery(self.dataset, settings, bundle)
        self.run_id = _sha(canonical_json(self.plan).encode())[:24]
        self.record_dir = Path(record_dir or bundle.directory / "private-execution")
        self.record_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.record_dir / f"bigquery-{self.run_id}.json"
        self.records: list[dict] = []
        self.counts = {"load": 0, "query": 0, "dry_run": 0}
        self.started = False
        with self.ledger_path.open("x", encoding="utf-8") as stream:
            stream.write(canonical_json(self._ledger()))
        self.client = (
            client
            if client is not None
            else bigquery.Client(project=settings.project_id, location=settings.location)
        )

    def _ledger(self) -> dict:
        return {
            "run_id": self.run_id,
            "source_dataset_sha256": self.bundle.source_sha256,
            "project_id": self.settings.project_id,
            "dataset_id": self.settings.dataset_id,
            "location": self.settings.location,
            "submission_counts": self.counts,
            "records": self.records,
        }

    def _persist(self) -> None:
        temporary = self.ledger_path.with_suffix(".pending")
        temporary.write_text(canonical_json(self._ledger()), encoding="utf-8", newline="\n")
        temporary.replace(self.ledger_path)

    def _attempt(self, kind: str, name: str, operation: Any) -> Any:
        if kind in self.counts:
            limit = 5 if kind == "load" else 6
            if self.counts[kind] >= limit:
                raise ValueError(f"{kind} submission budget exhausted")
            self.counts[kind] += 1
        record = {
            "kind": kind,
            "name": name,
            "state": "submission_outcome_unknown",
            "job_id": f"ops_{self.run_id}_{kind}_{name}",
        }
        self.records.append(record)
        self._persist()  # Reservation precedes the call, including failures/timeouts.
        try:
            result = operation(record["job_id"])
        except Exception as exc:
            record["error_type"] = type(exc).__name__
            self._persist()  # Exception text can contain credentials or private configuration.
            raise
        record["state"] = "observed_complete"
        for attr in ("total_bytes_processed", "total_bytes_billed", "output_rows", "cache_hit"):
            value = getattr(result, attr, None)
            if isinstance(value, (int, str, bool, float)):
                record[attr] = value
        self._persist()
        return result

    def create_resources(self) -> None:
        dataset = bigquery.Dataset(self.settings.dataset_ref)
        dataset.location = self.settings.location
        dataset.default_table_expiration_ms = TABLE_EXPIRY_DAYS * 86400 * 1000
        dataset.labels = self.plan["dataset_labels"]
        remote = self._attempt(
            "dataset",
            "create",
            lambda _: self.client.create_dataset(
                dataset, exists_ok=True, retry=None, timeout=REQUEST_TIMEOUT_SECONDS
            ),
        )
        if (
            remote.project != self.settings.project_id
            or remote.dataset_id != self.settings.dataset_id
            or remote.location.lower() != self.settings.location.lower()
            or any(remote.labels.get(k) != v for k, v in dataset.labels.items())
        ):
            raise ValueError("Existing dataset does not match the planned synthetic scope/location")
        for name in TABLE_FIELDS:
            table = bigquery.Table(
                table_ref(self.settings, self.bundle.source_sha256, name),
                schema=[bigquery.SchemaField(n, t, mode=m) for n, t, m in SCHEMAS[name]],
            )
            table.expires = datetime.now(UTC) + timedelta(days=TABLE_EXPIRY_DAYS)
            table.labels = self.plan["dataset_labels"]
            self._attempt(
                "table",
                name,
                lambda _, table=table: self.client.create_table(
                    table, exists_ok=False, retry=None, timeout=REQUEST_TIMEOUT_SECONDS
                ),
            )

    def load_tables(self) -> None:
        verify_export(self.dataset, self.bundle)
        for name, path in self.bundle.paths.items():
            config = bigquery.LoadJobConfig(
                schema=[bigquery.SchemaField(n, t, mode=m) for n, t, m in SCHEMAS[name]],
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                write_disposition=bigquery.WriteDisposition.WRITE_EMPTY,
                create_disposition=bigquery.CreateDisposition.CREATE_NEVER,
                ignore_unknown_values=False,
                max_bad_records=0,
                autodetect=False,
            )

            def load(job_id: str, name: str = name, path: Path = path, config: Any = config) -> Any:
                with path.open("rb") as stream:
                    job = self.client.load_table_from_file(
                        stream,
                        table_ref(self.settings, self.bundle.source_sha256, name),
                        size=path.stat().st_size,
                        job_config=config,
                        job_id=job_id,
                        location=self.settings.location,
                        num_retries=0,
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )
                    job.result(retry=None, timeout=JOB_TIMEOUT_SECONDS)
                if job.output_rows != self.bundle.manifest["tables"][name]["row_count"]:
                    raise ValueError(f"Loaded row count differs for {name}")
                return job

            self._attempt("load", name, load)

    def run_queries(self) -> dict[str, list[dict]]:
        results = {}
        for name in QUERY_NAMES:
            sql = query_sql(name, self.settings, self.bundle.source_sha256)

            def submit(job_id: str, *, dry_run: bool, sql: str = sql) -> Any:
                config = bigquery.QueryJobConfig(
                    query_parameters=query_parameters(self.dataset),
                    use_legacy_sql=False,
                    dry_run=dry_run,
                    use_query_cache=False,
                    maximum_bytes_billed=MAX_BYTES_BILLED,
                )
                return self.client.query(
                    sql,
                    job_config=config,
                    job_id=job_id,
                    location=self.settings.location,
                    retry=None,
                    job_retry=None,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )

            dry = self._attempt("dry_run", name, lambda job_id: submit(job_id, dry_run=True))
            estimated = dry.total_bytes_processed
            if not isinstance(estimated, int) or estimated > MAX_BYTES_BILLED:
                raise ValueError(f"Dry run missing an estimate or exceeds the limit: {name}")

            def execute_query(job_id: str, name: str = name, submit: Any = submit) -> Any:
                job = submit(job_id, dry_run=False)
                rows = job.result(
                    retry=None, job_retry=None, timeout=JOB_TIMEOUT_SECONDS, max_results=101
                )
                results[name] = [_normalize(dict(row)) for row in rows]
                if len(results[name]) > len(self.dataset.services):
                    raise ValueError(f"Query returned too many service rows: {name}")
                return job

            self._attempt("query", name, execute_query)
        return results

    def run(self) -> dict:
        if self.started or self.records:
            raise ValueError("This batch has already started; automatic resubmission is forbidden")
        self.started = True
        self.create_resources()
        self.load_tables()
        results = self.run_queries()
        comparison = compare_query_results(self.dataset, results)
        output = {
            "execution": "bigquery_observed",
            "source_dataset_sha256": self.bundle.source_sha256,
            "query_results": results,
            "comparison": comparison,
            "job_records": self._ledger(),
        }
        (self.record_dir / f"results-{self.run_id}.json").write_text(
            canonical_json(output), encoding="utf-8", newline="\n"
        )
        if not comparison["matches"]:
            raise ValueError(
                "BigQuery results differ from the local reference; inspect private results"
            )
        return output
