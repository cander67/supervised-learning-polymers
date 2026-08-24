from supervised_learning_polymers.chemistry import (
    ChemistryAuditConfig,
    audit_dataset_row,
    audit_dataset_rows,
)
from supervised_learning_polymers.manifest import DatasetConfig


def _dataset() -> DatasetConfig:
    return DatasetConfig(
        dataset_version="open-polymer-train-fixture-v1",
        sample_id_column="id",
        smiles_column="SMILES",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )


def test_valid_parse_record_preserves_raw_smiles_and_canonical_smiles() -> None:
    record = audit_dataset_row(
        {"id": "poly-0001", "SMILES": "CCO"},
        _dataset(),
        row_index=0,
    )

    assert record.sample_id == "poly-0001"
    assert record.raw_smiles == "CCO"
    assert record.status == "valid"
    assert record.canonical_smiles == "CCO"
    assert record.failure is None


def test_invalid_smiles_becomes_structured_parse_failure() -> None:
    record = audit_dataset_row(
        {"id": "poly-0002", "SMILES": "not-a-smiles"},
        _dataset(),
        row_index=1,
    )

    assert record.sample_id == "poly-0002"
    assert record.raw_smiles == "not-a-smiles"
    assert record.status == "failed"
    assert record.failure is not None
    assert record.failure.failure_type == "parse_error"
    assert record.failure.stage == "parse"
    assert "RDKit could not parse" in record.failure.message


def test_empty_and_missing_smiles_become_structured_input_failures() -> None:
    empty = audit_dataset_row({"id": "poly-empty", "SMILES": ""}, _dataset(), row_index=0)
    missing = audit_dataset_row({"id": "poly-missing", "SMILES": None}, _dataset(), row_index=1)

    assert empty.raw_smiles == ""
    assert empty.status == "failed"
    assert empty.failure is not None
    assert empty.failure.failure_type == "missing_smiles"
    assert empty.failure.stage == "input"

    assert missing.raw_smiles is None
    assert missing.status == "failed"
    assert missing.failure is not None
    assert missing.failure.failure_type == "missing_smiles"
    assert missing.failure.stage == "input"


def test_wildcard_polymer_smiles_parse_and_record_attachment_points() -> None:
    record = audit_dataset_row(
        {"id": "poly-wildcard", "SMILES": "*CC(*)c1ccccc1"},
        _dataset(),
        row_index=0,
    )

    assert record.status == "valid"
    assert record.raw_smiles == "*CC(*)c1ccccc1"
    assert record.canonical_smiles == "*CC(*)c1ccccc1"
    assert record.attachment_points == ("*:0", "*:3")


def test_fixture_parse_cases_cover_common_chemistry_forms() -> None:
    cases = {
        "charged": ("[NH4+]", "[NH4+]"),
        "aromatic": ("c1ccccc1", "c1ccccc1"),
        "disconnected": ("CCO.CN", "CCO.CN"),
        "stereochemical": ("F[C@H](Cl)Br", "F[C@H](Cl)Br"),
        "isotope": ("[13CH4]", "[13CH4]"),
    }

    for index, (case_name, (raw_smiles, canonical_smiles)) in enumerate(cases.items()):
        record = audit_dataset_row(
            {"id": f"poly-{case_name}", "SMILES": raw_smiles},
            _dataset(),
            row_index=index,
        )

        assert record.sample_id == f"poly-{case_name}"
        assert record.raw_smiles == raw_smiles
        assert record.status == "valid"
        assert record.canonical_smiles == canonical_smiles
        assert record.failure is None


def test_batch_audit_returns_records_and_summary_counts_without_stopping_on_failures() -> None:
    artifact = audit_dataset_rows(
        (
            {"id": "poly-valid", "SMILES": "CCO"},
            {"id": "poly-invalid", "SMILES": "not-a-smiles"},
            {"id": "poly-missing", "SMILES": None},
            {"id": "poly-wildcard", "SMILES": "*CC(*)c1ccccc1"},
        ),
        _dataset(),
        ChemistryAuditConfig(config_id="chemistry-parse-fixture-v1"),
        rdkit_version="test-rdkit-version",
    )

    assert artifact.rdkit_version == "test-rdkit-version"
    assert [record.sample_id for record in artifact.records] == [
        "poly-valid",
        "poly-invalid",
        "poly-missing",
        "poly-wildcard",
    ]
    assert artifact.summary.total_records == 4
    assert artifact.summary.valid_records == 2
    assert artifact.summary.failed_records == 2
    assert {group.failure_type: group.count for group in artifact.summary.failure_groups} == {
        "missing_smiles": 1,
        "parse_error": 1,
    }
    assert {
        group.failure_type: group.example_sample_ids for group in artifact.summary.failure_groups
    } == {
        "missing_smiles": ("poly-missing",),
        "parse_error": ("poly-invalid",),
    }


def test_raw_smiles_are_preserved_byte_for_byte_in_batch_records() -> None:
    raw_smiles = " CCO "
    artifact = audit_dataset_rows(
        ({"id": "poly-spaced", "SMILES": raw_smiles},),
        _dataset(),
        ChemistryAuditConfig(config_id="chemistry-parse-fixture-v1"),
    )

    assert artifact.records[0].raw_smiles == raw_smiles
    assert artifact.records[0].status == "valid"


def test_missing_sample_id_falls_back_to_deterministic_split_row_index() -> None:
    dataset = DatasetConfig(
        dataset_version="open-polymer-public-fixture-v1",
        sample_id_column=None,
        missing_sample_id_strategy="split_row_index",
        smiles_column="SMILES",
        target_columns=("Tg", "FFV", "Tc", "Density", "Rg"),
    )

    artifact = audit_dataset_rows(
        ({"SMILES": "CCO"}, {"SMILES": "CN"}),
        dataset,
        ChemistryAuditConfig(config_id="chemistry-parse-fixture-v1"),
        split="public",
    )

    assert [record.sample_id for record in artifact.records] == ["public-0", "public-1"]
