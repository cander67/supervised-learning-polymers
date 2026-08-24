from json import loads
from pathlib import Path
from tomllib import loads as load_toml

import pytest

from supervised_learning_polymers.chemistry_audit_cli import main


def test_project_script_exposes_chemistry_audit_command() -> None:
    pyproject = load_toml(Path("pyproject.toml").read_text())

    assert (
        pyproject["project"]["scripts"]["slp-chemistry-audit"]
        == "supervised_learning_polymers.chemistry_audit_cli:main"
    )


def test_cli_writes_audit_artifacts_from_csv(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    input_csv = tmp_path / "train.csv"
    input_csv.write_text(
        "\n".join(
            [
                "id,SMILES,Tg,FFV,Tc,Density,Rg",
                "poly-valid,*CC*,,0.1,,,",
                "poly-invalid,not-a-smiles,,,,,",
                "poly-missing,,,,,,",
            ]
        )
        + "\n"
    )

    result = main(
        (
            str(input_csv),
            "--output-root",
            str(tmp_path / "artifacts"),
            "--dataset-version",
            "open-polymer-train-fixture-v1",
            "--chemistry-config-id",
            "chemistry-cli-fixture-v1",
            "--capping-strategy",
            "hydrogen",
        )
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "total=3 valid=1 failed=2" in output

    artifact_root = tmp_path / "artifacts" / "chemistry" / "chemistry-cli-fixture-v1"
    records = loads((artifact_root / "records.json").read_text())
    failures = loads((artifact_root / "failures.json").read_text())
    summary = loads((artifact_root / "summary.json").read_text())
    metadata = loads((artifact_root / "metadata.json").read_text())

    assert records[0]["sample_id"] == "poly-valid"
    assert records[0]["raw_smiles"] == "*CC*"
    assert records[0]["capped_smiles"] == "[H]CC[H]"
    assert [failure["sample_id"] for failure in failures] == ["poly-invalid", "poly-missing"]
    assert summary["total_records"] == 3
    assert metadata["dataset_version"] == "open-polymer-train-fixture-v1"
    assert metadata["chemistry_config_id"] == "chemistry-cli-fixture-v1"


def test_cli_generates_sample_ids_when_no_sample_id_column_is_configured(
    tmp_path: Path,
) -> None:
    input_csv = tmp_path / "public.csv"
    input_csv.write_text("SMILES,Tg,FFV,Tc,Density,Rg\nCCO,,,,,\nCN,,,,,\n")

    result = main(
        (
            str(input_csv),
            "--output-root",
            str(tmp_path / "artifacts"),
            "--dataset-version",
            "open-polymer-public-fixture-v1",
            "--chemistry-config-id",
            "chemistry-public-fixture-v1",
            "--no-sample-id-column",
            "--split",
            "public",
        )
    )

    assert result == 0

    records_path = (
        tmp_path / "artifacts" / "chemistry" / "chemistry-public-fixture-v1" / "records.json"
    )
    records = loads(records_path.read_text())

    assert [record["sample_id"] for record in records] == ["public-0", "public-1"]


def test_cli_accepts_standardization_and_capping_options(tmp_path: Path) -> None:
    input_csv = tmp_path / "train.csv"
    input_csv.write_text("id,SMILES,Tg,FFV,Tc,Density,Rg\npoly-1,*C[NH3+],,,,,\n")

    result = main(
        (
            str(input_csv),
            "--output-root",
            str(tmp_path / "artifacts"),
            "--chemistry-config-id",
            "chemistry-options-fixture-v1",
            "--charge-policy",
            "neutralize",
            "--capping-strategy",
            "carbon",
            "--capping-version",
            "2",
        )
    )

    assert result == 0

    artifact_root = tmp_path / "artifacts" / "chemistry" / "chemistry-options-fixture-v1"
    records = loads((artifact_root / "records.json").read_text())
    metadata = loads((artifact_root / "metadata.json").read_text())

    assert records[0]["standardized_smiles"] == "*CN"
    assert records[0]["capped_smiles"] == "CCN"
    assert metadata["settings"]["standardization"]["charge_policy"] == "neutralize"
    assert metadata["settings"]["capping"] == {"strategy": "carbon", "version": "2"}
