from pathlib import Path

import pytest
from pydantic import ValidationError

from supervised_learning_polymers import (
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
    assert chemistry.total_records == 8
    assert chemistry.failed_records == 2
    assert {group.failure_type for group in chemistry.failure_groups} == {
        "parse_error",
        "standardization_error",
    }

    assert artifact.run_metadata.status == "running"
    assert artifact.run_metadata.progress_steps[-1].name == "Fit target chain"
    assert artifact.result_summary.primary_metric == "mean_absolute_error"
    assert artifact.result_summary.leaderboard[0].run_id == artifact.run_metadata.run_id


def test_interface_discovery_artifact_rejects_target_summary_that_drifted_from_manifest() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)
    data = artifact.model_dump(mode="json")
    data["target_mode_summary"]["selected_targets"] = ["FFV", "Density"]

    with pytest.raises(ValidationError, match="target summary selected targets"):
        InterfaceDiscoveryArtifact.model_validate(data)


def test_interface_discovery_artifact_rejects_inconsistent_chemistry_counts() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)
    data = artifact.model_dump(mode="json")
    data["chemistry_failure_summary"]["failed_records"] = 3

    with pytest.raises(ValidationError, match="valid and failed chemistry records"):
        InterfaceDiscoveryArtifact.model_validate(data)


def test_interface_discovery_artifact_rejects_metrics_outside_selected_targets() -> None:
    artifact = load_interface_discovery_artifact(FIXTURE_PATH)
    data = artifact.model_dump(mode="json")
    data["result_summary"]["metrics"].append(
        {"target": "Missing", "metric": "mean_absolute_error", "value": 1.0, "split": "validation"}
    )

    with pytest.raises(ValidationError, match="metrics reference targets missing"):
        InterfaceDiscoveryArtifact.model_validate(data)
