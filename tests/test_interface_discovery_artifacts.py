from pathlib import Path

import pytest
from pydantic import ValidationError

from supervised_learning_polymers import (
    ChemistryAuditSummary,
    GeometrySummary,
    InterfaceDiscoveryArtifact,
    load_interface_discovery_artifact,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "interface_discovery_run.json"


def test_interface_discovery_fixture_loads_manifest_backed_run() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)

    assert artifact.manifest.dataset.dataset_version == "open-polymer-train-fixture-v1"
    assert artifact.run_metadata.run_id == "run-interface-discovery-fixture-001"
    assert artifact.manifest.chemistry.config_id == "chemistry-audit-fixture-v1"


def test_interface_discovery_fixture_represents_target_mode_for_ui_display() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)

    assert artifact.target_mode_summary.mode == "sequential"
    assert artifact.target_mode_summary.selected_targets == (
        "FFV",
        "Density",
        "Tc",
        "Tg",
        "Rg",
    )
    assert (
        artifact.target_mode_summary.sequential_order == artifact.manifest.target.resolve_targets()
    )


def test_interface_discovery_fixture_includes_chemistry_run_and_result_summaries() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)

    chemistry = artifact.chemistry_failure_summary
    assert isinstance(chemistry, ChemistryAuditSummary)
    assert chemistry.total_records == 9
    assert chemistry.failed_records == 3
    assert {group.failure_type for group in chemistry.failure_groups} == {
        "capping_error",
        "parse_error",
        "standardization_error",
    }

    assert artifact.run_metadata.status == "running"
    assert artifact.run_metadata.progress_steps[-1].name == "Fit target chain"
    assert artifact.result_summary.primary_metric == "weighted_mean_absolute_error"
    assert artifact.result_summary.leaderboard[0].run_id == artifact.run_metadata.run_id


def test_interface_discovery_fixture_includes_geometry_summary_for_viewer_workbench() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)

    geometry = artifact.geometry_summary
    assert isinstance(geometry, GeometrySummary)
    assert geometry.total_chemistry_valid_records == 6
    assert geometry.attempted_records == 5
    assert geometry.successful_records == 3
    assert geometry.failed_records == 2
    assert geometry.skipped_records == 1
    assert geometry.coverage_fraction == 0.5
    assert {group.failure_type: group.count for group in geometry.failure_groups} == {
        "embedding_failed": 2
    }
    assert artifact.run_metadata.artifact_paths["geometry_summary"] == (
        "artifacts/geometry/geometry-rdkit-fixture-v1/summary.json"
    )
    assert artifact.run_metadata.artifact_paths["graph_records"] == (
        "artifacts/graphs/graph-fixture-v1/records.json"
    )


def test_interface_discovery_fixture_includes_weighted_mae_metadata() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)

    metric_names = {metric.metric for metric in artifact.result_summary.metrics}
    assert metric_names == {"mean_absolute_error", "weighted_mean_absolute_error"}

    weighted_metadata = next(
        metadata
        for metadata in artifact.result_summary.metric_metadata
        if metadata.metric == "weighted_mean_absolute_error"
    )
    assert weighted_metadata.display_name == "Open Polymer wMAE"
    assert {weight.target for weight in weighted_metadata.target_weights} == {
        "FFV",
        "Density",
        "Tc",
        "Tg",
        "Rg",
    }
    assert all(weight.weight > 0 for weight in weighted_metadata.target_weights)


def test_interface_discovery_artifact_rejects_target_summary_that_drifted_from_manifest() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)
    data = artifact.model_dump(mode="json")
    data["target_mode_summary"]["selected_targets"] = ["FFV", "Density"]

    with pytest.raises(ValidationError, match="target summary selected targets"):
        InterfaceDiscoveryArtifact.model_validate(data)


def test_interface_discovery_artifact_rejects_inconsistent_chemistry_counts() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)
    data = artifact.model_dump(mode="json")
    data["chemistry_failure_summary"]["failed_records"] = 4

    with pytest.raises(ValidationError, match="valid and failed chemistry records"):
        InterfaceDiscoveryArtifact.model_validate(data)


def test_interface_discovery_artifact_rejects_unknown_chemistry_failure_type() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)
    data = artifact.model_dump(mode="json")
    data["chemistry_failure_summary"]["failure_groups"][0]["failure_type"] = "legacy_error"

    with pytest.raises(ValidationError, match="literal_error"):
        InterfaceDiscoveryArtifact.model_validate(data)


def test_interface_discovery_artifact_rejects_inconsistent_geometry_counts() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)
    data = artifact.model_dump(mode="json")
    assert data["geometry_summary"] is not None
    data["geometry_summary"]["successful_records"] = 4

    with pytest.raises(ValidationError, match="successful and failed records"):
        InterfaceDiscoveryArtifact.model_validate(data)


def test_interface_discovery_artifact_accepts_missing_geometry_summary_for_legacy_fixtures() -> (
    None
):
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)
    data = artifact.model_dump(mode="json")
    data.pop("geometry_summary")

    validated = InterfaceDiscoveryArtifact.model_validate(data)

    assert validated.geometry_summary is None


def test_interface_discovery_artifact_rejects_metrics_outside_selected_targets() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)
    data = artifact.model_dump(mode="json")
    data["result_summary"]["metrics"].append(
        {"target": "Missing", "metric": "mean_absolute_error", "value": 1.0, "split": "validation"}
    )

    with pytest.raises(ValidationError, match="metrics reference targets missing"):
        InterfaceDiscoveryArtifact.model_validate(data)


def test_interface_discovery_artifact_rejects_missing_metric_metadata() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)
    data = artifact.model_dump(mode="json")
    data["result_summary"]["metric_metadata"] = [
        metadata
        for metadata in data["result_summary"]["metric_metadata"]
        if metadata["metric"] != "weighted_mean_absolute_error"
    ]

    with pytest.raises(ValidationError, match="missing metadata definitions"):
        InterfaceDiscoveryArtifact.model_validate(data)
