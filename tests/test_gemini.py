"""Offline boundary tests; fake responses are not model-quality evidence."""

import copy
import json
from types import SimpleNamespace

import httpx
import pytest
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials

from gcp_ai_analytics.analytics import build_report
from gcp_ai_analytics.evaluation import load_cases
from gcp_ai_analytics.gemini_client import (
    RUNBOOK,
    GeminiSettings,
    RequestBudget,
    build_evidence_bundle,
    build_prompt,
    render_triage,
    triage_report,
)
from gcp_ai_analytics.generate_data import generate_dataset


def report_for(case_id="fresh_down"):
    case = next(case for case in load_cases() if case.case_id == case_id)
    return build_report(case.dataset)


def supported_payload(report):
    bundle = build_evidence_bundle(report)
    return {
        "status": "ok",
        "issues": [
            {
                "service_id": fact.service_id,
                "metric_id": fact.metric_id,
                "category": fact.category,
                "evidence_refs": [fact.fact_id],
                "uncertainty": "cause_unknown",
                "explanation": "The recorded condition needs review; its cause is not established.",
                "next_check_ids": [
                    next(
                        key for key, value in RUNBOOK.items() if value["category"] == fact.category
                    )
                ],
            }
            for fact in bundle.facts
        ],
        "refusal_reason": None,
    }


def raw_response(payload, *, finish="STOP"):
    return {
        "text": json.dumps(payload),
        "candidates": [{"finish_reason": finish, "content": {"parts": []}}],
        "model_version": "returned-model-version",
        "response_id": "response-fixture",
        "usage_metadata": {
            "prompt_token_count": 230,
            "candidates_token_count": 70,
            "total_token_count": 300,
        },
    }


class FakeClient:
    def __init__(self, response=None, error=None):
        self.models = self
        self.response = response
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def test_default_is_offline_and_prompt_includes_schema(monkeypatch):
    def forbidden(*args):
        raise AssertionError("Offline preparation must not construct a cloud client")

    monkeypatch.setattr("gcp_ai_analytics.gemini_client._new_live_client", forbidden)
    report = build_report(generate_dataset())
    result = triage_report(report)
    assert result.mode == "prepared"
    assert result.attempted_requests == 0
    assert 0 < result.prompt_characters <= 8000
    assert result.prompt_characters > len(build_prompt(result.evidence))
    assert len(result.evidence.facts) == 6
    assert result.evidence.omitted_findings == len(report["findings"]) - 6
    assert result.usage == {}


def test_known_values_are_rendered_from_authoritative_evidence():
    report = report_for("cpu_high")
    client = FakeClient(raw_response(supported_payload(report)))
    result = triage_report(report, client=client)
    assert result.status == "ok"
    assert result.mode == "injected_client"
    assert result.usage["prompt_token_count"] == 230
    assert result.response_model_version == "returned-model-version"
    assert result.latency_ms >= 0
    rendered = render_triage(result)
    assert '"value_pct": 96.0' in rendered
    assert "review_resource_history" in rendered
    assert "does not prove generated prose is true" in rendered
    config = client.calls[0]["config"]
    assert config.temperature is None
    assert config.thinking_config.thinking_level == "MINIMAL"
    assert config.thinking_config.thinking_budget is None
    assert config.max_output_tokens == 1024
    assert config.http_options.timeout == 30_000
    assert config.http_options.retry_options.attempts == 1
    assert config.automatic_function_calling.disable
    assert config.automatic_continuation is False
    assert config.tools == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("service_id", "private_server"),
        ("metric_id", "invented_metric"),
        ("evidence_refs", ["fact_999"]),
        ("next_check_ids", ["restart_server"]),
        ("category", "job_failure"),
        ("explanation", "There were 999 failures."),
        ("uncertainty", "certain"),
        ("command", "restart everything"),
    ],
)
def test_unsupported_or_unstructured_claims_fail_closed(field, value):
    report = report_for()
    payload = supported_payload(report)
    payload["issues"][0][field] = value
    result = triage_report(report, client=FakeClient(raw_response(payload)))
    assert result.status == "invalid_response"
    assert result.response is None


