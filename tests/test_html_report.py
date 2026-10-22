import copy
from html.parser import HTMLParser

import pytest

from gcp_ai_analytics.analytics import build_report
from gcp_ai_analytics.generate_data import generate_dataset
from gcp_ai_analytics.html_report import render_html


class ParsedHTML(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


@pytest.fixture
def report():
    return build_report(generate_dataset(42))


def test_report_has_core_content_and_clear_synthetic_scope(report):
    html = render_html(report)
    parsed = ParsedHTML(html)
    text = " ".join(parsed.text)
    assert html.startswith("<!doctype html>")
    for heading in (
        "Synthetic demonstration",
        "Attention queue",
        "Service visibility",
        "Resource observations",
        "Data protection & recovery",
        "Application work",
        "Evidence & interpretation",
    ):
        assert heading in text
    assert "do not describe an actual server" in text
    assert "not the time you open this file" in text
    assert "No model-generated explanation is included" in text
    assert "Sampled success = up / known up-or-down slots" in text
    for service in report["services"]:
        assert service["service_id"] in text
    for finding in report["findings"]:
        assert finding["summary"] in text


def test_untrusted_strings_cannot_create_elements_or_attributes(report):
    payload = '<script>alert("x")</script><img src=x onerror="alert(1)">&'
    report["services"][0]["service_id"] = payload
    report["services"][0]["resources"]["pool_health"] = payload
    report["findings"][0].update(
        service_id=payload,
        summary=payload,
        severity=payload,
        code=payload,
        evidence={payload: payload},
    )
    report["as_of"] = payload
    report["limitations"].append(payload)
    report["provenance"] = {"dataset_sha256": payload}
    html = render_html(report)
    parsed = ParsedHTML(html)
    assert payload not in html
    assert payload in " ".join(parsed.text)
    assert "&lt;script&gt;" in html
    assert not any(tag in {"script", "img"} for tag, _ in parsed.elements)
    assert not any(key.startswith("on") for _, attrs in parsed.elements for key in attrs)


def test_missing_measurements_and_empty_denominators_are_unknown(report):
    service = report["services"][0]
    service["resources"]["cpu_pct"] = None
    service["resources"]["memory_pct"] = 0
    service["checks"]["sampled_success_pct"] = None
    html = render_html(report)
    assert "<span>CPU</span><strong>Unknown</strong>" in html
    assert "<span>Memory</span><strong>0%</strong>" in html
    assert '<div class="track absent" aria-hidden="true"></div>' in html
    assert 'class="numeric">Unknown</td>' in html
    # The generator has no completed compute jobs; this must not become 100% success.
    assert service["jobs"]["success_pct"] is None
    assert "No success recorded" in html


def test_stale_up_check_never_claims_current_up_status(report):
    service = report["services"][0]
    service["checks"]["is_fresh"] = False
    service["checks"]["latest_status"] = "up"
    service["resources"]["is_fresh"] = False
    report["services"] = [service]
    html = render_html(report)
    assert "Current status unknown" in html
    assert "Last observed: up" in html
    assert "Stale · historical only" in html
    assert 'class="resource-metric historical"' in html
    assert '<span class="badge teal">up</span>' not in html
    assert "Stale data feeds</span><strong>2</strong>" in html


def test_document_is_self_contained_and_requires_no_javascript(report):
    html = render_html(report)
    parsed = ParsedHTML(html)
    for tag, attrs in parsed.elements:
        assert tag not in {"script", "link", "iframe", "object", "embed", "form"}
        assert "src" not in attrs
        assert "srcset" not in attrs
        if "href" in attrs:
            assert attrs["href"].startswith("#")
    assert "url(" not in html
    assert "@import" not in html
    assert "default-src 'none'" in html
    assert "<details>" in html
    assert "@media print" in html
    assert "@media(max-width:600px)" in html


def test_empty_report_does_not_claim_healthy_server():
    html = render_html({"data_classification": "synthetic"})
    assert "Missing evidence is not proof of health" in html
    assert "Unknown" in html
    assert "All systems operational" not in html


@pytest.mark.parametrize("classification", [None, "private", "production", "Synthetic"])
def test_report_rejects_unverified_classification(classification):
    with pytest.raises(ValueError, match="explicitly synthetic"):
        render_html({"data_classification": classification})


def test_rendering_is_deterministic_and_does_not_modify_report(report):
    original = copy.deepcopy(report)
    assert render_html(report) == render_html(report)
    assert original == report
