"""Offline integration of SQL-result provenance into the actual Gemini prompt builder.

The fixtures project local metrics into fake SQL-shaped rows to exercise wiring only.
Independent arithmetic expectations belong to test_bigquery.py; no SQL/model call runs here.
"""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from gcp_ai_analytics import bigquery_pipeline as pipeline
from gcp_ai_analytics import gemini_client as gemini
from gcp_ai_analytics.analytics import build_report
from gcp_ai_analytics.cli import main
from gcp_ai_analytics.contracts import Dataset
from gcp_ai_analytics.generate_data import generate_dataset
from gcp_ai_analytics.reporting import canonical_json


def sql_shaped_result(dataset):
    """Fixture conversion, not an alternate implementation of the SQL calculations."""
    report = build_report(dataset)
    rows = {name: [] for name in pipeline.QUERY_NAMES}
    freshness_keys = {
        "latest_observed_at",
        "latest_age_hours",
        "is_fresh",
        "freshness_limit_seconds",
    }
    for service in report["services"]:
        identity = {"service_id": service["service_id"]}
        rows["checks"].append(
            {
                **identity,
                **{
                    key: value
                    for key, value in service["checks"].items()
                    if key not in freshness_keys
                },
            }
        )
        rows["freshness"].append(
            {
                **identity,
                **{
                    f"{section}_{key}": service[section][key]
                    for section in ("checks", "resources")
                    for key in freshness_keys
                },
            }
        )
        rows["resources"].append({**identity, **service["resources"]})
        for name in ("backups", "restore_tests"):
            rows[name].append(
                {
                    **identity,
                    **{
                        key: value
                        for key, value in service["backups"].items()
                        if ("restore" in key) == (name == "restore_tests")
                    },
                }
            )
        rows["jobs"].append({**identity, **service["jobs"]})
    return {
        "execution": "bigquery_observed",
        "source_dataset_sha256": hashlib.sha256(
            canonical_json(dataset.model_dump(mode="json")).encode()
        ).hexdigest(),
        "query_results": rows,
        "comparison": pipeline.compare_query_results(dataset, rows),
        "job_records": {"fixture_only": True},
    }


def cpu_fixture():
    end = datetime(2026, 10, 22, tzinfo=UTC)
    return Dataset.model_validate(
        {
            "data_classification": "synthetic",
            "window_start": end - timedelta(hours=4),
            "as_of": end,
            "services": [
                {"service_id": "server", "backup_max_age_hours": None, "restore_max_age_days": None}
            ],
            "service_checks": [
                {
                    "event_id": f"check_{hour}",
                    "service_id": "server",
                    "observed_at": end - timedelta(hours=hour),
                    "status": "up",
                }
                for hour in (1, 2, 3, 4)
            ],
            "resource_samples": [
                {
                    "event_id": "resource",
                    "service_id": "server",
                    "observed_at": end - timedelta(hours=1),
                    "cpu_pct": 96.123456,
                }
            ],
        }
    )


def install_fake_boundaries(monkeypatch, result):
    captured_prompts = []
    captured_reports = []

    class Runner:
        def __init__(self, *args, **kwargs):
            assert kwargs["execute"] is True

        def run(self):
            return copy.deepcopy(result)

    def generate_content(**kwargs):
        payload = json.loads(kwargs["contents"])
        captured_prompts.append(payload)
        issues = []
        for fact in payload["evidence"]["facts"]:
            check = next(
                key
                for key, value in gemini.RUNBOOK.items()
                if value["category"] == fact["category"]
            )
            issues.append(
                {
                    "service_id": fact["service_id"],
                    "metric_id": fact["metric_id"],
                    "category": fact["category"],
                    "evidence_refs": [fact["fact_id"]],
                    "uncertainty": "observed_condition_only",
                    "explanation": "The observed condition needs review.",
                    "next_check_ids": [check],
                }
            )
        return {
            "text": json.dumps({"status": "ok", "issues": issues}),
            "candidates": [{"finish_reason": "STOP", "content": {"parts": []}}],
        }

    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    original_triage = gemini.triage_report

    def triage(report, settings=None, *, execute=False, **kwargs):
        if execute:
            captured_reports.append(copy.deepcopy(report))
            kwargs["client"] = fake_client
        return original_triage(report, settings, execute=execute, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("Offline integration test attempted to create a live cloud client")

    monkeypatch.setattr(pipeline, "BigQueryRunner", Runner)
    monkeypatch.setattr(pipeline.bigquery, "Client", forbidden)
    monkeypatch.setattr(gemini, "_new_live_client", forbidden)
    monkeypatch.setattr(gemini, "triage_report", triage)
    return captured_prompts, captured_reports


def execute_cli(tmp_path, monkeypatch, dataset):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "synthetic.json"
    source.write_text(canonical_json(dataset.model_dump(mode="json")), encoding="utf-8")
    return main(
        [
            "cloud-demo",
            "--input",
            str(source),
            "--project",
            "example-project",
            "--output",
            "artifacts/local/cloud-test",
            "--execute",
        ]
    )


def test_combined_cli_sends_actual_sql_aggregate_values_to_gemini(tmp_path, monkeypatch):
    dataset = cpu_fixture()
    result = sql_shaped_result(dataset)
    sql_cpu = 96.12345600001  # Valid floating difference under the explicit comparison tolerance.
    result["query_results"]["resources"][0]["cpu_pct"] = sql_cpu
    assert pipeline.compare_query_results(dataset, result["query_results"])["matches"]
    prompts, reports = install_fake_boundaries(monkeypatch, result)
    assert execute_cli(tmp_path, monkeypatch, dataset) == 0
    assert len(prompts) == len(reports) == 1
    assert reports[0]["provenance"]["execution"] == "bigquery_aggregates_verified"
    fact = next(fact for fact in prompts[0]["evidence"]["facts"] if fact["metric_id"] == "cpu_high")
    assert fact["values"]["cpu_pct"] == sql_cpu
    assert fact["values"]["cpu_pct"] != dataset.resource_samples[0].cpu_pct
    assert "event_id" not in fact["values"]


@pytest.mark.parametrize("corruption", ["failed_comparison", "forged_pass", "source_hash"])
def test_combined_cli_rejects_unverified_results_before_ai(tmp_path, monkeypatch, corruption):
    dataset = cpu_fixture()
    result = sql_shaped_result(dataset)
    if corruption == "failed_comparison":
        result["comparison"]["matches"] = False
    elif corruption == "forged_pass":
        result["query_results"]["resources"][0]["cpu_pct"] = 20.0
    else:
        result["source_dataset_sha256"] = "0" * 64
    prompts, reports = install_fake_boundaries(monkeypatch, result)
    assert execute_cli(tmp_path, monkeypatch, dataset) == 2
    assert prompts == reports == []


def test_seed_42_verified_sql_evidence_fits_full_prompt_bound():
    dataset = generate_dataset(seed=42)
    result = sql_shaped_result(dataset)
    verified = pipeline.build_verified_report(dataset, result)
    evidence = gemini.build_evidence_bundle(verified)
    prompt = gemini.build_prompt(evidence)
    assert gemini.prompt_characters(prompt) <= 8000
    assert len(evidence.facts) <= gemini.MAX_FINDINGS
    assert evidence.total_findings == len(verified["findings"])
    assert evidence.omitted_findings == evidence.total_findings - len(evidence.facts)
    assert all(
        "event_id" not in fact.values and "job_ids" not in fact.values for fact in evidence.facts
    )
