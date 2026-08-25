from json import loads
from pathlib import Path
from tomllib import loads as load_toml

import pytest

from supervised_learning_polymers.chemistry import (
    CappingConfig,
    ChemistryAuditConfig,
    audit_dataset_rows,
    write_chemistry_audit_artifacts,
)
from supervised_learning_polymers.geometry_cli import main
from supervised_learning_polymers.manifest import DatasetConfig


def _dataset() -> DatasetConfig:
    return DatasetConfig(
        dataset_version="open-polymer-train-fixture-v1",
        sample_id_column="id",
        smiles_column="SMILES",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )


def _write_chemistry_artifacts(tmp_path: Path) -> Path:
    chemistry = ChemistryAuditConfig(
        config_id="chemistry-hydrogen-fixture-v1",
        capping=CappingConfig(strategy="hydrogen", version="1"),
    )
    artifact = audit_dataset_rows(
        (
            {"id": "poly-ethanol", "SMILES": "CCO"},
            {"id": "poly-invalid", "SMILES": "not-a-smiles"},
        ),
        _dataset(),
        chemistry,
        rdkit_version="test-rdkit-version",
    )
    paths = write_chemistry_audit_artifacts(
        artifact,
        tmp_path / "artifacts",
        created_at="2026-08-25T12:00:00+00:00",
    )
    return Path(paths.artifact_root)


def test_project_script_exposes_geometry_feasibility_command() -> None:
    pyproject = load_toml(Path("pyproject.toml").read_text())

    assert (
        pyproject["project"]["scripts"]["slp-geometry-feasibility"]
        == "supervised_learning_polymers.geometry_cli:main"
    )


def test_cli_writes_geometry_artifacts_from_chemistry_artifact_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chemistry_artifact_root = _write_chemistry_artifacts(tmp_path)

    result = main(
        (
            str(chemistry_artifact_root),
            "--output-root",
            str(tmp_path / "geometry-artifacts"),
            "--geometry-config-id",
            "geometry-cli-fixture-v1",
            "--input-representation",
            "capped_smiles",
            "--random-seed",
            "13",
            "--embed-attempts",
            "5",
            "--optimization-max-iterations",
            "250",
            "--fallback-methods",
            "xtb,mlip",
        )
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "total_chemistry_valid=1 attempted=1 success=1 failed=0" in output
    assert "skipped_chemistry_failed=1" in output
    assert "coverage=100.00%" in output

    artifact_root = tmp_path / "geometry-artifacts" / "geometry" / "geometry-cli-fixture-v1"
    records = loads((artifact_root / "records.json").read_text())
    failures = loads((artifact_root / "failures.json").read_text())
    summary = loads((artifact_root / "summary.json").read_text())
    metadata = loads((artifact_root / "metadata.json").read_text())

    assert [record["sample_id"] for record in records] == ["poly-ethanol"]
    assert records[0]["status"] == "success"
    assert records[0]["sdf_text"].endswith("$$$$\n")
    assert failures == []
    assert summary["total_chemistry_valid_records"] == 1
    assert summary["successful_records"] == 1
    assert metadata["chemistry_config_id"] == "chemistry-hydrogen-fixture-v1"
    assert metadata["settings"]["fallback_methods"] == ["xtb", "mlip"]


def test_cli_accepts_records_json_path_and_uncapped_input_representation(
    tmp_path: Path,
) -> None:
    chemistry_artifact_root = _write_chemistry_artifacts(tmp_path)

    result = main(
        (
            str(chemistry_artifact_root / "records.json"),
            "--output-root",
            str(tmp_path / "geometry-artifacts"),
            "--geometry-config-id",
            "geometry-standardized-fixture-v1",
            "--input-representation",
            "standardized_smiles",
        )
    )

    assert result == 0
    records = loads(
        (
            tmp_path
            / "geometry-artifacts"
            / "geometry"
            / "geometry-standardized-fixture-v1"
            / "records.json"
        ).read_text()
    )

    assert records[0]["input_representation"] == "standardized_smiles"
    assert records[0]["selected_input_smiles"] == "CCO"
