"""Structure viewer contracts joining chemistry and geometry artifacts."""

from importlib import import_module
from json import loads
from pathlib import Path
from typing import Literal

from pydantic import Field

from supervised_learning_polymers.chemistry import (
    ChemistryAuditFailureGroup,
    ChemistryAuditRecord,
    ChemistryFailureRecord,
)
from supervised_learning_polymers.geometry import (
    GeometryAttemptRecord,
    GeometryFailureGroup,
    GeometryFailureRecord,
)
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
GraphViewerStatus = Literal["available", "not_generated", "artifact_missing"]
GraphCoordinateMode = Literal["2d", "3d"]
DownstreamViewerStatus = Literal["available", "not_available", "artifact_missing"]
StructureStatusFilter = Literal[
    "all",
    "geometry_success",
    "geometry_failure",
    "not_generated",
    "chemistry_failed",
]
FailureTriageDomain = Literal["chemistry", "geometry"]
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


class StructureGraphNode(ContractModel):
    """One viewer-ready graph node keyed by stable atom index."""

    atom_index: int = Field(ge=0)
    element: str = Field(min_length=1)
    coordinates_2d: tuple[float, float] | None = None
    coordinates_3d: tuple[float, float, float] | None = None
    features: dict[str, object] = Field(default_factory=dict)


class StructureGraphEdge(ContractModel):
    """One viewer-ready graph edge keyed by atom indices."""

    source: int = Field(ge=0)
    target: int = Field(ge=0)
    bond_order: float = Field(gt=0)
    features: dict[str, object] = Field(default_factory=dict)


class StructureGraphRecord(ContractModel):
    """Project-owned graph artifact shape reserved for PRD 09 compatibility."""

    sample_id: str = Field(min_length=1)
    smiles: str = Field(min_length=1)
    graph_config_id: str = Field(min_length=1)
    coordinate_modes: tuple[GraphCoordinateMode, ...] = Field(min_length=1)
    missing_features: tuple[str, ...] = Field(default_factory=tuple)
    nodes: tuple[StructureGraphNode, ...] = Field(min_length=1)
    edges: tuple[StructureGraphEdge, ...] = Field(default_factory=tuple)


class StructureGraphPayload(ContractModel):
    """Graph panel state for a selected structure."""

    status: GraphViewerStatus
    graph_config_id: str | None = Field(default=None, min_length=1)
    artifact_path: str | None = Field(default=None, min_length=1)
    payload_ref: str | None = Field(default=None, min_length=1)
    coordinate_modes: tuple[GraphCoordinateMode, ...] = Field(default_factory=tuple)
    missing_features: tuple[str, ...] = Field(default_factory=tuple)
    nodes: tuple[StructureGraphNode, ...] = Field(default_factory=tuple)
    edges: tuple[StructureGraphEdge, ...] = Field(default_factory=tuple)
    message: str | None = Field(default=None, min_length=1)


class StructureDownstreamReference(ContractModel):
    """One downstream artifact reference linked to a structure sample."""

    run_id: str = Field(min_length=1)
    model_family: str = Field(min_length=1)
    target: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    split: str = Field(min_length=1)
    prediction_artifact_path: str | None = Field(default=None, min_length=1)
    prediction_ref: str | None = Field(default=None, min_length=1)
    diagnostic_artifact_path: str | None = Field(default=None, min_length=1)
    diagnostic_ref: str | None = Field(default=None, min_length=1)


class StructureDownstreamRecord(ContractModel):
    """Downstream references keyed by sample identity."""

    sample_id: str = Field(min_length=1)
    references: tuple[StructureDownstreamReference, ...] = Field(min_length=1)


class StructureDownstreamPayload(ContractModel):
    """Downstream artifact panel state for a selected structure."""

    status: DownstreamViewerStatus
    artifact_path: str | None = Field(default=None, min_length=1)
    references: tuple[StructureDownstreamReference, ...] = Field(default_factory=tuple)
    message: str | None = Field(default=None, min_length=1)


