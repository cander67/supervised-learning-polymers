import numpy as np
import pytest
from pydantic import ValidationError

from supervised_learning_polymers.chemistry import (
    CappingConfig,
    ChemistryAuditConfig,
    ChemistryAuditRecord,
)
from supervised_learning_polymers.representations import (
    FeatureSetConfig,
    MorganFingerprintSettings,
    generate_morgan_fingerprint_features,
    morgan_fingerprint_feature_set_config,
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


def test_morgan_fingerprint_config_exposes_validated_defaults() -> None:
    feature_set = morgan_fingerprint_feature_set_config()

    assert feature_set.feature_set_id == "morgan_radius2_2048_chiral"
    assert feature_set.family == "fingerprint"
    assert feature_set.input_representation == "capped_smiles"
    assert feature_set.settings == {
        "radius": 2,
        "size": 2048,
        "include_chirality": True,
        "mode": "bit",
    }
    assert feature_set.output_shape == (1, 2048)
    assert feature_set.feature_name_policy == "bit_index"


def test_morgan_fingerprint_settings_reject_invalid_values() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        MorganFingerprintSettings(radius=-1)

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        MorganFingerprintSettings(size=0)

    with pytest.raises(ValidationError):
        MorganFingerprintSettings(mode="unsupported")  # type: ignore[arg-type]


def test_morgan_fingerprints_preserve_sample_order_and_metadata() -> None:
    records = (
        _valid_record("poly-0001", capped_smiles="CCO"),
        _valid_record("poly-0002", capped_smiles="c1ccccc1"),
    )

    bundle = generate_morgan_fingerprint_features(
        records,
        _chemistry(),
        rdkit_version="2026.03.3",
    )

    assert bundle.feature_set.feature_set_id == "morgan_radius2_2048_chiral"
    assert bundle.sample_ids == ("poly-0001", "poly-0002")
    assert bundle.matrix.shape == (2, 2048)
    assert bundle.matrix.dtype == np.float64
    assert set(np.unique(bundle.matrix)).issubset({0.0, 1.0})
    assert bundle.feature_names[:3] == ("bit_0", "bit_1", "bit_2")
    assert bundle.feature_names[-1] == "bit_2047"
    assert bundle.metadata.family == "fingerprint"
    assert bundle.metadata.settings["radius"] == 2
    assert bundle.metadata.settings["size"] == 2048
    assert bundle.metadata.settings["include_chirality"] is True
    assert bundle.metadata.settings["mode"] == "bit"
    assert bundle.metadata.input_representation == "capped_smiles"
    assert bundle.metadata.rdkit_version == "2026.03.3"
    assert len(bundle.metadata.matrix_hash) == 64
    assert len(bundle.metadata.feature_names_hash or "") == 64
    assert bundle.summary.successful_records == 2
    assert bundle.summary.dimensions[0].columns == 2048


def test_morgan_fingerprints_support_count_mode_and_custom_size() -> None:
    feature_set = morgan_fingerprint_feature_set_config(size=128, mode="count")
    records = (_valid_record("poly-count", capped_smiles="CCCCCCCC"),)

    bundle = generate_morgan_fingerprint_features(
        records,
        _chemistry(),
        feature_set=feature_set,
    )

    assert bundle.matrix.shape == (1, 128)
    assert bundle.feature_names[-1] == "bit_127"
    assert bundle.metadata.settings["mode"] == "count"
    assert bundle.metadata.settings["size"] == 128
    assert bundle.matrix.max() >= 1.0


def test_morgan_fingerprints_can_use_standardized_smiles() -> None:
    feature_set = morgan_fingerprint_feature_set_config(input_representation="standardized_smiles")
    records = (
        _valid_record(
            "poly-uncapped",
            capped_smiles="not-a-smiles",
            standardized_smiles="CCO",
        ),
    )

    bundle = generate_morgan_fingerprint_features(records, _chemistry(), feature_set=feature_set)

    assert bundle.sample_ids == ("poly-uncapped",)
    assert bundle.attempts[0].input_representation == "standardized_smiles"
    assert bundle.attempts[0].selected_input_smiles == "CCO"
    assert bundle.failures == ()


def test_morgan_fingerprints_report_missing_and_invalid_inputs_without_stopping() -> None:
    records = (
        _valid_record("poly-good", capped_smiles="CCO"),
        _valid_record("poly-missing", capped_smiles=None),
        _valid_record("poly-invalid", capped_smiles="not-a-smiles"),
    )

    bundle = generate_morgan_fingerprint_features(records, _chemistry())

    assert bundle.sample_ids == ("poly-good",)
    assert bundle.matrix.shape == (1, 2048)
    assert [attempt.sample_id for attempt in bundle.attempts] == [
        "poly-good",
        "poly-missing",
        "poly-invalid",
    ]
    assert [
        (failure.sample_id, failure.feature_set_id, failure.failure_type)
        for failure in bundle.failures
    ] == [
        ("poly-missing", "morgan_radius2_2048_chiral", "missing_input_smiles"),
        ("poly-invalid", "morgan_radius2_2048_chiral", "parse_error"),
    ]
    assert bundle.summary.successful_records == 1
    assert bundle.summary.failed_representation_records == 2


def test_morgan_fingerprint_generation_is_deterministic_for_fixture_molecules() -> None:
    records = (
        _valid_record("poly-0001", capped_smiles="CCO"),
        _valid_record("poly-0002", capped_smiles="CCN"),
    )

    first = generate_morgan_fingerprint_features(records, _chemistry())
    second = generate_morgan_fingerprint_features(records, _chemistry())

    assert first.sample_ids == second.sample_ids
    assert first.feature_names == second.feature_names
    np.testing.assert_allclose(first.matrix, second.matrix, rtol=0, atol=0)
    assert first.metadata.matrix_hash == second.metadata.matrix_hash
    assert first.metadata.feature_names_hash == second.metadata.feature_names_hash


def test_morgan_fingerprint_generation_rejects_invalid_feature_config() -> None:
    with pytest.raises(ValueError, match="fingerprint family"):
        generate_morgan_fingerprint_features(
            (_valid_record("poly-0001", capped_smiles="CCO"),),
            _chemistry(),
            feature_set=FeatureSetConfig(
                feature_set_id="not-morgan",
                family="descriptor",
                version="1",
                rdkit_method="rdkit.Chem.rdFingerprintGenerator.GetMorganGenerator",
                output_shape=(1, 2048),
                feature_name_policy="bit_index",
                hash_identity_fields=("feature_set_id",),
            ),
        )

    with pytest.raises(ValueError, match="vector size"):
        generate_morgan_fingerprint_features(
            (_valid_record("poly-0001", capped_smiles="CCO"),),
            _chemistry(),
            feature_set=FeatureSetConfig(
                feature_set_id="morgan_bad_size",
                family="fingerprint",
                version="1",
                rdkit_method="rdkit.Chem.rdFingerprintGenerator.GetMorganGenerator",
                settings={"radius": 2, "size": 2048, "include_chirality": True, "mode": "bit"},
                output_shape=(1, 128),
                feature_name_policy="bit_index",
                hash_identity_fields=("feature_set_id",),
            ),
        )
