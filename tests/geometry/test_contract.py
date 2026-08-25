import pytest
from pydantic import ValidationError

from supervised_learning_polymers.chemistry import CappingConfig, ChemistryAuditConfig
from supervised_learning_polymers.geometry import (
    ChemistryGeometryProvenance,
    FallbackMethodProvenance,
    GeometryArtifact,
    GeometryArtifactPaths,
    GeometryAttemptRecord,
    GeometryConfig,
    GeometryFailureGroup,
    GeometryFailureRecord,
    GeometryMethodProvenance,
    GeometryOutputMetadata,
    GeometrySummary,
    GeometryTiming,
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
        config_id="chemistry-audit-v1",
        capping=CappingConfig(strategy="hydrogen", version="1"),
    )


def test_geometry_config_records_method_and_fallback_settings() -> None:
    config = GeometryConfig(
        config_id="geometry-rdkit-v1",
        input_representation="capped_smiles",
        random_seed=13,
        embed_attempts=5,
        optimization_max_iterations=250,
        fallback_methods=("xtb", "mlip"),
    )

    assert config.config_id == "geometry-rdkit-v1"
    assert config.primary_method == "rdkit_etkdg_mmff"
    assert config.input_representation == "capped_smiles"
    assert config.random_seed == 13
    assert config.embed_attempts == 5
    assert config.optimization_max_iterations == 250
    assert config.fallback_methods == ("xtb", "mlip")


def test_geometry_attempt_records_successful_sdf_and_chemistry_provenance() -> None:
    record = GeometryAttemptRecord(
        sample_id="poly-0001",
        chemistry_config_id="chemistry-audit-v1",
        input_representation="capped_smiles",
        selected_input_smiles="CCO",
        raw_smiles="CCO",
        canonical_smiles="CCO",
        standardized_smiles="CCO",
        capped_smiles="CCO",
        attachment_points=(),
        status="success",
        method=GeometryMethodProvenance(
            method_name="rdkit_etkdg_mmff",
            rdkit_version="2026.03.3",
            embedding_status="success",
            optimization_status="success",
        ),
        timing=GeometryTiming(runtime_seconds=0.025),
        sdf_text="poly-0001\n  RDKit\n\nM  END\n$$$$\n",
        fallback_provenance=(
            FallbackMethodProvenance(
                method_name="xtb",
                priority=1,
                status="skipped_not_needed",
                reason="RDKit conformer generation succeeded.",
                dependency_available=False,
            ),
        ),
    )

    assert record.status == "success"
    assert record.sdf_text is not None
    assert record.fallback_provenance[0].method_name == "xtb"


def test_successful_geometry_attempt_requires_sdf_text() -> None:
    with pytest.raises(ValidationError, match="successful geometry records must include SDF text"):
        GeometryAttemptRecord(
            sample_id="poly-0001",
            chemistry_config_id="chemistry-audit-v1",
            input_representation="capped_smiles",
            selected_input_smiles="CCO",
            raw_smiles="CCO",
            status="success",
            method=GeometryMethodProvenance(
                method_name="rdkit_etkdg_mmff",
                rdkit_version="2026.03.3",
                embedding_status="success",
            ),
            timing=GeometryTiming(runtime_seconds=0.025),
        )


def test_failed_geometry_attempt_requires_failure_details() -> None:
    with pytest.raises(ValidationError, match="failed geometry records must include a failure"):
        GeometryAttemptRecord(
            sample_id="poly-0002",
            chemistry_config_id="chemistry-audit-v1",
            input_representation="standardized_smiles",
            selected_input_smiles="*CC(*)",
            raw_smiles="*CC(*)",
            status="failed",
            method=GeometryMethodProvenance(
                method_name="rdkit_etkdg_mmff",
                rdkit_version="2026.03.3",
                embedding_status="failed",
            ),
            timing=GeometryTiming(runtime_seconds=0.01),
        )


