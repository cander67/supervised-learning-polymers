from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256
from json import dumps, loads
from pathlib import Path
from threading import Thread
from typing import cast
from urllib.request import urlopen

from supervised_learning_polymers.interface_backend import create_interface_discovery_server

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "interface_discovery_run.json"
THREEDMOL_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "supervised_learning_polymers"
    / "static"
    / "interface_gui"
    / "vendor"
    / "3dmol"
    / "3Dmol-min.js"
)
THREEDMOL_SHA256 = "f7cc78921ae72e7623e89cdd111434f58c2efddd2ffda1cd212644b406fb8016"


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
    assert artifact["geometry_summary"]["total_chemistry_valid_records"] == 6
    assert artifact["geometry_summary"]["successful_records"] == 2
    assert artifact["geometry_summary"]["failed_records"] == 2
    assert artifact["geometry_summary"]["skipped_records"] == 2
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
    assert 'id="structure-browser"' in index
    assert 'id="structure-search"' in index
    assert 'id="structure-filter"' in index
    assert 'id="structure-rows"' in index
    assert 'id="structure-smiles-panel"' in index
    assert 'id="structure-2d-panel"' in index
    assert 'id="structure-3d-panel"' in index
    assert 'id="structure-graph-panel"' in index
    assert 'id="graph-mode"' in index
    assert 'id="structure-status-panel"' in index
    assert 'id="structure-provenance-panel"' in index
    assert 'id="structure-panel-states"' in index
    assert 'id="triage-group-rows"' in index
    assert 'id="triage-example-rows"' in index
    assert 'id="triage-detail-panel"' in index
    assert 'id="triage-pattern-guide"' in index
    assert "window.__nativeFetch = window.fetch;" in index
    assert "const nativeFetch = (window.__nativeFetch || window.fetch).bind(window);" in app_js
    assert 'nativeFetch("/api/artifact")' in app_js
    assert 'nativeFetch("/api/structure-failures")' in app_js
    assert 'src="/vendor/3dmol/3Dmol-min.js"' in index
    assert index.index("window.__nativeFetch = window.fetch;") < index.index(
        'src="/vendor/3dmol/3Dmol-min.js"',
    )
    assert index.index('src="/vendor/3dmol/3Dmol-min.js"') < index.index('src="/app.js"')
    assert "loadStructures" in app_js
    assert "selectStructure" in app_js
    assert "renderDepictionPanel" in app_js
    assert "renderConformerPanel" in app_js
    assert "renderGraphPanel" in app_js
    assert "drawGraph" in app_js
    assert "renderFailureTriage" in app_js
    assert "openFailureGroup" in app_js
    assert "geometryUnavailableAction" in app_js
    assert 'window["3Dmol"]' in app_js
    assert "smilesVariantField" in app_js
    assert "fallback_provenance" in app_js
    assert "state.structureFilter" in app_js
    assert "state.structureQuery" in app_js
    assert "No structures match the current search and status filter" in app_js
    assert "renderGeometrySummary" in app_js
    assert "renderMetricRows" in app_js
    assert "run-interface-discovery-fixture-001" not in app_js
    assert ".summary-grid" in css
    assert ".structure-grid" in css
    assert ".triage-workbench" in css
    assert ".triage-grid" in css
    assert ".pattern-guide" in css
    assert ".selected-row" in css
    assert ".depiction-panel" in css
    assert ".conformer-panel" in css
    assert ".graph-panel" in css
    assert ".graph-canvas" in css
    assert ".molecule-viewer" in css
    assert "position: relative;" in css
    assert "overflow: hidden;" in css
    assert ".badge-selected" in css


def test_backend_serves_vendored_3dmol_asset_and_checksum_is_pinned() -> None:
    assert sha256(THREEDMOL_PATH.read_bytes()).hexdigest() == THREEDMOL_SHA256
    with running_server() as base_url:
        asset = fetch_text(f"{base_url}/vendor/3dmol/3Dmol-min.js")
        license_notice = fetch_text(f"{base_url}/vendor/3dmol/3Dmol-min.js.LICENSE.txt")

    assert "3dmol v2.5.5" in license_notice
    assert "$3Dmol" in asset


