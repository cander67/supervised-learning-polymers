"""Thin local backend for the public interface discovery GUI prototype."""

from argparse import ArgumentParser
from collections.abc import Sequence
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import dumps, loads
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from supervised_learning_polymers.chemistry import (
    ChemistryAuditConfig,
    ChemistryAuditRecord,
    ChemistryAuditSummary,
)
from supervised_learning_polymers.geometry import (
    GeometryAttemptRecord,
    GeometryConfig,
    GeometrySummary,
)
from supervised_learning_polymers.interface_discovery import (
    InterfaceDiscoveryArtifact,
    LeaderboardEntry,
    MetricMetadata,
    ResultMetric,
    ResultSummary,
    RunMetadata,
    RunProgressStep,
    TargetModeSummary,
    load_interface_discovery_artifact,
)
from supervised_learning_polymers.manifest import BenchmarkManifest, ConfigReference, DatasetConfig
from supervised_learning_polymers.structure_viewer import (
    StructureArtifactBundle,
    StructureStatusFilter,
)
from supervised_learning_polymers.targets import AllTargetMode, open_polymer_target_config

STATIC_DIR = Path(__file__).parent / "static" / "interface_gui"


class InterfaceDiscoveryServer(ThreadingHTTPServer):
    """HTTP server carrying the loaded discovery artifact for request handlers."""

    artifact: InterfaceDiscoveryArtifact
    artifact_path: Path
    bind_host: str


def create_interface_discovery_server(
    artifact_path: str | Path, host: str = "127.0.0.1", port: int = 8765
) -> InterfaceDiscoveryServer:
    """Create a local GUI server backed by a validated discovery artifact."""

    artifact = load_interface_discovery_artifact(artifact_path)
    return create_interface_discovery_server_from_artifact(
        artifact,
        artifact_path=Path(artifact_path),
        host=host,
        port=port,
    )


