"""Command line entry point for fixed-vector representation artifact generation."""

from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from json import loads
from pathlib import Path
from typing import Any, Literal, cast

from supervised_learning_polymers.chemistry import ChemistryAuditConfig, ChemistryAuditRecord
from supervised_learning_polymers.manifest import DatasetConfig
from supervised_learning_polymers.representations import (
    FeatureMatrixBundle,
    FeatureSetConfig,
    MolecularInputRepresentation,
    MorganFingerprintMode,
    RepresentationConfig,
    generate_morgan_fingerprint_features,
    generate_rdkit_2d_features,
    morgan_fingerprint_feature_set_config,
    rdkit_2d_feature_set_config,
    representation_artifact_from_bundles,
    representation_cache_key,
    write_representation_artifacts,
)

FeatureSetId = Literal["rdkit_2d", "morgan_radius2_2048_chiral"]
DEFAULT_FEATURE_SET_IDS = "rdkit_2d,morgan_radius2_2048_chiral"


def main(argv: Sequence[str] | None = None) -> int:
    """Generate fixed-vector representations from persisted chemistry audit artifacts."""

    args = _parse_args(argv)
    records_path = _records_path(args.chemistry_artifact)
    metadata_path = records_path.parent / "metadata.json"
    chemistry_metadata = loads(metadata_path.read_text(encoding="utf-8"))
    chemistry = ChemistryAuditConfig.model_validate(chemistry_metadata["settings"])
    chemistry_records = _read_chemistry_records(records_path)

    dataset = DatasetConfig(
        dataset_version=chemistry_metadata["dataset_version"],
        sample_id_column=args.sample_id_column,
        missing_sample_id_strategy=args.missing_sample_id_strategy,
        smiles_column=args.smiles_column,
        target_columns=tuple(args.target_columns.split(",")),
    )
    feature_sets = _feature_sets_from_args(args)
    representation = RepresentationConfig(
        config_id=args.representation_config_id,
        selected_feature_set_ids=tuple(feature_set.feature_set_id for feature_set in feature_sets),
        feature_sets=feature_sets,
    )
    rdkit_version = str(chemistry_metadata["rdkit_version"])
    bundles = _generate_feature_bundles(
        chemistry_records,
        chemistry,
        feature_sets,
        rdkit_version=rdkit_version,
    )
    artifact = representation_artifact_from_bundles(
        dataset,
        chemistry,
        str(chemistry_metadata["cache_key"]),
        representation,
        bundles,
        rdkit_version=rdkit_version,
    )
    paths = write_representation_artifacts(artifact, bundles, args.output_root)
    cache_key = representation_cache_key(
        dataset,
        chemistry,
        str(chemistry_metadata["cache_key"]),
        representation,
        rdkit_version=rdkit_version,
    )

    print(
        "Representation generation complete: "
        f"total_chemistry_valid={artifact.summary.total_chemistry_valid_records} "
        f"attempted={artifact.summary.attempted_records} "
        f"success={artifact.summary.successful_records} "
        f"failed={artifact.summary.failed_representation_records} "
        f"skipped_chemistry_failed={artifact.summary.skipped_upstream_chemistry_records}"
    )
    print(
        "Dimensions: "
        + ", ".join(
            f"{dimension.feature_set_id}={dimension.rows}x{dimension.columns}"
            for dimension in artifact.summary.dimensions
        )
    )
    print(f"Representation cache key: {cache_key}")
    print(f"Artifacts written to {paths.artifact_root}")
    return 0