def test_backend_serves_failure_triage_from_failure_artifact_files() -> None:
    with running_server() as base_url:
        triage = loads(fetch_text(f"{base_url}/api/structure-failures"))

    assert triage["total_groups"] == 4
    assert triage["total_examples"] == 5
    assert triage["pattern_reference"] == [
        "embedding_failed",
        "parse_error",
        "optimization_failed",
        "unsupported_wildcard_atoms",
        "method_unavailable",
    ]
    assert {
        (group["domain"], group["failure_type"]): group["structure_filter"]
        for group in triage["groups"]
    } == {
        ("chemistry", "capping_error"): "chemistry_failed",
        ("chemistry", "parse_error"): "chemistry_failed",
        ("chemistry", "standardization_error"): "chemistry_failed",
        ("geometry", "embedding_failed"): "geometry_failure",
    }

    geometry_examples = {
        example["sample_id"]: example
        for example in triage["examples"]
        if example["domain"] == "geometry"
    }
    assert geometry_examples["poly-0006"]["selected_input_representation"] == "capped_smiles"
    assert geometry_examples["poly-0006"]["selected_input_smiles"] == "[H]C([H])C(C)C"
    assert geometry_examples["poly-0006"]["runtime_seconds"] == 0.112
    assert geometry_examples["poly-0006"]["structure_detail_available"] is True
    assert geometry_examples["poly-0009"]["structure_detail_available"] is False
    assert (
        geometry_examples["poly-0009"]["message"] == "RDKit ETKDG embedding failed with status -1."
    )


def test_backend_serves_searchable_structure_summaries() -> None:
    with running_server() as base_url:
        payload = loads(fetch_text(f"{base_url}/api/structures"))

    assert payload["total_records"] == 9
    assert payload["returned_records"] == 9
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
        "has_graph_payload": False,
    }


def test_structure_search_filters_by_sample_id_and_smiles_text() -> None:
    with running_server() as base_url:
        by_id = loads(fetch_text(f"{base_url}/api/structures?query=0006"))
        by_smiles = loads(fetch_text(f"{base_url}/api/structures?query=benzene"))

    assert [record["sample_id"] for record in by_id["records"]] == ["poly-0006"]
    assert [record["sample_id"] for record in by_smiles["records"]] == ["poly-0003"]


def test_structure_status_filter_returns_fixture_backed_browser_states() -> None:
    with running_server() as base_url:
        successes = loads(fetch_text(f"{base_url}/api/structures?status=geometry_success"))
        failures = loads(fetch_text(f"{base_url}/api/structures?status=geometry_failure"))
        not_generated = loads(fetch_text(f"{base_url}/api/structures?status=not_generated"))
        chemistry_failed = loads(fetch_text(f"{base_url}/api/structures?status=chemistry_failed"))

    assert [record["sample_id"] for record in successes["records"]] == [
        "poly-0001",
        "poly-0002",
    ]
    assert [record["sample_id"] for record in failures["records"]] == ["poly-0006"]
    assert [record["sample_id"] for record in not_generated["records"]] == [
        "poly-0003",
        "poly-0005",
        "1125785790",
    ]
    assert [record["sample_id"] for record in chemistry_failed["records"]] == [
        "poly-0004",
        "poly-0007",
        "poly-0008",
    ]


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
    assert detail["geometry"]["method"]["method_name"] == "rdkit_etkdg_mmff"
    assert detail["geometry"]["timing"]["runtime_seconds"] == 0.021
    assert detail["geometry"]["failure"] is None
    assert detail["geometry"]["payload_ref"] == ("/api/structures/poly-0001/geometry.sdf")
    assert detail["depiction"] == {
        "status": "available",
        "source_smiles": "CCO",
        "payload_ref": "/api/structures/poly-0001/depiction.svg",
        "failure": None,
    }
    assert detail["graph"]["status"] == "not_generated"


