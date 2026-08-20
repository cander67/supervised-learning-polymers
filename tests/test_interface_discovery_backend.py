from collections.abc import Iterator
from contextlib import contextmanager
from json import loads
from pathlib import Path
from threading import Thread
from typing import cast
from urllib.request import urlopen

from supervised_learning_polymers.interface_backend import create_interface_discovery_server

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "interface_discovery_run.json"


def test_backend_serves_health_check() -> None:
    with running_server() as base_url:
        payload = fetch_text(f"{base_url}/api/health")

    assert loads(payload) == {"status": "ok"}


def test_backend_serves_artifact_backed_json_endpoint() -> None:
    with running_server() as base_url:
        artifact = loads(fetch_text(f"{base_url}/api/artifact"))

    assert artifact["manifest"]["dataset"]["dataset_version"] == "open-polymer-train-fixture-v1"
    assert artifact["target_mode_summary"]["mode"] == "sequential"
    assert (
        artifact["chemistry_failure_summary"]["failure_groups"][0]["failure_type"] == "parse_error"
    )
    assert artifact["run_metadata"]["progress_steps"][-1]["name"] == "Fit target chain"
    assert (
        artifact["result_summary"]["leaderboard"][0]["run_id"] == artifact["run_metadata"]["run_id"]
    )


def test_backend_serves_shared_markdown_report_endpoint() -> None:
    with running_server() as base_url:
        report = fetch_text(f"{base_url}/api/report")

    assert "## Target Mode" in report
    assert "## Chemistry Failures" in report
    assert "## Leaderboard" in report


def test_backend_serves_static_gui_assets() -> None:
    with running_server() as base_url:
        index = fetch_text(f"{base_url}/")
        app_js = fetch_text(f"{base_url}/app.js")
        css = fetch_text(f"{base_url}/styles.css")

    assert '<div id="target-mode"></div>' in index
    assert 'fetch("/api/artifact")' in app_js
    assert "run-interface-discovery-fixture-001" not in app_js
    assert ".summary-grid" in css


@contextmanager
def running_server() -> Iterator[str]:
    server = create_interface_discovery_server(FIXTURE_PATH, port=0)
    host = server.bind_host
    port = server.server_port
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def fetch_text(url: str) -> str:
    with urlopen(url, timeout=5) as response:
        return cast(str, response.read().decode("utf-8"))