def _parse_args(argv: Sequence[str] | None) -> Namespace:
    parser = ArgumentParser(
        description="Generate fixed-vector representations from chemistry audit artifacts."
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
        help="Artifact root; outputs are written under representations/<config-id>/.",
    )
    parser.add_argument(
        "--representation-config-id",
        default="fixed-vector-v1",
        help="Derived representation config identity used in artifact paths and cache keys.",
    )
    parser.add_argument(
        "--input-representation",
        choices=("capped_smiles", "standardized_smiles"),
        default="capped_smiles",
        help="Chemistry record SMILES representation used for feature generation.",
    )
    parser.add_argument(
        "--feature-set-ids",
        default=DEFAULT_FEATURE_SET_IDS,
        help=(
            "Comma-separated feature sets to generate. Supported values: "
            "rdkit_2d,morgan_radius2_2048_chiral."
        ),
    )
    parser.add_argument(
        "--morgan-radius",
        type=int,
        default=2,
        help="Morgan fingerprint radius.",
    )
    parser.add_argument(
        "--morgan-size",
        type=int,
        default=2048,
        help="Morgan fingerprint vector size.",
    )
    parser.add_argument(
        "--morgan-mode",
        choices=("bit", "count"),
        default="bit",
        help="Morgan fingerprint vector mode.",
    )
    parser.add_argument(
        "--no-morgan-chirality",
        action="store_true",
        help="Disable chirality in Morgan fingerprint generation.",
    )
    parser.add_argument(
        "--sample-id-column",
        default="id",
        help="Dataset sample ID column recorded in representation metadata.",
    )
    parser.add_argument(
        "--smiles-column",
        default="SMILES",
        help="Dataset SMILES column recorded in representation metadata.",
    )
    parser.add_argument(
        "--target-columns",
        default="Tg,FFV,Tc,Density,Rg",
        help="Comma-separated target columns recorded in representation metadata.",
    )
    args = parser.parse_args(argv)
    args.missing_sample_id_strategy = "error"
    args.input_representation = cast(MolecularInputRepresentation, args.input_representation)
    args.morgan_mode = cast(MorganFingerprintMode, args.morgan_mode)
    args.feature_set_ids = _parse_feature_set_ids(args.feature_set_ids)
    return args


def _records_path(path: Path) -> Path:
    if path.is_dir():
        return path / "records.json"
    return path


def _read_chemistry_records(path: Path) -> tuple[ChemistryAuditRecord, ...]:
    return tuple(
        ChemistryAuditRecord.model_validate(record)
        for record in loads(path.read_text(encoding="utf-8"))
    )


def _parse_feature_set_ids(value: str) -> tuple[FeatureSetId, ...]:
    feature_set_ids = tuple(item.strip() for item in value.split(",") if item.strip())
    if not feature_set_ids:
        raise ValueError("at least one feature set must be selected")
    unknown_feature_sets = sorted(set(feature_set_ids) - set(_supported_feature_set_ids()))
    if unknown_feature_sets:
        raise ValueError(f"unknown feature sets: {', '.join(unknown_feature_sets)}")
    duplicate_feature_sets = _duplicates(feature_set_ids)
    if duplicate_feature_sets:
        raise ValueError(f"duplicate feature sets: {', '.join(duplicate_feature_sets)}")
    return cast(tuple[FeatureSetId, ...], feature_set_ids)


def _supported_feature_set_ids() -> tuple[FeatureSetId, ...]:
    return ("rdkit_2d", "morgan_radius2_2048_chiral")


def _feature_sets_from_args(args: Namespace) -> tuple[FeatureSetConfig, ...]:
    feature_sets: list[FeatureSetConfig] = []
    for feature_set_id in cast(tuple[FeatureSetId, ...], args.feature_set_ids):
        if feature_set_id == "rdkit_2d":
            feature_sets.append(
                rdkit_2d_feature_set_config(
                    input_representation=args.input_representation,
                )
            )
        elif feature_set_id == "morgan_radius2_2048_chiral":
            feature_sets.append(
                morgan_fingerprint_feature_set_config(
                    input_representation=args.input_representation,
                    radius=args.morgan_radius,
                    size=args.morgan_size,
                    include_chirality=not args.no_morgan_chirality,
                    mode=args.morgan_mode,
                )
            )
    return tuple(feature_sets)


def _generate_feature_bundles(
    records: Sequence[ChemistryAuditRecord],
    chemistry: ChemistryAuditConfig,
    feature_sets: Sequence[FeatureSetConfig],
    *,
    rdkit_version: str,
) -> tuple[FeatureMatrixBundle, ...]:
    bundles: list[FeatureMatrixBundle] = []
    for feature_set in feature_sets:
        if feature_set.feature_set_id == "rdkit_2d":
            bundles.append(
                generate_rdkit_2d_features(
                    records,
                    chemistry,
                    feature_set=feature_set,
                    rdkit_version=rdkit_version,
                )
            )
        elif feature_set.feature_set_id == "morgan_radius2_2048_chiral":
            bundles.append(
                generate_morgan_fingerprint_features(
                    records,
                    chemistry,
                    feature_set=feature_set,
                    rdkit_version=rdkit_version,
                )
            )
        else:
            raise ValueError(f"unsupported feature set: {feature_set.feature_set_id}")
    return tuple(bundles)


def _duplicates(values: Sequence[Any]) -> list[Any]:
    seen: set[Any] = set()
    duplicates: list[Any] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


if __name__ == "__main__":
    raise SystemExit(main())
