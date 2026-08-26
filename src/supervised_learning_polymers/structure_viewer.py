"""Structure viewer contracts joining chemistry and geometry artifacts."""

from json import loads
from pathlib import Path
from typing import Literal

from pydantic import Field

from supervised_learning_polymers.chemistry import ChemistryAuditRecord, ChemistryFailureRecord
from supervised_learning_polymers.geometry import GeometryAttemptRecord
from supervised_learning_polymers.interface_discovery import InterfaceDiscoveryArtifact
from supervised_learning_polymers.targets import ContractModel

ChemistryViewerStatus = Literal["valid", "failed"]
GeometryViewerStatus = Literal[
    "success",
    "failed",
    "not_generated",
    "artifact_missing",
    "chemistry_failed",
]


class StructureSmilesPayload(ContractModel):
    """SMILES variants and attachment points for one structure record."""

    raw: str | None = None
    canonical: str | None = None
    standardized: str | None = None
    capped: str | None = None
    selected_geometry_input: str | None = None
    attachment_points: tuple[str, ...] = Field(default_factory=tuple)


class StructureProvenance(ContractModel):
    """Artifact and config identity shown with a selected structure."""

    chemistry_config_id: str = Field(min_length=1)
    geometry_config_id: str | None = Field(default=None, min_length=1)
    chemistry_records_path: str | None = Field(default=None, min_length=1)
    geometry_records_path: str | None = Field(default=None, min_length=1)


class StructureGeometryFailurePayload(ContractModel):
    """Failure details normalized for the viewer."""

    failure_type: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    message: str = Field(min_length=1)
    method: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)


class StructureGeometryPayload(ContractModel):
    """Geometry state for a selected structure."""

    status: GeometryViewerStatus
    method: dict[str, object] | None = None
    timing: dict[str, object] | None = None
    sdf_text: str | None = None
    payload_ref: str | None = None
    failure: StructureGeometryFailurePayload | None = None
    fallback_provenance: tuple[dict[str, object], ...] = Field(default_factory=tuple)


class StructureRecordSummary(ContractModel):
    """Search-result row for a structure record."""

    sample_id: str = Field(min_length=1)
    chemistry_status: ChemistryViewerStatus
    geometry_status: GeometryViewerStatus
    display_smiles: str | None = None
    has_3d_payload: bool = False


class StructureRecordDetail(ContractModel):
    """Full selected-record payload for the structure viewer."""

    sample_id: str = Field(min_length=1)
    chemistry_status: ChemistryViewerStatus
    smiles: StructureSmilesPayload
    provenance: StructureProvenance
    geometry: StructureGeometryPayload
    chemistry_failure: ChemistryFailureRecord | None = None


class StructureListResponse(ContractModel):
    """Searchable structure summaries returned by the public API."""

    total_records: int = Field(ge=0)
    returned_records: int = Field(ge=0)
    query: str | None = None
    records: tuple[StructureRecordSummary, ...] = Field(default_factory=tuple)


class StructureArtifactBundle:
    """Lazy structure-viewer bundle resolved from interface artifact paths."""

    def __init__(self, artifact: InterfaceDiscoveryArtifact, artifact_path: str | Path) -> None:
        self.artifact = artifact
        self.artifact_path = Path(artifact_path)
        self._chemistry_records = _load_chemistry_records(artifact, self.artifact_path)
        self._geometry_records = _load_geometry_records(artifact, self.artifact_path)

    def list_structures(self, query: str | None = None) -> StructureListResponse:
        records = tuple(self._detail_for_record(record) for record in self._chemistry_records)
        summaries = tuple(_summary_from_detail(record) for record in records)
        filtered = _filter_summaries(summaries, records, query)
        return StructureListResponse(
            total_records=len(summaries),
            returned_records=len(filtered),
            query=query,
            records=filtered,
        )

    def structure_detail(self, sample_id: str) -> StructureRecordDetail | None:
        chemistry_record = next(
            (record for record in self._chemistry_records if record.sample_id == sample_id),
            None,
        )
        if chemistry_record is None:
            return None
        return self._detail_for_record(chemistry_record)

    def sdf_text(self, sample_id: str) -> str | None:
        detail = self.structure_detail(sample_id)
        if detail is None or detail.geometry.status != "success":
            return None
        return detail.geometry.sdf_text

    def _detail_for_record(self, chemistry_record: ChemistryAuditRecord) -> StructureRecordDetail:
        geometry_record = (
            None
            if self._geometry_records is None
            else self._geometry_records.get(chemistry_record.sample_id)
        )
        smiles = _smiles_payload(chemistry_record, geometry_record)
        chemistry_failure = chemistry_record.failure
        return StructureRecordDetail(
            sample_id=chemistry_record.sample_id,
            chemistry_status=chemistry_record.status,
            smiles=smiles,
            provenance=StructureProvenance(
                chemistry_config_id=self.artifact.manifest.chemistry.config_id,
                geometry_config_id=_geometry_config_id(self.artifact, geometry_record),
                chemistry_records_path=self.artifact.run_metadata.artifact_paths.get(
                    "chemistry_records"
                ),
                geometry_records_path=self.artifact.run_metadata.artifact_paths.get(
                    "geometry_records"
                ),
            ),
            geometry=_geometry_payload(chemistry_record, geometry_record, self._geometry_records),
            chemistry_failure=chemistry_failure,
        )