class StructureRecordSummary(ContractModel):
    """Search-result row for a structure record."""

    sample_id: str = Field(min_length=1)
    chemistry_status: ChemistryViewerStatus
    geometry_status: GeometryViewerStatus
    display_smiles: str | None = None
    has_3d_payload: bool = False
    has_graph_payload: bool = False


class StructureRecordDetail(ContractModel):
    """Full selected-record payload for the structure viewer."""

    sample_id: str = Field(min_length=1)
    chemistry_status: ChemistryViewerStatus
    smiles: StructureSmilesPayload
    provenance: StructureProvenance
    geometry: StructureGeometryPayload
    depiction: StructureDepictionPayload
    graph: StructureGraphPayload
    downstream: StructureDownstreamPayload
    chemistry_failure: ChemistryFailureRecord | None = None


class StructureListResponse(ContractModel):
    """Searchable structure summaries returned by the public API."""

    total_records: int = Field(ge=0)
    returned_records: int = Field(ge=0)
    query: str | None = None
    records: tuple[StructureRecordSummary, ...] = Field(default_factory=tuple)


class StructureFailureTriageGroup(ContractModel):
    """Aggregate failure group that can open representative triage examples."""

    domain: FailureTriageDomain
    failure_type: str = Field(min_length=1)
    count: int = Field(ge=1)
    example_sample_ids: tuple[str, ...] = Field(default_factory=tuple)
    recommended_action: str = Field(min_length=1)
    structure_filter: StructureStatusFilter


class StructureFailureTriageExample(ContractModel):
    """One failure-file example normalized for reviewer triage."""

    domain: FailureTriageDomain
    sample_id: str = Field(min_length=1)
    failure_type: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    message: str = Field(min_length=1)
    method: str | None = None
    recommended_action: str = Field(min_length=1)
    raw_smiles: str | None = None
    canonical_smiles: str | None = None
    standardized_smiles: str | None = None
    capped_smiles: str | None = None
    selected_input_representation: str | None = None
    selected_input_smiles: str | None = None
    attachment_points: tuple[str, ...] = Field(default_factory=tuple)
    runtime_seconds: float | None = None
    fallback_provenance: tuple[dict[str, object], ...] = Field(default_factory=tuple)
    structure_detail_available: bool = False


class StructureFailureTriageResponse(ContractModel):
    """Failure triage payload built from failures.json with record fallbacks."""

    total_groups: int = Field(ge=0)
    total_examples: int = Field(ge=0)
    groups: tuple[StructureFailureTriageGroup, ...] = Field(default_factory=tuple)
    examples: tuple[StructureFailureTriageExample, ...] = Field(default_factory=tuple)
    pattern_reference: tuple[str, ...] = Field(default_factory=tuple)


