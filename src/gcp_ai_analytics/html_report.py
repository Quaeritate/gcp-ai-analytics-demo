"""Portable, escaped HTML presentation of deterministic synthetic report facts."""

# HTML rows remain together to make their semantics and escaping reviewable.
# ruff: noqa: E501

from __future__ import annotations

import json
import math
from collections import Counter
from html import escape
from typing import Any


def _text(value: Any) -> str:
    return escape("Unknown" if value is None else str(value), quote=True)


def _number(value: Any, suffix: str = "") -> str:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return "Unknown"
    return f"{value:,.2f}".rstrip("0").rstrip(".") + suffix


def _badge(label: str, tone: str = "neutral") -> str:
    # Tone is always an internal constant, never a report value.
    return f'<span class="badge {tone}">{_text(label)}</span>'


def _freshness(data: dict) -> str:
    if data.get("is_fresh") is True:
        return _badge("Fresh at cutoff", "teal")
    if data.get("is_fresh") is False:
        return _badge("Stale · historical only", "amber")
    return _badge("Freshness unknown")


def _evidence(value: Any, label: str = "Inspect evidence") -> str:
    content = escape(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), quote=True)
    return f"<details><summary>{_text(label)}</summary><pre>{content}</pre></details>"


def _finding(item: dict) -> str:
    severity = item.get("severity")
    tone = {"critical": "red", "warning": "amber", "info": "teal"}.get(severity, "neutral")
    return (
        f'<article class="finding {tone}"><div class="finding-meta">'
        f"{_badge(severity or 'unknown', tone)}"
        f'<span class="mono">{_text(item.get("service_id"))}</span></div>'
        f"<h3>{_text(item.get('summary'))}</h3>"
        f'<p class="finding-code">{_text(item.get("code"))}</p>'
        f"{_evidence(item.get('evidence'))}</article>"
    )


def _check_status(checks: dict) -> str:
    status = checks.get("latest_status")
    if checks.get("is_fresh") is not True:
        return _badge("Current status unknown") + (
            f"<small>Last observed: {_text(status)} · "
            f"{_number(checks.get('latest_age_hours'), ' h')} old</small>"
        )
    tone = {"up": "teal", "down": "red"}.get(status, "neutral")
    return _badge(status or "unknown", tone) + (
        f"<small>{_number(checks.get('latest_age_hours'), ' h')} old at cutoff</small>"
    )


def _service_row(service: dict) -> str:
    checks = service.get("checks", {})
    return (
        f'<tr><th scope="row" class="mono">{_text(service.get("service_id"))}</th>'
        f"<td>{_check_status(checks)}</td>"
        f'<td class="numeric">{_number(checks.get("sampled_success_pct"), "%")}</td>'
        f'<td class="numeric">{_number(checks.get("monitoring_coverage_pct"), "%")}</td>'
        f'<td class="numeric">{_number(checks.get("down_slots"))}</td>'
        f'<td class="numeric">{_number(checks.get("missing_slots"))}</td>'
        f'<td class="numeric">{_number(checks.get("unknown_slots"))}</td></tr>'
    )


def _resource_bar(label: str, value: Any, fresh: bool) -> str:
    valid = (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and math.isfinite(value)
        and 0 <= value <= 100
    )
    bar = (
        f'<div class="track" aria-hidden="true"><span style="width:{value:.4f}%"></span></div>'
        if valid
        else '<div class="track absent" aria-hidden="true"></div>'
    )
    return (
        f'<div class="resource-metric {"" if fresh else "historical"}">'
        f"<div><span>{_text(label)}</span><strong>{_number(value, '%')}</strong></div>"
        f"{bar}</div>"
    )


