import pytest
from pydantic import ValidationError

from supervised_learning_polymers import (
    AllTargetMode,
    BenchmarkManifest,
    ConfigReference,
    DatasetConfig,
    open_polymer_target_config,
)


def test_dataset_contract_records_source_schema() -> None:
    dataset = DatasetConfig(
        dataset_version="open-polymer-train-v1",
        sample_id_column="id",
        smiles_column="SMILES",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
        grouping_columns=("scaffold",),
    )

    assert dataset.dataset_version == "open-polymer-train-v1"
    assert dataset.sample_id_column == "id"
    assert dataset.smiles_column == "SMILES"
    assert dataset.target_columns == ("Tg", "FFV", "Tc", "Density", "Rg")
    assert dataset.grouping_columns == ("scaffold",)


def test_dataset_contract_allows_deterministic_sample_ids_without_column() -> None:
    dataset = DatasetConfig(
        dataset_version="open-polymer-public-v1",
        sample_id_column=None,
        missing_sample_id_strategy="split_row_index",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )

    assert dataset.sample_id_column is None
    assert dataset.missing_sample_id_strategy == "split_row_index"


def test_dataset_without_sample_id_column_requires_generation_strategy() -> None:
    with pytest.raises(ValidationError, match="split_row_index"):
        DatasetConfig(
            dataset_version="open-polymer-public-v1",
            sample_id_column=None,
            target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
        )


def test_manifest_references_all_component_config_identities() -> None:
    manifest = BenchmarkManifest(
        dataset=DatasetConfig(
            dataset_version="open-polymer-train-v1",
            target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
        ),
        target=open_polymer_target_config(AllTargetMode()),
        chemistry=ConfigReference(config_id="chemistry-placeholder-v1"),
        representation=ConfigReference(config_id="representation-placeholder-v1"),
        split=ConfigReference(config_id="split-placeholder-v1"),
        model=ConfigReference(config_id="model-placeholder-v1"),
        reporting=ConfigReference(config_id="reporting-placeholder-v1"),
    )

    assert manifest.chemistry.config_id == "chemistry-placeholder-v1"
    assert manifest.representation.config_id == "representation-placeholder-v1"
    assert manifest.split.config_id == "split-placeholder-v1"
    assert manifest.model.config_id == "model-placeholder-v1"
    assert manifest.reporting.config_id == "reporting-placeholder-v1"


def test_manifest_validates_from_plain_config_data() -> None:
    manifest = BenchmarkManifest.model_validate(
        {
            "dataset": {
                "dataset_version": "open-polymer-train-v1",
                "target_columns": ["Tg", "FFV", "Tc", "Density", "Rg"],
            },
            "target": open_polymer_target_config(AllTargetMode()).model_dump(mode="json"),
            "chemistry": {"config_id": "chemistry-placeholder-v1"},
            "representation": {"config_id": "representation-placeholder-v1"},
            "split": {"config_id": "split-placeholder-v1"},
            "model": {"config_id": "model-placeholder-v1"},
            "reporting": {"config_id": "reporting-placeholder-v1"},
        }
    )

    assert manifest.dataset.sample_id_column == "id"
    assert manifest.target.resolve_targets() == ("Tg", "FFV", "Tc", "Density", "Rg")


def test_manifest_validation_rejects_missing_required_identities() -> None:
    with pytest.raises(ValidationError, match="chemistry"):
        BenchmarkManifest.model_validate(
            {
                "dataset": {
                    "dataset_version": "open-polymer-train-v1",
                    "target_columns": ["Tg", "FFV", "Tc", "Density", "Rg"],
                },
                "target": open_polymer_target_config(AllTargetMode()).model_dump(mode="json"),
                "representation": {"config_id": "representation-placeholder-v1"},
                "split": {"config_id": "split-placeholder-v1"},
                "model": {"config_id": "model-placeholder-v1"},
                "reporting": {"config_id": "reporting-placeholder-v1"},
            }
        )


def test_manifest_keeps_source_identity_separate_from_derived_config_identities() -> None:
    with pytest.raises(ValidationError, match="separate from dataset version: chemistry"):
        BenchmarkManifest(
            dataset=DatasetConfig(
                dataset_version="open-polymer-train-v1",
                target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
            ),
            target=open_polymer_target_config(AllTargetMode()),
            chemistry=ConfigReference(config_id="open-polymer-train-v1"),
            representation=ConfigReference(config_id="representation-placeholder-v1"),
            split=ConfigReference(config_id="split-placeholder-v1"),
            model=ConfigReference(config_id="model-placeholder-v1"),
            reporting=ConfigReference(config_id="reporting-placeholder-v1"),
        )


def test_manifest_rejects_target_config_not_present_in_dataset_schema() -> None:
    with pytest.raises(ValidationError, match="missing from dataset target columns: Rg"):
        BenchmarkManifest(
            dataset=DatasetConfig(
                dataset_version="open-polymer-train-v1",
                target_columns=("Tg", "FFV", "Tc", "Density"),
            ),
            target=open_polymer_target_config(AllTargetMode()),
            chemistry=ConfigReference(config_id="chemistry-placeholder-v1"),
            representation=ConfigReference(config_id="representation-placeholder-v1"),
            split=ConfigReference(config_id="split-placeholder-v1"),
            model=ConfigReference(config_id="model-placeholder-v1"),
            reporting=ConfigReference(config_id="reporting-placeholder-v1"),
        )
