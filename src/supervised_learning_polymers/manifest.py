"""Dataset and experiment manifest contract for benchmark artifacts."""

from typing import Literal

from pydantic import Field, model_validator

from supervised_learning_polymers.targets import ContractModel, TargetConfig

MissingSampleIdStrategy = Literal["error", "split_row_index"]


class DatasetConfig(ContractModel):
    """Source dataset schema and identity fields before derived artifacts exist."""

    dataset_version: str = Field(min_length=1)
    sample_id_column: str | None = Field(default="id", min_length=1)
    missing_sample_id_strategy: MissingSampleIdStrategy = "error"
    smiles_column: str = Field(default="SMILES", min_length=1)
    target_columns: tuple[str, ...] = Field(min_length=1)
    grouping_columns: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_dataset_columns(self) -> "DatasetConfig":
        duplicate_targets = _duplicates(self.target_columns)
        if duplicate_targets:
            raise ValueError(f"duplicate target columns: {', '.join(duplicate_targets)}")

        duplicate_grouping_columns = _duplicates(self.grouping_columns)
        if duplicate_grouping_columns:
            raise ValueError(f"duplicate grouping columns: {', '.join(duplicate_grouping_columns)}")

        reserved_columns = {self.smiles_column, *self.target_columns}
        overlapping_grouping_columns = [
            column for column in self.grouping_columns if column in reserved_columns
        ]
        if overlapping_grouping_columns:
            raise ValueError(
                "grouping columns must be separate from SMILES and target columns: "
                f"{', '.join(overlapping_grouping_columns)}"
            )

        if self.sample_id_column is None and self.missing_sample_id_strategy == "error":
            raise ValueError(
                "missing_sample_id_strategy must be 'split_row_index' when no sample ID column is "
                "configured"
            )

        if self.sample_id_column is not None:
            source_columns = {self.smiles_column, *self.target_columns, *self.grouping_columns}
            if self.sample_id_column in source_columns:
                raise ValueError(
                    "sample ID column must be separate from SMILES, target, and grouping columns"
                )

        return self


class ConfigReference(ContractModel):
    """Stable identity for a future component config or artifact family."""

    config_id: str = Field(min_length=1)


class BenchmarkManifest(ContractModel):
    """Single typed manifest object for a benchmark experiment."""

    manifest_version: str = Field(default="1", min_length=1)
    dataset: DatasetConfig
    target: TargetConfig
    chemistry: ConfigReference
    representation: ConfigReference
    split: ConfigReference
    model: ConfigReference
    reporting: ConfigReference

    @model_validator(mode="after")
    def validate_manifest_references(self) -> "BenchmarkManifest":
        dataset_targets = set(self.dataset.target_columns)
        unknown_target_columns = [
            target_name
            for target_name in self.target.target_names()
            if target_name not in dataset_targets
        ]
        if unknown_target_columns:
            raise ValueError(
                "target config references targets missing from dataset target columns: "
                f"{', '.join(unknown_target_columns)}"
            )

        component_ids = {
            "chemistry": self.chemistry.config_id,
            "representation": self.representation.config_id,
            "split": self.split.config_id,
            "model": self.model.config_id,
            "reporting": self.reporting.config_id,
        }
        overlapping_dataset_ids = [
            name
            for name, config_id in component_ids.items()
            if config_id == self.dataset.dataset_version
        ]
        if overlapping_dataset_ids:
            raise ValueError(
                "derived config identities must be separate from dataset version: "
                f"{', '.join(overlapping_dataset_ids)}"
            )

        return self


def _duplicates(values: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates
