"""Typed chemistry audit contracts for polymer source data."""

from typing import Literal

from pydantic import Field, model_validator

from supervised_learning_polymers.manifest import DatasetConfig
from supervised_learning_polymers.targets import ContractModel

FragmentPolicy = Literal["keep_all", "largest_fragment"]
ChargePolicy = Literal["preserve", "neutralize"]
TautomerPolicy = Literal["preserve", "canonicalize"]
StereochemistryPolicy = Literal["preserve", "drop"]
IsotopePolicy = Literal["preserve", "drop"]
CappingStrategyName = Literal["uncapped", "hydrogen", "carbon"]
ChemistryAuditStatus = Literal["valid", "failed"]
ChemistryFailureType = Literal[
    "missing_smiles",
    "parse_error",
    "standardization_error",
    "capping_error",
    "unsupported_polymer_notation",
]
ChemistryProcessingStage = Literal["input", "parse", "standardization", "capping"]


class StandardizationConfig(ContractModel):
    """Configurable molecule standardization choices for an audit run."""

    fragment_policy: FragmentPolicy = "keep_all"
    charge_policy: ChargePolicy = "preserve"
    tautomer_policy: TautomerPolicy = "preserve"
    stereochemistry_policy: StereochemistryPolicy = "preserve"
    isotope_policy: IsotopePolicy = "preserve"


class CappingConfig(ContractModel):
    """Versioned polymer attachment-point capping strategy."""

    strategy: CappingStrategyName = "uncapped"
    version: str = Field(default="1", min_length=1)


class ChemistryAuditConfig(ContractModel):
    """Chemistry processing identity and settings for derived audit artifacts."""

    config_id: str = Field(min_length=1)
    standardization: StandardizationConfig = Field(default_factory=StandardizationConfig)
    capping: CappingConfig = Field(default_factory=CappingConfig)


class ChemistryFailureRecord(ContractModel):
    """Structured failure emitted for a sample that cannot complete chemistry processing."""

    sample_id: str = Field(min_length=1)
    raw_smiles: str | None = None
    failure_type: ChemistryFailureType
    message: str = Field(min_length=1)
    stage: ChemistryProcessingStage


class ChemistryAuditRecord(ContractModel):
    """Per-sample chemistry audit record preserving source and derived SMILES."""

    sample_id: str = Field(min_length=1)
    raw_smiles: str | None = None
    status: ChemistryAuditStatus
    canonical_smiles: str | None = Field(default=None, min_length=1)
    standardized_smiles: str | None = Field(default=None, min_length=1)
    capped_smiles: str | None = Field(default=None, min_length=1)
    attachment_points: tuple[str, ...] = Field(default_factory=tuple)
    failure: ChemistryFailureRecord | None = None

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "ChemistryAuditRecord":
        if self.status == "valid" and self.failure is not None:
            raise ValueError("valid chemistry audit records must not include a failure")
        if self.status == "failed" and self.failure is None:
            raise ValueError("failed chemistry audit records must include a failure")
        if self.failure is not None and self.failure.sample_id != self.sample_id:
            raise ValueError("failure sample ID must match audit record sample ID")
        if self.failure is not None and self.failure.raw_smiles != self.raw_smiles:
            raise ValueError("failure raw SMILES must match audit record raw SMILES")
        return self


class ChemistryAuditFailureGroup(ContractModel):
    """Aggregated failure group for triage and interface display."""

    failure_type: ChemistryFailureType
    count: int = Field(ge=1)
    example_sample_ids: tuple[str, ...] = Field(default_factory=tuple)
    recommended_action: str = Field(min_length=1)


class ChemistryAuditSummary(ContractModel):
    """Aggregate chemistry audit counts and grouped failures."""

    total_records: int = Field(ge=0)
    valid_records: int = Field(ge=0)
    failed_records: int = Field(ge=0)
    failure_groups: tuple[ChemistryAuditFailureGroup, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_counts(self) -> "ChemistryAuditSummary":
        if self.valid_records + self.failed_records != self.total_records:
            raise ValueError("valid and failed chemistry records must add up to total records")
        grouped_failures = sum(group.count for group in self.failure_groups)
        if grouped_failures != self.failed_records:
            raise ValueError("chemistry failure group counts must add up to failed records")
        return self


class ChemistryAuditArtifact(ContractModel):
    """Complete fixture-sized chemistry audit artifact contract."""

    artifact_version: str = Field(default="1", min_length=1)
    dataset: DatasetConfig
    chemistry: ChemistryAuditConfig
    rdkit_version: str = Field(min_length=1)
    records: tuple[ChemistryAuditRecord, ...] = Field(default_factory=tuple)
    summary: ChemistryAuditSummary

    @model_validator(mode="after")
    def validate_artifact_consistency(self) -> "ChemistryAuditArtifact":
        if self.chemistry.config_id == self.dataset.dataset_version:
            raise ValueError("chemistry config ID must be separate from dataset version")

        if len(self.records) != self.summary.total_records:
            raise ValueError("chemistry audit record count must match summary total records")

        valid_records = sum(record.status == "valid" for record in self.records)
        failed_records = sum(record.status == "failed" for record in self.records)
        if (
            valid_records != self.summary.valid_records
            or failed_records != self.summary.failed_records
        ):
            raise ValueError("chemistry audit record statuses must match summary counts")

        failed_record_ids = {
            record.sample_id for record in self.records if record.status == "failed"
        }
        example_ids = {
            sample_id
            for group in self.summary.failure_groups
            for sample_id in group.example_sample_ids
        }
        unknown_examples = sorted(example_ids - failed_record_ids)
        if unknown_examples:
            raise ValueError(
                "chemistry failure group examples must reference failed records: "
                f"{', '.join(unknown_examples)}"
            )

        return self
