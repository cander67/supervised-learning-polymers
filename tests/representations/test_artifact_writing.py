import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from supervised_learning_polymers.chemistry import (
    CappingConfig,
    ChemistryAuditConfig,
    ChemistryAuditRecord,
)
from supervised_learning_polymers.manifest import DatasetConfig
from supervised_learning_polymers.representations import (
    FeatureMatrixBundle,
    FeatureSetConfig,
    RepresentationConfig,
    feature_matrix_hash,
    feature_names_hash,
    generate_morgan_fingerprint_features,
    generate_rdkit_2d_features,
    morgan_fingerprint_feature_set_config,
    rdkit_2d_feature_set_config,
    representation_artifact_from_bundles,
    representation_cache_key,
    write_representation_artifacts,
)


def _dataset(version: str = "open-polymer-train-fixture-v1") -> DatasetConfig:
    return DatasetConfig(
        dataset_version=version,
        sample_id_column="id",
        smiles_column="SMILES",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )


def _chemistry(config_id: str = "chemistry-audit-v1") -> ChemistryAuditConfig:
    return ChemistryAuditConfig(
        config_id=config_id,
        capping=CappingConfig(strategy="hydrogen", version="1"),
    )


def _records() -> tuple[ChemistryAuditRecord, ...]:
    return (
        ChemistryAuditRecord(
            sample_id="poly-0001",
            raw_smiles="CCO",
            status="valid",
            canonical_smiles="CCO",
            standardized_smiles="CCO",
            capped_smiles="CCO",
        ),
        ChemistryAuditRecord(
            sample_id="poly-0002",
            raw_smiles="not-a-smiles",
            status="valid",
            canonical_smiles="not-a-smiles",
            standardized_smiles="not-a-smiles",
            capped_smiles="not-a-smiles",
        ),
    )


def _representation(
    descriptor_feature_set: FeatureSetConfig,
    fingerprint_feature_set: FeatureSetConfig,
    *,
    config_id: str = "fixed-vector-v1",
) -> RepresentationConfig:
    return RepresentationConfig(
        config_id=config_id,
        selected_feature_set_ids=(
            descriptor_feature_set.feature_set_id,
            fingerprint_feature_set.feature_set_id,
        ),
        feature_sets=(descriptor_feature_set, fingerprint_feature_set),
    )


def _bundles() -> tuple[RepresentationConfig, tuple[FeatureMatrixBundle, FeatureMatrixBundle]]:
    descriptor_feature_set = rdkit_2d_feature_set_config()
    fingerprint_feature_set = morgan_fingerprint_feature_set_config(size=128)
    representation = _representation(descriptor_feature_set, fingerprint_feature_set)
    records = _records()
    return representation, (
        generate_rdkit_2d_features(records, _chemistry(), feature_set=descriptor_feature_set),
        generate_morgan_fingerprint_features(
            records,
            _chemistry(),
            feature_set=fingerprint_feature_set,
        ),
    )


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_write_representation_artifacts_persists_npz_and_json_sidecars(
    tmp_path: Path,
) -> None:
    representation, bundles = _bundles()
    artifact = representation_artifact_from_bundles(
        _dataset(),
        _chemistry(),
        "chemistry-cache-key",
        representation,
        bundles,
        rdkit_version="2026.03.3",
    )

    paths = write_representation_artifacts(
        artifact,
        bundles,
        tmp_path,
        created_at="2026-09-09T00:00:00+00:00",
    )

    assert Path(paths.artifact_root) == tmp_path / "representations" / "fixed-vector-v1"
    assert Path(paths.records).name == "records.json"
    assert Path(paths.summary).name == "summary.json"
    assert Path(paths.failures).name == "failures.json"
    assert set(paths.feature_set_matrices) == {"rdkit_2d", "morgan_radius2_2048_chiral"}

    descriptor_matrix = np.load(paths.feature_set_matrices["rdkit_2d"])["features"]
    fingerprint_matrix = np.load(paths.feature_set_matrices["morgan_radius2_2048_chiral"])[
        "features"
    ]
    np.testing.assert_allclose(descriptor_matrix, bundles[0].matrix, rtol=0, atol=0)
    np.testing.assert_allclose(fingerprint_matrix, bundles[1].matrix, rtol=0, atol=0)

    assert _read_json(paths.sample_ids["rdkit_2d"]) == ["poly-0001"]
    assert _read_json(paths.feature_names["morgan_radius2_2048_chiral"])[-1] == "bit_127"
    feature_metadata = _read_json(paths.feature_set_metadata["morgan_radius2_2048_chiral"])
    assert feature_metadata["settings"]["size"] == 128
    assert feature_metadata["columns"] == 128


