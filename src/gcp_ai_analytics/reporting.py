"""Render measured results without model-generated interpretation."""

import json
from datetime import datetime


def canonical_json(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"


def _label(value: str) -> str:
    return value.replace("_", " ").capitalize()


def _display(value: object) -> str:
    if value is None:
        return "Unknown / not applicable"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict) -> str:
    lines = [
        "# Server & App Operations Insights",
        "",
        "**Synthetic demonstration — these are not observations of your server.**",
        "",
        f"Reporting window: {report['window_start']} to {report['as_of']} (exclusive).",
        "",
        "## What needs attention",
        "",
    ]
    findings = report.get("findings", [])
    if not findings:
        lines.append(
            "No rules triggered in the supplied evidence. Review coverage before concluding health."
        )
    for finding in findings:
        lines.append(
            f"- **{finding['severity'].upper()} · {finding['service_id']}**: {finding['summary']}"
        )
        evidence = "; ".join(
            f"{_label(key)}: {_display(value)}"
            for key, value in finding.get("evidence", {}).items()
        )
        if evidence:
            lines.extend(["", f"  Evidence: {evidence}"])
    for service in report.get("services", []):
        lines.extend(["", f"## {service['service_id']}", ""])
        for section, values in service.items():
            if section == "service_id":
                continue
            lines.extend([f"### {_label(section)}", "", "| Measure | Result |", "| --- | --- |"])
            if isinstance(values, dict):
                lines.extend(
                    f"| {_label(key)} | {_display(value)} |" for key, value in values.items()
                )
            else:
                lines.append(f"| {_label(section)} | {_display(values)} |")
            lines.append("")
    lines.extend(["## Interpretation limits", ""])
    lines.extend(f"- {item}" for item in report.get("limitations", []))
    lines.extend(
        [
            "",
            "## Provenance",
            "",
            "Dataset SHA-256: "
            f"`{report.get('provenance', {}).get('dataset_sha256', 'not recorded')}`.",
            "",
            "Computed locally from supplied synthetic records. BigQuery and Gemini have not run.",
        ]
    )
    return "\n".join(lines) + "\n"
