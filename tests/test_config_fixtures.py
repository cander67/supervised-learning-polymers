import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from supervised_learning_polymers import BenchmarkManifest, TargetConfig

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "benchmark_contract_cases.json"


@pytest.fixture(scope="module")
def contract_cases() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE_PATH.read_text()))


@pytest.mark.parametrize(
    ("case_name", "expected_targets"),
    [
        ("single", ("FFV",)),
        ("group", ("Tg", "Tc")),
        ("all", ("Tg", "FFV", "Tc", "Density", "Rg")),
        ("sequential", ("FFV", "Density", "Tc", "Tg", "Rg")),
    ],
)
def test_valid_target_fixture_configs_resolve_expected_targets(
    contract_cases: dict[str, Any], case_name: str, expected_targets: tuple[str, ...]
) -> None:
    config = TargetConfig.model_validate(contract_cases["valid_targets"][case_name])

    assert config.resolve_targets() == expected_targets


@pytest.mark.parametrize(
    "case_name",
    [
        "unknown_target",
        "missing_metadata",
        "bad_range",
        "duplicate_definition",
        "illegal_sequential",
    ],
)
def test_invalid_target_fixture_configs_fail_validation(
    contract_cases: dict[str, Any], case_name: str
) -> None:
    with pytest.raises(ValidationError):
        TargetConfig.model_validate(contract_cases["invalid_targets"][case_name])


@pytest.mark.parametrize("case_name", ["train_all_targets", "public_sequential_targets"])
def test_valid_manifest_fixture_configs_reference_expected_identities(
    contract_cases: dict[str, Any], case_name: str
) -> None:
    manifest_data = _manifest_data(contract_cases, case_name, valid=True)

    manifest = BenchmarkManifest.model_validate(manifest_data)

    assert manifest.dataset.dataset_version.startswith("open-polymer-")
    assert manifest.target.resolve_targets()
    assert manifest.chemistry.config_id == "chemistry-placeholder-v1"
    assert manifest.representation.config_id == "representation-placeholder-v1"
    assert manifest.model.config_id == "model-placeholder-v1"
    assert manifest.reporting.config_id == "reporting-placeholder-v1"


@pytest.mark.parametrize(
    "case_name", ["missing_component_identity", "derived_identity_reuses_dataset_version"]
)
def test_invalid_manifest_fixture_configs_fail_validation(
    contract_cases: dict[str, Any], case_name: str
) -> None:
    manifest_data = _manifest_data(contract_cases, case_name, valid=False)

    with pytest.raises(ValidationError):
        BenchmarkManifest.model_validate(manifest_data)


def _manifest_data(
    contract_cases: dict[str, Any], case_name: str, *, valid: bool
) -> dict[str, Any]:
    section = "valid_manifests" if valid else "invalid_manifests"
    manifest_data = dict(contract_cases[section][case_name])
    target_ref = manifest_data.pop("target_ref")
    manifest_data["target"] = contract_cases["valid_targets"][target_ref]
    return manifest_data
