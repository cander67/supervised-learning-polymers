"""Typed chemistry audit contracts for polymer source data."""

from collections.abc import Mapping, Sequence
from hashlib import sha256
from importlib import import_module
from json import dumps
from math import isnan
from typing import Any, Literal

from pydantic import Field, model_validator

from supervised_learning_polymers.manifest import DatasetConfig
from supervised_learning_polymers.targets import ContractModel

_rdkit: Any = import_module("rdkit")
Chem: Any = import_module("rdkit.Chem")
rdMolStandardize: Any = import_module("rdkit.Chem.MolStandardize.rdMolStandardize")
rdBase: Any = import_module("rdkit.rdBase")
RDKIT_VERSION = str(_rdkit.__version__)

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
DatasetRow = Mapping[str, object]

_MAX_FAILURE_EXAMPLES = 3
_RECOMMENDED_ACTIONS: dict[ChemistryFailureType, str] = {
    "missing_smiles": "Inspect source data for blank or missing SMILES values.",
    "parse_error": "Inspect malformed SMILES and decide whether to repair or exclude.",
    "standardization_error": "Review standardization settings for this molecule.",
    "capping_error": "Review attachment points and the selected capping strategy.",
    "unsupported_polymer_notation": "Review polymer repeat-unit notation before processing.",
}


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


def audit_dataset_rows(
    rows: Sequence[DatasetRow],
    dataset: DatasetConfig,
    chemistry: ChemistryAuditConfig,
    *,
    split: str = "train",
    rdkit_version: str = RDKIT_VERSION,
) -> ChemistryAuditArtifact:
    """Parse dataset-shaped rows into a fixture-sized chemistry audit artifact."""

    records = tuple(
        audit_dataset_row(row, dataset, row_index=index, split=split, chemistry=chemistry)
        for index, row in enumerate(rows)
    )
    return ChemistryAuditArtifact(
        dataset=dataset,
        chemistry=chemistry,
        rdkit_version=rdkit_version,
        records=records,
        summary=summarize_chemistry_records(records),
    )


def audit_dataset_row(
    row: DatasetRow,
    dataset: DatasetConfig,
    *,
    row_index: int,
    split: str = "train",
    chemistry: ChemistryAuditConfig | None = None,
) -> ChemistryAuditRecord:
    """Parse one dataset-shaped row into a chemistry audit record."""

    chemistry = chemistry or ChemistryAuditConfig(config_id="chemistry-default-v1")
    sample_id = _sample_id_for_row(row, dataset, row_index=row_index, split=split)
    raw_smiles = _raw_smiles_for_row(row, dataset)
    if raw_smiles is None or raw_smiles.strip() == "":
        return _failed_record(
            sample_id=sample_id,
            raw_smiles=raw_smiles,
            failure_type="missing_smiles",
            message=f"Missing source SMILES in column '{dataset.smiles_column}'.",
            stage="input",
        )

    with rdBase.BlockLogs():
        molecule = Chem.MolFromSmiles(raw_smiles)
    if molecule is None:
        return _failed_record(
            sample_id=sample_id,
            raw_smiles=raw_smiles,
            failure_type="parse_error",
            message="RDKit could not parse source SMILES.",
            stage="parse",
        )

    canonical_smiles = Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
    try:
        standardized_molecule = standardize_molecule(molecule, chemistry.standardization)
        standardized_smiles = Chem.MolToSmiles(
            standardized_molecule, canonical=True, isomericSmiles=True
        )
    except Exception as error:
        return _failed_record(
            sample_id=sample_id,
            raw_smiles=raw_smiles,
            failure_type="standardization_error",
            message=f"RDKit standardization failed: {error}",
            stage="standardization",
        )

    try:
        capped_molecule = cap_molecule(standardized_molecule, chemistry.capping)
        capped_smiles = Chem.MolToSmiles(capped_molecule, canonical=True, isomericSmiles=True)
    except Exception as error:
        return _failed_record(
            sample_id=sample_id,
            raw_smiles=raw_smiles,
            failure_type="capping_error",
            message=f"RDKit capping failed: {error}",
            stage="capping",
        )

    return ChemistryAuditRecord(
        sample_id=sample_id,
        raw_smiles=raw_smiles,
        status="valid",
        canonical_smiles=canonical_smiles,
        standardized_smiles=standardized_smiles,
        capped_smiles=capped_smiles,
        attachment_points=_attachment_points(molecule),
    )


