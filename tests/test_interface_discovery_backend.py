from collections.abc import Iterator
from contextlib import contextmanager
from json import dumps, loads
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
    assert {
        group["failure_type"] for group in artifact["chemistry_failure_summary"]["failure_groups"]
    } == {
        "capping_error",
        "parse_error",
        "standardization_error",
    }
    assert artifact["run_metadata"]["artifact_paths"]["chemistry_summary"] == (
        "artifacts/chemistry/chemistry-audit-fixture-v1/summary.json"
    )
    assert artifact["geometry_summary"]["total_chemistry_valid_records"] == 5
    assert artifact["geometry_summary"]["successful_records"] == 2
    assert artifact["geometry_summary"]["failed_records"] == 2
    assert artifact["geometry_summary"]["skipped_records"] == 1
    assert artifact["run_metadata"]["artifact_paths"]["geometry_summary"] == (
        "artifacts/geometry/geometry-rdkit-fixture-v1/summary.json"
    )
    assert artifact["run_metadata"]["progress_steps"][-1]["name"] == "Fit target chain"
    assert artifact["result_summary"]["primary_metric"] == "weighted_mean_absolute_error"
    assert {metadata["metric"] for metadata in artifact["result_summary"]["metric_metadata"]} == {
        "mean_absolute_error",
        "weighted_mean_absolute_error",
    }
    assert (
        artifact["result_summary"]["leaderboard"][0]["run_id"] == artifact["run_metadata"]["run_id"]
    )


def test_backend_serves_static_gui_assets() -> None:
    with running_server() as base_url:
        index = fetch_text(f"{base_url}/")
        app_js = fetch_text(f"{base_url}/app.js")
        css = fetch_text(f"{base_url}/styles.css")

    assert '<div id="target-mode"></div>' in index
    assert 'id="geometry-summary"' in index
    assert 'id="metric-filter"' in index
    assert 'fetch("/api/artifact")' in app_js
    assert "renderGeometrySummary" in app_js
    assert "renderMetricRows" in app_js
    assert "run-interface-discovery-fixture-001" not in app_js
    assert ".summary-grid" in css


def test_backend_serves_searchable_structure_summaries() -> None:
    with running_server() as base_url:
        payload = loads(fetch_text(f"{base_url}/api/structures"))

    assert payload["total_records"] == 8
    assert payload["returned_records"] == 8
    assert {record["geometry_status"] for record in payload["records"]} == {
        "success",
        "failed",
        "not_generated",
        "chemistry_failed",
    }
    assert payload["records"][0] == {
        "sample_id": "poly-0001",
        "chemistry_status": "valid",
        "geometry_status": "success",
        "display_smiles": "CCO",
        "has_3d_payload": True,
    }


def test_structure_search_filters_by_sample_id_and_smiles_text() -> None:
    with running_server() as base_url:
        by_id = loads(fetch_text(f"{base_url}/api/structures?query=0006"))
        by_smiles = loads(fetch_text(f"{base_url}/api/structures?query=benzene"))

    assert [record["sample_id"] for record in by_id["records"]] == ["poly-0006"]
    assert [record["sample_id"] for record in by_smiles["records"]] == ["poly-0003"]


def test_backend_serves_successful_structure_detail() -> None:
    with running_server() as base_url:
        detail = loads(fetch_text(f"{base_url}/api/structures/poly-0001"))

    assert detail["sample_id"] == "poly-0001"
    assert detail["smiles"]["raw"] == "CCO"
    assert detail["smiles"]["canonical"] == "CCO"
    assert detail["smiles"]["selected_geometry_input"] == "CCO"
    assert detail["smiles"]["attachment_points"] == []
    assert detail["provenance"]["chemistry_config_id"] == "chemistry-audit-fixture-v1"
    assert detail["provenance"]["geometry_config_id"] == "geometry-rdkit-fixture-v1"
    assert detail["geometry"]["status"] == "success"
    assert detail["geometry"]["sdf_text"].endswith("$$$$\n")
    assert detail["geometry"]["failure"] is None
    assert detail["geometry"]["payload_ref"] == ("/api/structures/poly-0001/geometry.sdf")


