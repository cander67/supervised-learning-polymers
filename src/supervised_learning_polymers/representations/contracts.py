"""Typed fixed-vector representation artifact contracts."""

from collections.abc import Mapping
from hashlib import sha256
from importlib import import_module
from json import dumps
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from supervised_learning_polymers.chemistry import ChemistryAuditConfig, ChemistryAuditRecord
from supervised_learning_polymers.manifest import DatasetConfig
from supervised_learning_polymers.targets import ContractModel

_rdkit: Any = import_module("rdkit")
RDKIT_VERSION = str(_rdkit.__version__)

MolecularInputRepresentation = Literal["capped_smiles", "standardized_smiles"]
FeatureFamily = Literal["descriptor", "fingerprint"]
FeatureNamePolicy = Literal["named", "bit_index", "none"]
RepresentationAttemptStatus = Literal["success", "failed"]
RepresentationFailureType = Literal[
    "missing_input_smiles",
    "parse_error",
    "descriptor_error",
    "fingerprint_error",
    "invalid_feature_values",
]
RepresentationProcessingStage = Literal[
    "input",
    "parse",
    "descriptor_generation",
    "fingerprint_generation",
    "validation",
]


class FeatureSetConfig(ContractModel):
    """Stable identity and settings for one generated fixed-vector feature set."""

    feature_set_id: str = Field(min_length=1)
    family: FeatureFamily
    version: str = Field(min_length=1)
    input_representation: MolecularInputRepresentation = "capped_smiles"
    rdkit_method: str = Field(min_length=1)
    settings: Mapping[str, object] = Field(default_factory=dict)
    output_shape: tuple[int, ...] = Field(min_length=1)
    feature_name_policy: FeatureNamePolicy
    hash_identity_fields: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_feature_set(self) -> "FeatureSetConfig":
        if any(dimension <= 0 for dimension in self.output_shape):
            raise ValueError("feature-set output dimensions must be positive")
        duplicate_hash_fields = _duplicates(self.hash_identity_fields)
        if duplicate_hash_fields:
            raise ValueError(
                "feature-set hash identity fields must be unique: "
                f"{', '.join(duplicate_hash_fields)}"
            )
        return self