def test_write_representation_artifacts_records_summary_failures_metadata_and_hashes(
    tmp_path: Path,
) -> None:
    representation, bundles = _bundles()
    artifact = representation_artifact_from_bundles(
        _dataset(),
        _chemistry(),
        "chemistry-cache-key",
        representation,
        bundles,
        rdkit_version="2026.03.3",
    )

    paths = write_representation_artifacts(
        artifact,
        bundles,
        tmp_path,
        created_at="2026-09-09T00:00:00+00:00",
    )
    metadata = _read_json(paths.metadata)
    summary = _read_json(paths.summary)
    failures = _read_json(paths.failures)
    records = _read_json(paths.records)

    assert metadata["dataset_version"] == "open-polymer-train-fixture-v1"
    assert metadata["chemistry_config_id"] == "chemistry-audit-v1"
    assert metadata["chemistry_cache_key"] == "chemistry-cache-key"
    assert metadata["representation_config_id"] == "fixed-vector-v1"
    assert metadata["rdkit_version"] == "2026.03.3"
    assert metadata["created_at"] == "2026-09-09T00:00:00+00:00"
    assert metadata["content_hashes"]["rdkit_2d:matrix"] == bundles[0].metadata.matrix_hash
    assert (
        metadata["content_hashes"]["morgan_radius2_2048_chiral:feature_names"]
        == bundles[1].metadata.feature_names_hash
    )
    assert summary["attempted_records"] == 4
    assert summary["successful_records"] == 2
    assert summary["failed_representation_records"] == 2
    assert summary["dimensions"] == [
        {"columns": 217, "feature_set_id": "rdkit_2d", "rows": 1},
        {"columns": 128, "feature_set_id": "morgan_radius2_2048_chiral", "rows": 1},
    ]
    assert len(failures) == 2
    assert len(records) == 4


def test_representation_cache_key_is_deterministic_and_invalidates_on_identity_changes() -> None:
    representation, _ = _bundles()
    baseline = representation_cache_key(
        _dataset(),
        _chemistry(),
        "chemistry-cache-key",
        representation,
        rdkit_version="2026.03.3",
    )

    assert baseline == representation_cache_key(
        _dataset(),
        _chemistry(),
        "chemistry-cache-key",
        representation,
        rdkit_version="2026.03.3",
    )
    assert baseline != representation_cache_key(
        _dataset("different-dataset"),
        _chemistry(),
        "chemistry-cache-key",
        representation,
        rdkit_version="2026.03.3",
    )
    assert baseline != representation_cache_key(
        _dataset(),
        _chemistry("different-chemistry"),
        "chemistry-cache-key",
        representation,
        rdkit_version="2026.03.3",
    )
    assert baseline != representation_cache_key(
        _dataset(),
        _chemistry(),
        "different-chemistry-cache-key",
        representation,
        rdkit_version="2026.03.3",
    )
    assert baseline != representation_cache_key(
        _dataset(),
        _chemistry(),
        "chemistry-cache-key",
        _representation(
            rdkit_2d_feature_set_config(input_representation="standardized_smiles"),
            morgan_fingerprint_feature_set_config(size=128),
        ),
        rdkit_version="2026.03.3",
    )
    assert baseline != representation_cache_key(
        _dataset(),
        _chemistry(),
        "chemistry-cache-key",
        _representation(
            rdkit_2d_feature_set_config(),
            morgan_fingerprint_feature_set_config(size=256),
        ),
        rdkit_version="2026.03.3",
    )
    assert baseline != representation_cache_key(
        _dataset(),
        _chemistry(),
        "chemistry-cache-key",
        representation,
        rdkit_version="2027.01.1",
    )


def test_content_hashes_detect_matrix_and_feature_name_changes() -> None:
    matrix = np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.float64)

    assert feature_matrix_hash(matrix) == feature_matrix_hash(matrix.copy())
    assert feature_matrix_hash(matrix) != feature_matrix_hash(matrix + 1.0)
    assert feature_names_hash(("a", "b")) == feature_names_hash(("a", "b"))
    assert feature_names_hash(("a", "b")) != feature_names_hash(("b", "a"))


def test_write_representation_artifacts_rejects_missing_or_extra_bundles(tmp_path: Path) -> None:
    representation, bundles = _bundles()
    artifact = representation_artifact_from_bundles(
        _dataset(),
        _chemistry(),
        "chemistry-cache-key",
        representation,
        bundles,
    )

    with pytest.raises(ValueError, match="missing selected feature sets"):
        write_representation_artifacts(artifact, bundles[:1], tmp_path)

    descriptor_only = RepresentationConfig(
        config_id="descriptor-only",
        selected_feature_set_ids=("rdkit_2d",),
        feature_sets=(rdkit_2d_feature_set_config(),),
    )
    descriptor_artifact = representation_artifact_from_bundles(
        _dataset(),
        _chemistry(),
        "chemistry-cache-key",
        descriptor_only,
        bundles[:1],
    )
    with pytest.raises(ValueError, match="unselected feature sets"):
        write_representation_artifacts(descriptor_artifact, bundles, tmp_path)
