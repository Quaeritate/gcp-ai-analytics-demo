"""Synthetic operations reports and explicitly gated cloud workflows."""

import argparse
import hashlib
import sys
from pathlib import Path

from pydantic import ValidationError

from .analytics import build_report
from .contracts import Dataset
from .generate_data import generate_dataset
from .html_report import render_html
from .reporting import canonical_json, render_markdown

MAX_INPUT_BYTES = 20 * 1024 * 1024


def _write_outputs(output: Path, files: dict[str, str]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = output / name
        if path.exists() and path.read_bytes() != content.encode("utf-8"):
            raise ValueError(f"Existing output differs: {path}. Choose a new output directory.")
    for name, content in files.items():
        path = output / name
        if not path.exists():
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)


def _read_dataset(path: Path) -> Dataset:
    with path.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Input exceeds the 20 MiB local limit")
    return Dataset.model_validate_json(raw)


def _local_report(dataset: Dataset) -> dict:
    report = build_report(dataset)
    report["provenance"] = {
        "dataset_sha256": hashlib.sha256(
            canonical_json(dataset.model_dump(mode="json")).encode()
        ).hexdigest(),
        "seed": dataset.seed,
        "generator_version": dataset.generator_version,
        "duplicate_events_removed": dataset.duplicates_removed,
        "execution": "local_only",
    }
    return report


def _report_files(report: dict) -> dict[str, str]:
    return {
        "report.json": canonical_json(report),
        "report.md": render_markdown(report),
        "report.html": render_html(report),
    }