class StructureArtifactBundle:
    """Lazy structure-viewer bundle resolved from interface artifact paths."""

    def __init__(self, artifact: InterfaceDiscoveryArtifact, artifact_path: str | Path) -> None:
        self.artifact = artifact
        self.artifact_path = Path(artifact_path)
        self._chemistry_records = _load_chemistry_records(artifact, self.artifact_path)
        self._geometry_records = _load_geometry_records(artifact, self.artifact_path)
        self._graph_records = _load_graph_records(artifact, self.artifact_path)
        self._downstream_records = _load_downstream_records(artifact, self.artifact_path)
        self._chemistry_failures = _load_chemistry_failures(
            artifact,
            self.artifact_path,
            self._chemistry_records,
        )
        self._geometry_failures = _load_geometry_failures(
            artifact,
            self.artifact_path,
            self._geometry_records,
        )

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

    def failure_triage(self) -> StructureFailureTriageResponse:
        groups = _triage_groups(self.artifact)
        examples = tuple(
            [
                *(
                    _chemistry_triage_example(
                        failure,
                        _chemistry_group_action(self.artifact, failure.failure_type),
                        self._chemistry_records,
                    )
                    for failure in self._chemistry_failures
                ),
                *(
                    _geometry_triage_example(
                        failure,
                        self._geometry_records.get(failure.sample_id)
                        if self._geometry_records is not None
                        else None,
                        self._chemistry_records,
                    )
                    for failure in self._geometry_failures
                ),
            ]
        )
        return StructureFailureTriageResponse(
            total_groups=len(groups),
            total_examples=len(examples),
            groups=groups,
            examples=examples,
            pattern_reference=(
                "embedding_failed",
                "parse_error",
                "optimization_failed",
                "unsupported_wildcard_atoms",
                "method_unavailable",
            ),
        )

    def sdf_text(self, sample_id: str) -> str | None:
        detail = self.structure_detail(sample_id)
        if detail is None or detail.geometry.status != "success":
            return None
        return detail.geometry.sdf_text

    def graph_payload(self, sample_id: str) -> StructureGraphPayload | None:
        detail = self.structure_detail(sample_id)
        if detail is None or detail.graph.status != "available":
            return None
        return detail.graph

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
            graph=_graph_payload(
                chemistry_record,
                self._graph_records,
                self.artifact.run_metadata.artifact_paths.get("graph_records"),
                geometry_record,
            ),
            downstream=_downstream_payload(
                chemistry_record,
                self._downstream_records,
                self.artifact.run_metadata.artifact_paths.get("downstream_links"),
            ),
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


def _load_graph_records(
    artifact: InterfaceDiscoveryArtifact,
    artifact_path: Path,
) -> dict[str, StructureGraphRecord] | None:
    path = _resolve_artifact_path(
        artifact.run_metadata.artifact_paths.get("graph_records"),
        artifact_path,
    )
    if path is None:
        return None
    payload = loads(path.read_text())
    return {
        record.sample_id: record
        for record in (StructureGraphRecord.model_validate(record) for record in payload)
    }


def _load_downstream_records(
    artifact: InterfaceDiscoveryArtifact,
    artifact_path: Path,
) -> dict[str, StructureDownstreamRecord] | None:
    path = _resolve_artifact_path(
        artifact.run_metadata.artifact_paths.get("downstream_links"),
        artifact_path,
    )
    if path is None:
        return None
    payload = loads(path.read_text())
    return {
        record.sample_id: record
        for record in (StructureDownstreamRecord.model_validate(record) for record in payload)
    }


def _load_chemistry_failures(
    artifact: InterfaceDiscoveryArtifact,
    artifact_path: Path,
    records: tuple[ChemistryAuditRecord, ...],
) -> tuple[ChemistryFailureRecord, ...]:
    path = _resolve_artifact_path(
        artifact.run_metadata.artifact_paths.get("chemistry_failures"),
        artifact_path,
    )
    if path is not None:
        payload = loads(path.read_text())
        return tuple(ChemistryFailureRecord.model_validate(record) for record in payload)
    failures: list[ChemistryFailureRecord] = []
    for record in records:
        if record.failure is not None:
            failures.append(record.failure)
    return tuple(failures)


def _load_geometry_failures(
    artifact: InterfaceDiscoveryArtifact,
    artifact_path: Path,
    records: dict[str, GeometryAttemptRecord] | None,
) -> tuple[GeometryFailureRecord, ...]:
    path = _resolve_artifact_path(
        artifact.run_metadata.artifact_paths.get("geometry_failures"),
        artifact_path,
    )
    if path is not None:
        payload = loads(path.read_text())
        return tuple(GeometryFailureRecord.model_validate(record) for record in payload)
    if records is None:
        return ()
    failures: list[GeometryFailureRecord] = []
    for record in records.values():
        if record.failure is not None:
            failures.append(record.failure)
    return tuple(failures)


