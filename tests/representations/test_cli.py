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
from supervised_learning_polymers.manifest import DatasetConfig
from supervised_learning_polymers.representation_cli import main


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
            {"id": "poly-benzene", "SMILES": "c1ccccc1"},
            {"id": "poly-invalid", "SMILES": "not-a-smiles"},
        ),
        _dataset(),
        chemistry,
        rdkit_version="test-rdkit-version",
    )
    paths = write_chemistry_audit_artifacts(
        artifact,
        tmp_path / "artifacts",
        created_at="2026-09-09T12:00:00+00:00",
    )
    return Path(paths.artifact_root)


def test_project_script_exposes_representation_command() -> None:
    pyproject = load_toml(Path("pyproject.toml").read_text())

    assert (
        pyproject["project"]["scripts"]["slp-representations"]
        == "supervised_learning_polymers.representation_cli:main"
    )


def test_cli_writes_default_descriptor_and_fingerprint_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    chemistry_artifact_root = _write_chemistry_artifacts(tmp_path)

    result = main(
        (
            str(chemistry_artifact_root),
            "--output-root",
            str(tmp_path / "representation-artifacts"),
            "--representation-config-id",
            "fixed-vector-cli-fixture-v1",
            "--morgan-size",
            "128",
        )
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "total_chemistry_valid=2 attempted=4 success=4 failed=0" in output
    assert "skipped_chemistry_failed=1" in output
    assert "rdkit_2d=2x217" in output
    assert "morgan_radius2_2048_chiral=2x128" in output
    assert "Representation cache key:" in output

    artifact_root = (
        tmp_path / "representation-artifacts" / "representations" / "fixed-vector-cli-fixture-v1"
    )
    metadata = loads((artifact_root / "metadata.json").read_text())
    summary = loads((artifact_root / "summary.json").read_text())
    failures = loads((artifact_root / "failures.json").read_text())
    descriptor_samples = loads(
        (artifact_root / "features" / "rdkit_2d" / "sample_ids.json").read_text()
    )
    fingerprint_metadata = loads(
        (artifact_root / "features" / "morgan_radius2_2048_chiral" / "metadata.json").read_text()
    )

    assert metadata["chemistry_config_id"] == "chemistry-hydrogen-fixture-v1"
    assert metadata["feature_sets"][0]["feature_set_id"] == "rdkit_2d"
    assert metadata["feature_sets"][1]["settings"]["size"] == 128
    assert summary["successful_records"] == 4
    assert failures == []
    assert descriptor_samples == ["poly-ethanol", "poly-benzene"]
    assert fingerprint_metadata["columns"] == 128
    assert (artifact_root / "features" / "rdkit_2d" / "matrix.npz").exists()
    assert (artifact_root / "features" / "morgan_radius2_2048_chiral" / "matrix.npz").exists()


def test_cli_accepts_descriptor_only_selection(tmp_path: Path) -> None:
    chemistry_artifact_root = _write_chemistry_artifacts(tmp_path)

    result = main(
        (
            str(chemistry_artifact_root / "records.json"),
            "--output-root",
            str(tmp_path / "representation-artifacts"),
            "--representation-config-id",
            "descriptor-only-fixture-v1",
            "--feature-set-ids",
            "rdkit_2d",
        )
    )

    assert result == 0
    artifact_root = (
        tmp_path / "representation-artifacts" / "representations" / "descriptor-only-fixture-v1"
    )
    metadata = loads((artifact_root / "metadata.json").read_text())
    summary = loads((artifact_root / "summary.json").read_text())

    assert [feature["feature_set_id"] for feature in metadata["feature_sets"]] == ["rdkit_2d"]
    assert summary["attempted_records"] == 2
    assert not (artifact_root / "features" / "morgan_radius2_2048_chiral").exists()


def test_cli_accepts_fingerprint_only_selection_and_settings(tmp_path: Path) -> None:
    chemistry_artifact_root = _write_chemistry_artifacts(tmp_path)

    result = main(
        (
            str(chemistry_artifact_root),
            "--output-root",
            str(tmp_path / "representation-artifacts"),
            "--representation-config-id",
            "fingerprint-only-fixture-v1",
            "--feature-set-ids",
            "morgan_radius2_2048_chiral",
            "--input-representation",
            "standardized_smiles",
            "--morgan-size",
            "64",
            "--morgan-radius",
            "1",
            "--morgan-mode",
            "count",
            "--no-morgan-chirality",
        )
    )

    assert result == 0
    artifact_root = (
        tmp_path / "representation-artifacts" / "representations" / "fingerprint-only-fixture-v1"
    )
    metadata = loads((artifact_root / "metadata.json").read_text())
    feature_metadata = loads(
        (artifact_root / "features" / "morgan_radius2_2048_chiral" / "metadata.json").read_text()
    )
    records = loads((artifact_root / "records.json").read_text())

    assert [feature["feature_set_id"] for feature in metadata["feature_sets"]] == [
        "morgan_radius2_2048_chiral"
    ]
    assert feature_metadata["columns"] == 64
    assert feature_metadata["settings"] == {
        "include_chirality": False,
        "mode": "count",
        "radius": 1,
        "size": 64,
    }
    assert records[0]["input_representation"] == "standardized_smiles"
    assert records[0]["selected_input_smiles"] == "CCO"


def test_cli_rejects_unknown_feature_set(tmp_path: Path) -> None:
    chemistry_artifact_root = _write_chemistry_artifacts(tmp_path)

    with pytest.raises(ValueError, match="unknown feature sets"):
        main((str(chemistry_artifact_root), "--feature-set-ids", "not-real"))