def test_failure_details_must_match_attempt_identity_and_method() -> None:
    with pytest.raises(ValidationError, match="failure method name"):
        GeometryAttemptRecord(
            sample_id="poly-0002",
            chemistry_config_id="chemistry-audit-v1",
            input_representation="standardized_smiles",
            selected_input_smiles="*CC(*)",
            raw_smiles="*CC(*)",
            status="failed",
            method=GeometryMethodProvenance(
                method_name="rdkit_etkdg_mmff",
                rdkit_version="2026.03.3",
                embedding_status="failed",
            ),
            timing=GeometryTiming(runtime_seconds=0.01),
            failure=GeometryFailureRecord(
                sample_id="poly-0002",
                method_name="xtb",
                failure_type="embedding_failed",
                message="Embedding failed.",
                stage="embedding",
                recommended_action="Try a capped input representation or inspect the molecule.",
            ),
        )


def test_geometry_summary_validates_counts_and_coverage() -> None:
    summary = GeometrySummary(
        total_chemistry_valid_records=4,
        attempted_records=3,
        successful_records=2,
        failed_records=1,
        skipped_records=1,
        skipped_fallback_records=2,
        coverage_fraction=0.5,
        total_runtime_seconds=1.5,
        failure_groups=(
            GeometryFailureGroup(
                failure_type="embedding_failed",
                count=1,
                example_sample_ids=("poly-0003",),
                recommended_action="Try a capped input representation.",
            ),
        ),
    )

    assert summary.successful_records == 2
    assert summary.coverage_fraction == 0.5


def test_geometry_summary_rejects_invalid_counts() -> None:
    with pytest.raises(ValidationError, match="attempted and skipped records"):
        GeometrySummary(
            total_chemistry_valid_records=4,
            attempted_records=4,
            successful_records=2,
            failed_records=1,
            skipped_records=1,
            coverage_fraction=0.5,
            total_runtime_seconds=1.5,
        )


def test_geometry_artifact_rejects_config_identity_collisions() -> None:
    with pytest.raises(ValidationError, match="separate from dataset version and chemistry config"):
        GeometryArtifact(
            dataset=_dataset(),
            chemistry=_chemistry(),
            chemistry_cache_key="chemistry-cache-key",
            geometry=GeometryConfig(config_id="chemistry-audit-v1"),
            records=(),
            summary=GeometrySummary(
                total_chemistry_valid_records=0,
                attempted_records=0,
                successful_records=0,
                failed_records=0,
                skipped_records=0,
                coverage_fraction=0.0,
                total_runtime_seconds=0.0,
            ),
        )


def test_geometry_artifact_validates_record_counts_against_summary() -> None:
    with pytest.raises(ValidationError, match="geometry attempt record count"):
        GeometryArtifact(
            dataset=_dataset(),
            chemistry=_chemistry(),
            chemistry_cache_key="chemistry-cache-key",
            geometry=GeometryConfig(config_id="geometry-rdkit-v1"),
            records=(),
            summary=GeometrySummary(
                total_chemistry_valid_records=1,
                attempted_records=1,
                successful_records=1,
                failed_records=0,
                skipped_records=0,
                coverage_fraction=1.0,
                total_runtime_seconds=0.0,
            ),
        )


def test_geometry_output_metadata_repeats_readable_chemistry_provenance() -> None:
    metadata = GeometryOutputMetadata(
        artifact_version="1",
        dataset_version="open-polymer-train-fixture-v1",
        chemistry_config_id="chemistry-audit-v1",
        chemistry_cache_key="chemistry-cache-key",
        chemistry_provenance=ChemistryGeometryProvenance(
            capping_strategy="hydrogen",
            capping_version="1",
            geometry_input_representation="capped_smiles",
        ),
        geometry_config_id="geometry-rdkit-v1",
        geometry_cache_key="geometry-cache-key",
        rdkit_version="2026.03.3",
        created_at="2026-08-25T00:00:00+00:00",
        settings=GeometryConfig(config_id="geometry-rdkit-v1"),
        output_paths=GeometryArtifactPaths(
            artifact_root="artifacts/geometry/geometry-rdkit-v1",
            records="artifacts/geometry/geometry-rdkit-v1/records.json",
            failures="artifacts/geometry/geometry-rdkit-v1/failures.json",
            summary="artifacts/geometry/geometry-rdkit-v1/summary.json",
            metadata="artifacts/geometry/geometry-rdkit-v1/metadata.json",
        ),
    )

    assert metadata.chemistry_cache_key == "chemistry-cache-key"
    assert metadata.chemistry_provenance.capping_strategy == "hydrogen"
    assert metadata.chemistry_provenance.geometry_input_representation == "capped_smiles"
