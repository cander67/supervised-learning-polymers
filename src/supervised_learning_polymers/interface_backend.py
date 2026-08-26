"""Thin local backend for the public interface discovery GUI prototype."""

from argparse import ArgumentParser
from collections.abc import Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import dumps
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from supervised_learning_polymers.interface_discovery import (
    InterfaceDiscoveryArtifact,
    load_interface_discovery_artifact,
)
from supervised_learning_polymers.structure_viewer import (
    StructureArtifactBundle,
    StructureStatusFilter,
)

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
    server = InterfaceDiscoveryServer((host, port), InterfaceDiscoveryRequestHandler)
    server.artifact = artifact
    server.artifact_path = Path(artifact_path)
    server.bind_host = host
    return server


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
        self.wfile.write(body)

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
    parser.add_argument("artifact", type=Path, help="Path to interface discovery artifact JSON.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    args = parser.parse_args(argv)

    server = create_interface_discovery_server(args.artifact, args.host, args.port)
    host = server.bind_host
    port = server.server_port
    print(f"Serving interface discovery GUI at http://{host}:{port}")
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


if __name__ == "__main__":
    raise SystemExit(main())
