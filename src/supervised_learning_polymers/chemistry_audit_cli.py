"""Command line entry point for chemistry audit artifact generation."""

from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from csv import DictReader
from pathlib import Path
from typing import cast

from supervised_learning_polymers.chemistry import (
    CappingConfig,
    ChemistryAuditConfig,
    StandardizationConfig,
    audit_dataset_rows,
    write_chemistry_audit_artifacts,
)
from supervised_learning_polymers.manifest import DatasetConfig, MissingSampleIdStrategy


def main(argv: Sequence[str] | None = None) -> int:
    """Run a chemistry audit over a CSV dataset and persist artifact files."""

    args = _parse_args(argv)
    rows = _read_csv_rows(args.input_csv)
    dataset = DatasetConfig(
        dataset_version=args.dataset_version,
        sample_id_column=args.sample_id_column,
        missing_sample_id_strategy=args.missing_sample_id_strategy,
        smiles_column=args.smiles_column,
        target_columns=tuple(args.target_columns.split(",")),
    )
    chemistry = ChemistryAuditConfig(
        config_id=args.chemistry_config_id,
        standardization=StandardizationConfig(
            fragment_policy=args.fragment_policy,
            charge_policy=args.charge_policy,
            tautomer_policy=args.tautomer_policy,
            stereochemistry_policy=args.stereochemistry_policy,
            isotope_policy=args.isotope_policy,
        ),
        capping=CappingConfig(strategy=args.capping_strategy, version=args.capping_version),
    )

    artifact = audit_dataset_rows(rows, dataset, chemistry, split=args.split)
    paths = write_chemistry_audit_artifacts(artifact, args.output_root)

    print(
        "Chemistry audit complete: "
        f"total={artifact.summary.total_records} "
        f"valid={artifact.summary.valid_records} "
        f"failed={artifact.summary.failed_records}"
    )
    print(f"Artifacts written to {paths.artifact_root}")
    return 0


def _parse_args(argv: Sequence[str] | None) -> Namespace:
    parser = ArgumentParser(description="Run the polymer chemistry audit over a CSV file.")
    parser.add_argument("input_csv", type=Path, help="Input CSV file to audit.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("artifacts"),
        help="Artifact root; outputs are written under chemistry/<config-id>/.",
    )
    parser.add_argument(
        "--dataset-version",
        default="open-polymer-train-v1",
        help="Source dataset identity recorded in audit metadata.",
    )
    parser.add_argument(
        "--chemistry-config-id",
        default="chemistry-audit-v1",
        help="Derived chemistry config identity used in artifact paths and cache keys.",
    )
    parser.add_argument(
        "--smiles-column", default="SMILES", help="Column containing source SMILES."
    )
    parser.add_argument(
        "--sample-id-column",
        default="id",
        help="Column containing sample IDs. Use --no-sample-id-column when absent.",
    )
    parser.add_argument(
        "--no-sample-id-column",
        action="store_true",
        help="Generate deterministic sample IDs from split and row index.",
    )
    parser.add_argument(
        "--missing-sample-id-strategy",
        choices=("error", "split_row_index"),
        default="error",
        help="Dataset contract strategy for missing sample ID columns.",
    )
    parser.add_argument("--split", default="train", help="Split label for generated sample IDs.")
    parser.add_argument(
        "--target-columns",
        default="Tg,FFV,Tc,Density,Rg",
        help="Comma-separated target column names recorded in the dataset contract.",
    )
    parser.add_argument(
        "--fragment-policy",
        choices=("keep_all", "largest_fragment"),
        default="keep_all",
        help="Standardization policy for disconnected fragments.",
    )
    parser.add_argument(
        "--charge-policy",
        choices=("preserve", "neutralize"),
        default="preserve",
        help="Standardization policy for charged molecules.",
    )
    parser.add_argument(
        "--tautomer-policy",
        choices=("preserve", "canonicalize"),
        default="preserve",
        help="Standardization policy for tautomers.",
    )
    parser.add_argument(
        "--stereochemistry-policy",
        choices=("preserve", "drop"),
        default="preserve",
        help="Standardization policy for stereochemistry.",
    )
    parser.add_argument(
        "--isotope-policy",
        choices=("preserve", "drop"),
        default="preserve",
        help="Standardization policy for isotopes.",
    )
    parser.add_argument(
        "--capping-strategy",
        choices=("uncapped", "hydrogen", "carbon"),
        default="uncapped",
        help="Wildcard attachment-point capping strategy.",
    )
    parser.add_argument("--capping-version", default="1", help="Version of the capping strategy.")

    args = parser.parse_args(argv)
    if args.no_sample_id_column:
        args.sample_id_column = None
        args.missing_sample_id_strategy = "split_row_index"
    args.missing_sample_id_strategy = cast(MissingSampleIdStrategy, args.missing_sample_id_strategy)
    return args


def _read_csv_rows(path: Path) -> tuple[dict[str, object], ...]:
    with path.open(newline="") as csv_file:
        return tuple(dict(row) for row in DictReader(csv_file))


if __name__ == "__main__":
    raise SystemExit(main())
