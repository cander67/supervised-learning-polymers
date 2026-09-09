from pathlib import Path

import pytest
from pydantic import ValidationError

from supervised_learning_polymers.chemistry import (
    CappingConfig,
    ChemistryAuditConfig,
    ChemistryAuditRecord,
)
from supervised_learning_polymers.manifest import DatasetConfig
from supervised_learning_polymers.representations import (
    FeatureSetConfig,
    FeatureSetDimension,
    RepresentationArtifact,
    RepresentationArtifactPaths,
    RepresentationAttemptRecord,
    RepresentationConfig,
    RepresentationFailureGroup,
    RepresentationFailureRecord,
    RepresentationOutputMetadata,
    RepresentationSummary,
    representation_artifact_dir,
    representation_cache_key,
)


def _dataset() -> DatasetConfig:
    return DatasetConfig(
        dataset_version="open-polymer-train-fixture-v1",
        sample_id_column="id",
        smiles_column="SMILES",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )


def _chemistry() -> ChemistryAuditConfig:
    return ChemistryAuditConfig(
        config_id="chemistry-audit-v1",
        capping=CappingConfig(strategy="hydrogen", version="1"),
    )


def _chemistry_record() -> ChemistryAuditRecord:
    return ChemistryAuditRecord(
        sample_id="poly-0001",
        raw_smiles="*CC(*)c1ccccc1",
        status="valid",
        canonical_smiles="*CC(*)c1ccccc1",
        standardized_smiles="*CC(*)c1ccccc1",
        capped_smiles="[H]CC([H])c1ccccc1",
        attachment_points=("*:0", "*:3"),
    )


def _descriptor_feature_set() -> FeatureSetConfig:
    return FeatureSetConfig(
        feature_set_id="rdkit_2d",
        family="descriptor",
        version="1",
        rdkit_method="rdkit.Chem.Descriptors",
        settings={"descriptor_family": "all_named_2d"},
        output_shape=(1, 217),
        feature_name_policy="named",
        hash_identity_fields=(
            "feature_set_id",
            "family",
            "version",
            "input_representation",
            "rdkit_method",
            "settings",
            "output_shape",
            "feature_name_policy",
        ),
    )


def _fingerprint_feature_set() -> FeatureSetConfig:
    return FeatureSetConfig(
        feature_set_id="morgan_radius2_2048_chiral",
        family="fingerprint",
        version="1",
        rdkit_method="rdkit.Chem.rdFingerprintGenerator.GetMorganGenerator",
        settings={"radius": 2, "size": 2048, "include_chirality": True, "mode": "bit"},
        output_shape=(1, 2048),
        feature_name_policy="bit_index",
        hash_identity_fields=(
            "feature_set_id",
            "family",
            "version",
            "input_representation",
            "rdkit_method",
            "settings",
            "output_shape",
            "feature_name_policy",
        ),
    )


def _representation() -> RepresentationConfig:
    return RepresentationConfig(
        config_id="fixed-vector-v1",
        selected_feature_set_ids=("rdkit_2d", "morgan_radius2_2048_chiral"),
        feature_sets=(_descriptor_feature_set(), _fingerprint_feature_set()),
    )


def test_representation_config_records_feature_selection_and_defaults() -> None:
    representation = _representation()

    assert representation.config_id == "fixed-vector-v1"
    assert representation.selected_feature_set_ids == (
        "rdkit_2d",
        "morgan_radius2_2048_chiral",
    )
    assert representation.feature_sets[0].input_representation == "capped_smiles"
    assert [feature.feature_set_id for feature in representation.selected_feature_sets()] == [
        "rdkit_2d",
        "morgan_radius2_2048_chiral",
    ]


def test_feature_set_config_records_identity_shape_policy_and_hash_fields() -> None:
    feature_set = FeatureSetConfig(
        feature_set_id="rdkit_2d_uncapped",
        family="descriptor",
        version="1",
        input_representation="standardized_smiles",
        rdkit_method="rdkit.Chem.Descriptors",
        settings={"descriptor_family": "all_named_2d"},
        output_shape=(1, 217),
        feature_name_policy="named",
        hash_identity_fields=("feature_set_id", "input_representation", "rdkit_method"),
    )

    assert feature_set.feature_set_id == "rdkit_2d_uncapped"
    assert feature_set.input_representation == "standardized_smiles"
    assert feature_set.output_shape == (1, 217)
    assert feature_set.feature_name_policy == "named"