def test_known_but_unrelated_check_is_rejected():
    report = report_for()
    payload = supported_payload(report)
    payload["issues"][0]["next_check_ids"] = ["review_backup_history"]
    assert (
        triage_report(report, client=FakeClient(raw_response(payload))).status == "invalid_response"
    )


@pytest.mark.parametrize(
    "raw,status",
    [
        ({"text": "", "candidates": []}, "invalid_response"),
        ({"text": "{}", "candidates": [{"finish_reason": "MAX_TOKENS"}]}, "invalid_response"),
        ({"text": "{}", "candidates": [{"finish_reason": "SAFETY"}]}, "refused"),
        ({"text": "{}", "prompt_feedback": {"block_reason": "SAFETY"}}, "refused"),
        ({"text": "{", "candidates": [{"finish_reason": "STOP"}]}, "invalid_response"),
        ({"text": "", "candidates": [{"finish_reason": "STOP"}]}, "invalid_response"),
    ],
)
def test_empty_blocked_truncated_and_malformed_outputs_are_not_advice(raw, status):
    result = triage_report(report_for(), client=FakeClient(raw))
    assert result.status == status
    assert result.attempted_requests == 1
    assert result.response is None


def test_valid_json_cannot_hide_a_truncated_generation():
    report = report_for()
    raw = raw_response(supported_payload(report), finish="MAX_TOKENS")
    assert triage_report(report, client=FakeClient(raw)).status == "invalid_response"


def test_function_calls_are_rejected_even_with_valid_json():
    report = report_for()
    raw = raw_response(supported_payload(report))
    raw["candidates"][0]["content"]["parts"] = [{"function_call": {"name": "restart"}}]
    assert triage_report(report, client=FakeClient(raw)).status == "invalid_response"


def test_refusal_does_not_become_accepted_advice():
    payload = {"status": "refused", "issues": [], "refusal_reason": "Insufficient evidence"}
    result = triage_report(report_for(), client=FakeClient(raw_response(payload)))
    assert result.status == "refused"
    assert result.response is None


def test_timeouts_and_failures_consume_shared_budget_without_hidden_retries():
    client = FakeClient(error=TimeoutError("private-credential-must-not-be-recorded"))
    budget = RequestBudget(2)
    results = [triage_report(report_for(), client=client, budget=budget) for _ in range(3)]
    assert [result.status for result in results] == ["api_error", "api_error", "budget_exhausted"]
    assert len(client.calls) == budget.attempted_requests == 2
    assert sum(result.attempted_requests for result in results) == 2
    assert "private-credential" not in json.dumps([r.model_dump() for r in results])


def test_missing_project_fails_before_a_request():
    result = triage_report(report_for(), execute=True)
    assert result.status == "api_error"
    assert result.attempted_requests == 0


def test_live_factory_uses_explicit_adc_even_with_ambient_api_keys(monkeypatch):
    """The production constructor path uses only mocked credentials and HTTP here."""
    import google.auth

    report = report_for()
    payload = supported_payload(report)
    seen = []
    adc_calls = []
    original_client = genai.Client
    monkeypatch.setenv("GOOGLE_API_KEY", "synthetic-ignored-api-key")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-ignored-gemini-key")

    def adc(*, scopes):
        adc_calls.append(scopes)
        return Credentials(token="synthetic-adc-token"), "unused-default-project"

    def transport(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [{"text": json.dumps(payload)}],
                        },
                    }
                ],
            },
        )

    def constructor(**kwargs):
        kwargs["http_options"] = kwargs["http_options"].model_copy(
            update={
                "httpx_client": httpx.Client(transport=httpx.MockTransport(transport)),
            }
        )
        return original_client(**kwargs)

    monkeypatch.setattr(google.auth, "default", adc)
    monkeypatch.setattr(genai, "Client", constructor)
    result = triage_report(report, GeminiSettings(project="synthetic-test-project"), execute=True)
    assert result.status == "ok"
    assert adc_calls == [["https://www.googleapis.com/auth/cloud-platform"]]
    assert len(seen) == 1
    assert seen[0].headers["Authorization"] == "Bearer synthetic-adc-token"
    assert "x-goog-api-key" not in seen[0].headers


def test_oversized_prompt_and_non_synthetic_report_are_rejected():
    report = report_for()
    report["findings"][0]["evidence"]["oversized"] = "x" * 8000
    with pytest.raises(ValueError, match="8000"):
        triage_report(report)
    report["data_classification"] = "private"
    with pytest.raises(ValueError, match="synthetic"):
        triage_report(report)