def _resource_card(service: dict) -> str:
    resources = service.get("resources", {})
    bars = "".join(
        _resource_bar(label, resources.get(field), resources.get("is_fresh") is True)
        for label, field in (
            ("CPU", "cpu_pct"),
            ("Memory", "memory_pct"),
            ("Disk", "disk_used_pct"),
        )
    )
    return (
        f'<article class="card"><div class="card-top"><h3 class="mono">'
        f"{_text(service.get('service_id'))}</h3>{_freshness(resources)}</div>{bars}"
        '<dl class="mini-facts">'
        f"<div><dt>Free inodes</dt><dd>{_number(resources.get('disk_free_inodes_pct'), '%')}</dd>"
        f"</div><div><dt>Storage pool</dt><dd>{_text(resources.get('pool_health'))}</dd></div>"
        f"<div><dt>Disk health</dt><dd>{_text(resources.get('disk_health'))}</dd></div>"
        f"<div><dt>Sample age at cutoff</dt><dd>"
        f"{_number(resources.get('latest_age_hours'), ' h')}</dd></div></dl>"
        f"{_evidence(resources, 'Inspect resource sample')}</article>"
    )


def _age_status(overdue: Any, age: Any, target: Any) -> str:
    if target is None:
        return _badge("No age target")
    if age is None:
        return _badge("No success recorded", "amber")
    if overdue is True:
        return _badge("Overdue", "amber")
    if overdue is False:
        return _badge("Within age target", "teal")
    return _badge("Age status unknown")


def _protection_card(service: dict) -> str:
    backups = service.get("backups", {})
    backup_age = backups.get("last_success_age_hours")
    backup_target = backups.get("max_age_hours")
    restore_age = backups.get("last_passed_restore_age_days")
    restore_target = backups.get("restore_max_age_days")
    return (
        f'<article class="card"><h3 class="mono">{_text(service.get("service_id"))}</h3>'
        '<div class="protection-row"><div><span class="eyebrow">Last successful backup</span>'
        f'<strong class="age">{_number(backup_age, " h")}</strong></div>'
        f"{_age_status(backups.get('is_overdue'), backup_age, backup_target)}</div>"
        f'<p class="muted">Target: {_number(backup_target, " h")} · latest attempt: '
        f"{_text(backups.get('latest_attempt_outcome'))}</p>"
        '<div class="protection-row divided"><div><span class="eyebrow">Last passed restore</span>'
        f'<strong class="age">{_number(restore_age, " days")}</strong></div>'
        f"{_age_status(backups.get('restore_is_overdue'), restore_age, restore_target)}</div>"
        f'<p class="muted">Target: {_number(restore_target, " days")} · latest test: '
        f"{_text(backups.get('latest_restore_outcome'))}</p>"
        f"{_evidence(backups, 'Inspect backup & restore evidence')}</article>"
    )


def _jobs_row(service: dict) -> str:
    jobs = service.get("jobs", {})
    values = "".join(
        f'<td class="numeric">{_number(jobs.get(key), suffix)}</td>'
        for key, suffix in (
            ("completed_runs", ""),
            ("success_pct", "%"),
            ("failed_runs", ""),
            ("retries", ""),
            ("running_runs", ""),
            ("blocked_runs", ""),
            ("stale_pending_runs", ""),
        )
    )
    return f'<tr><th scope="row" class="mono">{_text(service.get("service_id"))}</th>{values}</tr>'