def test_feature_set_config_rejects_empty_dimensions() -> None:
    with pytest.raises(ValidationError, match="positive"):
        FeatureSetConfig(
            feature_set_id="bad",
            family="descriptor",
            version="1",
            rdkit_method="rdkit.Chem.Descriptors",
            output_shape=(0, 217),
            feature_name_policy="named",
            hash_identity_fields=("feature_set_id",),
        )


def test_representation_config_rejects_duplicate_or_unknown_feature_sets() -> None:
    with pytest.raises(ValidationError, match="feature-set IDs must be unique"):
        RepresentationConfig(
            config_id="fixed-vector-v1",
            selected_feature_set_ids=("rdkit_2d",),
            feature_sets=(_descriptor_feature_set(), _descriptor_feature_set()),
        )

    with pytest.raises(ValidationError, match="not configured"):
        RepresentationConfig(
            config_id="fixed-vector-v1",
            selected_feature_set_ids=("not-real",),
            feature_sets=(_descriptor_feature_set(),),
        )


def test_attempt_records_copy_chemistry_provenance_and_input_representation() -> None:
    record = RepresentationAttemptRecord.from_chemistry_record(
        _chemistry_record(),
        _chemistry(),
        _descriptor_feature_set(),
        status="success",
    )

    assert record.sample_id == "poly-0001"
    assert record.chemistry_config_id == "chemistry-audit-v1"
    assert record.feature_set_id == "rdkit_2d"
    assert record.input_representation == "capped_smiles"
    assert record.selected_input_smiles == "[H]CC([H])c1ccccc1"
    assert record.standardized_smiles == "*CC(*)c1ccccc1"


def test_failed_attempt_records_require_matching_failure_details() -> None:
    failure = RepresentationFailureRecord(
        sample_id="poly-0001",
        feature_set_id="rdkit_2d",
        input_representation="capped_smiles",
        selected_input_smiles="[H]CC([H])c1ccccc1",
        failure_type="descriptor_error",
        message="Descriptor calculation failed.",
        stage="descriptor_generation",
        recommended_action="Inspect descriptor support for this molecule.",
    )

    record = RepresentationAttemptRecord.from_chemistry_record(
        _chemistry_record(),
        _chemistry(),
        _descriptor_feature_set(),
        status="failed",
        failure=failure,
    )

    assert record.failure == failure


def test_failed_attempt_records_reject_mismatched_failure_identity() -> None:
    with pytest.raises(ValidationError, match="failure feature-set ID"):
        RepresentationAttemptRecord(
            sample_id="poly-0001",
            chemistry_config_id="chemistry-audit-v1",
            feature_set_id="rdkit_2d",
            input_representation="capped_smiles",
            selected_input_smiles="CCO",
            status="failed",
            failure=RepresentationFailureRecord(
                sample_id="poly-0001",
                feature_set_id="morgan_radius2_2048_chiral",
                input_representation="capped_smiles",
                selected_input_smiles="CCO",
                failure_type="fingerprint_error",
                message="Fingerprint calculation failed.",
                stage="fingerprint_generation",
                recommended_action="Inspect fingerprint settings for this molecule.",
            ),
        )


def test_summary_records_attempts_skips_dimensions_and_grouped_failures() -> None:
    summary = RepresentationSummary(
        total_chemistry_valid_records=2,
        attempted_records=4,
        successful_records=3,
        failed_representation_records=1,
        skipped_upstream_chemistry_records=1,
        dimensions=(
            FeatureSetDimension(feature_set_id="rdkit_2d", rows=2, columns=217),
            FeatureSetDimension(feature_set_id="morgan_radius2_2048_chiral", rows=1, columns=2048),
        ),
        failure_groups=(
            RepresentationFailureGroup(
                feature_set_id="morgan_radius2_2048_chiral",
                failure_type="parse_error",
                count=1,
                example_sample_ids=("poly-0002",),
                recommended_action="Inspect the selected chemistry representation.",
            ),
        ),
    )

    assert summary.total_chemistry_valid_records == 2
    assert summary.skipped_upstream_chemistry_records == 1
    assert summary.dimensions[1].columns == 2048


