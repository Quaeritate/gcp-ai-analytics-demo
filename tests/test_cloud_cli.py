import json

import pytest

from gcp_ai_analytics.cli import main
from gcp_ai_analytics.generate_data import generate_dataset
from gcp_ai_analytics.reporting import canonical_json


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "synthetic.json"
    path.write_text(canonical_json(generate_dataset().model_dump(mode="json")))
    return path


def test_cloud_plan_produces_exports_and_prepared_ai_without_network(source, tmp_path):
    output = tmp_path / "plan"
    assert (
        main(
            [
                "plan-cloud",
                "--input",
                str(source),
                "--project",
                "example-project",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    plan = json.loads((output / "bigquery-plan.json").read_text())
    ai = json.loads((output / "triage-preview.json").read_text())
    assert len(plan["queries"]) == 6
    assert len(list((output / "export").glob("*.jsonl"))) == 5
    assert ai["status"] == "prepared"
    assert ai["attempted_requests"] == 0
    assert ai["prompt_characters"] <= 8000


def test_bigquery_without_execute_never_constructs_runner(source, tmp_path, monkeypatch):
    import gcp_ai_analytics.bigquery_pipeline as pipeline

    def forbidden(*args, **kwargs):
        pytest.fail("A cloud runner was constructed without --execute")

    monkeypatch.setattr(pipeline, "BigQueryRunner", forbidden)
    assert (
        main(
            [
                "run-bigquery",
                "--input",
                str(source),
                "--project",
                "example-project",
                "--output",
                str(tmp_path / "unapproved"),
            ]
        )
        == 2
    )
    assert not (tmp_path / "unapproved").exists()


def test_live_output_must_stay_private_and_new(source, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    public_output = tmp_path / "examples"
    assert (
        main(
            [
                "triage",
                "--input",
                str(source),
                "--project",
                "example-project",
                "--output",
                str(public_output),
                "--execute",
            ]
        )
        == 2
    )
    assert not public_output.exists()
    existing = tmp_path / "artifacts" / "local" / "existing"
    existing.mkdir(parents=True)
    (existing / "receipt.json").write_text("retain")
    assert (
        main(
            [
                "triage",
                "--input",
                str(source),
                "--project",
                "example-project",
                "--output",
                str(existing),
                "--execute",
            ]
        )
        == 2
    )
    assert (existing / "receipt.json").read_text() == "retain"


def test_sql_mismatch_prevents_live_ai(source, tmp_path, monkeypatch):
    import gcp_ai_analytics.bigquery_pipeline as pipeline
    import gcp_ai_analytics.gemini_client as gemini

    monkeypatch.chdir(tmp_path)
    real_triage = gemini.triage_report
    executions = []

    def guarded_triage(*args, **kwargs):
        executions.append(kwargs.get("execute", False))
        assert not kwargs.get("execute", False)
        return real_triage(*args, **kwargs)

    class MismatchRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self):
            return {"comparison": {"matches": False}}

    monkeypatch.setattr(pipeline, "BigQueryRunner", MismatchRunner)
    monkeypatch.setattr(gemini, "triage_report", guarded_triage)
    assert (
        main(
            [
                "cloud-demo",
                "--input",
                str(source),
                "--project",
                "example-project",
                "--output",
                "artifacts/local/mismatch",
                "--execute",
            ]
        )
        == 2
    )
    assert executions == [False]


def test_evaluation_cli_distinguishes_offline_corpus_from_model_accuracy(tmp_path):
    assert main(["evaluate-ai", "--output", str(tmp_path)]) == 0
    result = json.loads((tmp_path / "evaluation.json").read_text())
    assert result["case_count"] == 24
    assert result["attempted_requests"] == 0


@pytest.mark.parametrize("command", ["plan-cloud", "run-bigquery"])
def test_bigquery_workflows_support_data_outside_ai_prompt_scope(tmp_path, monkeypatch, command):
    import gcp_ai_analytics.bigquery_pipeline as pipeline
    import gcp_ai_analytics.gemini_client as gemini
    from gcp_ai_analytics.analytics import build_report
    from gcp_ai_analytics.contracts import Dataset

    monkeypatch.chdir(tmp_path)
    dataset = Dataset.model_validate(
        {
            "data_classification": "synthetic",
            "window_start": "2026-10-21T00:00:00Z",
            "as_of": "2026-10-22T00:00:00Z",
            "services": [{"service_id": f"svc_{index:03d}_" + "x" * 88} for index in range(100)],
        }
    )
    with pytest.raises(ValueError, match="8000 characters"):
        gemini.build_prompt(gemini.build_evidence_bundle(build_report(dataset)))
    source = tmp_path / "many-services.json"
    source.write_text(canonical_json(dataset.model_dump(mode="json")), encoding="utf-8")
    output = tmp_path / "artifacts" / "local" / command
    runner_calls = []
    preview_calls = []
    real_triage = gemini.triage_report

    class SuccessfulRunner:
        def __init__(self, settings, data, bundle, **kwargs):
            assert kwargs["execute"] is True
            assert len(data.services) == 100
            runner_calls.append(bundle)

        def run(self):
            return {"comparison": {"matches": True}}

    def offline_preview(*args, **kwargs):
        assert not kwargs.get("execute", False)
        preview_calls.append(True)
        return real_triage(*args, **kwargs)

    def forbidden_client(*args, **kwargs):
        pytest.fail("CLI regression test attempted to construct a live cloud client")

    monkeypatch.setattr(pipeline, "BigQueryRunner", SuccessfulRunner)
    monkeypatch.setattr(pipeline.bigquery, "Client", forbidden_client)
    monkeypatch.setattr(gemini, "_new_live_client", forbidden_client)
    monkeypatch.setattr(gemini, "triage_report", offline_preview)
    arguments = [
        command,
        "--input",
        str(source),
        "--project",
        "example-project",
        "--output",
        str(output),
    ]
    if command == "run-bigquery":
        arguments.append("--execute")
    assert main(arguments) == 0
    assert len(list((output / "export").glob("*.jsonl"))) == 5
    assert (output / "bigquery-plan.json").exists()
    if command == "run-bigquery":
        assert len(runner_calls) == 1
        assert preview_calls == []
        assert not (output / "triage-preview.json").exists()
        assert json.loads((output / "bigquery-results.json").read_text())["comparison"]["matches"]
    else:
        assert runner_calls == []
        assert preview_calls == [True]
        preview = json.loads((output / "triage-preview.json").read_text())
        assert preview["status"] == "unavailable"
        assert preview["attempted_requests"] == 0


@pytest.mark.parametrize("acceptance", [False, None, True])
def test_live_evaluation_exit_status_requires_explicit_acceptance(
    tmp_path, monkeypatch, acceptance
):
    import gcp_ai_analytics.evaluation as evaluation

    monkeypatch.chdir(tmp_path)
    output = tmp_path / "artifacts" / "local" / "evaluation"
    receipt = {
        "mode": "live_model_evaluation",
        "attempted_requests": 24,
        "api_failure_count": 0 if acceptance else 24,
    }
    if acceptance is not None:
        receipt["acceptance_passed"] = acceptance
    calls = []

    def completed_evaluation(**kwargs):
        assert kwargs["execute"] is True
        assert kwargs["settings"].project == "example-project"
        assert kwargs["record_dir"] == output / "cases"
        calls.append(True)
        return receipt

    monkeypatch.setattr(evaluation, "evaluate_cases", completed_evaluation)
    status = main(
        [
            "evaluate-ai",
            "--project",
            "example-project",
            "--output",
            str(output),
            "--execute",
        ]
    )
    assert status == (0 if acceptance is True else 2)
    assert calls == [True]
    assert json.loads((output / "evaluation.json").read_text()) == receipt
    assert (output / "execution-started.json").exists()
