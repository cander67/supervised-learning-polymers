"""Fixture artifact contract for public interface discovery prototypes."""

from json import loads
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from supervised_learning_polymers.chemistry import (
    ChemistryAuditFailureGroup,
    ChemistryAuditSummary,
)
from supervised_learning_polymers.manifest import BenchmarkManifest
from supervised_learning_polymers.targets import ContractModel

RunStatus = Literal["queued", "running", "completed", "failed"]
type ChemistryFailureGroup = ChemistryAuditFailureGroup
type ChemistryFailureSummary = ChemistryAuditSummary


class TargetModeSummary(ContractModel):
    """Display-ready target-mode summary derived from the shared target contract."""

    mode: str = Field(min_length=1)
    selected_targets: tuple[str, ...] = Field(min_length=1)
    description: str = Field(min_length=1)
    sequential_order: tuple[str, ...] = Field(default_factory=tuple)


class RunProgressStep(ContractModel):
    """Status for one interface-visible run step."""

    name: str = Field(min_length=1)
    status: RunStatus
    completed_units: int = Field(ge=0)
    total_units: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_units(self) -> "RunProgressStep":
        if self.completed_units > self.total_units:
            raise ValueError("completed units cannot exceed total units")
        return self


class RunMetadata(ContractModel):
    """Experiment identity and progress fields expected by discovery prototypes."""

    run_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    status: RunStatus
    created_at: str = Field(min_length=1)
    updated_at: str = Field(min_length=1)
    progress_steps: tuple[RunProgressStep, ...] = Field(min_length=1)
    artifact_paths: dict[str, str] = Field(default_factory=dict)


class ResultMetric(ContractModel):
    """One target-level metric shown in result review surfaces."""

    target: str | None = Field(default=None, min_length=1)
    metric: str = Field(min_length=1)
    value: float
    split: str = Field(min_length=1)
    scope: Literal["target", "aggregate"] = "target"

    @model_validator(mode="after")
    def validate_scope(self) -> "ResultMetric":
        if self.scope == "target" and self.target is None:
            raise ValueError("target-level metrics must include a target")
        if self.scope == "aggregate" and self.target is not None:
            raise ValueError("aggregate metrics must not include a target")
        return self


class LeaderboardEntry(ContractModel):
    """One model comparison row for leaderboard-style review."""

    rank: int = Field(ge=1)
    run_id: str = Field(min_length=1)
    model_family: str = Field(min_length=1)
    primary_metric: str = Field(min_length=1)
    primary_score: float
    target_mode: str = Field(min_length=1)


class MetricWeightMetadata(ContractModel):
    """Display metadata for weighted benchmark metrics computed outside the interface."""

    target: str = Field(min_length=1)
    weight: float = Field(gt=0)
    range: float = Field(gt=0)
    label_count: int = Field(ge=1)


class MetricMetadata(ContractModel):
    """Artifact-provided metric context used for review and filtering."""

    metric: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    target_weights: tuple[MetricWeightMetadata, ...] = Field(default_factory=tuple)


class ResultSummary(ContractModel):
    """Result review fields shared by notebook, CLI/report, and GUI prototypes."""

    primary_metric: str = Field(min_length=1)
    metrics: tuple[ResultMetric, ...] = Field(min_length=1)
    leaderboard: tuple[LeaderboardEntry, ...] = Field(min_length=1)
    metric_metadata: tuple[MetricMetadata, ...] = Field(default_factory=tuple)
    notes: tuple[str, ...] = Field(default_factory=tuple)


class InterfaceDiscoveryArtifact(ContractModel):
    """Single fixture artifact bundle consumed by public interface discovery prototypes."""

    artifact_version: str = Field(default="1", min_length=1)
    manifest: BenchmarkManifest
    target_mode_summary: TargetModeSummary
    chemistry_failure_summary: ChemistryFailureSummary
    run_metadata: RunMetadata
    result_summary: ResultSummary

    @model_validator(mode="after")
    def validate_artifact_consistency(self) -> "InterfaceDiscoveryArtifact":
        manifest_targets = self.manifest.target.resolve_targets()
        if self.target_mode_summary.selected_targets != manifest_targets:
            raise ValueError("target summary selected targets must match manifest target mode")

        if self.target_mode_summary.sequential_order:
            if self.target_mode_summary.sequential_order != manifest_targets:
                raise ValueError("sequential target summary order must match manifest target mode")

        metric_targets = {metric.target for metric in self.result_summary.metrics if metric.target}
        unknown_metric_targets = [
            target for target in sorted(metric_targets) if target not in manifest_targets
        ]
        if unknown_metric_targets:
            raise ValueError(
                "result metrics reference targets missing from manifest target mode: "
                f"{', '.join(unknown_metric_targets)}"
            )

        metric_names = {metric.metric for metric in self.result_summary.metrics}
        leaderboard_metric_names = {
            entry.primary_metric for entry in self.result_summary.leaderboard
        }
        metadata_metric_names = {
            metadata.metric for metadata in self.result_summary.metric_metadata
        }
        missing_metric_metadata = sorted(
            (metric_names | leaderboard_metric_names) - metadata_metric_names
        )
        if missing_metric_metadata:
            raise ValueError(
                "result metrics are missing metadata definitions: "
                f"{', '.join(missing_metric_metadata)}"
            )

        metadata_targets = {
            target_metadata.target
            for metric_metadata in self.result_summary.metric_metadata
            for target_metadata in metric_metadata.target_weights
        }
        unknown_metadata_targets = [
            target for target in sorted(metadata_targets) if target not in manifest_targets
        ]
        if unknown_metadata_targets:
            raise ValueError(
                "metric metadata references targets missing from manifest target mode: "
                f"{', '.join(unknown_metadata_targets)}"
            )

        leaderboard_run_ids = {entry.run_id for entry in self.result_summary.leaderboard}
        if self.run_metadata.run_id not in leaderboard_run_ids:
            raise ValueError("run metadata run ID is missing from leaderboard entries")

        return self


def load_interface_discovery_artifact(path: str | Path) -> InterfaceDiscoveryArtifact:
    """Load and validate a fixture artifact bundle from JSON."""

    return InterfaceDiscoveryArtifact.model_validate(loads(Path(path).read_text()))