def test_summary_rejects_invalid_counts_and_duplicate_dimensions() -> None:
    with pytest.raises(ValidationError, match="add up to attempts"):
        RepresentationSummary(
            total_chemistry_valid_records=2,
            attempted_records=4,
            successful_records=4,
            failed_representation_records=1,
        )

    with pytest.raises(ValidationError, match="dimensions must be unique"):
        RepresentationSummary(
            total_chemistry_valid_records=1,
            attempted_records=1,
            successful_records=1,
            failed_representation_records=0,
            dimensions=(
                FeatureSetDimension(feature_set_id="rdkit_2d", rows=1, columns=217),
                FeatureSetDimension(feature_set_id="rdkit_2d", rows=1, columns=217),
            ),
        )


def test_artifact_metadata_records_provenance_paths_hashes_and_feature_settings() -> None:
    representation = _representation()
    cache_key = representation_cache_key(
        _dataset(),
        _chemistry(),
        "chemistry-cache-key",
        representation,
        rdkit_version="2026.03.3",
    )
    paths = RepresentationArtifactPaths(
        artifact_root="artifacts/representations/fixed-vector-v1",
        records="artifacts/representations/fixed-vector-v1/records.json",
        metadata="artifacts/representations/fixed-vector-v1/metadata.json",
        summary="artifacts/representations/fixed-vector-v1/summary.json",
        failures="artifacts/representations/fixed-vector-v1/failures.json",
        feature_set_matrices={"rdkit_2d": "features/rdkit_2d/matrix.npz"},
    )
    metadata = RepresentationOutputMetadata(
        artifact_version="1",
        dataset_version=_dataset().dataset_version,
        chemistry_config_id=_chemistry().config_id,
        chemistry_cache_key="chemistry-cache-key",
        representation_config_id=representation.config_id,
        representation_cache_key=cache_key,
        rdkit_version="2026.03.3",
        feature_sets=representation.selected_feature_sets(),
        created_at="2026-09-09T00:00:00+00:00",
        output_paths=paths,
        content_hashes={"rdkit_2d:matrix": "abc123"},
    )

    assert metadata.representation_config_id == "fixed-vector-v1"
    assert metadata.output_paths.feature_set_matrices["rdkit_2d"].endswith("matrix.npz")
    assert metadata.content_hashes["rdkit_2d:matrix"] == "abc123"
    assert len(metadata.representation_cache_key) == 64


def test_artifact_validates_identity_collisions_counts_and_failure_examples() -> None:
    with pytest.raises(ValidationError, match="separate from dataset version"):
        RepresentationArtifact(
            dataset=_dataset(),
            chemistry=_chemistry(),
            chemistry_cache_key="chemistry-cache-key",
            representation=RepresentationConfig(
                config_id="open-polymer-train-fixture-v1",
                selected_feature_set_ids=("rdkit_2d",),
                feature_sets=(_descriptor_feature_set(),),
            ),
            rdkit_version="2026.03.3",
            records=(),
            summary=RepresentationSummary(
                total_chemistry_valid_records=0,
                attempted_records=0,
                successful_records=0,
                failed_representation_records=0,
            ),
        )

    failure = RepresentationFailureRecord(
        sample_id="poly-0001",
        feature_set_id="rdkit_2d",
        input_representation="capped_smiles",
        selected_input_smiles="[H]CC([H])c1ccccc1",
        failure_type="parse_error",
        message="RDKit could not parse selected representation input SMILES.",
        stage="parse",
        recommended_action="Inspect the selected chemistry representation.",
    )
    failed_record = RepresentationAttemptRecord.from_chemistry_record(
        _chemistry_record(),
        _chemistry(),
        _descriptor_feature_set(),
        status="failed",
        failure=failure,
    )

    with pytest.raises(ValidationError, match="failure group examples"):
        RepresentationArtifact(
            dataset=_dataset(),
            chemistry=_chemistry(),
            chemistry_cache_key="chemistry-cache-key",
            representation=_representation(),
            rdkit_version="2026.03.3",
            records=(failed_record,),
            summary=RepresentationSummary(
                total_chemistry_valid_records=1,
                attempted_records=1,
                successful_records=0,
                failed_representation_records=1,
                failure_groups=(
                    RepresentationFailureGroup(
                        feature_set_id="rdkit_2d",
                        failure_type="parse_error",
                        count=1,
                        example_sample_ids=("poly-missing",),
                        recommended_action="Inspect the selected chemistry representation.",
                    ),
                ),
            ),
        )


def test_artifact_directory_uses_representation_config_id() -> None:
    assert representation_artifact_dir("artifacts", _representation()) == Path(
        "artifacts/representations/fixed-vector-v1"
    )