def test_backend_serves_failed_structure_detail_with_failure_provenance() -> None:
    with running_server() as base_url:
        detail = loads(fetch_text(f"{base_url}/api/structures/poly-0006"))

    assert detail["geometry"]["status"] == "failed"
    assert detail["geometry"]["sdf_text"] is None
    assert detail["geometry"]["failure"] == {
        "failure_type": "embedding_failed",
        "stage": "embedding",
        "message": "RDKit ETKDG embedding failed with status -1.",
        "method": "rdkit_etkdg_mmff",
        "recommended_action": "Try a capped input representation or inspect the molecule.",
    }


def test_backend_serves_not_generated_and_chemistry_failed_structure_states() -> None:
    with running_server() as base_url:
        not_generated = loads(fetch_text(f"{base_url}/api/structures/poly-0005"))
        chemistry_failed = loads(fetch_text(f"{base_url}/api/structures/poly-0004"))

    assert not_generated["chemistry_status"] == "valid"
    assert not_generated["geometry"]["status"] == "not_generated"
    assert not_generated["geometry"]["failure"] is None
    assert chemistry_failed["chemistry_status"] == "failed"
    assert chemistry_failed["geometry"]["status"] == "chemistry_failed"
    assert chemistry_failed["chemistry_failure"]["failure_type"] == "parse_error"


def test_missing_geometry_artifact_is_distinct_from_not_generated(tmp_path: Path) -> None:
    fixture = loads(FIXTURE_PATH.read_text())
    fixture["run_metadata"]["artifact_paths"]["geometry_records"] = (
        "artifacts/geometry/missing-fixture/records.json"
    )
    local_fixture = tmp_path / "interface_discovery_run.json"
    local_fixture.write_text(dumps(fixture) + "\n")

    with running_server(local_fixture) as base_url:
        detail = loads(fetch_text(f"{base_url}/api/structures/poly-0001"))

    assert detail["geometry"]["status"] == "artifact_missing"
    assert detail["geometry"]["failure"] is None


def test_backend_serves_structure_sdf_payload() -> None:
    with running_server() as base_url:
        sdf_text = fetch_text(f"{base_url}/api/structures/poly-0001/geometry.sdf")

    assert "poly-0001" in sdf_text
    assert sdf_text.endswith("$$$$\n")


def test_gui_metric_filter_changes_visible_metric_and_leaderboard_rows() -> None:
    with running_server() as base_url:
        html = fetch_text(f"{base_url}/")
        app_js = fetch_text(f"{base_url}/app.js")
        artifact_json = fetch_text(f"{base_url}/api/artifact")

    assert 'id="metric-filter"' in html
    assert "state.metricFilter" in app_js

    artifact = loads(artifact_json)
    all_metric_rows = artifact["result_summary"]["metrics"]
    filtered_metric_rows = [
        row for row in all_metric_rows if row["metric"] == "weighted_mean_absolute_error"
    ]
    all_leaderboard_rows = artifact["result_summary"]["leaderboard"]
    filtered_leaderboard_rows = [
        row
        for row in all_leaderboard_rows
        if row["primary_metric"] == "weighted_mean_absolute_error"
    ]

    assert len(filtered_metric_rows) < len(all_metric_rows)
    assert {row["scope"] for row in filtered_metric_rows} == {"aggregate"}
    assert len(filtered_leaderboard_rows) < len(all_leaderboard_rows)
    assert all(
        row["primary_metric"] == "weighted_mean_absolute_error" for row in filtered_leaderboard_rows
    )


@contextmanager
def running_server(fixture_path: Path = FIXTURE_PATH) -> Iterator[str]:
    server = create_interface_discovery_server(fixture_path, port=0)
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