def test_backend_serves_failed_structure_detail_with_failure_provenance() -> None:
    with running_server() as base_url:
        detail = loads(fetch_text(f"{base_url}/api/structures/poly-0006"))

    assert detail["geometry"]["status"] == "failed"
    assert detail["geometry"]["sdf_text"] is None
    assert detail["geometry"]["method"]["embedding_status"] == "failed"
    assert detail["geometry"]["timing"]["runtime_seconds"] == 0.112
    assert detail["geometry"]["failure"] == {
        "failure_type": "embedding_failed",
        "stage": "embedding",
        "message": "RDKit ETKDG embedding failed with status -1.",
        "method": "rdkit_etkdg_mmff",
        "recommended_action": "Try a capped input representation or inspect the molecule.",
    }


def test_structure_detail_preserves_fallback_provenance_for_display(tmp_path: Path) -> None:
    fixture = loads(FIXTURE_PATH.read_text())
    geometry_records = loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "structure_viewer_artifacts"
            / "geometry"
            / "geometry-rdkit-fixture-v1"
            / "records.json"
        ).read_text()
    )
    fallback_statuses = [
        "disabled",
        "skipped_not_needed",
        "skipped_dependency_unavailable",
        "attempted",
        "success",
        "failed",
        "unavailable",
    ]
    geometry_records[0]["fallback_provenance"] = [
        {
            "method_name": "xtb" if index % 2 else "mlip",
            "priority": index,
            "status": status,
            "reason": f"{status} fixture reason.",
            "runtime_seconds": None,
            "dependency_available": status
            not in {"disabled", "skipped_dependency_unavailable", "unavailable"},
        }
        for index, status in enumerate(fallback_statuses, start=1)
    ]
    geometry_path = tmp_path / "records.json"
    geometry_path.write_text(dumps(geometry_records) + "\n")
    fixture["run_metadata"]["artifact_paths"]["geometry_records"] = str(geometry_path)
    local_fixture = tmp_path / "interface_discovery_run.json"
    local_fixture.write_text(dumps(fixture) + "\n")

    with running_server(local_fixture) as base_url:
        detail = loads(fetch_text(f"{base_url}/api/structures/poly-0001"))

    assert [
        fallback["status"] for fallback in detail["geometry"]["fallback_provenance"]
    ] == fallback_statuses


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
    assert chemistry_failed["depiction"]["status"] == "upstream_failed"
    assert chemistry_failed["depiction"]["failure"]["recommended_action"] == (
        "Inspect the chemistry failure before reviewing 2D structure."
    )
    assert chemistry_failed["graph"]["status"] == "not_generated"


def test_backend_serves_graph_preview_payload_for_fixture_sample() -> None:
    with running_server() as base_url:
        detail = loads(fetch_text(f"{base_url}/api/structures/1125785790"))
        graph = loads(fetch_text(f"{base_url}/api/structures/1125785790/graph.json"))

    assert detail["sample_id"] == "1125785790"
    assert detail["geometry"]["status"] == "not_generated"
    assert detail["graph"]["status"] == "available"
    assert detail["graph"]["payload_ref"] == "/api/structures/1125785790/graph.json"
    assert detail["graph"]["graph_config_id"] == "graph-fixture-v1"
    assert detail["graph"]["coordinate_modes"] == ["2d", "3d"]
    assert detail["graph"]["missing_features"] == ["partial_charge", "chirality_class"]
    assert len(detail["graph"]["nodes"]) == 37
    assert len(detail["graph"]["edges"]) == 38
    assert detail["graph"]["nodes"][0]["element"] == "*"
    assert detail["graph"]["nodes"][0]["features"]["atomic_number"] == 0
    assert detail["graph"]["nodes"][2]["coordinates_2d"] == [-5.165, -4.814]
    assert detail["graph"]["nodes"][2]["coordinates_3d"] == [-6.13, 3.729, 1.809]
    assert graph == detail["graph"]


