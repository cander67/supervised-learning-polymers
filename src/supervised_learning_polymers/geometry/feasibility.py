"""Typed geometry feasibility contracts for conformer artifact groundwork."""

import signal
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from importlib import import_module
from json import dumps
from pathlib import Path
from time import perf_counter
from types import FrameType
from typing import Any, Literal, TypedDict

from pydantic import Field, model_validator

from supervised_learning_polymers.chemistry import ChemistryAuditConfig, ChemistryAuditRecord
from supervised_learning_polymers.manifest import DatasetConfig
from supervised_learning_polymers.targets import ContractModel

_rdkit: Any = import_module("rdkit")
Chem: Any = import_module("rdkit.Chem")
AllChem: Any = import_module("rdkit.Chem.AllChem")
RDKIT_VERSION = str(_rdkit.__version__)
_MAX_FAILURE_EXAMPLES = 3

GeometryInputRepresentation = Literal["standardized_smiles", "capped_smiles"]
GeometryMethodName = Literal["rdkit_etkdg_mmff", "xtb", "mlip"]
FallbackMethodName = Literal["xtb", "mlip"]
FALLBACK_METHODS: tuple[FallbackMethodName, ...] = ("xtb", "mlip")
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
_RECOMMENDED_ACTIONS: dict[GeometryFailureType, str] = {
    "missing_input_smiles": (
        "Inspect the upstream chemistry record or choose a representation with SMILES."
    ),
    "parse_error": "Inspect the selected chemistry representation.",
    "embedding_failed": "Try a capped input representation or inspect the molecule.",
    "optimization_failed": "Inspect the molecule or try a fallback geometry method.",
    "unsupported_wildcard_atoms": "Try a capped input representation or inspect wildcard atoms.",
    "method_unavailable": "Install or configure the requested geometry method.",
}


class _AttemptBasePayload(TypedDict):
    sample_id: str
    chemistry_config_id: str
    input_representation: GeometryInputRepresentation
    selected_input_smiles: str | None
    raw_smiles: str | None
    canonical_smiles: str | None
    standardized_smiles: str | None
    capped_smiles: str | None
    attachment_points: tuple[str, ...]


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


def summarize_geometry_records(
    records: Sequence[GeometryAttemptRecord],
    *,
    total_chemistry_valid_records: int | None = None,
) -> GeometrySummary:
    """Summarize geometry attempts into coverage, failure, fallback, and runtime counts."""

    total_records = (
        len(records) if total_chemistry_valid_records is None else total_chemistry_valid_records
    )
    if total_records < len(records):
        raise ValueError("total chemistry-valid records cannot be less than attempted records")

    successful_records = sum(record.status == "success" for record in records)
    failure_records = tuple(record for record in records if record.failure is not None)
    grouped_failures: dict[GeometryFailureType, list[GeometryFailureRecord]] = {}
    for record in failure_records:
        assert record.failure is not None
        grouped_failures.setdefault(record.failure.failure_type, []).append(record.failure)

    skipped_fallback_records = sum(
        1
        for record in records
        for fallback in record.fallback_provenance
        if fallback.status.startswith("skipped")
    )
    coverage_fraction = 0.0 if total_records == 0 else successful_records / total_records
    return GeometrySummary(
        total_chemistry_valid_records=total_records,
        attempted_records=len(records),
        successful_records=successful_records,
        failed_records=len(failure_records),
        skipped_records=total_records - len(records),
        skipped_fallback_records=skipped_fallback_records,
        coverage_fraction=coverage_fraction,
        total_runtime_seconds=sum(record.timing.runtime_seconds for record in records),
        failure_groups=tuple(
            GeometryFailureGroup(
                failure_type=failure_type,
                count=len(failures),
                example_sample_ids=tuple(
                    failure.sample_id for failure in failures[:_MAX_FAILURE_EXAMPLES]
                ),
                recommended_action=_RECOMMENDED_ACTIONS[failure_type],
            )
            for failure_type, failures in sorted(grouped_failures.items())
        ),
    )


