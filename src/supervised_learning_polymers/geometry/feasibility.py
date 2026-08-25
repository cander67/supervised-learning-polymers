"""Typed geometry feasibility contracts for conformer artifact groundwork."""

from typing import Literal

from pydantic import Field, model_validator

from supervised_learning_polymers.chemistry import ChemistryAuditConfig
from supervised_learning_polymers.manifest import DatasetConfig
from supervised_learning_polymers.targets import ContractModel

GeometryInputRepresentation = Literal["standardized_smiles", "capped_smiles"]
GeometryMethodName = Literal["rdkit_etkdg_mmff", "xtb", "mlip"]
FallbackMethodName = Literal["xtb", "mlip"]
GeometryAttemptStatus = Literal["success", "failed"]
GeometryFailureType = Literal[
    "missing_input_smiles",
    "parse_error",
    "embedding_failed",
    "optimization_failed",
    "unsupported_wildcard_atoms",
    "method_unavailable",
]
GeometryProcessingStage = Literal["input", "parse", "embedding", "optimization", "fallback"]
FallbackMethodStatus = Literal[
    "disabled",
    "unavailable",
    "skipped_not_needed",
    "skipped_dependency_unavailable",
    "attempted",
    "success",
    "failed",
]


class GeometryConfig(ContractModel):
    """Configurable geometry feasibility method and input choices."""

    config_id: str = Field(min_length=1)
    primary_method: Literal["rdkit_etkdg_mmff"] = "rdkit_etkdg_mmff"
    input_representation: GeometryInputRepresentation = "capped_smiles"
    random_seed: int = 61453
    embed_attempts: int = Field(default=20, ge=1)
    optimization_max_iterations: int = Field(default=200, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)
    fallback_methods: tuple[FallbackMethodName, ...] = Field(default_factory=tuple)


class ChemistryGeometryProvenance(ContractModel):
    """Readable upstream chemistry settings repeated for artifact inspection."""

    capping_strategy: str = Field(min_length=1)
    capping_version: str = Field(min_length=1)
    geometry_input_representation: GeometryInputRepresentation


class GeometryTiming(ContractModel):
    """Runtime accounting for one geometry attempt."""

    runtime_seconds: float = Field(ge=0)


class GeometryMethodProvenance(ContractModel):
    """Method-level provenance for the primary conformer attempt."""

    method_name: GeometryMethodName
    rdkit_version: str = Field(min_length=1)
    embedding_status: str = Field(min_length=1)
    optimization_status: str | None = Field(default=None, min_length=1)


class FallbackMethodProvenance(ContractModel):
    """Fallback method status recorded without requiring the dependency by default."""

    method_name: FallbackMethodName
    priority: int = Field(ge=1)
    status: FallbackMethodStatus
    reason: str = Field(min_length=1)
    runtime_seconds: float | None = Field(default=None, ge=0)
    dependency_available: bool


class GeometryFailureRecord(ContractModel):
    """Structured failure for a sample that cannot produce viewer-ready geometry."""

    sample_id: str = Field(min_length=1)
    method_name: GeometryMethodName
    failure_type: GeometryFailureType
    message: str = Field(min_length=1)
    stage: GeometryProcessingStage
    recommended_action: str = Field(min_length=1)