def _resolve_artifact_path(value: str | None, artifact_path: Path) -> Path | None:
    if value is None:
        return None

    path = Path(value)
    candidates = (
        (path,)
        if path.is_absolute()
        else (
            _fixture_artifact_path(path),
            artifact_path.parent / path,
            Path.cwd() / path,
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


def _graph_payload(
    chemistry_record: ChemistryAuditRecord,
    graph_records: dict[str, StructureGraphRecord] | None,
    graph_records_path: str | None,
    geometry_record: GeometryAttemptRecord | None,
) -> StructureGraphPayload:
    if graph_records is None:
        if graph_records_path is None:
            return StructureGraphPayload(
                status="not_generated",
                message="No graph records artifact is configured for this run.",
            )
        return StructureGraphPayload(
            status="artifact_missing",
            artifact_path=graph_records_path,
            message="The configured graph records artifact could not be resolved.",
        )

    graph_record = graph_records.get(chemistry_record.sample_id)
    if graph_record is None:
        return StructureGraphPayload(
            status="not_generated",
            artifact_path=graph_records_path,
            message="No graph record is available for this sample.",
        )

    coordinate_modes = tuple(graph_record.coordinate_modes)
    if not (
        geometry_record is not None
        and geometry_record.status == "success"
        and geometry_record.sdf_text is not None
    ):
        coordinate_modes = tuple(mode for mode in coordinate_modes if mode != "3d")
    nodes = graph_record.nodes
    if "3d" not in coordinate_modes:
        nodes = tuple(node.model_copy(update={"coordinates_3d": None}) for node in nodes)

    return StructureGraphPayload(
        status="available",
        graph_config_id=graph_record.graph_config_id,
        artifact_path=graph_records_path,
        payload_ref=f"/api/structures/{chemistry_record.sample_id}/graph.json",
        coordinate_modes=coordinate_modes,
        missing_features=graph_record.missing_features,
        nodes=nodes,
        edges=graph_record.edges,
    )


def _downstream_payload(
    chemistry_record: ChemistryAuditRecord,
    downstream_records: dict[str, StructureDownstreamRecord] | None,
    downstream_records_path: str | None,
) -> StructureDownstreamPayload:
    if downstream_records is None:
        if downstream_records_path is None:
            return StructureDownstreamPayload(
                status="not_available",
                message="No downstream artifact links are configured for this run.",
            )
        return StructureDownstreamPayload(
            status="artifact_missing",
            artifact_path=downstream_records_path,
            message="The configured downstream artifact links could not be resolved.",
        )

    downstream_record = downstream_records.get(chemistry_record.sample_id)
    if downstream_record is None:
        return StructureDownstreamPayload(
            status="not_available",
            artifact_path=downstream_records_path,
            message="No downstream model artifacts are linked for this sample.",
        )

    return StructureDownstreamPayload(
        status="available",
        artifact_path=downstream_records_path,
        references=downstream_record.references,
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
        has_graph_payload=detail.graph.status == "available",
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


def _triage_groups(
    artifact: InterfaceDiscoveryArtifact,
) -> tuple[StructureFailureTriageGroup, ...]:
    chemistry_groups = tuple(
        _chemistry_triage_group(group)
        for group in artifact.chemistry_failure_summary.failure_groups
    )
    geometry_groups: tuple[StructureFailureTriageGroup, ...] = ()
    if artifact.geometry_summary is not None:
        geometry_groups = tuple(
            _geometry_triage_group(group) for group in artifact.geometry_summary.failure_groups
        )
    return (*chemistry_groups, *geometry_groups)


def _chemistry_triage_group(
    group: ChemistryAuditFailureGroup,
) -> StructureFailureTriageGroup:
    return StructureFailureTriageGroup(
        domain="chemistry",
        failure_type=group.failure_type,
        count=group.count,
        example_sample_ids=group.example_sample_ids,
        recommended_action=group.recommended_action,
        structure_filter="chemistry_failed",
    )


def _geometry_triage_group(group: GeometryFailureGroup) -> StructureFailureTriageGroup:
    return StructureFailureTriageGroup(
        domain="geometry",
        failure_type=group.failure_type,
        count=group.count,
        example_sample_ids=group.example_sample_ids,
        recommended_action=group.recommended_action,
        structure_filter="geometry_failure",
    )


def _chemistry_group_action(
    artifact: InterfaceDiscoveryArtifact,
    failure_type: str,
) -> str:
    return next(
        (
            group.recommended_action
            for group in artifact.chemistry_failure_summary.failure_groups
            if group.failure_type == failure_type
        ),
        "Inspect the chemistry failure record.",
    )


def _chemistry_triage_example(
    failure: ChemistryFailureRecord,
    recommended_action: str,
    records: tuple[ChemistryAuditRecord, ...],
) -> StructureFailureTriageExample:
    chemistry_record = _chemistry_record_for_sample(records, failure.sample_id)
    return StructureFailureTriageExample(
        domain="chemistry",
        sample_id=failure.sample_id,
        failure_type=failure.failure_type,
        stage=failure.stage,
        message=failure.message,
        recommended_action=recommended_action,
        raw_smiles=failure.raw_smiles,
        canonical_smiles=chemistry_record.canonical_smiles if chemistry_record else None,
        standardized_smiles=chemistry_record.standardized_smiles if chemistry_record else None,
        capped_smiles=chemistry_record.capped_smiles if chemistry_record else None,
        attachment_points=chemistry_record.attachment_points if chemistry_record else (),
        structure_detail_available=chemistry_record is not None,
    )


def _geometry_triage_example(
    failure: GeometryFailureRecord,
    geometry_record: GeometryAttemptRecord | None,
    chemistry_records: tuple[ChemistryAuditRecord, ...],
) -> StructureFailureTriageExample:
    chemistry_record = _chemistry_record_for_sample(chemistry_records, failure.sample_id)
    return StructureFailureTriageExample(
        domain="geometry",
        sample_id=failure.sample_id,
        failure_type=failure.failure_type,
        stage=failure.stage,
        message=failure.message,
        method=failure.method_name,
        recommended_action=failure.recommended_action,
        raw_smiles=(
            geometry_record.raw_smiles
            if geometry_record is not None
            else chemistry_record.raw_smiles
            if chemistry_record is not None
            else None
        ),
        canonical_smiles=(
            geometry_record.canonical_smiles
            if geometry_record is not None
            else chemistry_record.canonical_smiles
            if chemistry_record is not None
            else None
        ),
        standardized_smiles=(
            geometry_record.standardized_smiles
            if geometry_record is not None
            else chemistry_record.standardized_smiles
            if chemistry_record is not None
            else None
        ),
        capped_smiles=(
            geometry_record.capped_smiles
            if geometry_record is not None
            else chemistry_record.capped_smiles
            if chemistry_record is not None
            else None
        ),
        selected_input_representation=(
            geometry_record.input_representation if geometry_record is not None else None
        ),
        selected_input_smiles=(
            geometry_record.selected_input_smiles if geometry_record is not None else None
        ),
        attachment_points=(
            geometry_record.attachment_points
            if geometry_record is not None
            else chemistry_record.attachment_points
            if chemistry_record is not None
            else ()
        ),
        runtime_seconds=(
            geometry_record.timing.runtime_seconds if geometry_record is not None else None
        ),
        fallback_provenance=(
            tuple(
                fallback.model_dump(mode="json") for fallback in geometry_record.fallback_provenance
            )
            if geometry_record is not None
            else ()
        ),
        structure_detail_available=chemistry_record is not None,
    )


def _chemistry_record_for_sample(
    records: tuple[ChemistryAuditRecord, ...],
    sample_id: str,
) -> ChemistryAuditRecord | None:
    return next((record for record in records if record.sample_id == sample_id), None)


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
