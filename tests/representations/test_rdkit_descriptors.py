import math

import numpy as np
import pytest
from pydantic import ValidationError

from supervised_learning_polymers.chemistry import (
    CappingConfig,
    ChemistryAuditConfig,
    ChemistryAuditRecord,
    ChemistryFailureRecord,
)
from supervised_learning_polymers.representations import (
    FeatureSetConfig,
    contracts,
    generate_rdkit_2d_features,
    rdkit_2d_feature_set_config,
)


def _chemistry() -> ChemistryAuditConfig:
    return ChemistryAuditConfig(
        config_id="chemistry-audit-v1",
        capping=CappingConfig(strategy="hydrogen", version="1"),
    )


def _valid_record(
    sample_id: str,
    *,
    capped_smiles: str | None,
    standardized_smiles: str | None = None,
) -> ChemistryAuditRecord:
    selected_standardized = (
        standardized_smiles if standardized_smiles is not None else capped_smiles
    )
    return ChemistryAuditRecord(
        sample_id=sample_id,
        raw_smiles=selected_standardized,
        status="valid",
        canonical_smiles=selected_standardized,
        standardized_smiles=selected_standardized,
        capped_smiles=capped_smiles,
    )


def _failed_chemistry_record(sample_id: str) -> ChemistryAuditRecord:
    return ChemistryAuditRecord(
        sample_id=sample_id,
        raw_smiles="not-a-smiles",
        status="failed",
        failure=ChemistryFailureRecord(
            sample_id=sample_id,
            raw_smiles="not-a-smiles",
            failure_type="parse_error",
            message="RDKit could not parse source SMILES.",
            stage="parse",
        ),
    )


def test_rdkit_2d_features_preserve_successful_sample_order_and_metadata() -> None:
    records = (
        _valid_record("poly-0001", capped_smiles="CCO"),
        _valid_record("poly-0002", capped_smiles="c1ccccc1"),
    )

    bundle = generate_rdkit_2d_features(records, _chemistry(), rdkit_version="2026.03.3")

    assert bundle.feature_set.feature_set_id == "rdkit_2d"
    assert bundle.sample_ids == ("poly-0001", "poly-0002")
    assert bundle.matrix.shape == (2, 217)
    assert bundle.matrix.dtype == np.float64
    assert bundle.feature_names[:5] == (
        "MaxAbsEStateIndex",
        "MaxEStateIndex",
        "MinAbsEStateIndex",
        "MinEStateIndex",
        "qed",
    )
    assert bundle.metadata.feature_names == bundle.feature_names
    assert bundle.metadata.rows == 2
    assert bundle.metadata.columns == 217
    assert bundle.metadata.dtype == "float64"
    assert bundle.metadata.input_representation == "capped_smiles"
    assert bundle.metadata.rdkit_version == "2026.03.3"
    assert len(bundle.metadata.matrix_hash) == 64
    assert len(bundle.metadata.feature_names_hash or "") == 64
    assert [attempt.status for attempt in bundle.attempts] == ["success", "success"]
    assert bundle.summary.successful_records == 2
    assert bundle.summary.failed_representation_records == 0
    assert bundle.summary.dimensions[0].columns == 217


def test_rdkit_2d_generation_can_use_standardized_smiles() -> None:
    feature_set = rdkit_2d_feature_set_config(input_representation="standardized_smiles")
    records = (
        _valid_record(
            "poly-uncapped",
            capped_smiles="not-a-smiles",
            standardized_smiles="CCO",
        ),
    )

    bundle = generate_rdkit_2d_features(records, _chemistry(), feature_set=feature_set)

    assert bundle.sample_ids == ("poly-uncapped",)
    assert bundle.attempts[0].input_representation == "standardized_smiles"
    assert bundle.attempts[0].selected_input_smiles == "CCO"
    assert bundle.failures == ()


