"""Command line entry point for geometry feasibility artifact generation."""

from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from json import loads
from pathlib import Path
from typing import cast

from supervised_learning_polymers.chemistry import ChemistryAuditConfig, ChemistryAuditRecord
from supervised_learning_polymers.geometry import (
    FallbackMethodName,
    GeometryArtifact,
    GeometryConfig,
    GeometryInputRepresentation,
    attempt_geometry_record,
    summarize_geometry_records,
    write_geometry_artifacts,
)
from supervised_learning_polymers.manifest import DatasetConfig


def main(argv: Sequence[str] | None = None) -> int:
    """Run geometry feasibility over a persisted chemistry audit artifact."""

    args = _parse_args(argv)
    records_path = _records_path(args.chemistry_artifact)
    metadata_path = records_path.parent / "metadata.json"
    chemistry_metadata = loads(metadata_path.read_text())
    chemistry = ChemistryAuditConfig.model_validate(chemistry_metadata["settings"])
    chemistry_records = _read_chemistry_records(records_path)
    valid_records = tuple(record for record in chemistry_records if record.status == "valid")
    skipped_chemistry_failed = len(chemistry_records) - len(valid_records)

    dataset = DatasetConfig(
        dataset_version=chemistry_metadata["dataset_version"],
        sample_id_column=args.sample_id_column,
        missing_sample_id_strategy=args.missing_sample_id_strategy,
        smiles_column=args.smiles_column,
        target_columns=tuple(args.target_columns.split(",")),
    )
    geometry = GeometryConfig(
        config_id=args.geometry_config_id,
        input_representation=args.input_representation,
        random_seed=args.random_seed,
        embed_attempts=args.embed_attempts,
        optimization_max_iterations=args.optimization_max_iterations,
        timeout_seconds=args.timeout_seconds,
        fallback_methods=args.fallback_methods,
    )

    geometry_records = tuple(
        attempt_geometry_record(
            record,
            chemistry,
            geometry,
            rdkit_version=chemistry_metadata["rdkit_version"],
        )
        for record in valid_records
    )
    artifact = GeometryArtifact(
        dataset=dataset,
        chemistry=chemistry,
        chemistry_cache_key=chemistry_metadata["cache_key"],
        geometry=geometry,
        rdkit_version=chemistry_metadata["rdkit_version"],
        records=geometry_records,
        summary=summarize_geometry_records(
            geometry_records,
            total_chemistry_valid_records=len(valid_records),
        ),
    )
    paths = write_geometry_artifacts(artifact, args.output_root)

    print(
        "Geometry feasibility complete: "
        f"total_chemistry_valid={artifact.summary.total_chemistry_valid_records} "
        f"attempted={artifact.summary.attempted_records} "
        f"success={artifact.summary.successful_records} "
        f"failed={artifact.summary.failed_records} "
        f"skipped_chemistry_failed={skipped_chemistry_failed} "
        f"coverage={artifact.summary.coverage_fraction:.2%} "
        f"runtime_seconds={artifact.summary.total_runtime_seconds:.3f}"
    )
    print(f"Artifacts written to {paths.artifact_root}")
    return 0


def _parse_args(argv: Sequence[str] | None) -> Namespace:
    parser = ArgumentParser(
        description="Run 3D geometry feasibility from chemistry audit artifacts."
    )
    parser.add_argument(
        "chemistry_artifact",
        type=Path,
        help="Path to chemistry artifact directory or chemistry records.json.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("artifacts"),
        help="Artifact root; outputs are written under geometry/<geometry-config-id>/.",
    )
    parser.add_argument(
        "--geometry-config-id",
        default="geometry-rdkit-v1",
        help="Derived geometry config identity used in artifact paths and cache keys.",
    )
    parser.add_argument(
        "--input-representation",
        choices=("capped_smiles", "standardized_smiles"),
        default="capped_smiles",
        help="Chemistry record SMILES representation used for geometry attempts.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=61453,
        help="Random seed passed to RDKit embedding.",
    )
    parser.add_argument(
        "--embed-attempts",
        type=int,
        default=20,
        help="Maximum RDKit embedding attempts per molecule.",
    )
    parser.add_argument(
        "--optimization-max-iterations",
        type=int,
        default=200,
        help="Maximum RDKit MMFF optimization iterations per conformer.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="Reserved per-record timeout setting recorded in geometry config.",
    )
    parser.add_argument(
        "--fallback-methods",
        default="",
        help="Comma-separated optional fallback methods to record, such as xtb,mlip.",
    )
    parser.add_argument(
        "--sample-id-column",
        default="id",
        help="Dataset sample ID column recorded in geometry metadata.",
    )
    parser.add_argument(
        "--smiles-column",
        default="SMILES",
        help="Dataset SMILES column recorded in geometry metadata.",
    )
    parser.add_argument(
        "--target-columns",
        default="Tg,FFV,Tc,Density,Rg",
        help="Comma-separated target columns recorded in geometry metadata.",
    )
    args = parser.parse_args(argv)
    args.missing_sample_id_strategy = "error"
    args.input_representation = cast(GeometryInputRepresentation, args.input_representation)
    args.fallback_methods = _parse_fallback_methods(args.fallback_methods)
    return args


def _records_path(path: Path) -> Path:
    if path.is_dir():
        return path / "records.json"
    return path


def _read_chemistry_records(path: Path) -> tuple[ChemistryAuditRecord, ...]:
    return tuple(ChemistryAuditRecord.model_validate(record) for record in loads(path.read_text()))


def _parse_fallback_methods(value: str) -> tuple[FallbackMethodName, ...]:
    if value.strip() == "":
        return ()
    methods = tuple(method.strip() for method in value.split(",") if method.strip())
    unknown_methods = sorted(set(methods) - {"xtb", "mlip"})
    if unknown_methods:
        raise ValueError(f"unknown fallback methods: {', '.join(unknown_methods)}")
    return cast(tuple[FallbackMethodName, ...], methods)


if __name__ == "__main__":
    raise SystemExit(main())