class RepresentationConfig(ContractModel):
    """Top-level fixed-vector representation run identity and feature selection."""

    config_id: str = Field(min_length=1)
    selected_feature_set_ids: tuple[str, ...] = Field(min_length=1)
    feature_sets: tuple[FeatureSetConfig, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_feature_selection(self) -> "RepresentationConfig":
        duplicate_feature_sets = _duplicates(
            tuple(feature_set.feature_set_id for feature_set in self.feature_sets)
        )
        if duplicate_feature_sets:
            raise ValueError(
                "representation feature-set IDs must be unique: "
                f"{', '.join(duplicate_feature_sets)}"
            )

        duplicate_selected = _duplicates(self.selected_feature_set_ids)
        if duplicate_selected:
            raise ValueError(
                "selected representation feature-set IDs must be unique: "
                f"{', '.join(duplicate_selected)}"
            )

        known_feature_sets = {feature_set.feature_set_id for feature_set in self.feature_sets}
        unknown_selected = sorted(set(self.selected_feature_set_ids) - known_feature_sets)
        if unknown_selected:
            raise ValueError(
                "selected representation feature sets are not configured: "
                f"{', '.join(unknown_selected)}"
            )
        return self

    def selected_feature_sets(self) -> tuple[FeatureSetConfig, ...]:
        """Return selected feature-set configs in selection order."""

        by_id = {feature_set.feature_set_id: feature_set for feature_set in self.feature_sets}
        return tuple(by_id[feature_set_id] for feature_set_id in self.selected_feature_set_ids)


class RepresentationFailureRecord(ContractModel):
    """Structured failure emitted when a valid chemistry record cannot be featurized."""

    sample_id: str = Field(min_length=1)
    feature_set_id: str = Field(min_length=1)
    input_representation: MolecularInputRepresentation
    selected_input_smiles: str | None = Field(default=None, min_length=1)
    failure_type: RepresentationFailureType
    message: str = Field(min_length=1)
    stage: RepresentationProcessingStage
    recommended_action: str = Field(min_length=1)


class RepresentationAttemptRecord(ContractModel):
    """Per-sample feature-generation attempt linked to a valid chemistry audit record."""

    sample_id: str = Field(min_length=1)
    chemistry_config_id: str = Field(min_length=1)
    feature_set_id: str = Field(min_length=1)
    input_representation: MolecularInputRepresentation
    selected_input_smiles: str | None = Field(default=None, min_length=1)
    raw_smiles: str | None = None
    canonical_smiles: str | None = Field(default=None, min_length=1)
    standardized_smiles: str | None = Field(default=None, min_length=1)
    capped_smiles: str | None = Field(default=None, min_length=1)
    status: RepresentationAttemptStatus
    failure: RepresentationFailureRecord | None = None

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "RepresentationAttemptRecord":
        if self.status == "success" and self.failure is not None:
            raise ValueError("successful representation records must not include a failure")
        if self.status == "failed" and self.failure is None:
            raise ValueError("failed representation records must include a failure")
        if self.failure is not None and self.failure.sample_id != self.sample_id:
            raise ValueError("failure sample ID must match representation attempt sample ID")
        if self.failure is not None and self.failure.feature_set_id != self.feature_set_id:
            raise ValueError("failure feature-set ID must match representation attempt feature set")
        if (
            self.failure is not None
            and self.failure.input_representation != self.input_representation
        ):
            raise ValueError("failure input representation must match representation attempt input")
        if (
            self.failure is not None
            and self.failure.selected_input_smiles != self.selected_input_smiles
        ):
            raise ValueError("failure input SMILES must match representation attempt input")
        return self

    @classmethod
    def from_chemistry_record(
        cls,
        chemistry_record: ChemistryAuditRecord,
        chemistry: ChemistryAuditConfig,
        feature_set: FeatureSetConfig,
        *,
        status: RepresentationAttemptStatus,
        failure: RepresentationFailureRecord | None = None,
    ) -> "RepresentationAttemptRecord":
        """Create an attempt payload with upstream chemistry provenance copied through."""

        input_smiles = _selected_input_smiles(chemistry_record, feature_set.input_representation)
        return cls(
            sample_id=chemistry_record.sample_id,
            chemistry_config_id=chemistry.config_id,
            feature_set_id=feature_set.feature_set_id,
            input_representation=feature_set.input_representation,
            selected_input_smiles=input_smiles,
            raw_smiles=chemistry_record.raw_smiles,
            canonical_smiles=chemistry_record.canonical_smiles,
            standardized_smiles=chemistry_record.standardized_smiles,
            capped_smiles=chemistry_record.capped_smiles,
            status=status,
            failure=failure,
        )


class FeatureSetDimension(ContractModel):
    """Matrix dimensions recorded for one generated feature set."""

    feature_set_id: str = Field(min_length=1)
    rows: int = Field(ge=0)
    columns: int = Field(ge=1)


class RepresentationFailureGroup(ContractModel):
    """Aggregated representation failure group for triage."""

    feature_set_id: str = Field(min_length=1)
    failure_type: RepresentationFailureType
    count: int = Field(ge=1)
    example_sample_ids: tuple[str, ...] = Field(default_factory=tuple)
    recommended_action: str = Field(min_length=1)


class RepresentationSummary(ContractModel):
    """Aggregate fixed-vector representation counts, dimensions, and failures."""

    total_chemistry_valid_records: int = Field(ge=0)
    attempted_records: int = Field(ge=0)
    successful_records: int = Field(ge=0)
    failed_representation_records: int = Field(ge=0)
    skipped_upstream_chemistry_records: int = Field(default=0, ge=0)
    dimensions: tuple[FeatureSetDimension, ...] = Field(default_factory=tuple)
    failure_groups: tuple[RepresentationFailureGroup, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_counts(self) -> "RepresentationSummary":
        if self.successful_records + self.failed_representation_records != self.attempted_records:
            raise ValueError("successful and failed representation records must add up to attempts")
        if self.attempted_records < self.total_chemistry_valid_records:
            raise ValueError(
                "attempted representation records must cover every selected feature set for "
                "chemistry-valid inputs"
            )
        grouped_failures = sum(group.count for group in self.failure_groups)
        if grouped_failures != self.failed_representation_records:
            raise ValueError("representation failure group counts must add up to failed records")

        duplicate_dimensions = _duplicates(
            tuple(dimension.feature_set_id for dimension in self.dimensions)
        )
        if duplicate_dimensions:
            raise ValueError(
                "representation summary dimensions must be unique by feature set: "
                f"{', '.join(duplicate_dimensions)}"
            )
        return self


class RepresentationArtifact(ContractModel):
    """Complete fixed-vector representation artifact contract."""

    artifact_version: str = Field(default="1", min_length=1)
    dataset: DatasetConfig
    chemistry: ChemistryAuditConfig
    chemistry_cache_key: str = Field(min_length=1)
    representation: RepresentationConfig
    rdkit_version: str = Field(min_length=1)
    records: tuple[RepresentationAttemptRecord, ...] = Field(default_factory=tuple)
    summary: RepresentationSummary

    @model_validator(mode="after")
    def validate_artifact_consistency(self) -> "RepresentationArtifact":
        reserved_ids = {self.dataset.dataset_version, self.chemistry.config_id}
        if self.representation.config_id in reserved_ids:
            raise ValueError(
                "representation config ID must be separate from dataset version and chemistry config"
            )

        colliding_feature_sets = sorted(
            feature_set.feature_set_id
            for feature_set in self.representation.feature_sets
            if feature_set.feature_set_id in {self.representation.config_id, *reserved_ids}
        )
        if colliding_feature_sets:
            raise ValueError(
                "feature-set IDs must be separate from dataset, chemistry, and representation IDs: "
                f"{', '.join(colliding_feature_sets)}"
            )

        if len(self.records) != self.summary.attempted_records:
            raise ValueError("representation attempt record count must match summary attempts")

        successful_records = sum(record.status == "success" for record in self.records)
        failed_records = sum(record.status == "failed" for record in self.records)
        if (
            successful_records != self.summary.successful_records
            or failed_records != self.summary.failed_representation_records
        ):
            raise ValueError("representation record statuses must match summary counts")

        configured_feature_sets = {
            feature_set.feature_set_id for feature_set in self.representation.feature_sets
        }
        unknown_record_feature_sets = sorted(
            {
                record.feature_set_id
                for record in self.records
                if record.feature_set_id not in configured_feature_sets
            }
        )
        if unknown_record_feature_sets:
            raise ValueError(
                "representation records reference unknown feature sets: "
                f"{', '.join(unknown_record_feature_sets)}"
            )

        failed_record_ids = {
            (record.feature_set_id, record.sample_id)
            for record in self.records
            if record.status == "failed"
        }
        unknown_examples = sorted(
            (group.feature_set_id, sample_id)
            for group in self.summary.failure_groups
            for sample_id in group.example_sample_ids
            if (group.feature_set_id, sample_id) not in failed_record_ids
        )
        if unknown_examples:
            formatted_examples = ", ".join(
                f"{feature_set_id}:{sample_id}" for feature_set_id, sample_id in unknown_examples
            )
            raise ValueError(
                "representation failure group examples must reference failed records: "
                f"{formatted_examples}"
            )
        return self


class RepresentationArtifactPaths(ContractModel):
    """Paths written for one persisted representation artifact bundle."""

    artifact_root: str = Field(min_length=1)
    metadata: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    failures: str = Field(min_length=1)
    feature_set_matrices: Mapping[str, str] = Field(default_factory=dict)
    feature_set_metadata: Mapping[str, str] = Field(default_factory=dict)
    sample_ids: Mapping[str, str] = Field(default_factory=dict)
    feature_names: Mapping[str, str] = Field(default_factory=dict)


class RepresentationOutputMetadata(ContractModel):
    """Metadata persisted alongside representation matrices and sidecars."""

    artifact_version: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    chemistry_config_id: str = Field(min_length=1)
    chemistry_cache_key: str = Field(min_length=1)
    representation_config_id: str = Field(min_length=1)
    representation_cache_key: str = Field(min_length=1)
    rdkit_version: str = Field(min_length=1)
    feature_sets: tuple[FeatureSetConfig, ...] = Field(min_length=1)
    created_at: str = Field(min_length=1)
    output_paths: RepresentationArtifactPaths
    content_hashes: Mapping[str, str] = Field(default_factory=dict)


def representation_artifact_dir(
    artifact_root: str | Path, representation: RepresentationConfig
) -> Path:
    """Return the conventional representation artifact directory for a config."""

    return Path(artifact_root) / "representations" / representation.config_id


def representation_cache_key(
    dataset: DatasetConfig,
    chemistry: ChemistryAuditConfig,
    chemistry_cache_key: str,
    representation: RepresentationConfig,
    *,
    rdkit_version: str = RDKIT_VERSION,
) -> str:
    """Return a deterministic cache key for representation settings."""

    payload = {
        "dataset": dataset.model_dump(mode="json"),
        "chemistry": {
            "config_id": chemistry.config_id,
            "cache_key": chemistry_cache_key,
        },
        "representation": representation.model_dump(mode="json"),
        "rdkit_version": rdkit_version,
    }
    serialized = dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _selected_input_smiles(
    chemistry_record: ChemistryAuditRecord,
    input_representation: MolecularInputRepresentation,
) -> str | None:
    if input_representation == "standardized_smiles":
        return chemistry_record.standardized_smiles
    return chemistry_record.capped_smiles


def _duplicates(values: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates
