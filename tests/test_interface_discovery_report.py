from pathlib import Path

from pytest import CaptureFixture

from supervised_learning_polymers import (
    load_interface_discovery_artifact,
    render_interface_discovery_report,
    write_interface_discovery_report,
)
from supervised_learning_polymers.interface_report import main

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "interface_discovery_run.json"


def test_report_renders_expected_artifact_sections() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)

    report = render_interface_discovery_report(artifact)

    assert "# Sequential Ridge Baseline Fixture" in report
    assert "## Manifest" in report
    assert "Dataset: `open-polymer-train-fixture-v1`" in report
    assert "## Target Mode" in report
    assert "Mode: `sequential`" in report
    assert "FFV -> Density -> Tc -> Tg -> Rg" in report
    assert "## Chemistry Failures" in report
    assert "parse_error" in report
    assert "## Run Progress" in report
    assert "Fit target chain" in report
    assert "## Results" in report
    assert "mean_absolute_error" in report
    assert "## Leaderboard" in report
    assert "`run-interface-discovery-fixture-001`" in report


def test_report_can_be_persisted_for_reviewer_inspection(tmp_path: Path) -> None:
    output_path = tmp_path / "reports" / "interface-report.md"

    written_path = write_interface_discovery_report(FIXTURE_PATH, output_path)

    assert written_path == output_path
    assert output_path.read_text().startswith("# Sequential Ridge Baseline Fixture")


def test_cli_writes_report_to_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "reports" / "cli-report.md"

    exit_code = main([str(FIXTURE_PATH), "--output", str(output_path)])

    assert exit_code == 0
    assert "Chemistry Failures" in output_path.read_text()


def test_cli_prints_report_when_output_is_omitted(capsys: CaptureFixture[str]) -> None:
    exit_code = main([str(FIXTURE_PATH)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Sequential Ridge Baseline Fixture" in captured.out
    assert "Leaderboard" in captured.out