_CSS = """
:root{color-scheme:light;--ink:#172c3c;--muted:#587080;--line:#dce5e9;--paper:#f3f6f7;
--teal:#14756d;--amber:#8a5300;--red:#a63739;--navy:#102b3b}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);
color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:inherit}a:focus-visible,summary:focus-visible{outline:3px solid #dc9100;outline-offset:4px}
.skip{position:absolute;left:16px;top:-80px;background:white;padding:12px;z-index:10}
.skip:focus{top:16px}.shell{max-width:1400px;margin:auto;padding:0 44px}
.topbar{background:var(--navy);color:#dbe8ed}.topbar .shell{display:flex;justify-content:space-between;
align-items:center;gap:20px;min-height:72px}.brand{font-weight:650;letter-spacing:.02em;
display:flex;align-items:center;gap:12px}.brand-mark{font-size:26px;color:#73d5c4}
.topbar nav{display:flex;gap:24px;font-size:12px}.topbar a{text-decoration:none}
.hero{padding:40px 0 30px;display:flex;align-items:flex-end;justify-content:space-between;gap:24px}
.eyebrow{text-transform:uppercase;font-size:10px;letter-spacing:.12em;font-weight:700;color:var(--muted)}
h1{font-size:clamp(28px,3vw,42px);line-height:1.15;letter-spacing:-.04em;margin:10px 0 12px;
font-weight:650}h2{font-size:21px;letter-spacing:-.025em;line-height:1.25;margin:0}
h3{font-size:14px;font-weight:650;line-height:1.5;margin:0}.hero p{margin:0;color:var(--muted);
max-width:650px}.hero-meta{text-align:right;flex-shrink:0;font-size:12px}.hero-meta p{margin-top:8px}
.badge{display:inline-block;border:1px solid #cbd7de;background:#edf2f5;color:#466174;
border-radius:5px;padding:3px 8px;font-size:10px;line-height:1.5;letter-spacing:.02em;font-weight:650}
.badge.teal{color:#11685f;border-color:#b5dbd2;background:#e9f6f0}
.badge.amber{color:#815000;border-color:#e7ce9e;background:#fff5df}
.badge.red{color:#962d32;border-color:#ebbec1;background:#fff0f0}
.synthetic{border-radius:30px;padding:5px 12px;letter-spacing:.08em;text-transform:uppercase}
.scope-note{background:#e9f0f3;border:1px solid #d3e1e6;border-left:3px solid #2b7d82;
border-radius:5px;padding:12px 16px;color:#3b5a6b;font-size:12px;margin-bottom:24px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:34px}
.stat{background:#fff;border:1px solid var(--line);border-radius:8px;padding:20px 22px}
.stat strong{display:block;font-size:38px;letter-spacing:-.05em;line-height:1.2;margin:7px 0}
.stat small{color:var(--muted);font-size:11px}.stat.red strong{color:var(--red)}
.stat.amber strong{color:var(--amber)}.section{margin-bottom:32px;scroll-margin-top:20px}
.section-heading{display:flex;align-items:center;justify-content:space-between;gap:18px;margin:0 0 16px}
.section-heading p{color:var(--muted);font-size:12px;margin:5px 0 0}.section-index{color:#8da2ad;
font-size:11px;letter-spacing:.1em;font-weight:700;margin-right:10px}
.findings-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.finding{border:1px solid var(--line);border-left:3px solid #8ba8b3;background:#fff;
border-radius:6px;padding:15px 18px;min-width:0}.finding.red{border-left-color:#c15054}
.finding.amber{border-left-color:#c8973c}.finding.teal{border-left-color:#3f9b90}
.finding-meta{display:flex;align-items:center;gap:12px;margin-bottom:9px;color:var(--muted);font-size:11px}
.finding-code{font-family:Consolas,monospace;color:#647e8e;font-size:10px;margin:7px 0 10px}
.more-findings{margin-top:14px;border:1px solid var(--line);padding:12px 16px;border-radius:6px}
.more-findings>.findings-grid{margin-top:14px}.mono{font-family:Consolas,"SFMono-Regular",monospace}
details summary{cursor:pointer;font-size:11px;color:#365f73;font-weight:600;width:fit-content}
details[open]>summary{margin-bottom:12px}pre{font:11px/1.65 Consolas,monospace;white-space:pre-wrap;
overflow-wrap:anywhere;border-radius:5px;background:#edf3f5;padding:14px;margin:10px 0 0}
.table-wrap{overflow-x:auto;border:1px solid var(--line);background:#fff;border-radius:8px}
table{width:100%;border-collapse:collapse;font-size:12px;text-align:left}
caption{text-align:left;padding:16px 18px;color:var(--muted);font-size:11px;caption-side:bottom}
thead{background:#eaf0f3;color:#486474}thead th{font-size:10px;white-space:nowrap;letter-spacing:.025em}
th,td{padding:16px 18px;border-bottom:1px solid #e6edef}tbody tr:last-child>*{border-bottom:0}
th[scope=row]{font-weight:600}.numeric{font-variant-numeric:tabular-nums;text-align:right}
td small{display:block;color:var(--muted);font-size:10px;margin-top:4px}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:20px;min-width:0}
.card-top{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;margin-bottom:22px}
.resource-metric{margin-bottom:16px}.resource-metric>div:first-child{display:flex;
justify-content:space-between;font-size:11px;margin-bottom:7px}.resource-metric strong{font-weight:650}
.track{height:6px;background:#e5eef0;border-radius:10px;overflow:hidden}.track span{display:block;
height:100%;background:#31988c;border-radius:10px}.historical .track span{background:#94a7b1}
.track.absent{background:repeating-linear-gradient(90deg,#d9e2e7 0,#d9e2e7 5px,transparent 5px,
transparent 9px)}.mini-facts{margin:22px 0 18px;font-size:11px}.mini-facts>div{display:flex;
justify-content:space-between;gap:10px;padding:5px 0}.mini-facts dt{color:var(--muted)}
.mini-facts dd{margin:0;text-align:right}.protection-row{display:flex;align-items:center;
justify-content:space-between;gap:12px;margin-top:20px}.age{display:block;font-size:25px;
font-weight:600;letter-spacing:-.03em;margin-top:4px}.divided{border-top:1px solid var(--line);padding-top:18px}
.muted{color:var(--muted);font-size:11px;margin:8px 0 18px}.footnote{font-size:11px;color:var(--muted);
margin-top:12px}.evidence-panel{background:#e8eff2;border:1px solid #d5e1e6;border-radius:8px;padding:20px}
.evidence-panel ul{padding-left:20px;color:#476372;font-size:12px}.evidence-panel li{margin-bottom:8px}
.provenance{display:grid;grid-template-columns:1fr 2fr;gap:16px;margin:16px 0;font-size:11px}
.provenance dt{color:var(--muted)}.provenance dd{margin:0;overflow-wrap:anywhere}
.empty{padding:20px;border:1px dashed #c5d4dc;color:var(--muted)}
footer{border-top:1px solid #d5e1e6;margin-top:36px;padding:22px 0 32px;display:flex;
justify-content:space-between;gap:16px;font-size:11px;color:var(--muted)}
@media(max-width:950px){.shell{padding:0 24px}.cards{grid-template-columns:1fr}.hero{align-items:flex-start;
flex-direction:column}.hero-meta{text-align:left}.protection-row{justify-content:flex-start;gap:24px}
.card-top{justify-content:flex-start;gap:16px}.stats{gap:10px}.stat{padding:16px}}
@media(max-width:600px){.shell{padding:0 16px}.topbar nav{gap:12px;font-size:11px}.brand{font-size:11px;
gap:6px}.brand-mark{font-size:22px}.topbar .shell{min-height:60px}.hero{padding-top:26px}
.stats{grid-template-columns:repeat(2,1fr);gap:10px}.findings-grid{grid-template-columns:1fr}
.section-heading{align-items:flex-start}.section-index{display:none}.stat strong{font-size:32px}
th,td{padding:13px}.hero-meta{font-size:11px}.provenance{grid-template-columns:1fr;gap:6px}
footer{flex-direction:column}.scope-note{font-size:11px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{body{background:#fff;font-size:10px}.shell{max-width:none;padding:0}.topbar{background:#fff;
color:var(--ink);border-bottom:1px solid #bbb}.topbar nav,.skip{display:none}.hero{padding:20px 0}
.hero-meta{text-align:left}h1{font-size:28px}.stats{margin-bottom:20px}.stat{padding:12px}
.stat strong{font-size:25px}.card,.finding,.stat,tr{break-inside:avoid}.cards{grid-template-columns:1fr}
.section{break-inside:auto;margin-bottom:22px}.table-wrap{overflow:visible}th,td{padding:8px}
details>summary{font-size:10px}.more-findings>*,details>pre{display:block!important}
.findings-grid{grid-template-columns:1fr}.provenance{grid-template-columns:1fr 2fr}footer{margin-top:16px}
*{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
"""