def test_graph_state_distinguishes_missing_artifact_from_not_generated(tmp_path: Path) -> None:
    fixture = loads(FIXTURE_PATH.read_text())
    fixture["run_metadata"]["artifact_paths"]["graph_records"] = (
        "artifacts/graphs/missing-fixture/records.json"
    )
    local_fixture = tmp_path / "interface_discovery_run.json"
    local_fixture.write_text(dumps(fixture) + "\n")

    with running_server(local_fixture) as base_url:
        missing = loads(fetch_text(f"{base_url}/api/structures/1125785790"))

    assert missing["graph"]["status"] == "artifact_missing"
    assert (
        missing["graph"]["message"]
        == "The configured graph records artifact could not be resolved."
    )


def test_structure_detail_marks_smiles_variant_comparison_states() -> None:
    with running_server() as base_url:
        detail = loads(fetch_text(f"{base_url}/api/structures/poly-0002"))
        changed_detail = loads(fetch_text(f"{base_url}/api/structures/poly-0006"))
        failed_detail = loads(fetch_text(f"{base_url}/api/structures/poly-0004"))

    variant_states = {variant["name"]: variant["state"] for variant in detail["smiles"]["variants"]}
    assert variant_states == {
        "raw": "unchanged",
        "canonical": "unchanged",
        "standardized": "unchanged",
        "capped": "changed",
        "selected_geometry_input": "selected",
    }
    changed_variant_states = {
        variant["name"]: variant["state"] for variant in changed_detail["smiles"]["variants"]
    }
    assert changed_variant_states["canonical"] == "changed"
    assert changed_variant_states["standardized"] == "changed"
    assert changed_variant_states["capped"] == "changed"
    failed_variant_states = {
        variant["name"]: variant["state"] for variant in failed_detail["smiles"]["variants"]
    }
    assert failed_variant_states["raw"] == "unchanged"
    assert failed_variant_states["canonical"] == "missing"
    assert failed_variant_states["standardized"] == "missing"
    assert failed_variant_states["capped"] == "missing"
    assert failed_variant_states["selected_geometry_input"] == "missing"


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


def test_backend_serves_on_demand_structure_2d_svg_payload() -> None:
    with running_server() as base_url:
        detail = loads(fetch_text(f"{base_url}/api/structures/poly-0001"))
        svg_text = fetch_text(f"{base_url}/api/structures/poly-0001/depiction.svg")

    assert detail["depiction"]["payload_ref"] == "/api/structures/poly-0001/depiction.svg"
    assert svg_text.lstrip().startswith("<?xml")
    assert "<svg" in svg_text
    assert "</svg>" in svg_text


def test_structure_detail_reports_2d_render_failure_status(tmp_path: Path) -> None:
    fixture = loads(FIXTURE_PATH.read_text())
    chemistry_records = loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "structure_viewer_artifacts"
            / "chemistry"
            / "chemistry-audit-fixture-v1"
            / "records.json"
        ).read_text()
    )
    chemistry_records[0]["capped_smiles"] = "not-a-smiles"
    chemistry_path = tmp_path / "records.json"
    chemistry_path.write_text(dumps(chemistry_records) + "\n")
    fixture["run_metadata"]["artifact_paths"]["chemistry_records"] = str(chemistry_path)
    local_fixture = tmp_path / "interface_discovery_run.json"
    local_fixture.write_text(dumps(fixture) + "\n")

    with running_server(local_fixture) as base_url:
        detail = loads(fetch_text(f"{base_url}/api/structures/poly-0001"))

    assert detail["depiction"]["status"] == "render_failed"
    assert detail["depiction"]["failure"]["message"] == (
        "RDKit could not parse the selected SMILES for 2D depiction."
    )


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
