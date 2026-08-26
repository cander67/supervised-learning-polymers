"""Structure viewer contracts joining chemistry and geometry artifacts."""

from importlib import import_module
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
StructureStatusFilter = Literal[
    "all",
    "geometry_success",
    "geometry_failure",
    "not_generated",
    "chemistry_failed",
]
DepictionViewerStatus = Literal["available", "upstream_failed", "missing_smiles", "render_failed"]
SmilesVariantKind = Literal[
    "raw",
    "canonical",
    "standardized",
    "capped",
    "selected_geometry_input",
]

Chem: object = import_module("rdkit.Chem")
rdDepictor: object = import_module("rdkit.Chem.rdDepictor")
rdMolDraw2D: object = import_module("rdkit.Chem.Draw.rdMolDraw2D")


class StructureSmilesPayload(ContractModel):
    """SMILES variants and attachment points for one structure record."""

    raw: str | None = None
    canonical: str | None = None
    standardized: str | None = None
    capped: str | None = None
    selected_geometry_input: str | None = None
    attachment_points: tuple[str, ...] = Field(default_factory=tuple)
    variants: tuple["StructureSmilesVariant", ...] = Field(default_factory=tuple)


class StructureSmilesVariant(ContractModel):
    """One displayable SMILES variant with comparison state."""

    name: SmilesVariantKind
    label: str = Field(min_length=1)
    value: str | None = None
    state: Literal["missing", "unchanged", "changed", "selected"]


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


class StructureDepictionFailurePayload(ContractModel):
    """2D depiction failure normalized for GUI display."""

    failure_type: DepictionViewerStatus
    message: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)


class StructureDepictionPayload(ContractModel):
    """2D depiction state for a selected structure."""

    status: DepictionViewerStatus
    source_smiles: str | None = None
    payload_ref: str | None = None
    failure: StructureDepictionFailurePayload | None = None


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
    depiction: StructureDepictionPayload
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

    def list_structures(
        self,
        query: str | None = None,
        status_filter: StructureStatusFilter = "all",
    ) -> StructureListResponse:
        records = tuple(self._detail_for_record(record) for record in self._chemistry_records)
        summaries = tuple(_summary_from_detail(record) for record in records)
        filtered = _filter_summaries(summaries, records, query, status_filter)
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

    def depiction_svg(self, sample_id: str) -> str | None:
        detail = self.structure_detail(sample_id)
        if detail is None or detail.depiction.status != "available":
            return None
        assert detail.depiction.source_smiles is not None
        return render_2d_svg(detail.depiction.source_smiles)

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
            depiction=_depiction_payload(chemistry_record),
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
    selected_input = geometry_record.selected_input_smiles if geometry_record is not None else None
    return StructureSmilesPayload(
        raw=chemistry_record.raw_smiles,
        canonical=chemistry_record.canonical_smiles,
        standardized=chemistry_record.standardized_smiles,
        capped=chemistry_record.capped_smiles,
        selected_geometry_input=selected_input,
        attachment_points=chemistry_record.attachment_points,
        variants=_smiles_variants(chemistry_record, selected_input),
    )


def _smiles_variants(
    chemistry_record: ChemistryAuditRecord,
    selected_input: str | None,
) -> tuple[StructureSmilesVariant, ...]:
    values: tuple[tuple[SmilesVariantKind, str, str | None], ...] = (
        ("raw", "Raw", chemistry_record.raw_smiles),
        ("canonical", "Canonical", chemistry_record.canonical_smiles),
        ("standardized", "Standardized", chemistry_record.standardized_smiles),
        ("capped", "Capped", chemistry_record.capped_smiles),
        ("selected_geometry_input", "Geometry input", selected_input),
    )
    baseline = chemistry_record.raw_smiles
    return tuple(
        StructureSmilesVariant(
            name=name,
            label=label,
            value=value,
            state=_smiles_variant_state(name, value, baseline),
        )
        for name, label, value in values
    )


def _smiles_variant_state(
    name: SmilesVariantKind, value: str | None, baseline: str | None
) -> Literal["missing", "unchanged", "changed", "selected"]:
    if value is None:
        return "missing"
    if name == "selected_geometry_input":
        return "selected"
    if baseline is None or value != baseline:
        return "changed"
    return "unchanged"


def _depiction_payload(chemistry_record: ChemistryAuditRecord) -> StructureDepictionPayload:
    if chemistry_record.status == "failed":
        return StructureDepictionPayload(
            status="upstream_failed",
            failure=StructureDepictionFailurePayload(
                failure_type="upstream_failed",
                message="Chemistry processing failed before a 2D depiction input was available.",
                recommended_action="Inspect the chemistry failure before reviewing 2D structure.",
            ),
        )

    source_smiles = (
        chemistry_record.capped_smiles
        or chemistry_record.standardized_smiles
        or chemistry_record.canonical_smiles
    )
    if source_smiles is None:
        return StructureDepictionPayload(
            status="missing_smiles",
            failure=StructureDepictionFailurePayload(
                failure_type="missing_smiles",
                message="No validated SMILES representation is available for 2D depiction.",
                recommended_action="Inspect upstream chemistry artifacts for missing derived SMILES.",
            ),
        )

    try:
        render_2d_svg(source_smiles)
    except ValueError as error:
        return StructureDepictionPayload(
            status="render_failed",
            source_smiles=source_smiles,
            failure=StructureDepictionFailurePayload(
                failure_type="render_failed",
                message=str(error),
                recommended_action="Inspect the selected SMILES representation for depiction.",
            ),
        )

    return StructureDepictionPayload(
        status="available",
        source_smiles=source_smiles,
        payload_ref=f"/api/structures/{chemistry_record.sample_id}/depiction.svg",
    )


def render_2d_svg(smiles: str) -> str:
    """Render a deterministic RDKit SVG depiction for a validated SMILES string."""

    molecule = Chem.MolFromSmiles(smiles)  # type: ignore[attr-defined]
    if molecule is None:
        raise ValueError("RDKit could not parse the selected SMILES for 2D depiction.")

    rdDepictor.Compute2DCoords(molecule)  # type: ignore[attr-defined]
    drawer = rdMolDraw2D.MolDraw2DSVG(360, 260)  # type: ignore[attr-defined]
    drawer.DrawMolecule(molecule)
    drawer.FinishDrawing()
    return str(drawer.GetDrawingText())


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
    status_filter: StructureStatusFilter,
) -> tuple[StructureRecordSummary, ...]:
    matching_status = tuple(
        summary for summary in summaries if _matches_status_filter(summary, status_filter)
    )
    if query is None or query.strip() == "":
        return matching_status
    needle = query.casefold()
    matched_ids = {
        detail.sample_id for detail in details if needle in _search_text(detail).casefold()
    }
    return tuple(summary for summary in matching_status if summary.sample_id in matched_ids)


def _matches_status_filter(
    summary: StructureRecordSummary, status_filter: StructureStatusFilter
) -> bool:
    if status_filter == "all":
        return True
    if status_filter == "geometry_success":
        return summary.geometry_status == "success"
    if status_filter == "geometry_failure":
        return summary.geometry_status == "failed"
    if status_filter == "not_generated":
        return summary.geometry_status in {"not_generated", "artifact_missing"}
    return summary.geometry_status == "chemistry_failed"


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
