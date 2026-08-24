from typing import Literal

import pytest

from supervised_learning_polymers.chemistry import (
    CappingConfig,
    ChemistryAuditConfig,
    audit_dataset_row,
    audit_dataset_rows,
    chemistry_cache_key,
)
from supervised_learning_polymers.chemistry import audit as audit_module
from supervised_learning_polymers.manifest import DatasetConfig


def _dataset() -> DatasetConfig:
    return DatasetConfig(
        dataset_version="open-polymer-train-fixture-v1",
        sample_id_column="id",
        smiles_column="SMILES",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )


def test_uncapped_control_preserves_standardized_smiles_as_capped_smiles() -> None:
    record = audit_dataset_row(
        {"id": "poly-uncapped", "SMILES": "*CC(*)c1ccccc1"},
        _dataset(),
        row_index=0,
        chemistry=ChemistryAuditConfig(
            config_id="chemistry-uncapped-v1",
            capping=CappingConfig(strategy="uncapped", version="1"),
        ),
    )

    assert record.status == "valid"
    assert record.raw_smiles == "*CC(*)c1ccccc1"
    assert record.standardized_smiles == "*CC(*)c1ccccc1"
    assert record.capped_smiles == "*CC(*)c1ccccc1"
    assert record.attachment_points == ("*:0", "*:3")


def test_hydrogen_capping_handles_representative_wildcard_polymer() -> None:
    record = audit_dataset_row(
        {"id": "poly-hydrogen", "SMILES": "*CC(*)c1ccccc1"},
        _dataset(),
        row_index=0,
        chemistry=ChemistryAuditConfig(
            config_id="chemistry-hydrogen-v1",
            capping=CappingConfig(strategy="hydrogen", version="1"),
        ),
    )

    assert record.status == "valid"
    assert record.raw_smiles == "*CC(*)c1ccccc1"
    assert record.standardized_smiles == "*CC(*)c1ccccc1"
    assert record.capped_smiles == "[H]CC([H])c1ccccc1"
    assert record.attachment_points == ("*:0", "*:3")


def test_carbon_capping_handles_representative_wildcard_polymer_when_valence_permits() -> None:
    record = audit_dataset_row(
        {"id": "poly-carbon", "SMILES": "*CC(*)c1ccccc1"},
        _dataset(),
        row_index=0,
        chemistry=ChemistryAuditConfig(
            config_id="chemistry-carbon-v1",
            capping=CappingConfig(strategy="carbon", version="1"),
        ),
    )

    assert record.status == "valid"
    assert record.raw_smiles == "*CC(*)c1ccccc1"
    assert record.standardized_smiles == "*CC(*)c1ccccc1"
    assert record.capped_smiles == "CCC(C)c1ccccc1"
    assert record.attachment_points == ("*:0", "*:3")


@pytest.mark.parametrize(
    ("strategy", "capped_smiles"),
    [
        ("uncapped", "*CC*"),
        ("hydrogen", "[H]CC[H]"),
        ("carbon", "CCCC"),
    ],
)
def test_initial_capping_strategies_are_deterministic_for_linear_repeat_unit(
    strategy: Literal["uncapped", "hydrogen", "carbon"],
    capped_smiles: str,
) -> None:
    record = audit_dataset_row(
        {"id": f"poly-{strategy}", "SMILES": "*CC*"},
        _dataset(),
        row_index=0,
        chemistry=ChemistryAuditConfig(
            config_id=f"chemistry-{strategy}-v1",
            capping=CappingConfig(strategy=strategy, version="1"),
        ),
    )

    assert record.status == "valid"
    assert record.capped_smiles == capped_smiles
    assert record.attachment_points == ("*:0", "*:3")


def test_capping_failure_becomes_structured_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_sanitize(_: object) -> None:
        raise RuntimeError("valence check failed")

    monkeypatch.setattr(audit_module.Chem, "SanitizeMol", fail_sanitize)

    record = audit_dataset_row(
        {"id": "poly-bad-cap", "SMILES": "*CC*"},
        _dataset(),
        row_index=0,
        chemistry=ChemistryAuditConfig(
            config_id="chemistry-bad-cap-v1",
            capping=CappingConfig(strategy="carbon", version="1"),
        ),
    )

    assert record.status == "failed"
    assert record.failure is not None
    assert record.failure.failure_type == "capping_error"
    assert record.failure.stage == "capping"
    assert "valence check failed" in record.failure.message


def test_batch_summary_groups_capping_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_sanitize(_: object) -> None:
        raise RuntimeError("valence check failed")

    monkeypatch.setattr(audit_module.Chem, "SanitizeMol", fail_sanitize)

    artifact = audit_dataset_rows(
        ({"id": "poly-a", "SMILES": "*CC*"}, {"id": "poly-b", "SMILES": "*CO*"}),
        _dataset(),
        ChemistryAuditConfig(
            config_id="chemistry-bad-cap-v1",
            capping=CappingConfig(strategy="carbon", version="1"),
        ),
    )

    assert artifact.summary.total_records == 2
    assert artifact.summary.valid_records == 0
    assert artifact.summary.failed_records == 2
    assert {group.failure_type: group.count for group in artifact.summary.failure_groups} == {
        "capping_error": 2
    }


def test_cache_key_changes_when_capping_strategy_changes() -> None:
    uncapped = ChemistryAuditConfig(
        config_id="chemistry-cache-v1",
        capping=CappingConfig(strategy="uncapped", version="1"),
    )
    hydrogen = ChemistryAuditConfig(
        config_id="chemistry-cache-v1",
        capping=CappingConfig(strategy="hydrogen", version="1"),
    )

    assert chemistry_cache_key(_dataset(), uncapped) != chemistry_cache_key(_dataset(), hydrogen)


def test_cache_key_changes_when_capping_version_changes() -> None:
    version_one = ChemistryAuditConfig(
        config_id="chemistry-cache-v1",
        capping=CappingConfig(strategy="hydrogen", version="1"),
    )
    version_two = ChemistryAuditConfig(
        config_id="chemistry-cache-v1",
        capping=CappingConfig(strategy="hydrogen", version="2"),
    )

    assert chemistry_cache_key(_dataset(), version_one) != chemistry_cache_key(
        _dataset(), version_two
    )
