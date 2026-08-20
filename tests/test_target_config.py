import pytest
from pydantic import ValidationError

from supervised_learning_polymers import (
    AllTargetMode,
    GroupTargetMode,
    SequentialPredictionSource,
    SequentialTargetMode,
    SingleTargetMode,
    TargetConfig,
    TargetMetadata,
    ValidRange,
    open_polymer_target_config,
)


def test_single_target_config_accepts_one_known_target() -> None:
    config = open_polymer_target_config(SingleTargetMode(target="FFV"))

    assert config.resolve_targets() == ("FFV",)


def test_target_config_validates_from_plain_config_data() -> None:
    config = TargetConfig.model_validate(
        {
            "targets": [
                {"name": "Tg", "unit": "deg C"},
                {"name": "FFV", "unit": "dimensionless"},
            ],
            "groups": {"thermal": ["Tg"], "free_volume": ["FFV"]},
            "mode": {"mode": "group", "group": "free_volume"},
        }
    )

    assert config.resolve_targets() == ("FFV",)


def test_group_config_accepts_named_group() -> None:
    config = open_polymer_target_config(GroupTargetMode(group="sequential_poc"))

    assert config.resolve_targets() == ("FFV", "Density", "Tc", "Tg", "Rg")


def test_all_target_config_resolves_all_configured_targets() -> None:
    config = open_polymer_target_config(AllTargetMode())

    assert config.resolve_targets() == ("Tg", "FFV", "Tc", "Density", "Rg")


def test_sequential_config_accepts_ordered_dependency_chain() -> None:
    config = open_polymer_target_config(
        SequentialTargetMode(
            order=("FFV", "Density", "Tc", "Tg", "Rg"),
            prediction_source=SequentialPredictionSource(),
        )
    )

    assert config.resolve_targets() == ("FFV", "Density", "Tc", "Tg", "Rg")


def test_sequential_config_requires_prediction_source_strategy() -> None:
    with pytest.raises(ValidationError, match="prediction_source"):
        SequentialTargetMode.model_validate(
            {"mode": "sequential", "order": ["FFV", "Density", "Tc", "Tg", "Rg"]}
        )


def test_sequential_prediction_source_prevents_validation_label_leakage() -> None:
    with pytest.raises(ValidationError, match="validation"):
        SequentialTargetMode.model_validate(
            {
                "mode": "sequential",
                "order": ["FFV", "Density", "Tc", "Tg", "Rg"],
                "prediction_source": {
                    "training": "out_of_fold_predictions",
                    "validation": "true_labels",
                    "test": "upstream_model_predictions",
                },
            }
        )


def test_sequential_prediction_source_requires_out_of_fold_training_predictions() -> None:
    with pytest.raises(ValidationError, match="training"):
        SequentialTargetMode.model_validate(
            {
                "mode": "sequential",
                "order": ["FFV", "Density", "Tc", "Tg", "Rg"],
                "prediction_source": {
                    "training": "true_labels",
                    "validation": "upstream_model_predictions",
                    "test": "upstream_model_predictions",
                },
            }
        )


def test_sequential_prediction_source_prevents_test_label_leakage() -> None:
    with pytest.raises(ValidationError, match="test"):
        SequentialTargetMode.model_validate(
            {
                "mode": "sequential",
                "order": ["FFV", "Density", "Tc", "Tg", "Rg"],
                "prediction_source": {
                    "training": "out_of_fold_predictions",
                    "validation": "upstream_model_predictions",
                    "test": "true_labels",
                },
            }
        )


def test_target_metadata_supports_units_ranges_missing_policy_and_transform() -> None:
    config = TargetConfig(
        targets=(
            TargetMetadata(
                name="FFV",
                unit="dimensionless",
                valid_range=ValidRange(minimum=0.0, maximum=1.0),
                missing_value_policy="preserve",
                transform="standardize",
            ),
        ),
        mode=SingleTargetMode(target="FFV"),
    )

    metadata = config.metadata_by_name()["FFV"]
    assert metadata.unit == "dimensionless"
    assert metadata.valid_range == ValidRange(minimum=0.0, maximum=1.0)
    assert metadata.missing_value_policy == "preserve"
    assert metadata.transform == "standardize"


def test_invalid_target_names_fail_with_clear_validation_error() -> None:
    with pytest.raises(ValidationError, match="unknown targets: Missing"):
        open_polymer_target_config(SingleTargetMode(target="Missing"))


def test_duplicate_target_definitions_fail_with_clear_validation_error() -> None:
    with pytest.raises(ValidationError, match="duplicate target definitions: FFV"):
        TargetConfig(
            targets=(
                TargetMetadata(name="FFV", unit="dimensionless"),
                TargetMetadata(name="FFV", unit="dimensionless"),
            ),
            mode=AllTargetMode(),
        )


def test_group_definitions_can_overlap_without_duplicates_within_one_group() -> None:
    config = TargetConfig(
        targets=(
            TargetMetadata(name="Tg", unit="deg C"),
            TargetMetadata(name="Tc", unit="W/(m*K)"),
            TargetMetadata(name="FFV", unit="dimensionless"),
        ),
        groups={
            "thermal": ("Tg", "Tc"),
            "sequential_subset": ("FFV", "Tc", "Tg"),
        },
        mode=GroupTargetMode(group="thermal"),
    )

    assert config.resolve_targets() == ("Tg", "Tc")


def test_duplicate_targets_inside_one_group_fail() -> None:
    with pytest.raises(ValidationError, match="group 'bad' contains duplicate targets: FFV"):
        TargetConfig(
            targets=(
                TargetMetadata(name="FFV", unit="dimensionless"),
                TargetMetadata(name="Tg", unit="deg C"),
            ),
            groups={"bad": ("FFV", "FFV")},
            mode=GroupTargetMode(group="bad"),
        )


def test_duplicate_targets_inside_sequential_order_fail() -> None:
    with pytest.raises(ValidationError, match="sequential mode contains duplicate targets: FFV"):
        open_polymer_target_config(
            SequentialTargetMode(
                order=("FFV", "Density", "FFV"),
                prediction_source=SequentialPredictionSource(),
            )
        )


def test_unknown_targets_inside_sequential_order_fail() -> None:
    with pytest.raises(
        ValidationError, match="sequential mode references unknown targets: Missing"
    ):
        open_polymer_target_config(
            SequentialTargetMode(
                order=("FFV", "Density", "Missing"),
                prediction_source=SequentialPredictionSource(),
            )
        )