def write_geometry_artifacts(
    artifact: GeometryArtifact,
    artifact_root: str | Path,
    *,
    created_at: str | None = None,
) -> GeometryArtifactPaths:
    """Persist geometry attempt records, failures, summary, and metadata."""

    output_dir = geometry_artifact_dir(artifact_root, artifact.geometry)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = GeometryArtifactPaths(
        artifact_root=str(output_dir),
        records=str(output_dir / "records.json"),
        failures=str(output_dir / "failures.json"),
        summary=str(output_dir / "summary.json"),
        metadata=str(output_dir / "metadata.json"),
    )
    rdkit_version = artifact.rdkit_version or RDKIT_VERSION
    metadata = GeometryOutputMetadata(
        artifact_version=artifact.artifact_version,
        dataset_version=artifact.dataset.dataset_version,
        chemistry_config_id=artifact.chemistry.config_id,
        chemistry_cache_key=artifact.chemistry_cache_key,
        chemistry_provenance=ChemistryGeometryProvenance(
            capping_strategy=artifact.chemistry.capping.strategy,
            capping_version=artifact.chemistry.capping.version,
            geometry_input_representation=artifact.geometry.input_representation,
        ),
        geometry_config_id=artifact.geometry.config_id,
        geometry_cache_key=geometry_cache_key(
            artifact.dataset,
            artifact.chemistry,
            artifact.chemistry_cache_key,
            artifact.geometry,
            rdkit_version=rdkit_version,
        ),
        rdkit_version=rdkit_version,
        created_at=created_at or datetime.now(UTC).isoformat(),
        settings=artifact.geometry,
        output_paths=paths,
    )

    _write_json(
        Path(paths.records), [record.model_dump(mode="json") for record in artifact.records]
    )
    _write_json(
        Path(paths.failures),
        [
            record.failure.model_dump(mode="json")
            for record in artifact.records
            if record.failure is not None
        ],
    )
    _write_json(Path(paths.summary), artifact.summary.model_dump(mode="json"))
    _write_json(Path(paths.metadata), metadata.model_dump(mode="json"))
    return paths


def geometry_artifact_dir(artifact_root: str | Path, geometry: GeometryConfig) -> Path:
    """Return the conventional geometry artifact directory for a config."""

    return Path(artifact_root) / "geometry" / geometry.config_id


def geometry_cache_key(
    dataset: DatasetConfig,
    chemistry: ChemistryAuditConfig,
    chemistry_cache_key: str,
    geometry: GeometryConfig,
    *,
    rdkit_version: str = RDKIT_VERSION,
) -> str:
    """Return a deterministic cache key for geometry feasibility settings."""

    payload = {
        "dataset": dataset.model_dump(mode="json"),
        "chemistry": {
            "config_id": chemistry.config_id,
            "cache_key": chemistry_cache_key,
        },
        "geometry": geometry.model_dump(mode="json"),
        "rdkit_version": rdkit_version,
    }
    serialized = dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def attempt_geometry_record(
    chemistry_record: ChemistryAuditRecord,
    chemistry: ChemistryAuditConfig,
    geometry: GeometryConfig,
    *,
    rdkit_version: str = RDKIT_VERSION,
) -> GeometryAttemptRecord:
    """Attempt RDKit ETKDG/MMFF geometry generation for one chemistry audit record."""

    start = perf_counter()
    input_smiles = _selected_input_smiles(chemistry_record, geometry.input_representation)
    base_payload = _attempt_base_payload(chemistry_record, chemistry, geometry, input_smiles)
    try:
        with _geometry_timeout(geometry.timeout_seconds):
            return _attempt_geometry_record_without_timeout(
                input_smiles,
                base_payload,
                geometry,
                rdkit_version=rdkit_version,
                start=start,
            )
    except TimeoutError as error:
        return _failed_attempt(
            base_payload,
            geometry,
            rdkit_version=rdkit_version,
            start=start,
            failure_type="embedding_failed",
            message=f"RDKit geometry attempt timed out: {error}",
            stage="embedding",
            recommended_action=(
                "Increase the per-record timeout, try fewer embedding attempts, or inspect the molecule."
            ),
        )


