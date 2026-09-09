"""Typed fixed-vector representation artifact contracts."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from json import dumps
from math import isfinite
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
from pydantic import Field, model_validator

from supervised_learning_polymers.chemistry import ChemistryAuditConfig, ChemistryAuditRecord
from supervised_learning_polymers.manifest import DatasetConfig
from supervised_learning_polymers.targets import ContractModel

_rdkit: Any = import_module("rdkit")
Chem: Any = import_module("rdkit.Chem")
DataStructs: Any = import_module("rdkit.DataStructs")
Descriptors: Any = import_module("rdkit.Chem.Descriptors")
rdFingerprintGenerator: Any = import_module("rdkit.Chem.rdFingerprintGenerator")
RDKIT_VERSION = str(_rdkit.__version__)
_MAX_FAILURE_EXAMPLES = 3

MolecularInputRepresentation = Literal["capped_smiles", "standardized_smiles"]
FeatureFamily = Literal["descriptor", "fingerprint"]
FeatureNamePolicy = Literal["named", "bit_index", "none"]
MorganFingerprintMode = Literal["bit", "count"]
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
_RDKit_DESCRIPTOR_FEATURE_SET_ID = "rdkit_2d"
_RDKit_DESCRIPTOR_METHOD = "rdkit.Chem.Descriptors"
_MORGAN_FINGERPRINT_FEATURE_SET_ID = "morgan_radius2_2048_chiral"
_MORGAN_FINGERPRINT_METHOD = "rdkit.Chem.rdFingerprintGenerator.GetMorganGenerator"
_RECOMMENDED_ACTIONS: dict[RepresentationFailureType, str] = {
    "missing_input_smiles": (
        "Inspect the upstream chemistry record or choose a representation with SMILES."
    ),
    "parse_error": "Inspect the selected chemistry representation.",
    "descriptor_error": "Inspect descriptor support for this molecule.",
    "invalid_feature_values": "Inspect generated descriptor values before model training.",
    "fingerprint_error": "Inspect fingerprint settings for this molecule.",
}


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


class MorganFingerprintSettings(ContractModel):
    """Validated settings for Morgan-style fixed-vector fingerprints."""

    radius: int = Field(default=2, ge=0)
    size: int = Field(default=2048, ge=1)
    include_chirality: bool = True
    mode: MorganFingerprintMode = "bit"


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


class FeatureMatrixMetadata(ContractModel):
    """Metadata for an in-memory generated feature matrix before persistence."""

    feature_set_id: str = Field(min_length=1)
    feature_set_version: str = Field(min_length=1)
    family: FeatureFamily
    input_representation: MolecularInputRepresentation
    rdkit_version: str = Field(min_length=1)
    dtype: str = Field(min_length=1)
    rows: int = Field(ge=0)
    columns: int = Field(ge=1)
    settings: Mapping[str, object] = Field(default_factory=dict)
    feature_names: tuple[str, ...] = Field(default_factory=tuple)
    matrix_hash: str = Field(min_length=1)
    feature_names_hash: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_feature_names(self) -> "FeatureMatrixMetadata":
        if self.feature_names and len(self.feature_names) != self.columns:
            raise ValueError("feature names must match feature matrix column count")
        return self


@dataclass(frozen=True)
class FeatureMatrixBundle:
    """Generated matrix plus sidecar data that will later be persisted."""

    feature_set: FeatureSetConfig
    matrix: npt.NDArray[np.float64]
    sample_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    metadata: FeatureMatrixMetadata
    attempts: tuple[RepresentationAttemptRecord, ...]
    failures: tuple[RepresentationFailureRecord, ...]
    summary: RepresentationSummary


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


def rdkit_2d_feature_set_config(
    *,
    input_representation: MolecularInputRepresentation = "capped_smiles",
) -> FeatureSetConfig:
    """Return the default RDKit named 2D descriptor feature-set config."""

    descriptor_count = len(_rdkit_descriptor_items())
    return FeatureSetConfig(
        feature_set_id=_RDKit_DESCRIPTOR_FEATURE_SET_ID,
        family="descriptor",
        version="1",
        input_representation=input_representation,
        rdkit_method=_RDKit_DESCRIPTOR_METHOD,
        settings={"descriptor_family": "all_named_2d"},
        output_shape=(1, descriptor_count),
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


def morgan_fingerprint_feature_set_config(
    *,
    input_representation: MolecularInputRepresentation = "capped_smiles",
    radius: int = 2,
    size: int = 2048,
    include_chirality: bool = True,
    mode: MorganFingerprintMode = "bit",
) -> FeatureSetConfig:
    """Return the default Morgan fingerprint feature-set config."""

    settings = MorganFingerprintSettings(
        radius=radius,
        size=size,
        include_chirality=include_chirality,
        mode=mode,
    )
    return FeatureSetConfig(
        feature_set_id=_MORGAN_FINGERPRINT_FEATURE_SET_ID,
        family="fingerprint",
        version="1",
        input_representation=input_representation,
        rdkit_method=_MORGAN_FINGERPRINT_METHOD,
        settings=settings.model_dump(mode="json"),
        output_shape=(1, settings.size),
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


def generate_rdkit_2d_features(
    records: Sequence[ChemistryAuditRecord],
    chemistry: ChemistryAuditConfig,
    *,
    feature_set: FeatureSetConfig | None = None,
    rdkit_version: str = RDKIT_VERSION,
) -> FeatureMatrixBundle:
    """Generate deterministic RDKit named 2D descriptor features for valid chemistry records."""

    descriptor_feature_set = feature_set or rdkit_2d_feature_set_config()
    _validate_rdkit_2d_feature_set(descriptor_feature_set)
    descriptor_items = _rdkit_descriptor_items()
    descriptor_names = tuple(name for name, _ in descriptor_items)

    valid_records = tuple(record for record in records if record.status == "valid")
    matrix_rows: list[list[float]] = []
    sample_ids: list[str] = []
    attempts: list[RepresentationAttemptRecord] = []
    failures: list[RepresentationFailureRecord] = []

    for record in valid_records:
        values, failure = _generate_rdkit_2d_record(
            record,
            descriptor_feature_set,
            descriptor_items,
        )
        if failure is None and values is not None:
            attempts.append(
                RepresentationAttemptRecord.from_chemistry_record(
                    record,
                    chemistry,
                    descriptor_feature_set,
                    status="success",
                )
            )
            matrix_rows.append(values)
            sample_ids.append(record.sample_id)
            continue

        assert failure is not None
        attempts.append(
            RepresentationAttemptRecord.from_chemistry_record(
                record,
                chemistry,
                descriptor_feature_set,
                status="failed",
                failure=failure,
            )
        )
        failures.append(failure)

    matrix = np.asarray(matrix_rows, dtype=np.float64)
    if matrix.size == 0:
        matrix = np.empty((0, len(descriptor_names)), dtype=np.float64)

    metadata = FeatureMatrixMetadata(
        feature_set_id=descriptor_feature_set.feature_set_id,
        feature_set_version=descriptor_feature_set.version,
        family=descriptor_feature_set.family,
        input_representation=descriptor_feature_set.input_representation,
        rdkit_version=rdkit_version,
        dtype=str(matrix.dtype),
        rows=matrix.shape[0],
        columns=matrix.shape[1],
        settings=dict(descriptor_feature_set.settings),
        feature_names=descriptor_names,
        matrix_hash=feature_matrix_hash(matrix),
        feature_names_hash=feature_names_hash(descriptor_names),
    )
    summary = RepresentationSummary(
        total_chemistry_valid_records=len(valid_records),
        attempted_records=len(attempts),
        successful_records=len(sample_ids),
        failed_representation_records=len(failures),
        skipped_upstream_chemistry_records=len(records) - len(valid_records),
        dimensions=(
            FeatureSetDimension(
                feature_set_id=descriptor_feature_set.feature_set_id,
                rows=matrix.shape[0],
                columns=matrix.shape[1],
            ),
        ),
        failure_groups=_group_representation_failures(failures),
    )
    return FeatureMatrixBundle(
        feature_set=descriptor_feature_set,
        matrix=matrix,
        sample_ids=tuple(sample_ids),
        feature_names=descriptor_names,
        metadata=metadata,
        attempts=tuple(attempts),
        failures=tuple(failures),
        summary=summary,
    )


def generate_morgan_fingerprint_features(
    records: Sequence[ChemistryAuditRecord],
    chemistry: ChemistryAuditConfig,
    *,
    feature_set: FeatureSetConfig | None = None,
    rdkit_version: str = RDKIT_VERSION,
) -> FeatureMatrixBundle:
    """Generate deterministic Morgan fingerprint features for valid chemistry records."""

    fingerprint_feature_set = feature_set or morgan_fingerprint_feature_set_config()
    settings = _validate_morgan_fingerprint_feature_set(fingerprint_feature_set)

    valid_records = tuple(record for record in records if record.status == "valid")
    matrix_rows: list[list[float]] = []
    sample_ids: list[str] = []
    attempts: list[RepresentationAttemptRecord] = []
    failures: list[RepresentationFailureRecord] = []

    for record in valid_records:
        values, failure = _generate_morgan_fingerprint_record(
            record,
            fingerprint_feature_set,
            settings,
        )
        if failure is None and values is not None:
            attempts.append(
                RepresentationAttemptRecord.from_chemistry_record(
                    record,
                    chemistry,
                    fingerprint_feature_set,
                    status="success",
                )
            )
            matrix_rows.append(values)
            sample_ids.append(record.sample_id)
            continue

        assert failure is not None
        attempts.append(
            RepresentationAttemptRecord.from_chemistry_record(
                record,
                chemistry,
                fingerprint_feature_set,
                status="failed",
                failure=failure,
            )
        )
        failures.append(failure)

    matrix = np.asarray(matrix_rows, dtype=np.float64)
    if matrix.size == 0:
        matrix = np.empty((0, settings.size), dtype=np.float64)

    feature_names = tuple(f"bit_{index}" for index in range(settings.size))
    metadata = FeatureMatrixMetadata(
        feature_set_id=fingerprint_feature_set.feature_set_id,
        feature_set_version=fingerprint_feature_set.version,
        family=fingerprint_feature_set.family,
        input_representation=fingerprint_feature_set.input_representation,
        rdkit_version=rdkit_version,
        dtype=str(matrix.dtype),
        rows=matrix.shape[0],
        columns=matrix.shape[1],
        settings=dict(fingerprint_feature_set.settings),
        feature_names=feature_names,
        matrix_hash=feature_matrix_hash(matrix),
        feature_names_hash=feature_names_hash(feature_names),
    )
    summary = RepresentationSummary(
        total_chemistry_valid_records=len(valid_records),
        attempted_records=len(attempts),
        successful_records=len(sample_ids),
        failed_representation_records=len(failures),
        skipped_upstream_chemistry_records=len(records) - len(valid_records),
        dimensions=(
            FeatureSetDimension(
                feature_set_id=fingerprint_feature_set.feature_set_id,
                rows=matrix.shape[0],
                columns=matrix.shape[1],
            ),
        ),
        failure_groups=_group_representation_failures(failures),
    )
    return FeatureMatrixBundle(
        feature_set=fingerprint_feature_set,
        matrix=matrix,
        sample_ids=tuple(sample_ids),
        feature_names=feature_names,
        metadata=metadata,
        attempts=tuple(attempts),
        failures=tuple(failures),
        summary=summary,
    )


def feature_matrix_hash(matrix: npt.NDArray[np.float64]) -> str:
    """Return a deterministic content hash for a feature matrix."""

    normalized = np.ascontiguousarray(matrix, dtype=np.float64)
    payload = {
        "dtype": str(normalized.dtype),
        "shape": normalized.shape,
        "bytes": normalized.tobytes().hex(),
    }
    serialized = dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def feature_names_hash(feature_names: Sequence[str]) -> str:
    """Return a deterministic hash for feature names and order."""

    serialized = dumps(tuple(feature_names), sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _selected_input_smiles(
    chemistry_record: ChemistryAuditRecord,
    input_representation: MolecularInputRepresentation,
) -> str | None:
    if input_representation == "standardized_smiles":
        return chemistry_record.standardized_smiles
    return chemistry_record.capped_smiles


def _validate_rdkit_2d_feature_set(feature_set: FeatureSetConfig) -> None:
    if feature_set.family != "descriptor":
        raise ValueError("RDKit 2D feature set must use descriptor family")
    if feature_set.rdkit_method != _RDKit_DESCRIPTOR_METHOD:
        raise ValueError(f"RDKit 2D feature set must use {_RDKit_DESCRIPTOR_METHOD}")
    if feature_set.feature_name_policy != "named":
        raise ValueError("RDKit 2D feature set must use named feature policy")
    if len(feature_set.output_shape) != 2:
        raise ValueError("RDKit 2D feature set output shape must be matrix-shaped")
    if feature_set.output_shape[1] != len(_rdkit_descriptor_items()):
        raise ValueError("RDKit 2D feature set column count must match descriptor count")


def _validate_morgan_fingerprint_feature_set(
    feature_set: FeatureSetConfig,
) -> MorganFingerprintSettings:
    if feature_set.family != "fingerprint":
        raise ValueError("Morgan fingerprint feature set must use fingerprint family")
    if feature_set.rdkit_method != _MORGAN_FINGERPRINT_METHOD:
        raise ValueError(f"Morgan fingerprint feature set must use {_MORGAN_FINGERPRINT_METHOD}")
    if feature_set.feature_name_policy != "bit_index":
        raise ValueError("Morgan fingerprint feature set must use bit-index feature policy")
    settings = MorganFingerprintSettings.model_validate(feature_set.settings)
    if len(feature_set.output_shape) != 2:
        raise ValueError("Morgan fingerprint feature set output shape must be matrix-shaped")
    if feature_set.output_shape[1] != settings.size:
        raise ValueError("Morgan fingerprint column count must match configured vector size")
    return settings


def _generate_rdkit_2d_record(
    record: ChemistryAuditRecord,
    feature_set: FeatureSetConfig,
    descriptor_items: tuple[tuple[str, Any], ...],
) -> tuple[list[float] | None, RepresentationFailureRecord | None]:
    input_smiles = _selected_input_smiles(record, feature_set.input_representation)
    if input_smiles is None or input_smiles.strip() == "":
        return None, _representation_failure(
            record,
            feature_set,
            selected_input_smiles=input_smiles,
            failure_type="missing_input_smiles",
            message=(
                f"Missing representation input SMILES for '{feature_set.input_representation}'."
            ),
            stage="input",
        )

    with Chem.rdBase.BlockLogs():
        molecule = Chem.MolFromSmiles(input_smiles)
    if molecule is None:
        return None, _representation_failure(
            record,
            feature_set,
            selected_input_smiles=input_smiles,
            failure_type="parse_error",
            message="RDKit could not parse selected representation input SMILES.",
            stage="parse",
        )

    values: list[float] = []
    try:
        for _, descriptor_function in descriptor_items:
            values.append(float(descriptor_function(molecule)))
    except Exception as error:
        return None, _representation_failure(
            record,
            feature_set,
            selected_input_smiles=input_smiles,
            failure_type="descriptor_error",
            message=f"RDKit descriptor calculation failed: {error}",
            stage="descriptor_generation",
        )

    if any(not isfinite(value) for value in values):
        return None, _representation_failure(
            record,
            feature_set,
            selected_input_smiles=input_smiles,
            failure_type="invalid_feature_values",
            message="RDKit descriptor calculation produced NaN or infinite values.",
            stage="validation",
        )
    return values, None


def _generate_morgan_fingerprint_record(
    record: ChemistryAuditRecord,
    feature_set: FeatureSetConfig,
    settings: MorganFingerprintSettings,
) -> tuple[list[float] | None, RepresentationFailureRecord | None]:
    input_smiles = _selected_input_smiles(record, feature_set.input_representation)
    if input_smiles is None or input_smiles.strip() == "":
        return None, _representation_failure(
            record,
            feature_set,
            selected_input_smiles=input_smiles,
            failure_type="missing_input_smiles",
            message=(
                f"Missing representation input SMILES for '{feature_set.input_representation}'."
            ),
            stage="input",
        )

    with Chem.rdBase.BlockLogs():
        molecule = Chem.MolFromSmiles(input_smiles)
    if molecule is None:
        return None, _representation_failure(
            record,
            feature_set,
            selected_input_smiles=input_smiles,
            failure_type="parse_error",
            message="RDKit could not parse selected representation input SMILES.",
            stage="parse",
        )

    try:
        generator = rdFingerprintGenerator.GetMorganGenerator(
            radius=settings.radius,
            fpSize=settings.size,
            includeChirality=settings.include_chirality,
        )
        vector = np.zeros((settings.size,), dtype=np.float64)
        if settings.mode == "count":
            fingerprint = generator.GetCountFingerprint(molecule)
        else:
            fingerprint = generator.GetFingerprint(molecule)
        DataStructs.ConvertToNumpyArray(fingerprint, vector)
    except Exception as error:
        return None, _representation_failure(
            record,
            feature_set,
            selected_input_smiles=input_smiles,
            failure_type="fingerprint_error",
            message=f"RDKit Morgan fingerprint calculation failed: {error}",
            stage="fingerprint_generation",
        )

    if any(not isfinite(float(value)) for value in vector):
        return None, _representation_failure(
            record,
            feature_set,
            selected_input_smiles=input_smiles,
            failure_type="invalid_feature_values",
            message="RDKit Morgan fingerprint calculation produced NaN or infinite values.",
            stage="validation",
        )
    return vector.tolist(), None


def _representation_failure(
    record: ChemistryAuditRecord,
    feature_set: FeatureSetConfig,
    *,
    selected_input_smiles: str | None,
    failure_type: RepresentationFailureType,
    message: str,
    stage: RepresentationProcessingStage,
) -> RepresentationFailureRecord:
    return RepresentationFailureRecord(
        sample_id=record.sample_id,
        feature_set_id=feature_set.feature_set_id,
        input_representation=feature_set.input_representation,
        selected_input_smiles=selected_input_smiles,
        failure_type=failure_type,
        message=message,
        stage=stage,
        recommended_action=_RECOMMENDED_ACTIONS[failure_type],
    )


def _group_representation_failures(
    failures: Sequence[RepresentationFailureRecord],
) -> tuple[RepresentationFailureGroup, ...]:
    grouped_failures: dict[tuple[str, RepresentationFailureType], list[RepresentationFailureRecord]]
    grouped_failures = {}
    for failure in failures:
        grouped_failures.setdefault((failure.feature_set_id, failure.failure_type), []).append(
            failure
        )

    return tuple(
        RepresentationFailureGroup(
            feature_set_id=feature_set_id,
            failure_type=failure_type,
            count=len(group),
            example_sample_ids=tuple(
                failure.sample_id for failure in group[:_MAX_FAILURE_EXAMPLES]
            ),
            recommended_action=group[0].recommended_action,
        )
        for (feature_set_id, failure_type), group in sorted(grouped_failures.items())
    )


def _rdkit_descriptor_items() -> tuple[tuple[str, Any], ...]:
    return tuple(Descriptors.descList)


def _duplicates(values: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates
