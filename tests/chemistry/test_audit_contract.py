from typing import Literal

import pytest
from pydantic import ValidationError

from supervised_learning_polymers.chemistry import (
    CappingConfig,
    ChemistryAuditArtifact,
    ChemistryAuditConfig,
    ChemistryAuditFailureGroup,
    ChemistryAuditRecord,
    ChemistryAuditSummary,
    ChemistryFailureRecord,
    StandardizationConfig,
)
from supervised_learning_polymers.manifest import DatasetConfig


def _dataset() -> DatasetConfig:
    return DatasetConfig(
        dataset_version="open-polymer-train-fixture-v1",
        sample_id_column="id",
        smiles_column="SMILES",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )


def test_chemistry_config_records_standardization_and_capping_settings() -> None:
    config = ChemistryAuditConfig(
        config_id="chemistry-audit-v1",
        standardization=StandardizationConfig(
            fragment_policy="largest_fragment",
            charge_policy="neutralize",
            tautomer_policy="canonicalize",
            stereochemistry_policy="drop",
            isotope_policy="drop",
        ),
        capping=CappingConfig(strategy="hydrogen", version="1"),
    )

    assert config.config_id == "chemistry-audit-v1"
    assert config.standardization.fragment_policy == "largest_fragment"
    assert config.standardization.charge_policy == "neutralize"
    assert config.standardization.tautomer_policy == "canonicalize"
    assert config.standardization.stereochemistry_policy == "drop"
    assert config.standardization.isotope_policy == "drop"
    assert config.capping.strategy == "hydrogen"
    assert config.capping.version == "1"


@pytest.mark.parametrize("strategy", ["uncapped", "hydrogen", "carbon"])
def test_chemistry_config_supports_initial_capping_strategies(
    strategy: Literal["uncapped", "hydrogen", "carbon"],
) -> None:
    config = ChemistryAuditConfig(
        config_id=f"chemistry-{strategy}-v1",
        capping=CappingConfig(strategy=strategy, version="1"),
    )

    assert config.capping.strategy == strategy


def test_audit_record_preserves_source_and_derived_smiles() -> None:
    record = ChemistryAuditRecord(
        sample_id="poly-0001",
        raw_smiles="*CC(*)c1ccccc1",
        status="valid",
        canonical_smiles="*CC(*)c1ccccc1",
        standardized_smiles="*CC(*)c1ccccc1",
        capped_smiles="[H]CC([H])c1ccccc1",
        attachment_points=("*:0", "*:3"),
    )

    assert record.sample_id == "poly-0001"
    assert record.raw_smiles == "*CC(*)c1ccccc1"
    assert record.canonical_smiles == "*CC(*)c1ccccc1"
    assert record.standardized_smiles == "*CC(*)c1ccccc1"
    assert record.capped_smiles == "[H]CC([H])c1ccccc1"
    assert record.attachment_points == ("*:0", "*:3")


def test_failure_record_captures_source_and_failure_context() -> None:
    failure = ChemistryFailureRecord(
        sample_id="poly-0002",
        raw_smiles="not-a-smiles",
        failure_type="parse_error",
        message="RDKit could not parse source SMILES.",
        stage="parse",
    )
    record = ChemistryAuditRecord(
        sample_id="poly-0002",
        raw_smiles="not-a-smiles",
        status="failed",
        failure=failure,
    )

    assert record.failure == failure
    assert failure.failure_type == "parse_error"
    assert failure.stage == "parse"


def test_failed_audit_record_requires_failure_details() -> None:
    with pytest.raises(ValidationError, match="failed chemistry audit records"):
        ChemistryAuditRecord(
            sample_id="poly-0002",
            raw_smiles="not-a-smiles",
            status="failed",
        )


def test_valid_audit_record_rejects_failure_details() -> None:
    with pytest.raises(ValidationError, match="valid chemistry audit records"):
        ChemistryAuditRecord(
            sample_id="poly-0001",
            raw_smiles="CCO",
            status="valid",
            canonical_smiles="CCO",
            failure=ChemistryFailureRecord(
                sample_id="poly-0001",
                raw_smiles="CCO",
                failure_type="parse_error",
                message="Should not be present.",
                stage="parse",
            ),
        )


def test_failure_details_must_match_audit_record_source_identity() -> None:
    with pytest.raises(ValidationError, match="failure sample ID"):
        ChemistryAuditRecord(
            sample_id="poly-0001",
            raw_smiles="CCO",
            status="failed",
            failure=ChemistryFailureRecord(
                sample_id="poly-9999",
                raw_smiles="CCO",
                failure_type="standardization_error",
                message="Standardization failed.",
                stage="standardization",
            ),
        )


def test_summary_records_total_valid_failed_and_group_counts() -> None:
    summary = ChemistryAuditSummary(
        total_records=3,
        valid_records=1,
        failed_records=2,
        failure_groups=(
            ChemistryAuditFailureGroup(
                failure_type="parse_error",
                count=1,
                example_sample_ids=("poly-0002",),
                recommended_action="Inspect malformed SMILES and decide whether to repair.",
            ),
            ChemistryAuditFailureGroup(
                failure_type="capping_error",
                count=1,
                example_sample_ids=("poly-0003",),
                recommended_action="Review attachment points and capping strategy.",
            ),
        ),
    )

    assert summary.total_records == 3
    assert summary.valid_records == 1
    assert summary.failed_records == 2
    assert [group.failure_type for group in summary.failure_groups] == [
        "parse_error",
        "capping_error",
    ]


