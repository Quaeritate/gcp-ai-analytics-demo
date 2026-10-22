"""Validate the corpus and evaluation accounting without contacting a model."""

import json

import pytest

from gcp_ai_analytics.evaluation import evaluate_cases, load_cases, validate_corpus
from gcp_ai_analytics.gemini_client import RUNBOOK


class EvidenceEchoClient:
    """A mechanical test fixture, not a substitute for measured model responses."""

    def __init__(self, outcome="ok"):
        self.models = self
        self.outcome = outcome
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        if self.outcome == "error":
            raise TimeoutError("synthetic timeout")
        evidence = json.loads(kwargs["contents"])["evidence"]
        payload = {"status": "ok", "issues": [], "refusal_reason": None}
        for fact in evidence["facts"]:
            payload["issues"].append(
                {
                    "service_id": fact["service_id"],
                    "metric_id": fact["metric_id"],
                    "category": fact["category"],
                    "evidence_refs": [fact["fact_id"]],
                    "uncertainty": "cause_unknown",
                    "explanation": "Review the recorded evidence.",
                    "next_check_ids": [
                        next(
                            key
                            for key, value in RUNBOOK.items()
                            if value["category"] == fact["category"]
                        )
                    ],
                }
            )
        if self.outcome == "refused":
            payload = {"status": "refused", "issues": [], "refusal_reason": "Cannot assess"}
        if self.outcome == "empty":
            payload["issues"] = []
        return {
            "text": "malformed" if self.outcome == "invalid" else json.dumps(payload),
            "candidates": [{"finish_reason": "STOP"}],
        }


def test_all_curated_cases_have_independent_consistent_labels():
    result = validate_corpus()
    assert result["mode"] == "offline_corpus_validation"
    assert result["valid_cases"] == result["case_count"] == 24
    assert result["attempted_requests"] == 0
    assert result["model_accuracy"] is None
    assert result["tag_case_counts"]["prompt_injection"] == 3
    assert result["tag_case_counts"]["held_jobs"] == 1
    assert result["tag_case_counts"]["success_after_retry"] == 1
    assert result["human_review"]["status"] == "not_performed"
    assert all(case["prompt_characters_including_schema"] <= 8000 for case in result["cases"])
    assert evaluate_cases() == result


def test_case_materialization_does_not_mutate_other_cases():
    cases = load_cases()
    cases[0].dataset.services[0].service_id = "modified"
    assert cases[1].dataset.services[0].service_id == "compute"
    assert load_cases()[0].dataset.services[0].service_id == "compute"


def test_injected_results_have_denominators_and_unscored_human_review():
    client = EvidenceEchoClient()
    result = evaluate_cases(client=client)
    assert result["mode"] == "injected_client_evaluation"
    assert result["overall_denominator"] == 24
    assert result["attempted_requests"] == client.calls == 24
    assert result["automated_pass_count"] == 24
    assert result["valid_response_count"] == 24
    assert result["category_counts"]["monitoring"]["expected_cases"] == 7
    assert result["category_counts"]["monitoring"]["true_positive"] == 7
    assert all(case["human_factuality_score"] is None for case in result["cases"])
    assert "never live model accuracy" in result["interpretation"]


@pytest.mark.parametrize(
    "outcome,count_field",
    [
        ("error", "api_failure_count"),
        ("invalid", "invalid_response_count"),
        ("refused", "refusal_count"),
    ],
)
def test_failed_attempts_stay_in_denominator_and_exhaust_budget(outcome, count_field):
    client = EvidenceEchoClient(outcome)
    result = evaluate_cases(client=client, max_attempts=3)
    assert result["attempted_requests"] == client.calls == 3
    assert result[count_field] == 3
    assert result["skipped_budget_count"] == 21
    assert result["overall_denominator"] == 24
    assert result["automated_pass_count"] == 0


def test_empty_valid_json_does_not_score_as_correct_issue_coverage():
    result = evaluate_cases(client=EvidenceEchoClient("empty"))
    assert result["valid_response_count"] == 24
    assert result["automated_pass_count"] == 1  # The healthy control case only.
    assert result["category_counts"]["monitoring"]["false_negative"] == 7


def test_evaluation_cannot_exceed_reviewed_budget():
    with pytest.raises(ValueError, match="thirty"):
        evaluate_cases(client=EvidenceEchoClient(), max_attempts=31)


def test_each_case_is_persisted_before_the_next_request(tmp_path):
    class CheckpointClient(EvidenceEchoClient):
        def generate_content(self, **kwargs):
            assert len(list(tmp_path.glob("*.json"))) == self.calls
            return super().generate_content(**kwargs)

    result = evaluate_cases(client=CheckpointClient(), record_dir=tmp_path)
    assert result["completed"] and result["acceptance_passed"]
    assert len(list(tmp_path.glob("*.json"))) == 24
    case = json.loads((tmp_path / "healthy_reference.json").read_text())
    assert case["result"]["mode"] == "injected_client"
    assert case["human_factuality_score"] is None
    client = EvidenceEchoClient()
    with pytest.raises(ValueError, match="already exist"):
        evaluate_cases(client=client, record_dir=tmp_path)
    assert client.calls == 0


def test_completed_records_survive_an_interrupted_evaluation(tmp_path):
    class InterruptClient(EvidenceEchoClient):
        def generate_content(self, **kwargs):
            if self.calls == 2:
                raise KeyboardInterrupt
            return super().generate_content(**kwargs)

    with pytest.raises(KeyboardInterrupt):
        evaluate_cases(client=InterruptClient(), record_dir=tmp_path)
    assert len(list(tmp_path.glob("*.json"))) == 2