class GeometryAttemptRecord(ContractModel):
    """Per-sample geometry attempt linked to a valid chemistry audit record."""

    sample_id: str = Field(min_length=1)
    chemistry_config_id: str = Field(min_length=1)
    input_representation: GeometryInputRepresentation
    selected_input_smiles: str | None = Field(default=None, min_length=1)
    raw_smiles: str | None = None
    canonical_smiles: str | None = Field(default=None, min_length=1)
    standardized_smiles: str | None = Field(default=None, min_length=1)
    capped_smiles: str | None = Field(default=None, min_length=1)
    attachment_points: tuple[str, ...] = Field(default_factory=tuple)
    status: GeometryAttemptStatus
    method: GeometryMethodProvenance
    timing: GeometryTiming
    sdf_text: str | None = Field(default=None, min_length=1)
    failure: GeometryFailureRecord | None = None
    fallback_provenance: tuple[FallbackMethodProvenance, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "GeometryAttemptRecord":
        if self.status == "success":
            if self.failure is not None:
                raise ValueError("successful geometry records must not include a failure")
            if self.sdf_text is None:
                raise ValueError("successful geometry records must include SDF text")
        if self.status == "failed":
            if self.failure is None:
                raise ValueError("failed geometry records must include a failure")
            if self.sdf_text is not None:
                raise ValueError("failed geometry records must not include SDF text")
        if self.failure is not None and self.failure.sample_id != self.sample_id:
            raise ValueError("failure sample ID must match geometry attempt sample ID")
        if self.failure is not None and self.failure.method_name != self.method.method_name:
            raise ValueError("failure method name must match geometry attempt method name")
        return self


class GeometryFailureGroup(ContractModel):
    """Aggregated geometry failure group for triage and interface display."""

    failure_type: GeometryFailureType
    count: int = Field(ge=1)
    example_sample_ids: tuple[str, ...] = Field(default_factory=tuple)
    recommended_action: str = Field(min_length=1)


class GeometrySummary(ContractModel):
    """Aggregate geometry coverage, failure, fallback, and runtime summary."""

    total_chemistry_valid_records: int = Field(ge=0)
    attempted_records: int = Field(ge=0)
    successful_records: int = Field(ge=0)
    failed_records: int = Field(ge=0)
    skipped_records: int = Field(ge=0)
    skipped_fallback_records: int = Field(default=0, ge=0)
    coverage_fraction: float = Field(ge=0, le=1)
    total_runtime_seconds: float = Field(ge=0)
    failure_groups: tuple[GeometryFailureGroup, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_counts(self) -> "GeometrySummary":
        if self.attempted_records + self.skipped_records != self.total_chemistry_valid_records:
            raise ValueError(
                "attempted and skipped records must add up to total chemistry-valid records"
            )
        if self.successful_records + self.failed_records != self.attempted_records:
            raise ValueError("successful and failed records must add up to attempted records")
        grouped_failures = sum(group.count for group in self.failure_groups)
        if grouped_failures != self.failed_records:
            raise ValueError("geometry failure group counts must add up to failed records")
        expected_coverage = (
            0.0
            if self.total_chemistry_valid_records == 0
            else self.successful_records / self.total_chemistry_valid_records
        )
        if abs(self.coverage_fraction - expected_coverage) > 1e-9:
            raise ValueError("coverage fraction must equal successful records divided by inputs")
        return self


class GeometryArtifact(ContractModel):
    """Complete fixture-sized geometry feasibility artifact contract."""

    artifact_version: str = Field(default="1", min_length=1)
    dataset: DatasetConfig
    chemistry: ChemistryAuditConfig
    chemistry_cache_key: str = Field(min_length=1)
    geometry: GeometryConfig
    rdkit_version: str | None = Field(default=None, min_length=1)
    records: tuple[GeometryAttemptRecord, ...] = Field(default_factory=tuple)
    summary: GeometrySummary

    @model_validator(mode="after")
    def validate_artifact_consistency(self) -> "GeometryArtifact":
        if self.geometry.config_id in {
            self.dataset.dataset_version,
            self.chemistry.config_id,
        }:
            raise ValueError(
                "geometry config ID must be separate from dataset version and chemistry config"
            )
        if len(self.records) != self.summary.attempted_records:
            raise ValueError("geometry attempt record count must match summary attempted records")

        successful_records = sum(record.status == "success" for record in self.records)
        failed_records = sum(record.status == "failed" for record in self.records)
        if (
            successful_records != self.summary.successful_records
            or failed_records != self.summary.failed_records
        ):
            raise ValueError("geometry record statuses must match summary counts")

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
                "geometry failure group examples must reference failed records: "
                f"{', '.join(unknown_examples)}"
            )
        return self


class GeometryArtifactPaths(ContractModel):
    """Paths written for one persisted geometry feasibility bundle."""

    artifact_root: str = Field(min_length=1)
    records: str = Field(min_length=1)
    failures: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    metadata: str = Field(min_length=1)


class GeometryOutputMetadata(ContractModel):
    """Metadata persisted alongside geometry attempt records and summaries."""

    artifact_version: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    chemistry_config_id: str = Field(min_length=1)
    chemistry_cache_key: str = Field(min_length=1)
    chemistry_provenance: ChemistryGeometryProvenance
    geometry_config_id: str = Field(min_length=1)
    geometry_cache_key: str = Field(min_length=1)
    rdkit_version: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    settings: GeometryConfig
    output_paths: GeometryArtifactPaths