def test_summary_rejects_invalid_valid_failed_totals() -> None:
    with pytest.raises(ValidationError, match="valid and failed chemistry records"):
        ChemistryAuditSummary(total_records=2, valid_records=2, failed_records=1)


def test_summary_rejects_failure_groups_that_do_not_sum_to_failures() -> None:
    with pytest.raises(ValidationError, match="failure group counts"):
        ChemistryAuditSummary(
            total_records=3,
            valid_records=1,
            failed_records=2,
            failure_groups=(
                ChemistryAuditFailureGroup(
                    failure_type="parse_error",
                    count=1,
                    recommended_action="Inspect malformed SMILES.",
                ),
            ),
        )


def test_audit_artifact_rejects_chemistry_config_id_that_matches_dataset_version() -> None:
    with pytest.raises(ValidationError, match="separate from dataset version"):
        ChemistryAuditArtifact(
            dataset=_dataset(),
            chemistry=ChemistryAuditConfig(config_id="open-polymer-train-fixture-v1"),
            rdkit_version="2025.03.1",
            records=(),
            summary=ChemistryAuditSummary(total_records=0, valid_records=0, failed_records=0),
        )


def test_audit_artifact_validates_record_counts_against_summary() -> None:
    with pytest.raises(ValidationError, match="record count"):
        ChemistryAuditArtifact(
            dataset=_dataset(),
            chemistry=ChemistryAuditConfig(config_id="chemistry-audit-v1"),
            rdkit_version="2025.03.1",
            records=(),
            summary=ChemistryAuditSummary(total_records=1, valid_records=1, failed_records=0),
        )


def test_audit_artifact_validates_record_status_counts_against_summary() -> None:
    with pytest.raises(ValidationError, match="record statuses"):
        ChemistryAuditArtifact(
            dataset=_dataset(),
            chemistry=ChemistryAuditConfig(config_id="chemistry-audit-v1"),
            rdkit_version="2025.03.1",
            records=(
                ChemistryAuditRecord(
                    sample_id="poly-0001",
                    raw_smiles="not-a-smiles",
                    status="failed",
                    failure=ChemistryFailureRecord(
                        sample_id="poly-0001",
                        raw_smiles="not-a-smiles",
                        failure_type="parse_error",
                        message="RDKit could not parse source SMILES.",
                        stage="parse",
                    ),
                ),
            ),
            summary=ChemistryAuditSummary(total_records=1, valid_records=1, failed_records=0),
        )


def test_audit_artifact_validates_failure_group_examples_reference_failed_records() -> None:
    with pytest.raises(ValidationError, match="examples must reference failed records"):
        ChemistryAuditArtifact(
            dataset=_dataset(),
            chemistry=ChemistryAuditConfig(config_id="chemistry-audit-v1"),
            rdkit_version="2025.03.1",
            records=(
                ChemistryAuditRecord(
                    sample_id="poly-0001",
                    raw_smiles="not-a-smiles",
                    status="failed",
                    failure=ChemistryFailureRecord(
                        sample_id="poly-0001",
                        raw_smiles="not-a-smiles",
                        failure_type="parse_error",
                        message="RDKit could not parse source SMILES.",
                        stage="parse",
                    ),
                ),
            ),
            summary=ChemistryAuditSummary(
                total_records=1,
                valid_records=0,
                failed_records=1,
                failure_groups=(
                    ChemistryAuditFailureGroup(
                        failure_type="parse_error",
                        count=1,
                        example_sample_ids=("poly-9999",),
                        recommended_action="Inspect malformed SMILES.",
                    ),
                ),
            ),
        )


def test_audit_artifact_accepts_fixture_sized_success_and_failure_records() -> None:
    artifact = ChemistryAuditArtifact(
        dataset=_dataset(),
        chemistry=ChemistryAuditConfig(
            config_id="chemistry-audit-v1",
            capping=CappingConfig(strategy="uncapped", version="1"),
        ),
        rdkit_version="2025.03.1",
        records=(
            ChemistryAuditRecord(
                sample_id="poly-0001",
                raw_smiles="CCO",
                status="valid",
                canonical_smiles="CCO",
                standardized_smiles="CCO",
            ),
            ChemistryAuditRecord(
                sample_id="poly-0002",
                raw_smiles="not-a-smiles",
                status="failed",
                failure=ChemistryFailureRecord(
                    sample_id="poly-0002",
                    raw_smiles="not-a-smiles",
                    failure_type="parse_error",
                    message="RDKit could not parse source SMILES.",
                    stage="parse",
                ),
            ),
        ),
        summary=ChemistryAuditSummary(
            total_records=2,
            valid_records=1,
            failed_records=1,
            failure_groups=(
                ChemistryAuditFailureGroup(
                    failure_type="parse_error",
                    count=1,
                    example_sample_ids=("poly-0002",),
                    recommended_action="Inspect malformed SMILES.",
                ),
            ),
        ),
    )

    assert artifact.artifact_version == "1"
    assert artifact.dataset.smiles_column == "SMILES"
    assert artifact.chemistry.config_id == "chemistry-audit-v1"
    assert artifact.rdkit_version == "2025.03.1"
    assert artifact.summary.failed_records == 1
