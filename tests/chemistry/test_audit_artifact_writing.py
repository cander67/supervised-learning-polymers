from json import loads
from pathlib import Path

from supervised_learning_polymers.chemistry import (
    CappingConfig,
    ChemistryAuditArtifact,
    ChemistryAuditConfig,
    audit_dataset_rows,
    chemistry_artifact_dir,
    chemistry_cache_key,
    write_chemistry_audit_artifacts,
)
from supervised_learning_polymers.manifest import DatasetConfig


def _dataset() -> DatasetConfig:
    return DatasetConfig(
        dataset_version="open-polymer-train-fixture-v1",
        sample_id_column="id",
        smiles_column="SMILES",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )


def _artifact() -> ChemistryAuditArtifact:
    return audit_dataset_rows(
        (
            {"id": "poly-valid", "SMILES": "*CC*"},
            {"id": "poly-invalid", "SMILES": "not-a-smiles"},
            {"id": "poly-missing", "SMILES": None},
        ),
        _dataset(),
        ChemistryAuditConfig(
            config_id="chemistry-hydrogen-fixture-v1",
            capping=CappingConfig(strategy="hydrogen", version="1"),
        ),
        rdkit_version="test-rdkit-version",
    )


def test_chemistry_artifact_dir_uses_config_id_under_chemistry_root(tmp_path: Path) -> None:
    path = chemistry_artifact_dir(
        tmp_path / "artifacts",
        ChemistryAuditConfig(config_id="chemistry-hydrogen-fixture-v1"),
    )

    assert path == tmp_path / "artifacts" / "chemistry" / "chemistry-hydrogen-fixture-v1"


def test_write_chemistry_audit_artifacts_writes_expected_bundle(tmp_path: Path) -> None:
    artifact = _artifact()
    paths = write_chemistry_audit_artifacts(
        artifact,
        tmp_path / "artifacts",
        created_at="2026-08-24T12:00:00+00:00",
    )

    assert Path(paths.artifact_root) == (
        tmp_path / "artifacts" / "chemistry" / "chemistry-hydrogen-fixture-v1"
    )
    assert Path(paths.records).exists()
    assert Path(paths.failures).exists()
    assert Path(paths.summary).exists()
    assert Path(paths.metadata).exists()


def test_written_records_preserve_detailed_per_sample_outputs(tmp_path: Path) -> None:
    artifact = _artifact()
    paths = write_chemistry_audit_artifacts(artifact, tmp_path / "artifacts")

    records = loads(Path(paths.records).read_text())

    assert [record["sample_id"] for record in records] == [
        "poly-valid",
        "poly-invalid",
        "poly-missing",
    ]
    assert records[0]["raw_smiles"] == "*CC*"
    assert records[0]["canonical_smiles"] == "*CC*"
    assert records[0]["standardized_smiles"] == "*CC*"
    assert records[0]["capped_smiles"] == "[H]CC[H]"
    assert records[0]["attachment_points"] == ["*:0", "*:3"]


def test_written_failures_include_only_failed_samples_for_triage(tmp_path: Path) -> None:
    artifact = _artifact()
    paths = write_chemistry_audit_artifacts(artifact, tmp_path / "artifacts")

    failures = loads(Path(paths.failures).read_text())

    assert [failure["sample_id"] for failure in failures] == ["poly-invalid", "poly-missing"]
    assert {failure["failure_type"] for failure in failures} == {"missing_smiles", "parse_error"}
    assert {failure["stage"] for failure in failures} == {"input", "parse"}


def test_written_summary_is_gui_backend_ready(tmp_path: Path) -> None:
    artifact = _artifact()
    paths = write_chemistry_audit_artifacts(artifact, tmp_path / "artifacts")

    summary = loads(Path(paths.summary).read_text())

    assert summary["total_records"] == 3
    assert summary["valid_records"] == 1
    assert summary["failed_records"] == 2
    assert {group["failure_type"]: group["count"] for group in summary["failure_groups"]} == {
        "missing_smiles": 1,
        "parse_error": 1,
    }
    assert all(group["recommended_action"] for group in summary["failure_groups"])


def test_written_metadata_records_config_identity_and_cache_key(tmp_path: Path) -> None:
    artifact = _artifact()
    paths = write_chemistry_audit_artifacts(
        artifact,
        tmp_path / "artifacts",
        created_at="2026-08-24T12:00:00+00:00",
    )

    metadata = loads(Path(paths.metadata).read_text())

    assert metadata["artifact_version"] == "1"
    assert metadata["dataset_version"] == "open-polymer-train-fixture-v1"
    assert metadata["chemistry_config_id"] == "chemistry-hydrogen-fixture-v1"
    assert metadata["rdkit_version"] == "test-rdkit-version"
    assert metadata["cache_key"] == chemistry_cache_key(
        artifact.dataset,
        artifact.chemistry,
        rdkit_version="test-rdkit-version",
    )
    assert metadata["created_at"] == "2026-08-24T12:00:00+00:00"
    assert metadata["settings"]["capping"]["strategy"] == "hydrogen"
    assert metadata["output_paths"] == paths.model_dump(mode="json")


def test_cache_key_changes_when_dataset_identity_changes() -> None:
    config = ChemistryAuditConfig(config_id="chemistry-cache-v1")
    first = DatasetConfig(
        dataset_version="open-polymer-train-fixture-v1",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )
    second = DatasetConfig(
        dataset_version="open-polymer-train-fixture-v2",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )

    assert chemistry_cache_key(first, config) != chemistry_cache_key(second, config)


def test_cache_key_changes_when_chemistry_config_id_changes() -> None:
    first = ChemistryAuditConfig(config_id="chemistry-cache-v1")
    second = ChemistryAuditConfig(config_id="chemistry-cache-v2")

    assert chemistry_cache_key(_dataset(), first) != chemistry_cache_key(_dataset(), second)
