# Chemistry Audit

PRD 3 introduces the chemistry audit contract and fixture-sized processing path used before feature
generation or model training. The audit consumes the PRD 01 dataset contract, preserves source
SMILES, and records derived chemistry fields separately.

## Contract

The chemistry audit is keyed by a `ChemistryAuditConfig`. It records the source dataset version,
the chemistry config ID, the SMILES column, sample-ID handling, target columns, explicit
standardization settings, explicit capping settings, and the RDKit version observed at runtime.

Each per-sample record stores:

- `sample_id`, `split`, `raw_smiles`, and requested target values from the source row.
- `canonical_smiles` from the first RDKit parse of the raw source SMILES.
- `standardized_smiles` from the configured standardization path.
- `capped_smiles` from the configured capping path.
- `attachment_points` describing wildcard atoms found before capping.
- `status` plus a structured `failure` when processing fails.

Aggregate summaries store total, valid, and failed counts plus grouped failure counts and example
sample IDs. The same summary contract feeds both persisted chemistry artifacts and the GUI/backend
interface fixture.

PRD 13 will add a structure validation workbench on top of these records. The chemistry audit
remains the provenance source for raw, canonical, standardized, capped SMILES, and attachment-point
metadata; geometry and graph PRDs add the viewer-ready 3D and graph artifacts consumed by that page.

## SMILES Provenance

Source SMILES are immutable audit inputs. The audit never overwrites `raw_smiles`; every derived
representation is written to its own field so downstream representation, split, and model work can
trace features back to the exact training-set value.

The derived fields have separate meanings:

- `canonical_smiles`: RDKit's canonical rendering immediately after parsing the source value.
- `standardized_smiles`: the canonical parsed molecule after the selected standardization policies.
- `capped_smiles`: the standardized molecule after the selected capping strategy.

For uncapped runs, `capped_smiles` intentionally remains the standardized/parsed control
representation. Attachment-point metadata is still preserved so later graph and geometry work can
revisit the original repeat-unit notation.

## Initial Standardization Defaults

The default `StandardizationConfig` is conservative:

- `fragment_policy = keep_all`
- `charge_policy = preserve`
- `tautomer_policy = preserve`
- `stereochemistry_policy = preserve`
- `isotope_policy = preserve`

Opt-in settings can select the largest fragment, neutralize charges, canonicalize tautomers, drop
stereochemistry, or drop isotopes. The audit stores `canonical_smiles` from the source parse and
`standardized_smiles` from the configured standardization path as separate fields.

Standardization failures are emitted as structured `standardization_error` records during batch
runs, not uncaught exceptions that stop the whole audit.

## Initial Capping Strategies

The default `CappingConfig` uses `strategy = uncapped` and `version = 1`. This preserves wildcard
attachment points in `capped_smiles` as a control path.

Two simple terminal capping strategies are available for wildcard polymer repeat units:

- `hydrogen`: replaces wildcard attachment atoms with explicit hydrogen atoms.
- `carbon`: replaces wildcard attachment atoms with carbon atoms when RDKit valence checks permit.

Raw source SMILES, parsed canonical SMILES, standardized SMILES, capped SMILES, and attachment-point
metadata are stored separately. Capping failures are emitted as structured `capping_error` records
during batch runs.

## Cache Identity

Chemistry cache keys include:

- dataset contract fields;
- chemistry config ID;
- standardization settings;
- capping strategy and version;
- RDKit version.

This keeps standardization experiments from silently reusing stale chemistry artifacts.

## Artifact Layout

Persisted audit bundles are written under:

```text
artifacts/chemistry/<config-id>/
```

Each bundle contains:

- `records.json`: all per-sample audit records.
- `failures.json`: failure records only, for triage.
- `summary.json`: total, valid, failed, and failure-group counts for review surfaces.
- `metadata.json`: dataset version, chemistry config ID, RDKit version, settings, cache key,
  creation timestamp, and output paths.

The `<config-id>` is the chemistry artifact identity, not the source dataset version. Reusing the
same dataset with different standardization or capping settings should use a distinct chemistry
config ID and will also produce a distinct cache key.

## Failure Taxonomy

Batch audits classify failures without stopping the full run:

- `missing_smiles`: the configured SMILES field is missing or empty.
- `parse_error`: RDKit could not parse the raw source SMILES.
- `standardization_error`: parsing succeeded, but the configured standardization step failed.
- `capping_error`: parsing and standardization succeeded, but capping failed.
- `unsupported_attachment_notation`: reserved for polymer attachment notation that should be
  rejected before downstream representations consume it.

Use `summary.json` for a quick count by failure type. Use `failures.json` for triage because each
entry includes the sample ID, raw source SMILES, processing stage, failure type, and message. Use
`records.json` when comparing failed records against successful provenance fields or target values.

## Full Training Audit Script

Run the full training-set audit explicitly with:

```bash
slp-chemistry-audit data/train/train.csv \
  --output-root artifacts \
  --dataset-version open-polymer-train-v1 \
  --chemistry-config-id chemistry-audit-v1
```

The command reads the configured sample ID and SMILES columns, applies the selected standardization
and capping settings, writes the artifact bundle, and prints total, valid, and failed record counts.

Useful options include `--sample-id-column`, `--no-sample-id-column`, `--smiles-column`,
`--target-columns`, `--fragment-policy`, `--charge-policy`, `--tautomer-policy`,
`--stereochemistry-policy`, `--isotope-policy`, `--capping-strategy`, and `--capping-version`.

This command is intentionally outside the default test suite. Use fixture tests for deterministic
CI and run the full-data audit only when local source data is available.

## Review Workflow

For PRD 3 review, run the default quality gate first, then run the opt-in full-data audit when
`data/train/train.csv` is available:

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy
uv run pytest
uv run slp-chemistry-audit data/train/train.csv \
  --output-root artifacts \
  --dataset-version open-polymer-train-v1 \
  --chemistry-config-id chemistry-audit-v1
```

Review `artifacts/chemistry/chemistry-audit-v1/summary.json` first, then inspect `failures.json`
when failed records are present. The GUI/backend fixture is already shaped to consume this summary
contract through `chemistry_failure_summary` and artifact-path metadata.

## Deferred Chemistry Choices

The first full-data uncapped control run on 2026-08-24 processed all 7,973 rows in
`data/train/train.csv` with 7,973 valid records and 0 failures. The PRD 3 final-review run repeated
that result with RDKit `2026.03.3`, cache key
`4c3ed4fa21a257d9f28e4263c271d9b799ba2e9a277fa1f9183987670b352e10`, and generated artifacts under
`/tmp/slp-prd3-final-review-artifacts/chemistry/chemistry-audit-v1/`. Generated audit artifacts are
local review outputs and are not committed.

Hydrogen and carbon capping remain available fixture-tested strategies, but `uncapped` stays the
default until real wildcard-heavy polymer examples justify a different default. Carbon capping in
particular should remain opt-in until later representation or geometry PRDs validate that its valence
behavior is preferable for the selected downstream tasks.
