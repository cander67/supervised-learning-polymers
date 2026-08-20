"""Markdown report generation for public interface discovery artifacts."""

from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path

from supervised_learning_polymers.interface_discovery import (
    InterfaceDiscoveryArtifact,
    load_interface_discovery_artifact,
)


def render_interface_discovery_report(artifact: InterfaceDiscoveryArtifact) -> str:
    """Render a reviewable Markdown report from one interface discovery artifact."""

    manifest = artifact.manifest
    target_summary = artifact.target_mode_summary
    chemistry = artifact.chemistry_failure_summary
    run = artifact.run_metadata
    results = artifact.result_summary

    lines = [
        f"# {run.display_name}",
        "",
        "## Manifest",
        "",
        f"- Manifest version: `{manifest.manifest_version}`",
        f"- Dataset: `{manifest.dataset.dataset_version}`",
        f"- Chemistry config: `{manifest.chemistry.config_id}`",
        f"- Representation config: `{manifest.representation.config_id}`",
        f"- Split config: `{manifest.split.config_id}`",
        f"- Model config: `{manifest.model.config_id}`",
        f"- Reporting config: `{manifest.reporting.config_id}`",
        "",
        "## Target Mode",
        "",
        f"- Mode: `{target_summary.mode}`",
        f"- Selected targets: {_join_inline_code(target_summary.selected_targets)}",
        f"- Description: {target_summary.description}",
    ]

    if target_summary.sequential_order:
        lines.append(f"- Sequential order: {' -> '.join(target_summary.sequential_order)}")

    lines.extend(
        [
            "",
            "## Chemistry Failures",
            "",
            f"- Total records: {chemistry.total_records}",
            f"- Valid records: {chemistry.valid_records}",
            f"- Failed records: {chemistry.failed_records}",
            "",
        ]
    )

    if chemistry.failure_groups:
        lines.extend(
            [
                "| Failure Type | Count | Examples | Recommended Action |",
                "| --- | ---: | --- | --- |",
            ]
        )
        for group in chemistry.failure_groups:
            lines.append(
                "| "
                f"{group.failure_type} | "
                f"{group.count} | "
                f"{', '.join(group.example_sample_ids) or 'n/a'} | "
                f"{group.recommended_action} |"
            )
    else:
        lines.append("No chemistry failures are present in this artifact.")

    lines.extend(
        [
            "",
            "## Run Progress",
            "",
            f"- Run ID: `{run.run_id}`",
            f"- Status: `{run.status}`",
            f"- Created: {run.created_at}",
            f"- Updated: {run.updated_at}",
            "",
            "| Step | Status | Progress |",
            "| --- | --- | ---: |",
        ]
    )
    for step in run.progress_steps:
        lines.append(
            f"| {step.name} | `{step.status}` | {step.completed_units}/{step.total_units} |"
        )

    if run.artifact_paths:
        lines.extend(["", "### Artifact Paths", ""])
        for name, path in sorted(run.artifact_paths.items()):
            lines.append(f"- {name}: `{path}`")

    lines.extend(
        [
            "",
            "## Results",
            "",
            f"- Primary metric: `{results.primary_metric}`",
            "",
            "| Target | Split | Metric | Value |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for metric in results.metrics:
        lines.append(f"| {metric.target} | {metric.split} | {metric.metric} | {metric.value:g} |")

    lines.extend(
        [
            "",
            "## Leaderboard",
            "",
            "| Rank | Run ID | Model Family | Target Mode | Primary Metric | Score |",
            "| ---: | --- | --- | --- | --- | ---: |",
        ]
    )
    for entry in results.leaderboard:
        lines.append(
            "| "
            f"{entry.rank} | "
            f"`{entry.run_id}` | "
            f"{entry.model_family} | "
            f"{entry.target_mode} | "
            f"{entry.primary_metric} | "
            f"{entry.primary_score:g} |"
        )

    if results.notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in results.notes)

    return "\n".join(lines) + "\n"


def write_interface_discovery_report(input_path: str | Path, output_path: str | Path) -> Path:
    """Load an interface discovery artifact and write a Markdown report."""

    artifact = load_interface_discovery_artifact(input_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_interface_discovery_report(artifact))
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for generating a Markdown report from a fixture artifact."""

    parser = ArgumentParser(description="Generate a Markdown report from an interface artifact.")
    parser.add_argument("artifact", type=Path, help="Path to interface discovery artifact JSON.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional Markdown output path. Prints to stdout when omitted.",
    )
    args = parser.parse_args(argv)

    artifact = load_interface_discovery_artifact(args.artifact)
    report = render_interface_discovery_report(artifact)
    if args.output is None:
        print(report, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
    return 0


def _join_inline_code(values: Sequence[str]) -> str:
    return ", ".join(f"`{value}`" for value in values)


if __name__ == "__main__":
    raise SystemExit(main())