def _attempt_geometry_record_without_timeout(
    input_smiles: str | None,
    base_payload: _AttemptBasePayload,
    geometry: GeometryConfig,
    *,
    rdkit_version: str,
    start: float,
) -> GeometryAttemptRecord:
    if input_smiles is None or input_smiles.strip() == "":
        return _failed_attempt(
            base_payload,
            geometry,
            rdkit_version=rdkit_version,
            start=start,
            failure_type="missing_input_smiles",
            message=(
                f"Missing geometry input SMILES for representation "
                f"'{geometry.input_representation}'."
            ),
            stage="input",
            recommended_action=(
                "Inspect the upstream chemistry record or choose a representation with SMILES."
            ),
        )

    with Chem.rdBase.BlockLogs():
        molecule = Chem.MolFromSmiles(input_smiles)
    if molecule is None:
        return _failed_attempt(
            base_payload,
            geometry,
            rdkit_version=rdkit_version,
            start=start,
            failure_type="parse_error",
            message="RDKit could not parse selected geometry input SMILES.",
            stage="parse",
            recommended_action="Inspect the selected chemistry representation.",
        )

    molecule = Chem.AddHs(molecule)
    try:
        with Chem.rdBase.BlockLogs():
            embed_status = AllChem.EmbedMolecule(
                molecule,
                maxAttempts=geometry.embed_attempts,
                randomSeed=geometry.random_seed,
            )
    except Exception as error:
        return _failed_attempt(
            base_payload,
            geometry,
            rdkit_version=rdkit_version,
            start=start,
            failure_type="embedding_failed",
            message=f"RDKit ETKDG embedding failed: {error}",
            stage="embedding",
            recommended_action="Try a capped input representation or inspect the molecule.",
        )
    if embed_status != 0:
        return _failed_attempt(
            base_payload,
            geometry,
            rdkit_version=rdkit_version,
            start=start,
            failure_type="embedding_failed",
            message=f"RDKit ETKDG embedding failed with status {embed_status}.",
            stage="embedding",
            recommended_action="Try a capped input representation or inspect the molecule.",
        )

    try:
        optimization_status = _optimize_molecule(molecule, geometry)
    except Exception as error:
        return _failed_attempt(
            base_payload,
            geometry,
            rdkit_version=rdkit_version,
            start=start,
            failure_type="optimization_failed",
            message=f"RDKit MMFF optimization failed: {error}",
            stage="optimization",
            recommended_action="Inspect the molecule or try a fallback geometry method.",
            embedding_status="success",
            optimization_status="failed",
        )
    if optimization_status == "failed":
        return _failed_attempt(
            base_payload,
            geometry,
            rdkit_version=rdkit_version,
            start=start,
            failure_type="optimization_failed",
            message="RDKit MMFF optimization failed for the embedded conformer.",
            stage="optimization",
            recommended_action="Inspect the molecule or try a fallback geometry method.",
            embedding_status="success",
            optimization_status=optimization_status,
        )

    molecule.SetProp("_Name", base_payload["sample_id"])
    sdf_text = Chem.MolToMolBlock(molecule) + "\n$$$$\n"
    return GeometryAttemptRecord(
        **base_payload,
        status="success",
        method=GeometryMethodProvenance(
            method_name=geometry.primary_method,
            rdkit_version=rdkit_version,
            embedding_status="success",
            optimization_status=optimization_status,
        ),
        timing=GeometryTiming(runtime_seconds=perf_counter() - start),
        sdf_text=sdf_text,
        fallback_provenance=_fallback_provenance(geometry, rdkit_succeeded=True),
    )


@contextmanager
def _geometry_timeout(timeout_seconds: float | None) -> Iterator[None]:
    if timeout_seconds is None:
        yield
        return

    def raise_timeout(_: int, __: FrameType | None) -> None:
        raise TimeoutError(f"geometry attempt timed out after {timeout_seconds} seconds")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    signal.signal(signal.SIGALRM, raise_timeout)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def _selected_input_smiles(
    chemistry_record: ChemistryAuditRecord,
    input_representation: GeometryInputRepresentation,
) -> str | None:
    if input_representation == "standardized_smiles":
        return chemistry_record.standardized_smiles
    return chemistry_record.capped_smiles