def create_interface_discovery_server_from_artifact(
    artifact: InterfaceDiscoveryArtifact,
    *,
    artifact_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> InterfaceDiscoveryServer:
    """Create a local GUI server backed by an already validated artifact."""

    server = InterfaceDiscoveryServer((host, port), InterfaceDiscoveryRequestHandler)
    server.artifact = artifact
    server.artifact_path = Path(artifact_path)
    server.bind_host = host
    return server


def create_structure_viewer_server(
    chemistry_artifact: str | Path,
    geometry_artifact: str | Path,
    *,
    graph_records: str | Path | None = None,
    downstream_links: str | Path | None = None,
    display_name: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> InterfaceDiscoveryServer:
    """Create a local GUI server from real chemistry and geometry artifact bundles."""

    artifact = build_structure_viewer_artifact(
        chemistry_artifact,
        geometry_artifact,
        graph_records=graph_records,
        downstream_links=downstream_links,
        display_name=display_name,
    )
    return create_interface_discovery_server_from_artifact(
        artifact,
        artifact_path=Path.cwd() / ".runtime-structure-viewer.json",
        host=host,
        port=port,
    )


def build_structure_viewer_artifact(
    chemistry_artifact: str | Path,
    geometry_artifact: str | Path,
    *,
    graph_records: str | Path | None = None,
    downstream_links: str | Path | None = None,
    display_name: str | None = None,
) -> InterfaceDiscoveryArtifact:
    """Build the GUI artifact contract from local chemistry and geometry bundles."""

    chemistry_bundle = _resolve_artifact_bundle(chemistry_artifact, "chemistry")
    geometry_bundle = _resolve_artifact_bundle(geometry_artifact, "geometry")
    chemistry_metadata = _load_json(chemistry_bundle.metadata)
    geometry_metadata = _load_json(geometry_bundle.metadata)
    chemistry_summary = ChemistryAuditSummary.model_validate(_load_json(chemistry_bundle.summary))
    geometry_summary = GeometrySummary.model_validate(_load_json(geometry_bundle.summary))
    chemistry = ChemistryAuditConfig.model_validate(chemistry_metadata["settings"])
    geometry = GeometryConfig.model_validate(geometry_metadata["settings"])
    chemistry_records = tuple(
        ChemistryAuditRecord.model_validate(record)
        for record in _load_json(chemistry_bundle.records)
    )
    geometry_records = tuple(
        GeometryAttemptRecord.model_validate(record)
        for record in _load_json(geometry_bundle.records)
    )
    _validate_bundle_compatibility(
        chemistry_records=chemistry_records,
        geometry_records=geometry_records,
        chemistry_metadata=chemistry_metadata,
        geometry_metadata=geometry_metadata,
    )

    target_config = open_polymer_target_config(AllTargetMode())
    now = datetime.now(UTC).isoformat()
    run_id = f"structure-viewer-{geometry.config_id}"
    artifact_paths = {
        "chemistry_failures": str(chemistry_bundle.failures),
        "chemistry_metadata": str(chemistry_bundle.metadata),
        "chemistry_records": str(chemistry_bundle.records),
        "chemistry_summary": str(chemistry_bundle.summary),
        "geometry_failures": str(geometry_bundle.failures),
        "geometry_metadata": str(geometry_bundle.metadata),
        "geometry_records": str(geometry_bundle.records),
        "geometry_summary": str(geometry_bundle.summary),
    }
    if graph_records is not None:
        artifact_paths["graph_records"] = str(_required_file(graph_records, "graph_records"))
    if downstream_links is not None:
        artifact_paths["downstream_links"] = str(
            _required_file(downstream_links, "downstream_links")
        )

    return InterfaceDiscoveryArtifact(
        manifest=BenchmarkManifest(
            dataset=DatasetConfig(
                dataset_version=chemistry_metadata["dataset_version"],
                sample_id_column="id",
                smiles_column="SMILES",
                target_columns=target_config.target_names(),
            ),
            target=target_config,
            chemistry=ConfigReference(config_id=chemistry.config_id),
            representation=ConfigReference(config_id="structure-viewer-only"),
            split=ConfigReference(config_id="structure-viewer-only"),
            model=ConfigReference(config_id="structure-viewer-only"),
            reporting=ConfigReference(config_id="structure-viewer-local"),
        ),
        target_mode_summary=TargetModeSummary(
            mode="all",
            selected_targets=target_config.resolve_targets(),
            description="All Open Polymer targets; structure viewer launch does not run models.",
        ),
        chemistry_failure_summary=chemistry_summary,
        geometry_summary=geometry_summary,
        run_metadata=RunMetadata(
            run_id=run_id,
            display_name=display_name
            or f"Structure Viewer: {chemistry.config_id} + {geometry.config_id}",
            status="completed",
            created_at=chemistry_metadata.get("created_at", now),
            updated_at=geometry_metadata.get("created_at", now),
            progress_steps=(
                RunProgressStep(
                    name="Load chemistry artifacts",
                    status="completed",
                    completed_units=chemistry_summary.total_records,
                    total_units=chemistry_summary.total_records,
                ),
                RunProgressStep(
                    name="Load geometry artifacts",
                    status="completed",
                    completed_units=geometry_summary.attempted_records,
                    total_units=geometry_summary.total_chemistry_valid_records,
                ),
            ),
            artifact_paths=artifact_paths,
        ),
        result_summary=ResultSummary(
            primary_metric="structure_viewer_artifact_review",
            metrics=(
                ResultMetric(
                    target="Tg",
                    metric="structure_viewer_artifact_review",
                    value=geometry_summary.coverage_fraction,
                    split="local",
                    scope="target",
                ),
            ),
            leaderboard=(
                LeaderboardEntry(
                    rank=1,
                    run_id=run_id,
                    model_family="structure_viewer",
                    primary_metric="structure_viewer_artifact_review",
                    primary_score=geometry_summary.coverage_fraction,
                    target_mode="all",
                ),
            ),
            metric_metadata=(
                MetricMetadata(
                    metric="structure_viewer_artifact_review",
                    display_name="Structure Viewer Coverage",
                    description="Geometry coverage fraction used as a placeholder review metric.",
                ),
            ),
            notes=(
                "Generated at launch from local chemistry and geometry artifacts.",
                "No model training or prediction artifacts are required for this review surface.",
            ),
        ),
    )


class InterfaceDiscoveryRequestHandler(BaseHTTPRequestHandler):
    """Serve static GUI assets and artifact-backed JSON endpoints."""

    server: InterfaceDiscoveryServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/api/health":
            self._send_json({"status": "ok"})
        elif route == "/api/artifact":
            self._send_json(self.server.artifact.model_dump(mode="json"))
        elif route == "/api/structures":
            params = parse_qs(parsed.query)
            query = params.get("query", [None])[0]
            status_filter = _structure_status_filter(params.get("status", ["all"])[0])
            self._send_json(
                self._structure_bundle()
                .list_structures(query, status_filter)
                .model_dump(mode="json")
            )
        elif route == "/api/structure-failures":
            self._send_json(self._structure_bundle().failure_triage().model_dump(mode="json"))
        elif route.startswith("/api/structures/") and route.endswith("/depiction.svg"):
            sample_id = unquote(
                route.removeprefix("/api/structures/").removesuffix("/depiction.svg")
            ).strip("/")
            svg_text = self._structure_bundle().depiction_svg(sample_id)
            if svg_text is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Structure depiction not found")
            else:
                self._send_text(svg_text, "image/svg+xml")
        elif route.startswith("/api/structures/") and route.endswith("/geometry.sdf"):
            sample_id = unquote(
                route.removeprefix("/api/structures/").removesuffix("/geometry.sdf")
            ).strip("/")
            sdf_text = self._structure_bundle().sdf_text(sample_id)
            if sdf_text is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Structure geometry not found")
            else:
                self._send_text(sdf_text, "chemical/x-mdl-sdfile")
        elif route.startswith("/api/structures/") and route.endswith("/graph.json"):
            sample_id = unquote(
                route.removeprefix("/api/structures/").removesuffix("/graph.json")
            ).strip("/")
            graph_payload = self._structure_bundle().graph_payload(sample_id)
            if graph_payload is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Structure graph not found")
            else:
                self._send_json(graph_payload.model_dump(mode="json"))
        elif route.startswith("/api/structures/"):
            sample_id = unquote(route.removeprefix("/api/structures/")).strip("/")
            detail = self._structure_bundle().structure_detail(sample_id)
            if detail is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Structure not found")
            else:
                self._send_json(detail.model_dump(mode="json"))
        elif route in {"/", "/index.html"}:
            self._send_static_file("index.html")
        elif route in {"/app.js", "/styles.css"}:
            self._send_static_file(route.removeprefix("/"))
        elif route.startswith("/vendor/"):
            self._send_static_file(route.removeprefix("/"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args: object) -> None:
        """Keep prototype server quiet during tests and local smoke runs."""

    def _send_json(self, payload: dict[str, Any]) -> None:
        self._send_text(dumps(payload), "application/json")

    def _send_text(self, payload: str, content_type: str) -> None:
        body = payload.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            return

    def _send_static_file(self, filename: str) -> None:
        path = STATIC_DIR / filename
        if not _is_static_child(path) or not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        content_type = {
            ".css": "text/css",
            ".html": "text/html",
            ".js": "text/javascript",
            ".txt": "text/plain",
        }.get(path.suffix, "application/octet-stream")
        self._send_text(path.read_text(), content_type)

    def _structure_bundle(self) -> StructureArtifactBundle:
        return StructureArtifactBundle(self.server.artifact, self.server.artifact_path)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for serving the local GUI prototype."""

    parser = ArgumentParser(description="Serve the interface discovery GUI prototype.")
    parser.add_argument(
        "artifact",
        nargs="?",
        type=Path,
        help="Path to interface discovery artifact JSON.",
    )
    parser.add_argument(
        "--chemistry-artifact",
        type=Path,
        help="Chemistry artifact directory or records.json for direct structure review.",
    )
    parser.add_argument(
        "--geometry-artifact",
        type=Path,
        help="Geometry artifact directory or records.json for direct structure review.",
    )
    parser.add_argument("--graph-records", type=Path, help="Optional graph records JSON.")
    parser.add_argument(
        "--downstream-links",
        type=Path,
        help="Optional downstream link records JSON.",
    )
    parser.add_argument("--display-name", help="Display name for direct structure review runs.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    args = parser.parse_args(argv)

    direct_structure_launch = (
        args.chemistry_artifact is not None or args.geometry_artifact is not None
    )
    try:
        if direct_structure_launch:
            if args.artifact is not None:
                parser.error("artifact JSON cannot be combined with --chemistry-artifact")
            if args.chemistry_artifact is None or args.geometry_artifact is None:
                parser.error(
                    "--chemistry-artifact and --geometry-artifact must be provided together"
                )
            server = create_structure_viewer_server(
                args.chemistry_artifact,
                args.geometry_artifact,
                graph_records=args.graph_records,
                downstream_links=args.downstream_links,
                display_name=args.display_name,
                host=args.host,
                port=args.port,
            )
        else:
            if args.artifact is None:
                parser.error(
                    "provide an interface artifact JSON or both --chemistry-artifact and "
                    "--geometry-artifact"
                )
            server = create_interface_discovery_server(args.artifact, args.host, args.port)
    except (FileNotFoundError, OSError, ValueError) as error:
        parser.error(str(error))

    host = server.bind_host
    port = server.server_port
    _print_structure_viewer_summary(server.artifact)
    surface = "structure viewer" if direct_structure_launch else "interface discovery GUI"
    print(f"Serving {surface} at http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _structure_status_filter(value: str | None) -> StructureStatusFilter:
    if value == "geometry_success":
        return "geometry_success"
    if value == "geometry_failure":
        return "geometry_failure"
    if value == "not_generated":
        return "not_generated"
    if value == "chemistry_failed":
        return "chemistry_failed"
    return "all"


def _is_static_child(path: Path) -> bool:
    return path.resolve().is_relative_to(STATIC_DIR.resolve())


class _LocalArtifactBundle:
    def __init__(self, root: Path, records: Path, failures: Path, summary: Path, metadata: Path):
        self.root = root
        self.records = records
        self.failures = failures
        self.summary = summary
        self.metadata = metadata


def _resolve_artifact_bundle(path: str | Path, label: str) -> _LocalArtifactBundle:
    records = _records_path(Path(path))
    root = records.parent
    return _LocalArtifactBundle(
        root=root,
        records=_required_file(records, f"{label} records"),
        failures=_required_file(root / "failures.json", f"{label} failures"),
        summary=_required_file(root / "summary.json", f"{label} summary"),
        metadata=_required_file(root / "metadata.json", f"{label} metadata"),
    )


def _records_path(path: Path) -> Path:
    return path / "records.json" if path.is_dir() else path


def _required_file(path: str | Path, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} file not found: {resolved}")
    return resolved


def _load_json(path: Path) -> Any:
    return loads(path.read_text())


def _validate_bundle_compatibility(
    *,
    chemistry_records: tuple[ChemistryAuditRecord, ...],
    geometry_records: tuple[GeometryAttemptRecord, ...],
    chemistry_metadata: dict[str, Any],
    geometry_metadata: dict[str, Any],
) -> None:
    chemistry_dataset = chemistry_metadata.get("dataset_version")
    geometry_dataset = geometry_metadata.get("dataset_version")
    if chemistry_dataset != geometry_dataset:
        raise ValueError(
            "chemistry and geometry dataset versions do not match: "
            f"{chemistry_dataset} != {geometry_dataset}"
        )

    chemistry_config = chemistry_metadata.get("chemistry_config_id")
    geometry_chemistry_config = geometry_metadata.get("chemistry_config_id")
    if chemistry_config != geometry_chemistry_config:
        raise ValueError(
            "geometry artifacts were generated from a different chemistry config: "
            f"{geometry_chemistry_config} != {chemistry_config}"
        )

    valid_chemistry_ids = {
        record.sample_id for record in chemistry_records if record.status == "valid"
    }
    unknown_geometry_ids = sorted(
        record.sample_id
        for record in geometry_records
        if record.sample_id not in valid_chemistry_ids
    )
    if unknown_geometry_ids:
        examples = ", ".join(unknown_geometry_ids[:5])
        suffix = (
            "" if len(unknown_geometry_ids) <= 5 else f" and {len(unknown_geometry_ids) - 5} more"
        )
        raise ValueError(
            "geometry records contain sample IDs not present as valid chemistry records: "
            f"{examples}{suffix}"
        )


def _print_structure_viewer_summary(artifact: InterfaceDiscoveryArtifact) -> None:
    geometry = artifact.geometry_summary
    if geometry is None:
        return
    chemistry = artifact.chemistry_failure_summary
    print(
        "Loaded chemistry artifacts: "
        f"total={chemistry.total_records} valid={chemistry.valid_records} "
        f"failed={chemistry.failed_records}",
        flush=True,
    )
    print(
        "Loaded geometry artifacts: "
        f"inputs={geometry.total_chemistry_valid_records} attempted={geometry.attempted_records} "
        f"success={geometry.successful_records} failed={geometry.failed_records} "
        f"coverage={geometry.coverage_fraction:.2%}",
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
