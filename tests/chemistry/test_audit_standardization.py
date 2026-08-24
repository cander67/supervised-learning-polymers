import pytest

from supervised_learning_polymers.chemistry import (
    ChemistryAuditConfig,
    StandardizationConfig,
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


def test_default_standardization_preserves_parse_canonical_smiles() -> None:
    record = audit_dataset_row(
        {"id": "poly-default", "SMILES": "CCO"},
        _dataset(),
        row_index=0,
        chemistry=ChemistryAuditConfig(config_id="chemistry-standard-fixture-v1"),
    )

    assert record.status == "valid"
    assert record.raw_smiles == "CCO"
    assert record.canonical_smiles == "CCO"
    assert record.standardized_smiles == "CCO"


def test_largest_fragment_standardization_handles_disconnected_fragments() -> None:
    config = ChemistryAuditConfig(
        config_id="chemistry-largest-fragment-v1",
        standardization=StandardizationConfig(fragment_policy="largest_fragment"),
    )

    record = audit_dataset_row(
        {"id": "poly-fragment", "SMILES": "CCO.CCCCC"},
        _dataset(),
        row_index=0,
        chemistry=config,
    )

    assert record.status == "valid"
    assert record.raw_smiles == "CCO.CCCCC"
    assert record.canonical_smiles == "CCCCC.CCO"
    assert record.standardized_smiles == "CCCCC"


def test_neutralize_standardization_handles_charged_molecules() -> None:
    config = ChemistryAuditConfig(
        config_id="chemistry-neutralize-v1",
        standardization=StandardizationConfig(charge_policy="neutralize"),
    )

    record = audit_dataset_row(
        {"id": "poly-charged", "SMILES": "C[NH3+]"},
        _dataset(),
        row_index=0,
        chemistry=config,
    )

    assert record.status == "valid"
    assert record.canonical_smiles == "C[NH3+]"
    assert record.standardized_smiles == "CN"


def test_drop_stereochemistry_standardization_handles_stereochemical_smiles() -> None:
    config = ChemistryAuditConfig(
        config_id="chemistry-drop-stereo-v1",
        standardization=StandardizationConfig(stereochemistry_policy="drop"),
    )

    record = audit_dataset_row(
        {"id": "poly-stereo", "SMILES": "F[C@H](Cl)Br"},
        _dataset(),
        row_index=0,
        chemistry=config,
    )

    assert record.status == "valid"
    assert record.canonical_smiles == "F[C@H](Cl)Br"
    assert record.standardized_smiles == "FC(Cl)Br"


def test_drop_isotope_standardization_handles_isotopic_smiles() -> None:
    config = ChemistryAuditConfig(
        config_id="chemistry-drop-isotope-v1",
        standardization=StandardizationConfig(isotope_policy="drop"),
    )

    record = audit_dataset_row(
        {"id": "poly-isotope", "SMILES": "[13CH4]"},
        _dataset(),
        row_index=0,
        chemistry=config,
    )

    assert record.status == "valid"
    assert record.canonical_smiles == "[13CH4]"
    assert record.standardized_smiles == "C"


def test_canonicalize_tautomer_standardization_is_configured_explicitly() -> None:
    config = ChemistryAuditConfig(
        config_id="chemistry-tautomer-v1",
        standardization=StandardizationConfig(tautomer_policy="canonicalize"),
    )

    record = audit_dataset_row(
        {"id": "poly-tautomer", "SMILES": "C1=NC=CC=C1"},
        _dataset(),
        row_index=0,
        chemistry=config,
    )

    assert record.status == "valid"
    assert record.standardized_smiles == "c1ccncc1"


def test_standardization_error_becomes_structured_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenUncharger:
        def uncharge(self, molecule: object) -> object:
            raise RuntimeError("neutralization unavailable")

    monkeypatch.setattr(audit_module.rdMolStandardize, "Uncharger", BrokenUncharger)
    config = ChemistryAuditConfig(
        config_id="chemistry-broken-standardization-v1",
        standardization=StandardizationConfig(charge_policy="neutralize"),
    )

    record = audit_dataset_row(
        {"id": "poly-broken", "SMILES": "C[NH3+]"},
        _dataset(),
        row_index=0,
        chemistry=config,
    )

    assert record.status == "failed"
    assert record.failure is not None
    assert record.failure.failure_type == "standardization_error"
    assert record.failure.stage == "standardization"
    assert "neutralization unavailable" in record.failure.message


def test_batch_summary_groups_standardization_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenUncharger:
        def uncharge(self, molecule: object) -> object:
            raise RuntimeError("neutralization unavailable")

    monkeypatch.setattr(audit_module.rdMolStandardize, "Uncharger", BrokenUncharger)

    artifact = audit_dataset_rows(
        ({"id": "poly-valid", "SMILES": "CCO"}, {"id": "poly-broken", "SMILES": "C[NH3+]"}),
        _dataset(),
        ChemistryAuditConfig(
            config_id="chemistry-broken-standardization-v1",
            standardization=StandardizationConfig(charge_policy="neutralize"),
        ),
    )

    assert artifact.summary.total_records == 2
    assert artifact.summary.valid_records == 0
    assert artifact.summary.failed_records == 2
    assert {group.failure_type: group.count for group in artifact.summary.failure_groups} == {
        "standardization_error": 2
    }


def test_cache_key_changes_when_standardization_settings_change() -> None:
    preserve = ChemistryAuditConfig(
        config_id="chemistry-cache-v1",
        standardization=StandardizationConfig(charge_policy="preserve"),
    )
    neutralize = ChemistryAuditConfig(
        config_id="chemistry-cache-v1",
        standardization=StandardizationConfig(charge_policy="neutralize"),
    )

    assert chemistry_cache_key(_dataset(), preserve) != chemistry_cache_key(_dataset(), neutralize)


def test_cache_key_changes_when_rdkit_version_changes() -> None:
    config = ChemistryAuditConfig(config_id="chemistry-cache-v1")

    assert chemistry_cache_key(_dataset(), config, rdkit_version="rdkit-a") != chemistry_cache_key(
        _dataset(), config, rdkit_version="rdkit-b"
    )
