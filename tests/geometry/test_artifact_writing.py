from json import loads
from pathlib import Path

from supervised_learning_polymers.chemistry import (
    CappingConfig,
    ChemistryAuditConfig,
    audit_dataset_row,
    chemistry_cache_key,
)
from supervised_learning_polymers.geometry import (
    GeometryArtifact,
    GeometryAttemptRecord,
    GeometryConfig,
    attempt_geometry_record,
    geometry_artifact_dir,
    geometry_cache_key,
    summarize_geometry_records,
    write_geometry_artifacts,
)
from supervised_learning_polymers.manifest import DatasetConfig


def _dataset() -> DatasetConfig:
    return DatasetConfig(
        dataset_version="open-polymer-train-fixture-v1",
        sample_id_column="id",
        smiles_column="SMILES",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )


def _chemistry() -> ChemistryAuditConfig:
    return ChemistryAuditConfig(
        config_id="chemistry-hydrogen-fixture-v1",
        capping=CappingConfig(strategy="hydrogen", version="1"),
    )


def _records() -> tuple[GeometryAttemptRecord, ...]:
    chemistry = _chemistry()
    dataset = _dataset()
    successful_chemistry_record = audit_dataset_row(
        {"id": "poly-ethanol", "SMILES": "CCO"},
        dataset,
        row_index=0,
        chemistry=chemistry,
    )
    missing_input_record = successful_chemistry_record.model_copy(
        update={"sample_id": "poly-missing-input", "capped_smiles": None}
    )

    return (
        attempt_geometry_record(
            successful_chemistry_record,
            chemistry,
            GeometryConfig(config_id="geometry-rdkit-v1", random_seed=13),
            rdkit_version="test-rdkit-version",
        ),
        attempt_geometry_record(
            missing_input_record,
            chemistry,
            GeometryConfig(config_id="geometry-rdkit-v1", random_seed=13),
            rdkit_version="test-rdkit-version",
        ),
    )


def _artifact() -> GeometryArtifact:
    dataset = _dataset()
    chemistry = _chemistry()
    geometry = GeometryConfig(config_id="geometry-rdkit-v1", random_seed=13)
    records = _records()
    return GeometryArtifact(
        dataset=dataset,
        chemistry=chemistry,
        chemistry_cache_key=chemistry_cache_key(
            dataset,
            chemistry,
            rdkit_version="test-rdkit-version",
        ),
        geometry=geometry,
        rdkit_version="test-rdkit-version",
        records=records,
        summary=summarize_geometry_records(records, total_chemistry_valid_records=2),
    )


def test_geometry_artifact_dir_uses_config_id_under_geometry_root(tmp_path: Path) -> None:
    path = geometry_artifact_dir(
        tmp_path / "artifacts",
        GeometryConfig(config_id="geometry-rdkit-v1"),
    )

    assert path == tmp_path / "artifacts" / "geometry" / "geometry-rdkit-v1"


def test_summarize_geometry_records_returns_coverage_runtime_and_failures() -> None:
    records = _records()

    summary = summarize_geometry_records(records, total_chemistry_valid_records=3)

    assert summary.total_chemistry_valid_records == 3
    assert summary.attempted_records == 2
    assert summary.successful_records == 1
    assert summary.failed_records == 1
    assert summary.skipped_records == 1
    assert summary.coverage_fraction == 1 / 3
    assert summary.total_runtime_seconds >= 0
    assert {group.failure_type: group.count for group in summary.failure_groups} == {
        "missing_input_smiles": 1
    }


def test_write_geometry_artifacts_writes_expected_bundle(tmp_path: Path) -> None:
    artifact = _artifact()
    paths = write_geometry_artifacts(
        artifact,
        tmp_path / "artifacts",
        created_at="2026-08-25T12:00:00+00:00",
    )

    assert Path(paths.artifact_root) == tmp_path / "artifacts" / "geometry" / "geometry-rdkit-v1"
    assert Path(paths.records).exists()
    assert Path(paths.failures).exists()
    assert Path(paths.summary).exists()
    assert Path(paths.metadata).exists()