def _attempt_base_payload(
    chemistry_record: ChemistryAuditRecord,
    chemistry: ChemistryAuditConfig,
    geometry: GeometryConfig,
    input_smiles: str | None,
) -> _AttemptBasePayload:
    return {
        "sample_id": chemistry_record.sample_id,
        "chemistry_config_id": chemistry.config_id,
        "input_representation": geometry.input_representation,
        "selected_input_smiles": input_smiles,
        "raw_smiles": chemistry_record.raw_smiles,
        "canonical_smiles": chemistry_record.canonical_smiles,
        "standardized_smiles": chemistry_record.standardized_smiles,
        "capped_smiles": chemistry_record.capped_smiles,
        "attachment_points": chemistry_record.attachment_points,
    }


def _optimize_molecule(molecule: Any, geometry: GeometryConfig) -> str:
    if not AllChem.MMFFHasAllMoleculeParams(molecule):
        return "unavailable"

    status = AllChem.MMFFOptimizeMolecule(
        molecule,
        maxIters=geometry.optimization_max_iterations,
    )
    if status == 0:
        return "success"
    if status == 1:
        return "not_converged"
    return "failed"


def _failed_attempt(
    base_payload: _AttemptBasePayload,
    geometry: GeometryConfig,
    *,
    rdkit_version: str,
    start: float,
    failure_type: GeometryFailureType,
    message: str,
    stage: GeometryProcessingStage,
    recommended_action: str,
    embedding_status: str = "not_started",
    optimization_status: str | None = None,
) -> GeometryAttemptRecord:
    sample_id = base_payload["sample_id"]
    method_name: GeometryMethodName = "rdkit_etkdg_mmff"
    return GeometryAttemptRecord(
        **base_payload,
        status="failed",
        method=GeometryMethodProvenance(
            method_name=method_name,
            rdkit_version=rdkit_version,
            embedding_status=embedding_status,
            optimization_status=optimization_status,
        ),
        timing=GeometryTiming(runtime_seconds=perf_counter() - start),
        failure=GeometryFailureRecord(
            sample_id=sample_id,
            method_name=method_name,
            failure_type=failure_type,
            message=message,
            stage=stage,
            recommended_action=recommended_action,
        ),
        fallback_provenance=_fallback_provenance(geometry, rdkit_succeeded=False),
    )


def _fallback_provenance(
    geometry: GeometryConfig,
    *,
    rdkit_succeeded: bool,
) -> tuple[FallbackMethodProvenance, ...]:
    enabled_priorities = {
        method_name: index for index, method_name in enumerate(geometry.fallback_methods, start=1)
    }
    provenance: list[FallbackMethodProvenance] = []
    for default_index, method_name in enumerate(FALLBACK_METHODS, start=1):
        configured_priority = enabled_priorities.get(method_name)
        if configured_priority is None:
            provenance.append(
                FallbackMethodProvenance(
                    method_name=method_name,
                    priority=default_index,
                    status="disabled",
                    reason="Fallback method is not enabled in geometry config.",
                    dependency_available=False,
                )
            )
            continue

        if rdkit_succeeded:
            provenance.append(
                FallbackMethodProvenance(
                    method_name=method_name,
                    priority=configured_priority,
                    status="skipped_not_needed",
                    reason="RDKit conformer generation succeeded.",
                    dependency_available=False,
                )
            )
        else:
            provenance.append(
                FallbackMethodProvenance(
                    method_name=method_name,
                    priority=configured_priority,
                    status="skipped_dependency_unavailable",
                    reason="Fallback dependency is not installed or configured for local runs.",
                    dependency_available=False,
                )
            )
    return tuple(provenance)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(dumps(payload, indent=2, sort_keys=True) + "\n")