def _load_chemistry_records(
    artifact: InterfaceDiscoveryArtifact, artifact_path: Path
) -> tuple[ChemistryAuditRecord, ...]:
    path = _resolve_artifact_path(
        artifact.run_metadata.artifact_paths.get("chemistry_records"),
        artifact_path,
    )
    if path is None:
        return ()
    payload = loads(path.read_text())
    return tuple(ChemistryAuditRecord.model_validate(record) for record in payload)


def _load_geometry_records(
    artifact: InterfaceDiscoveryArtifact, artifact_path: Path
) -> dict[str, GeometryAttemptRecord] | None:
    path = _resolve_artifact_path(
        artifact.run_metadata.artifact_paths.get("geometry_records"),
        artifact_path,
    )
    if path is None:
        return None
    payload = loads(path.read_text())
    return {
        record.sample_id: record
        for record in (GeometryAttemptRecord.model_validate(record) for record in payload)
    }


def _resolve_artifact_path(value: str | None, artifact_path: Path) -> Path | None:
    if value is None:
        return None

    path = Path(value)
    candidates = (
        (path,)
        if path.is_absolute()
        else (
            artifact_path.parent / path,
            Path.cwd() / path,
            _fixture_artifact_path(path),
        )
    )
    return next((candidate for candidate in candidates if candidate.exists()), None)


def _fixture_artifact_path(path: Path) -> Path:
    parts = path.parts[1:] if path.parts[:1] == ("artifacts",) else path.parts
    return Path.cwd() / "tests" / "fixtures" / "structure_viewer_artifacts" / Path(*parts)


def _smiles_payload(
    chemistry_record: ChemistryAuditRecord,
    geometry_record: GeometryAttemptRecord | None,
) -> StructureSmilesPayload:
    return StructureSmilesPayload(
        raw=chemistry_record.raw_smiles,
        canonical=chemistry_record.canonical_smiles,
        standardized=chemistry_record.standardized_smiles,
        capped=chemistry_record.capped_smiles,
        selected_geometry_input=(
            geometry_record.selected_input_smiles if geometry_record is not None else None
        ),
        attachment_points=chemistry_record.attachment_points,
    )


def _geometry_payload(
    chemistry_record: ChemistryAuditRecord,
    geometry_record: GeometryAttemptRecord | None,
    geometry_records: dict[str, GeometryAttemptRecord] | None,
) -> StructureGeometryPayload:
    if chemistry_record.status == "failed":
        return StructureGeometryPayload(status="chemistry_failed")
    if geometry_records is None:
        return StructureGeometryPayload(status="artifact_missing")
    if geometry_record is None:
        return StructureGeometryPayload(status="not_generated")
    if geometry_record.status == "success":
        return StructureGeometryPayload(
            status="success",
            method=geometry_record.method.model_dump(mode="json"),
            timing=geometry_record.timing.model_dump(mode="json"),
            sdf_text=geometry_record.sdf_text,
            payload_ref=f"/api/structures/{geometry_record.sample_id}/geometry.sdf",
            fallback_provenance=tuple(
                fallback.model_dump(mode="json") for fallback in geometry_record.fallback_provenance
            ),
        )

    failure = geometry_record.failure
    assert failure is not None
    return StructureGeometryPayload(
        status="failed",
        method=geometry_record.method.model_dump(mode="json"),
        timing=geometry_record.timing.model_dump(mode="json"),
        failure=StructureGeometryFailurePayload(
            failure_type=failure.failure_type,
            stage=failure.stage,
            message=failure.message,
            method=failure.method_name,
            recommended_action=failure.recommended_action,
        ),
        fallback_provenance=tuple(
            fallback.model_dump(mode="json") for fallback in geometry_record.fallback_provenance
        ),
    )


def _summary_from_detail(detail: StructureRecordDetail) -> StructureRecordSummary:
    smiles = (
        detail.smiles.selected_geometry_input or detail.smiles.capped or detail.smiles.standardized
    )
    if smiles is None:
        smiles = detail.smiles.canonical or detail.smiles.raw
    return StructureRecordSummary(
        sample_id=detail.sample_id,
        chemistry_status=detail.chemistry_status,
        geometry_status=detail.geometry.status,
        display_smiles=smiles,
        has_3d_payload=detail.geometry.sdf_text is not None,
    )


def _filter_summaries(
    summaries: tuple[StructureRecordSummary, ...],
    details: tuple[StructureRecordDetail, ...],
    query: str | None,
) -> tuple[StructureRecordSummary, ...]:
    if query is None or query.strip() == "":
        return summaries
    needle = query.casefold()
    matched_ids = {
        detail.sample_id for detail in details if needle in _search_text(detail).casefold()
    }
    return tuple(summary for summary in summaries if summary.sample_id in matched_ids)


def _search_text(detail: StructureRecordDetail) -> str:
    values = (
        detail.sample_id,
        detail.smiles.raw,
        detail.smiles.canonical,
        detail.smiles.standardized,
        detail.smiles.capped,
        detail.smiles.selected_geometry_input,
        detail.geometry.status,
        detail.chemistry_status,
    )
    return " ".join(value for value in values if value is not None)


def _geometry_config_id(
    artifact: InterfaceDiscoveryArtifact, geometry_record: GeometryAttemptRecord | None
) -> str | None:
    path = artifact.run_metadata.artifact_paths.get("geometry_records")
    if path is not None:
        return Path(path).parent.name
    if geometry_record is not None:
        return geometry_record.method.method_name
    return None
