"""Fixture artifact contract for public interface discovery prototypes."""

from json import loads
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from supervised_learning_polymers.manifest import BenchmarkManifest
from supervised_learning_polymers.targets import ContractModel

RunStatus = Literal["queued", "running", "completed", "failed"]


class TargetModeSummary(ContractModel):
    """Display-ready target-mode summary derived from the shared target contract."""

    mode: str = Field(min_length=1)
    selected_targets: tuple[str, ...] = Field(min_length=1)
    description: str = Field(min_length=1)
    sequential_order: tuple[str, ...] = Field(default_factory=tuple)


class ChemistryFailureGroup(ContractModel):
    """Aggregated chemistry failures for triage without requiring full audit artifacts yet."""

    failure_type: str = Field(min_length=1)
    count: int = Field(ge=1)
    example_sample_ids: tuple[str, ...] = Field(default_factory=tuple)
    recommended_action: str = Field(min_length=1)


class ChemistryFailureSummary(ContractModel):
    """Small chemistry-audit-shaped summary for interface discovery."""

    total_records: int = Field(ge=0)
    valid_records: int = Field(ge=0)
    failed_records: int = Field(ge=0)
    failure_groups: tuple[ChemistryFailureGroup, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_counts(self) -> "ChemistryFailureSummary":
        if self.valid_records + self.failed_records != self.total_records:
            raise ValueError("valid and failed chemistry records must add up to total records")
        grouped_failures = sum(group.count for group in self.failure_groups)
        if grouped_failures != self.failed_records:
            raise ValueError("chemistry failure group counts must add up to failed records")
        return self


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

    target: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    value: float
    split: str = Field(min_length=1)


class LeaderboardEntry(ContractModel):
    """One model comparison row for leaderboard-style review."""

    rank: int = Field(ge=1)
    run_id: str = Field(min_length=1)
    model_family: str = Field(min_length=1)
    primary_metric: str = Field(min_length=1)
    primary_score: float
    target_mode: str = Field(min_length=1)


class ResultSummary(ContractModel):
    """Result review fields shared by notebook, CLI/report, and GUI prototypes."""

    primary_metric: str = Field(min_length=1)
    metrics: tuple[ResultMetric, ...] = Field(min_length=1)
    leaderboard: tuple[LeaderboardEntry, ...] = Field(min_length=1)
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

        metric_targets = {metric.target for metric in self.result_summary.metrics}
        unknown_metric_targets = [
            target for target in sorted(metric_targets) if target not in manifest_targets
        ]
        if unknown_metric_targets:
            raise ValueError(
                "result metrics reference targets missing from manifest target mode: "
                f"{', '.join(unknown_metric_targets)}"
            )

        leaderboard_run_ids = {entry.run_id for entry in self.result_summary.leaderboard}
        if self.run_metadata.run_id not in leaderboard_run_ids:
            raise ValueError("run metadata run ID is missing from leaderboard entries")

        return self


def load_interface_discovery_artifact(path: str | Path) -> InterfaceDiscoveryArtifact:
    """Load and validate a fixture artifact bundle from JSON."""

    return InterfaceDiscoveryArtifact.model_validate(loads(Path(path).read_text()))