def render_html(report: dict) -> str:
    """Render synthetic report data without scripts, network assets, or live claims.

    The analytics engine owns calculations and severity. This presentation formats
    supplied values and counts findings; it does not infer health from missing data.
    """
    if report.get("data_classification") != "synthetic":
        raise ValueError("HTML report requires explicitly synthetic data")
    services = report.get("services", [])
    findings = report.get("findings", [])
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings = sorted(findings, key=lambda item: severity_order.get(item.get("severity"), 3))
    counts = Counter(item.get("severity") for item in findings)
    stale = sum(
        service.get(feed, {}).get("is_fresh") is False
        for service in services
        for feed in ("checks", "resources")
    )
    unknown = sum(
        service.get(feed, {}).get("is_fresh") not in (True, False)
        for service in services
        for feed in ("checks", "resources")
    )
    priority_count = max(4, counts["critical"])
    primary = "".join(_finding(item) for item in findings[:priority_count])
    secondary = "".join(_finding(item) for item in findings[priority_count:])
    attention = (
        f'<div class="findings-grid">{primary}</div>'
        if primary
        else '<p class="empty">No findings in this report. Missing evidence is not proof of health.</p>'
    )
    if secondary:
        attention += (
            '<details class="more-findings"><summary>'
            f"{len(findings) - priority_count} more observations · expand to review all evidence"
            f'</summary><div class="findings-grid">{secondary}</div></details>'
        )
    checks_rows = "".join(_service_row(item) for item in services)
    resource_cards = "".join(_resource_card(item) for item in services)
    protection_cards = "".join(_protection_card(item) for item in services)
    jobs_rows = "".join(_jobs_row(item) for item in services)
    limitations = "".join(f"<li>{_text(item)}</li>" for item in report.get("limitations", []))
    provenance = report.get("provenance", {})
    provenance_html = "".join(
        f'<dt>{_text(label)}</dt><dd class="mono">{_text(provenance.get(key))}</dd>'
        for label, key in (
            ("Execution", "execution"),
            ("Generator version", "generator_version"),
            ("Seed", "seed"),
            ("Duplicate events removed", "duplicate_events_removed"),
            ("Dataset SHA-256", "dataset_sha256"),
        )
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer"><title>Server &amp; App Operations Insights · Synthetic report</title>
<style>{_CSS}</style></head><body>
<a class="skip" href="#overview">Skip to report</a>
<header class="topbar"><div class="shell"><div class="brand"><span class="brand-mark" aria-hidden="true">▦</span> OPERATIONS INSIGHTS</div>
<nav aria-label="Report sections"><a href="#attention">Attention</a><a href="#services">Services</a><a href="#evidence">Evidence</a></nav></div></header>
<main id="overview" class="shell">
<div class="hero"><div><span class="eyebrow">Server &amp; App Operations Insights / Snapshot report</span>
<h1>Know what needs attention.</h1><p>Service checks, resource pressure, recovery evidence and unfinished work.<br>Every observation is backed by inspectable facts.</p></div>
<div class="hero-meta"><span class="badge teal synthetic">Synthetic demonstration</span>
<p>Cutoff (exclusive): <span class="mono">{_text(report.get("as_of"))}</span><br>
Window begins: <span class="mono">{_text(report.get("window_start"))}</span></p></div></div>
<div class="scope-note"><strong>Reproducible local snapshot.</strong> All observations are synthetic and do not describe an actual server. Freshness is evaluated at the fixed report cutoff, not the time you open this file.</div>
<div class="stats" aria-label="Report summary">
<div class="stat"><span class="eyebrow">Services in scope</span><strong>{len(services)}</strong><small>Generic demonstration aliases</small></div>
<div class="stat red"><span class="eyebrow">Critical observations</span><strong>{counts["critical"]}</strong><small>Findings, not distinct incidents</small></div>
<div class="stat amber"><span class="eyebrow">Warnings</span><strong>{counts["warning"]}</strong><small>Thresholds and evidence gaps</small></div>
<div class="stat"><span class="eyebrow">Stale data feeds</span><strong>{stale}</strong><small>Checks + resources · {unknown} freshness unknown</small></div>
</div>
<section class="section" id="attention" aria-labelledby="attention-title"><div class="section-heading"><div>
<h2 id="attention-title"><span class="section-index">01</span>Attention queue</h2><p>Ordered by rule severity. Open a finding to see its supporting measurements.</p></div>
<span class="badge">{len(findings)} observations</span></div>{attention}</section>
<section class="section" id="services" aria-labelledby="services-title"><div class="section-heading"><div>
<h2 id="services-title"><span class="section-index">02</span>Service visibility</h2><p>Read success and coverage together. A stale “up” observation does not establish current status.</p></div></div>
<div class="table-wrap"><table><caption>Sampled success = up / known up-or-down slots. Known coverage = known / expected slots. Neither measures continuous uptime.</caption>
<thead><tr><th scope="col">Service</th><th scope="col">Status at cutoff</th><th scope="col" class="numeric">Sampled success</th><th scope="col" class="numeric">Known coverage</th><th scope="col" class="numeric">Down slots</th><th scope="col" class="numeric">Missing</th><th scope="col" class="numeric">Unknown</th></tr></thead>
<tbody>{checks_rows}</tbody></table></div></section>
<section class="section" aria-labelledby="resource-title"><div class="section-heading"><div>
<h2 id="resource-title"><span class="section-index">03</span>Resource observations</h2><p>Latest available sample per service. Grey bars are historical values; missing values stay unknown.</p></div></div>
<div class="cards">{resource_cards}</div><p class="footnote">Single samples do not establish sustained pressure or a storage exhaustion forecast.</p></section>
<section class="section" aria-labelledby="protection-title"><div class="section-heading"><div>
<h2 id="protection-title"><span class="section-index">04</span>Data protection &amp; recovery</h2><p>Backup freshness and restore evidence are separate checks. Ages are measured at the report cutoff.</p></div></div>
<div class="cards">{protection_cards}</div><p class="footnote">A successful backup, including checksum verification, does not prove recoverability. Restore records do not identify the backup generation tested.</p></section>
<section class="section" aria-labelledby="jobs-title"><div class="section-heading"><div>
<h2 id="jobs-title"><span class="section-index">05</span>Application work</h2><p>Final outcomes, retry overhead and pending work at the report cutoff.</p></div></div>
<div class="table-wrap"><table><caption>Completed runs finish inside the reporting window. Pending runs can begin earlier. Retries count attempts minus one for included runs.</caption>
<thead><tr><th scope="col">Service</th><th scope="col" class="numeric">Completed</th><th scope="col" class="numeric">Success</th><th scope="col" class="numeric">Failed</th><th scope="col" class="numeric">Retries</th><th scope="col" class="numeric">Running</th><th scope="col" class="numeric">Blocked</th><th scope="col" class="numeric">Over age target</th></tr></thead><tbody>{jobs_rows}</tbody></table></div>
<details class="more-findings"><summary>Inspect all service metrics</summary><pre>{escape(json.dumps(services, ensure_ascii=False, indent=2, sort_keys=True), quote=True)}</pre></details></section>
<section class="section evidence-panel" id="evidence" aria-labelledby="evidence-title"><div class="section-heading"><div>
<h2 id="evidence-title"><span class="section-index">06</span>Evidence &amp; interpretation</h2><p>Deterministic calculations. No model-generated explanation is included in this report.</p></div></div>
<dl class="provenance">{provenance_html}</dl>
<details><summary>Read metric definitions and limitations ({len(report.get("limitations", []))})</summary><ul>{limitations}</ul></details>
</section>
<footer><span>Server &amp; App Operations Insights · Matej Bicej</span><span>Synthetic data · Local report · Schema {_text(report.get("schema_version"))}</span></footer>
</main></body></html>
"""
