import json

from gcp_ai_analytics.cli import main


def test_two_generated_runs_and_imported_analysis_are_reproducible(tmp_path):
    first, second, imported = (tmp_path / name for name in ("first", "second", "imported"))
    assert main(["demo-local", "--output", str(first)]) == 0
    assert main(["demo-local", "--output", str(second)]) == 0
    for name in ("synthetic_server_data.json", "report.json", "report.md", "report.html"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert (
        main(
            [
                "analyze-local",
                "--input",
                str(first / "synthetic_server_data.json"),
                "--output",
                str(imported),
            ]
        )
        == 0
    )
    assert (first / "report.json").read_bytes() == (imported / "report.json").read_bytes()
    report = json.loads((first / "report.json").read_text())
    assert report["provenance"]["execution"] == "local_only"
    assert "Synthetic demonstration" in (first / "report.md").read_text()


def test_existing_different_report_is_preserved(tmp_path):
    path = tmp_path / "report.md"
    path.write_text("An existing report")
    assert main(["demo-local", "--output", str(tmp_path)]) == 2
    assert path.read_text() == "An existing report"
    assert not (tmp_path / "report.json").exists()


def test_unlabeled_json_fails_without_producing_output(tmp_path):
    source = tmp_path / "input.json"
    source.write_text("{}")
    destination = tmp_path / "output"
    assert main(["analyze-local", "--input", str(source), "--output", str(destination)]) == 2
    assert not destination.exists()