def standardize_molecule(molecule: Any, config: StandardizationConfig) -> Any:
    """Apply configured RDKit standardization choices to a molecule copy."""

    standardized = Chem.Mol(molecule)
    if config.fragment_policy == "largest_fragment":
        standardized = rdMolStandardize.LargestFragmentChooser().choose(standardized)
    if config.charge_policy == "neutralize":
        standardized = rdMolStandardize.Uncharger().uncharge(standardized)
    if config.tautomer_policy == "canonicalize":
        standardized = rdMolStandardize.TautomerEnumerator().Canonicalize(standardized)
    if config.stereochemistry_policy == "drop":
        Chem.RemoveStereochemistry(standardized)
    if config.isotope_policy == "drop":
        standardized = _drop_isotopes(standardized)
    return standardized


def cap_molecule(molecule: Any, config: CappingConfig) -> Any:
    """Apply a simple terminal cap to wildcard attachment points."""

    if config.strategy == "uncapped":
        return Chem.Mol(molecule)

    atomic_num = {"hydrogen": 1, "carbon": 6}[config.strategy]
    capped = Chem.RWMol(molecule)
    for atom in capped.GetAtoms():
        if atom.GetAtomicNum() == 0:
            atom.SetAtomicNum(atomic_num)
            atom.SetNoImplicit(False)

    capped_molecule = capped.GetMol()
    Chem.SanitizeMol(capped_molecule)
    return capped_molecule


def chemistry_cache_key(
    dataset: DatasetConfig,
    chemistry: ChemistryAuditConfig,
    *,
    rdkit_version: str = RDKIT_VERSION,
) -> str:
    """Return a deterministic cache key for chemistry audit settings."""

    payload = {
        "dataset": dataset.model_dump(mode="json"),
        "chemistry": chemistry.model_dump(mode="json"),
        "rdkit_version": rdkit_version,
    }
    serialized = dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def summarize_chemistry_records(
    records: Sequence[ChemistryAuditRecord],
) -> ChemistryAuditSummary:
    """Summarize audit records into aggregate counts and failure groups."""

    valid_records = sum(record.status == "valid" for record in records)
    failure_records = tuple(record for record in records if record.failure is not None)
    grouped_failures: dict[ChemistryFailureType, list[ChemistryFailureRecord]] = {}
    for record in failure_records:
        assert record.failure is not None
        grouped_failures.setdefault(record.failure.failure_type, []).append(record.failure)

    return ChemistryAuditSummary(
        total_records=len(records),
        valid_records=valid_records,
        failed_records=len(failure_records),
        failure_groups=tuple(
            ChemistryAuditFailureGroup(
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


def _failed_record(
    *,
    sample_id: str,
    raw_smiles: str | None,
    failure_type: ChemistryFailureType,
    message: str,
    stage: ChemistryProcessingStage,
) -> ChemistryAuditRecord:
    failure = ChemistryFailureRecord(
        sample_id=sample_id,
        raw_smiles=raw_smiles,
        failure_type=failure_type,
        message=message,
        stage=stage,
    )
    return ChemistryAuditRecord(
        sample_id=sample_id,
        raw_smiles=raw_smiles,
        status="failed",
        failure=failure,
    )


def _sample_id_for_row(
    row: DatasetRow,
    dataset: DatasetConfig,
    *,
    row_index: int,
    split: str,
) -> str:
    if dataset.sample_id_column is None:
        return f"{split}-{row_index}"

    value = row.get(dataset.sample_id_column)
    if _is_missing(value):
        return f"{split}-{row_index}"
    return str(value)


def _raw_smiles_for_row(row: DatasetRow, dataset: DatasetConfig) -> str | None:
    value = row.get(dataset.smiles_column)
    if _is_missing(value):
        return None
    return value if isinstance(value, str) else str(value)


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    return isinstance(value, float) and isnan(value)


def _drop_isotopes(molecule: Any) -> Any:
    standardized = Chem.RWMol(molecule)
    for atom in standardized.GetAtoms():
        atom.SetIsotope(0)
    return standardized.GetMol()


def _attachment_points(molecule: Any) -> tuple[str, ...]:
    return tuple(f"*:{atom.GetIdx()}" for atom in molecule.GetAtoms() if atom.GetAtomicNum() == 0)