def test_rdkit_2d_generation_reports_missing_and_invalid_inputs_without_stopping() -> None:
    records = (
        _valid_record("poly-good", capped_smiles="CCO"),
        _valid_record("poly-missing", capped_smiles=None),
        _valid_record("poly-invalid", capped_smiles="not-a-smiles"),
        _failed_chemistry_record("poly-upstream-failed"),
    )

    bundle = generate_rdkit_2d_features(records, _chemistry())

    assert bundle.sample_ids == ("poly-good",)
    assert bundle.matrix.shape == (1, 217)
    assert [attempt.sample_id for attempt in bundle.attempts] == [
        "poly-good",
        "poly-missing",
        "poly-invalid",
    ]
    assert [
        (failure.sample_id, failure.failure_type, failure.stage) for failure in bundle.failures
    ] == [
        ("poly-missing", "missing_input_smiles", "input"),
        ("poly-invalid", "parse_error", "parse"),
    ]
    assert bundle.summary.total_chemistry_valid_records == 3
    assert bundle.summary.attempted_records == 3
    assert bundle.summary.successful_records == 1
    assert bundle.summary.failed_representation_records == 2
    assert bundle.summary.skipped_upstream_chemistry_records == 1
    assert [group.failure_type for group in bundle.summary.failure_groups] == [
        "missing_input_smiles",
        "parse_error",
    ]


def test_rdkit_2d_generation_is_deterministic_for_fixture_molecules() -> None:
    records = (
        _valid_record("poly-0001", capped_smiles="CCO"),
        _valid_record("poly-0002", capped_smiles="CCN"),
    )

    first = generate_rdkit_2d_features(records, _chemistry())
    second = generate_rdkit_2d_features(records, _chemistry())

    assert first.sample_ids == second.sample_ids
    assert first.feature_names == second.feature_names
    np.testing.assert_allclose(first.matrix, second.matrix, rtol=0, atol=0)
    assert first.metadata.matrix_hash == second.metadata.matrix_hash
    assert first.metadata.feature_names_hash == second.metadata.feature_names_hash


def test_rdkit_2d_generation_reports_descriptor_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_descriptor(_: object) -> float:
        raise RuntimeError("fixture descriptor failure")

    monkeypatch.setattr(
        contracts.Descriptors, "descList", (("BrokenDescriptor", broken_descriptor),)
    )
    feature_set = rdkit_2d_feature_set_config()

    bundle = generate_rdkit_2d_features(
        (_valid_record("poly-0001", capped_smiles="CCO"),),
        _chemistry(),
        feature_set=feature_set,
    )

    assert bundle.matrix.shape == (0, 1)
    assert bundle.failures[0].failure_type == "descriptor_error"
    assert bundle.failures[0].stage == "descriptor_generation"
    assert "fixture descriptor failure" in bundle.failures[0].message


def test_rdkit_2d_generation_reports_nan_or_infinite_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(contracts.Descriptors, "descList", (("BadValue", lambda _: math.nan),))
    feature_set = rdkit_2d_feature_set_config()

    bundle = generate_rdkit_2d_features(
        (_valid_record("poly-0001", capped_smiles="CCO"),),
        _chemistry(),
        feature_set=feature_set,
    )

    assert bundle.matrix.shape == (0, 1)
    assert bundle.failures[0].failure_type == "invalid_feature_values"
    assert bundle.failures[0].stage == "validation"


def test_rdkit_2d_generation_rejects_non_descriptor_feature_config() -> None:
    with pytest.raises(ValueError, match="descriptor family"):
        generate_rdkit_2d_features(
            (_valid_record("poly-0001", capped_smiles="CCO"),),
            _chemistry(),
            feature_set=FeatureSetConfig(
                feature_set_id="not-rdkit-2d",
                family="fingerprint",
                version="1",
                rdkit_method="rdkit.Chem.Descriptors",
                output_shape=(1, 217),
                feature_name_policy="named",
                hash_identity_fields=("feature_set_id",),
            ),
        )


def test_feature_matrix_metadata_rejects_feature_name_dimension_mismatch() -> None:
    with pytest.raises(ValidationError, match="feature names"):
        contracts.FeatureMatrixMetadata(
            feature_set_id="rdkit_2d",
            feature_set_version="1",
            family="descriptor",
            input_representation="capped_smiles",
            rdkit_version="2026.03.3",
            dtype="float64",
            rows=1,
            columns=2,
            feature_names=("only_one",),
            matrix_hash="matrix-hash",
        )