def test_budgets_and_reviewed_model_settings_are_bounded():
    for limit in (0, 31, True):
        with pytest.raises(ValueError):
            RequestBudget(limit)
    with pytest.raises(ValueError):
        GeminiSettings(model="unreviewed-model")
    with pytest.raises(ValueError):
        GeminiSettings(max_output_tokens=9000)


def test_actual_sdk_serializes_schema_and_disables_retry_with_mock_transport(monkeypatch):
    """Exercise installed SDK serialization using an in-process HTTP transport only."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    requests = []
    report = report_for()
    payload = supported_payload(report)

    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"role": "model", "parts": [{"text": json.dumps(payload)}]},
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 20,
                    "totalTokenCount": 30,
                },
                "modelVersion": "mock-model",
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(transport))
    client = genai.Client(
        enterprise=True,
        project="synthetic-test-project",
        location="global",
        credentials=Credentials(token="synthetic-test-token"),
        http_options=types.HttpOptions(httpx_client=http_client),
    )
    try:
        result = triage_report(report, client=client)
    finally:
        client.close()
    assert result.status == "ok"
    assert len(requests) == 1
    config = requests[0]["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseSchema"]["properties"]["issues"]
    assert config["thinkingConfig"]["thinking_level"] == "MINIMAL"
    assert "temperature" not in config


def test_actual_sdk_failed_request_is_attempted_once(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    requests = []

    def transport(request):
        requests.append(request)
        return httpx.Response(503, json={"error": {"code": 503, "message": "temporary"}})

    client = genai.Client(
        enterprise=True,
        project="synthetic-test-project",
        location="global",
        credentials=Credentials(token="synthetic-test-token"),
        http_options=types.HttpOptions(
            httpx_client=httpx.Client(transport=httpx.MockTransport(transport)),
        ),
    )
    try:
        result = triage_report(report_for(), client=client)
    finally:
        client.close()
    assert result.status == "api_error"
    assert result.attempted_requests == len(requests) == 1


def test_actual_sdk_continuation_cannot_bypass_attempt_budget(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    requests = []

    def transport(request):
        requests.append(request)
        # Stop a regression from looping; without automatic_continuation=False this
        # second response would reveal a hidden request to the test.
        finish = "CONTINUATION" if len(requests) == 1 else "STOP"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": finish,
                        "continuationToken": "dGVzdA==",
                        "content": {"parts": [{"text": "{"}]},
                    }
                ],
            },
        )

    client = genai.Client(
        enterprise=True,
        project="synthetic-test-project",
        location="global",
        credentials=Credentials(token="synthetic-test-token"),
        http_options=types.HttpOptions(
            httpx_client=httpx.Client(transport=httpx.MockTransport(transport)),
        ),
    )
    try:
        result = triage_report(report_for(), client=client)
    finally:
        client.close()
    assert result.status == "invalid_response"
    assert result.finish_reason == "CONTINUATION"
    assert result.attempted_requests == len(requests) == 1


def test_reference_checks_do_not_claim_to_prove_prose_truth():
    report = report_for()
    payload = supported_payload(report)
    # This intentionally false spelled-out statement demonstrates a documented limitation.
    payload["issues"][0]["explanation"] = "Ninety outages were caused by a memory leak."
    result = triage_report(report, client=FakeClient(raw_response(payload)))
    assert result.status == "ok"
    assert "Human factuality and usefulness review is still required" in render_triage(result)


def test_multiple_candidates_and_duplicate_issues_rejected():
    report = report_for()
    payload = supported_payload(report)
    raw = raw_response(payload)
    raw["candidates"].append(copy.deepcopy(raw["candidates"][0]))
    assert triage_report(report, client=FakeClient(raw)).status == "invalid_response"
    payload["issues"].append(copy.deepcopy(payload["issues"][0]))
    assert (
        triage_report(report, client=FakeClient(raw_response(payload))).status == "invalid_response"
    )


def test_object_style_response_is_supported():
    report = report_for()
    raw = SimpleNamespace(**raw_response(supported_payload(report)))
    assert triage_report(report, client=FakeClient(raw)).status == "ok"