def _cloud_command(args: argparse.Namespace) -> int:
    from .bigquery_pipeline import (
        BigQueryRunner,
        BigQuerySettings,
        build_verified_report,
        export_dataset,
        plan_bigquery,
    )
    from .evaluation import evaluate_cases, validate_corpus
    from .gemini_client import GeminiSettings, render_triage, triage_report

    execute = getattr(args, "execute", False)
    if execute:
        # Raw cloud receipts may contain project/job IDs. Keep them out of public examples.
        private_root = (Path.cwd() / "artifacts" / "local").resolve()
        if not args.output.resolve().is_relative_to(private_root):
            raise ValueError("Live output must be inside artifacts/local/ (ignored by Git)")
        if args.output.exists():
            raise ValueError("Live execution requires a new output directory to preserve evidence")
        if not args.project:
            raise ValueError("Live execution requires --project")
        args.output.mkdir(parents=True)
        _write_outputs(
            args.output,
            {
                "execution-started.json": canonical_json(
                    {
                        "command": args.command,
                        "project": args.project,
                        "status": "started_not_yet_verified",
                        "automatic_resubmission": False,
                    }
                )
            },
        )
    if args.command == "evaluate-ai":
        result = (
            evaluate_cases(
                execute=True,
                settings=GeminiSettings(project=args.project),
                record_dir=args.output / "cases",
            )
            if execute
            else validate_corpus()
        )
        _write_outputs(args.output, {"evaluation.json": canonical_json(result)})
        print(f"Evaluation record: {(args.output / 'evaluation.json').resolve()}")
        print("Live model evaluation attempted." if execute else "Offline corpus validation only.")
        return 0 if not execute or result.get("acceptance_passed") is True else 2

    dataset = _read_dataset(args.input)
    report = _local_report(dataset)
    if args.command == "triage":
        result = triage_report(report, GeminiSettings(project=args.project), execute=execute)
        _write_outputs(
            args.output,
            {
                "triage.json": canonical_json(result.model_dump(mode="json")),
                "triage.md": render_triage(result),
            },
        )
        print(f"Triage: {result.status}; {(args.output / 'triage.md').resolve()}")
        return 0 if result.status in {"prepared", "ok"} else 2

    settings = BigQuerySettings(args.project, args.dataset, args.location)
    if args.command != "plan-cloud" and not execute:
        raise ValueError("Cloud execution requires --execute after reviewing plan-cloud")
    bundle = export_dataset(dataset, args.output / "export")
    plan = plan_bigquery(dataset, settings, bundle)
    _write_outputs(args.output, {"bigquery-plan.json": canonical_json(plan)})
    if args.command != "run-bigquery":
        try:
            preview = triage_report(report, GeminiSettings(project=args.project))
            preview_data = preview.model_dump(mode="json")
        except ValueError:
            if args.command == "cloud-demo":
                raise
            preview_data = {
                "status": "unavailable",
                "attempted_requests": 0,
                "reason": "Report exceeds the supported AI evidence scope; BigQuery plan is valid",
            }
        _write_outputs(args.output, {"triage-preview.json": canonical_json(preview_data)})
    if args.command == "plan-cloud":
        print(f"Cloud plan: {args.output.resolve()}")
        print("Local preparation only; no cloud client or paid request created.")
        return 0
    result = BigQueryRunner(
        settings, dataset, bundle, execute=True, record_dir=args.output / "jobs"
    ).run()
    _write_outputs(args.output, {"bigquery-results.json": canonical_json(result)})
    if not result["comparison"]["matches"]:
        raise ValueError("BigQuery/local comparison failed; no AI request permitted")
    if args.command == "cloud-demo":
        verified = build_verified_report(dataset, result)
        triage = triage_report(verified, GeminiSettings(project=args.project), execute=True)
        _write_outputs(
            args.output,
            {
                **_report_files(report),
                "verified-cloud-report.json": canonical_json(verified),
                "triage.json": canonical_json(triage.model_dump(mode="json")),
                "triage.md": render_triage(triage),
                "cloud-verification.json": canonical_json(
                    {
                        "source_dataset_sha256": bundle.source_sha256,
                        "bigquery_comparison": result["comparison"],
                        "gemini_status": triage.status,
                        "interpretation_input": (
                            "returned BigQuery aggregates verified against local reference"
                        ),
                    }
                ),
            },
        )
        print(f"BigQuery comparison passed; Gemini: {triage.status}")
        return 0 if triage.status == "ok" else 2
    print(f"BigQuery comparison passed. Private execution records: {args.output.resolve()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Server & App Operations Insights — synthetic analytics"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser(
        "demo-local", help="Generate and analyze a reproducible synthetic dataset"
    )
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--output", type=Path, default=Path("artifacts/local/server-demo"))
    analyze = commands.add_parser("analyze-local", help="Analyze an explicitly synthetic dataset")
    analyze.add_argument("--input", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True)
    for name in ("plan-cloud", "run-bigquery", "cloud-demo", "triage", "evaluate-ai"):
        command = commands.add_parser(name)
        if name != "evaluate-ai":
            command.add_argument("--input", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument(
            "--project", required=name in {"plan-cloud", "run-bigquery", "cloud-demo"}
        )
        if name in {"plan-cloud", "run-bigquery", "cloud-demo"}:
            command.add_argument("--dataset", default="operations_insights")
            command.add_argument("--location", default="US")
        if name != "plan-cloud":
            command.add_argument(
                "--execute",
                action="store_true",
                help="Run approved billable cloud operations using ADC; review plan first",
            )
    args = parser.parse_args(argv)
    try:
        if args.command not in {"demo-local", "analyze-local"}:
            return _cloud_command(args)
        if args.command == "demo-local":
            dataset = generate_dataset(args.seed)
        else:
            dataset = _read_dataset(args.input)
        data_json = canonical_json(dataset.model_dump(mode="json"))
        report = _local_report(dataset)
        files = _report_files(report)
        if args.command == "demo-local":
            files["synthetic_server_data.json"] = data_json
        _write_outputs(args.output, files)
    except (OSError, ValueError, ValidationError) as exc:
        print(f"Cannot produce report: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        if args.command in {"demo-local", "analyze-local"}:
            raise
        # SDK exception messages can contain credentials, URLs or request payloads.
        print(
            f"Cloud workflow failed ({type(exc).__name__}). "
            "Inspect private execution records before retrying.",
            file=sys.stderr,
        )
        return 2
    print(f"Synthetic report: {(args.output / 'report.html').resolve()}")
    print("Local calculations only; no server connections or Google Cloud calls.")
    return 0
