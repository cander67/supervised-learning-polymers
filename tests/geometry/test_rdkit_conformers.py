import pytest

from supervised_learning_polymers.chemistry import (
    CappingConfig,
    ChemistryAuditConfig,
    audit_dataset_row,
)
from supervised_learning_polymers.geometry import (
    GeometryConfig,
    attempt_geometry_record,
)
from supervised_learning_polymers.geometry import feasibility as geometry_module
from supervised_learning_polymers.manifest import DatasetConfig


def _dataset() -> DatasetConfig:
    return DatasetConfig(
        dataset_version="open-polymer-train-fixture-v1",
        sample_id_column="id",
        smiles_column="SMILES",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )


def test_rdkit_conformer_attempt_generates_viewer_ready_sdf_for_small_molecule() -> None:
    chemistry = ChemistryAuditConfig(config_id="chemistry-hydrogen-v1")
    chemistry_record = audit_dataset_row(
        {"id": "poly-ethanol", "SMILES": "CCO"},
        _dataset(),
        row_index=0,
        chemistry=chemistry,
    )

    record = attempt_geometry_record(
        chemistry_record,
        chemistry,
        GeometryConfig(config_id="geometry-rdkit-v1", random_seed=13, embed_attempts=5),
        rdkit_version="test-rdkit-version",
    )

    assert record.sample_id == "poly-ethanol"
    assert record.status == "success"
    assert record.selected_input_smiles == "CCO"
    assert record.method.method_name == "rdkit_etkdg_mmff"
    assert record.method.rdkit_version == "test-rdkit-version"
    assert record.method.embedding_status == "success"
    assert record.method.optimization_status in {"success", "not_converged", "unavailable"}
    assert record.sdf_text is not None
    assert record.sdf_text.endswith("$$$$\n")
    assert "M  END" in record.sdf_text
    assert record.failure is None


def test_geometry_input_representation_can_use_standardized_or_capped_smiles() -> None:
    chemistry = ChemistryAuditConfig(
        config_id="chemistry-hydrogen-v1",
        capping=CappingConfig(strategy="hydrogen", version="1"),
    )
    chemistry_record = audit_dataset_row(
        {"id": "poly-wildcard", "SMILES": "*CC*"},
        _dataset(),
        row_index=0,
        chemistry=chemistry,
    )

    capped_record = attempt_geometry_record(
        chemistry_record,
        chemistry,
        GeometryConfig(config_id="geometry-capped-v1", input_representation="capped_smiles"),
        rdkit_version="test-rdkit-version",
    )
    uncapped_record = attempt_geometry_record(
        chemistry_record,
        chemistry,
        GeometryConfig(
            config_id="geometry-uncapped-v1",
            input_representation="standardized_smiles",
        ),
        rdkit_version="test-rdkit-version",
    )

    assert capped_record.selected_input_smiles == chemistry_record.capped_smiles
    assert uncapped_record.selected_input_smiles == chemistry_record.standardized_smiles
    assert capped_record.raw_smiles == chemistry_record.raw_smiles
    assert uncapped_record.capped_smiles == chemistry_record.capped_smiles
    assert uncapped_record.attachment_points == ("*:0", "*:3")


def test_wildcard_uncapped_input_produces_explicit_geometry_outcome() -> None:
    chemistry = ChemistryAuditConfig(
        config_id="chemistry-uncapped-v1",
        capping=CappingConfig(strategy="uncapped", version="1"),
    )
    chemistry_record = audit_dataset_row(
        {"id": "poly-uncapped", "SMILES": "*CC*"},
        _dataset(),
        row_index=0,
        chemistry=chemistry,
    )

    record = attempt_geometry_record(
        chemistry_record,
        chemistry,
        GeometryConfig(
            config_id="geometry-uncapped-v1",
            input_representation="standardized_smiles",
        ),
        rdkit_version="test-rdkit-version",
    )

    assert record.sample_id == "poly-uncapped"
    assert record.selected_input_smiles == "*CC*"
    assert record.status in {"success", "failed"}
    if record.status == "failed":
        assert record.failure is not None
        assert record.failure.failure_type in {
            "embedding_failed",
            "optimization_failed",
            "parse_error",
            "unsupported_wildcard_atoms",
        }


def test_missing_selected_geometry_input_becomes_structured_failure() -> None:
    chemistry = ChemistryAuditConfig(config_id="chemistry-fixture-v1")
    chemistry_record = audit_dataset_row(
        {"id": "poly-ethanol", "SMILES": "CCO"},
        _dataset(),
        row_index=0,
        chemistry=chemistry,
    ).model_copy(update={"capped_smiles": None})

    record = attempt_geometry_record(
        chemistry_record,
        chemistry,
        GeometryConfig(config_id="geometry-rdkit-v1", input_representation="capped_smiles"),
        rdkit_version="test-rdkit-version",
    )

    assert record.status == "failed"
    assert record.failure is not None
    assert record.failure.failure_type == "missing_input_smiles"
    assert record.failure.stage == "input"
    assert record.sdf_text is None


def test_malformed_selected_geometry_input_becomes_structured_parse_failure() -> None:
    chemistry = ChemistryAuditConfig(config_id="chemistry-fixture-v1")
    chemistry_record = audit_dataset_row(
        {"id": "poly-ethanol", "SMILES": "CCO"},
        _dataset(),
        row_index=0,
        chemistry=chemistry,
    ).model_copy(update={"capped_smiles": "not-a-smiles"})

    record = attempt_geometry_record(
        chemistry_record,
        chemistry,
        GeometryConfig(config_id="geometry-rdkit-v1", input_representation="capped_smiles"),
        rdkit_version="test-rdkit-version",
    )

    assert record.status == "failed"
    assert record.failure is not None
    assert record.failure.failure_type == "parse_error"
    assert record.failure.stage == "parse"


def test_mmff_unavailable_is_recorded_in_method_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(geometry_module.AllChem, "MMFFHasAllMoleculeParams", lambda _: False)
    chemistry = ChemistryAuditConfig(config_id="chemistry-fixture-v1")
    chemistry_record = audit_dataset_row(
        {"id": "poly-ethanol", "SMILES": "CCO"},
        _dataset(),
        row_index=0,
        chemistry=chemistry,
    )

    record = attempt_geometry_record(
        chemistry_record,
        chemistry,
        GeometryConfig(config_id="geometry-rdkit-v1"),
        rdkit_version="test-rdkit-version",
    )

    assert record.status == "success"
    assert record.method.embedding_status == "success"
    assert record.method.optimization_status == "unavailable"


def test_failed_chemistry_record_is_reported_as_missing_geometry_input() -> None:
    chemistry = ChemistryAuditConfig(config_id="chemistry-fixture-v1")
    chemistry_record = audit_dataset_row(
        {"id": "poly-invalid", "SMILES": "not-a-smiles"},
        _dataset(),
        row_index=0,
        chemistry=chemistry,
    )

    record = attempt_geometry_record(
        chemistry_record,
        chemistry,
        GeometryConfig(config_id="geometry-rdkit-v1"),
        rdkit_version="test-rdkit-version",
    )

    assert record.status == "failed"
    assert record.failure is not None
    assert record.failure.failure_type == "missing_input_smiles"
    assert record.failure.stage == "input"
