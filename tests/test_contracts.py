from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from gcp_ai_analytics.contracts import Dataset

AS_OF = datetime(2026, 10, 19, tzinfo=UTC)


def payload():
    return {
        "data_classification": "synthetic",
        "window_start": AS_OF - timedelta(days=1),
        "as_of": AS_OF,
        "services": [{"service_id": "server"}],
        "service_checks": [
            {
                "event_id": "check",
                "service_id": "server",
                "observed_at": AS_OF - timedelta(hours=1),
                "status": "up",
            }
        ],
    }


def test_exact_duplicate_does_not_double_count_and_conflict_is_rejected():
    data = payload()
    data["service_checks"].append(deepcopy(data["service_checks"][0]))
    normalized = Dataset.model_validate(data)
    assert len(normalized.service_checks) == 1
    assert normalized.duplicates_removed == 1
    data["service_checks"][1]["status"] = "down"
    with pytest.raises(ValidationError, match="Conflicting event ID"):
        Dataset.model_validate(data)


def test_missing_or_private_classification_is_rejected():
    data = payload()
    del data["data_classification"]
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)
    data["data_classification"] = "private"
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_at", AS_OF),
        ("observed_at", AS_OF.replace(tzinfo=None)),
        ("service_id", "missing"),
        ("status", "healthy-ish"),
        ("latency_ms", float("nan")),
        ("latency_ms", True),
        ("document_title", "not-an-operational-field"),
    ],
)
def test_invalid_or_out_of_contract_event_is_rejected(field, value):
    data = payload()
    data["service_checks"][0][field] = value
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)


def test_timezones_normalize_and_conflicting_observation_cannot_inflate_samples():
    data = payload()
    data["service_checks"][0]["observed_at"] = "2026-10-18T19:00:00-04:00"
    normalized = Dataset.model_validate(data)
    assert normalized.service_checks[0].observed_at == AS_OF - timedelta(hours=1)
    duplicate = deepcopy(data["service_checks"][0])
    duplicate["event_id"] = "different-id"
    data["service_checks"].append(duplicate)
    with pytest.raises(ValidationError, match="Conflicting observation key"):
        Dataset.model_validate(data)


def test_impossible_disk_usage_and_job_lifecycle_are_rejected():
    data = payload()
    data["resource_samples"] = [
        {
            "event_id": "resource",
            "service_id": "server",
            "observed_at": AS_OF - timedelta(hours=1),
            "disk_used_bytes": 101,
            "disk_total_bytes": 100,
        }
    ]
    with pytest.raises(ValidationError, match="exceeds capacity"):
        Dataset.model_validate(data)
    del data["resource_samples"]
    data["job_runs"] = [
        {
            "event_id": "job",
            "service_id": "server",
            "job_id": "job",
            "job_type": "backup",
            "started_at": AS_OF - timedelta(hours=1),
            "status": "succeeded",
            "attempts": 1,
        }
    ]
    with pytest.raises(ValidationError, match="finish timestamp"):
        Dataset.model_validate(data)