def test_written_records_preserve_per_sample_sdf_and_provenance(tmp_path: Path) -> None:
    artifact = _artifact()
    paths = write_geometry_artifacts(artifact, tmp_path / "artifacts")

    records = loads(Path(paths.records).read_text())

    assert [record["sample_id"] for record in records] == [
        "poly-ethanol",
        "poly-missing-input",
    ]
    assert records[0]["status"] == "success"
    assert records[0]["sdf_text"].endswith("$$$$\n")
    assert records[0]["raw_smiles"] == "CCO"
    assert records[0]["canonical_smiles"] == "CCO"
    assert records[0]["standardized_smiles"] == "CCO"
    assert records[0]["capped_smiles"] == "CCO"
    assert records[0]["method"]["embedding_status"] == "success"


def test_written_failures_include_only_failed_geometry_attempts(tmp_path: Path) -> None:
    artifact = _artifact()
    paths = write_geometry_artifacts(artifact, tmp_path / "artifacts")

    failures = loads(Path(paths.failures).read_text())

    assert [failure["sample_id"] for failure in failures] == ["poly-missing-input"]
    assert failures[0]["failure_type"] == "missing_input_smiles"
    assert failures[0]["stage"] == "input"
    assert failures[0]["recommended_action"]


def test_written_summary_is_gui_backend_ready(tmp_path: Path) -> None:
    artifact = _artifact()
    paths = write_geometry_artifacts(artifact, tmp_path / "artifacts")

    summary = loads(Path(paths.summary).read_text())

    assert summary["total_chemistry_valid_records"] == 2
    assert summary["attempted_records"] == 2
    assert summary["successful_records"] == 1
    assert summary["failed_records"] == 1
    assert summary["coverage_fraction"] == 0.5
    assert summary["failure_groups"][0]["failure_type"] == "missing_input_smiles"


def test_written_metadata_records_cache_keys_and_readable_provenance(tmp_path: Path) -> None:
    artifact = _artifact()
    paths = write_geometry_artifacts(
        artifact,
        tmp_path / "artifacts",
        created_at="2026-08-25T12:00:00+00:00",
    )

    metadata = loads(Path(paths.metadata).read_text())

    assert metadata["artifact_version"] == "1"
    assert metadata["dataset_version"] == "open-polymer-train-fixture-v1"
    assert metadata["chemistry_config_id"] == "chemistry-hydrogen-fixture-v1"
    assert metadata["geometry_config_id"] == "geometry-rdkit-v1"
    assert metadata["rdkit_version"] == "test-rdkit-version"
    assert metadata["chemistry_cache_key"] == artifact.chemistry_cache_key
    assert metadata["geometry_cache_key"] == geometry_cache_key(
        artifact.dataset,
        artifact.chemistry,
        artifact.chemistry_cache_key,
        artifact.geometry,
        rdkit_version="test-rdkit-version",
    )
    assert metadata["chemistry_provenance"] == {
        "capping_strategy": "hydrogen",
        "capping_version": "1",
        "geometry_input_representation": "capped_smiles",
    }
    assert metadata["settings"]["input_representation"] == "capped_smiles"
    assert metadata["output_paths"] == paths.model_dump(mode="json")


def test_geometry_cache_key_changes_when_geometry_settings_change() -> None:
    dataset = _dataset()
    chemistry = _chemistry()
    chemistry_key = chemistry_cache_key(dataset, chemistry)

    first = GeometryConfig(config_id="geometry-rdkit-v1", random_seed=13)
    second = GeometryConfig(config_id="geometry-rdkit-v1", random_seed=21)

    assert geometry_cache_key(dataset, chemistry, chemistry_key, first) != geometry_cache_key(
        dataset,
        chemistry,
        chemistry_key,
        second,
    )


def test_geometry_cache_key_changes_when_rdkit_version_changes() -> None:
    dataset = _dataset()
    chemistry = _chemistry()
    chemistry_key = chemistry_cache_key(dataset, chemistry)
    geometry = GeometryConfig(config_id="geometry-rdkit-v1")

    assert geometry_cache_key(
        dataset,
        chemistry,
        chemistry_key,
        geometry,
        rdkit_version="first-version",
    ) != geometry_cache_key(
        dataset,
        chemistry,
        chemistry_key,
        geometry,
        rdkit_version="second-version",
    )


def test_geometry_cache_key_changes_when_upstream_chemistry_identity_changes() -> None:
    dataset = _dataset()
    chemistry = _chemistry()
    geometry = GeometryConfig(config_id="geometry-rdkit-v1")

    assert geometry_cache_key(dataset, chemistry, "first-chemistry-key", geometry) != (
        geometry_cache_key(dataset, chemistry, "second-chemistry-key", geometry)
    )
