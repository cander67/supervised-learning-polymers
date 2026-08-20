from json import loads
from pathlib import Path

from supervised_learning_polymers import (
    build_interface_discovery_notebook,
    write_interface_discovery_notebook,
)
from supervised_learning_polymers.interface_notebook import main

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "interface_discovery_run.json"


def test_notebook_report_reads_same_fixture_artifact_as_cli_report() -> None:
    notebook = build_interface_discovery_notebook(FIXTURE_PATH)

    code_source = _joined_cell_source(notebook, 1)
    assert "load_interface_discovery_artifact" in code_source
    assert "render_interface_discovery_report" in code_source
    assert str(FIXTURE_PATH) in code_source


def test_notebook_snapshot_supports_main_review_workflow() -> None:
    notebook = build_interface_discovery_notebook(FIXTURE_PATH)

    rendered_snapshot = _joined_cell_source(notebook, 2)
    assert "## Target Mode" in rendered_snapshot
    assert "FFV -> Density -> Tc -> Tg -> Rg" in rendered_snapshot
    assert "## Chemistry Failures" in rendered_snapshot
    assert "standardization_error" in rendered_snapshot
    assert "## Manifest" in rendered_snapshot
    assert "open-polymer-train-fixture-v1" in rendered_snapshot
    assert "## Run Progress" in rendered_snapshot
    assert "## Results" in rendered_snapshot
    assert "## Leaderboard" in rendered_snapshot


def test_notebook_report_can_be_reproduced_from_fixture(tmp_path: Path) -> None:
    output_path = tmp_path / "reports" / "interface-report.ipynb"

    written_path = write_interface_discovery_notebook(FIXTURE_PATH, output_path)

    notebook = loads(written_path.read_text())
    assert written_path == output_path
    assert notebook["nbformat"] == 4
    assert "Sequential Ridge Baseline Fixture" in _joined_cell_source(notebook, 2)


def test_notebook_cli_writes_report_to_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "reports" / "cli-report.ipynb"

    exit_code = main([str(FIXTURE_PATH), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()
    assert "Fixture-Rendered Snapshot" in output_path.read_text()


def _joined_cell_source(notebook: dict[str, object], cell_index: int) -> str:
    cells = notebook["cells"]
    assert isinstance(cells, list)
    cell = cells[cell_index]
    assert isinstance(cell, dict)
    source = cell["source"]
    assert isinstance(source, list)
    return "".join(str(line) for line in source)
