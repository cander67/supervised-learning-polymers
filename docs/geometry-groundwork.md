# Geometry Groundwork

PRD 4 introduces the early 3D geometry feasibility contract used before geometry-aware model work
depends on conformers.

## Current Scope

Geometry attempts consume valid records from the PRD 3 chemistry audit. Each attempt records the
source `sample_id`, chemistry config ID, raw/canonical/standardized/capped SMILES provenance,
attachment-point metadata, selected input representation, RDKit method provenance, runtime, fallback
metadata, and either viewer-ready single-record SDF text or a structured geometry failure.

The initial local method is RDKit ETKDG embedding plus MMFF optimization. Geometry config makes the
input representation explicit:

- `capped_smiles`: use the chemistry record's capped representation.
- `standardized_smiles`: use the chemistry record's uncapped/standardized representation.

Default geometry config values are:

- `primary_method = rdkit_etkdg_mmff`
- `input_representation = capped_smiles`
- `random_seed = 61453`
- `embed_attempts = 20`
- `optimization_max_iterations = 200`
- `timeout_seconds = None`
- `fallback_methods = ()`

Wildcard-heavy uncapped inputs may fail or produce limited optimization behavior. Those outcomes are
recorded as structured geometry results rather than blocking non-geometry model work.

Successful attempts persist a single-record SDF payload on the geometry record. This is the smallest
viewer-ready payload chosen for PRD 4 while still leaving room to extend each record later with
additional conformer or atom-mapping metadata.

## Fallback Provenance

xTB and MLIP fallback paths are represented in geometry config and per-attempt provenance, but they
are not installed or run by default.

Fallback status values distinguish:

- `disabled`: the fallback method is not enabled in geometry config.
- `skipped_not_needed`: RDKit produced a successful conformer, so configured fallbacks were not run.
- `skipped_dependency_unavailable`: RDKit did not produce geometry, but the configured fallback
  dependency is not installed or configured for local runs.
- `attempted`, `success`, and `failed`: reserved for later phases that wire real fallback runners.
- `unavailable`: reserved for method availability checks outside a specific skipped dependency path.

This keeps fallback decisions reproducible without adding quantum chemistry or MLIP dependencies to
the default development environment.

## Status Semantics

Geometry attempt records use `status = success` only when RDKit produces SDF text. Failed attempts
use `status = failed`, include no SDF text, and always carry a structured failure record with the
sample ID, method, processing stage, failure type, message, and recommended action.

Failure types are:

- `missing_input_smiles`: the selected chemistry representation was absent.
- `parse_error`: RDKit could not parse the selected SMILES.
- `embedding_failed`: RDKit ETKDG embedding failed or timed out.
- `optimization_failed`: MMFF optimization failed after embedding.
- `unsupported_wildcard_atoms`: reserved for explicit wildcard handling.
- `method_unavailable`: reserved for configured methods that cannot run locally.

Summary `skipped_records` are chemistry-valid inputs that were counted in the requested total but did
not have a geometry attempt record, which is useful for interrupted or sampled runs. Summary
`skipped_fallback_records` count configured fallback methods that were intentionally skipped because
RDKit succeeded or because the fallback dependency was unavailable.

## Artifact Layout

Persisted geometry bundles are written under:

```text
artifacts/geometry/<geometry-config-id>/
```

Each bundle contains:

- `records.json`: all per-sample geometry attempt records.
- `failures.json`: failed geometry attempts only, for triage.
- `summary.json`: aggregate coverage, failure, fallback, and runtime counts.
- `metadata.json`: dataset identity, chemistry identity, chemistry cache key, readable chemistry
  provenance, geometry settings, geometry cache key, RDKit version, creation timestamp, and output
  paths.

Geometry cache identity includes the upstream chemistry cache key plus geometry settings and RDKit
version. Metadata also repeats readable chemistry provenance such as capping strategy, capping
version, and selected geometry input representation so reviewers can inspect outputs without
decoding hashes.

`summary.json` reports the chemistry-valid input count, attempted count, success/failure counts,
skipped attempt count, skipped fallback count, coverage fraction, total runtime seconds, and grouped
failure examples. Coverage is `successful_records / total_chemistry_valid_records`.

## Geometry Feasibility Script

Run geometry feasibility from a persisted chemistry audit bundle with:

```bash
slp-geometry-feasibility artifacts/chemistry/chemistry-audit-v1 \
  --output-root artifacts \
  --geometry-config-id geometry-rdkit-v1 \
  --input-representation capped_smiles
```

The command accepts either a chemistry artifact directory or its `records.json` path. It reads the
sibling `metadata.json`, attempts geometry only for chemistry records with `status = valid`, writes a
geometry bundle, and prints total chemistry-valid inputs, attempted records, successes, failures,
skipped chemistry failures, coverage percentage, and runtime.

Useful options include `--input-representation`, `--random-seed`, `--embed-attempts`,
`--optimization-max-iterations`, `--timeout-seconds`, and `--fallback-methods`. Fallback methods are
recorded as provenance only unless later phases install/configure real fallback runners.

The full training-set feasibility run is intentionally outside default pytest. When local training
data is available, generate or reuse a PRD 3 chemistry audit bundle first, then run geometry
feasibility from that bundle.

## Local Full-Training-Set Run

A local full-training-set run was completed on ignored, reproducible artifacts under:

```text
artifacts/chemistry/chemistry-audit-v1/
artifacts/geometry/geometry-rdkit-v1/
```

These artifacts are intentionally not committed. The run used `open-polymer-train-v1`,
`chemistry-audit-v1`, `geometry-rdkit-v1`, RDKit `2026.03.3`, `rdkit_etkdg_mmff`,
`input_representation = capped_smiles`, `embed_attempts = 20`,
`optimization_max_iterations = 200`, `random_seed = 61453`, and no configured fallback methods. The
upstream chemistry provenance reported `capping_strategy = uncapped`, so the selected geometry
inputs still contained wildcard atoms.

Observed results:

- Chemistry audit: 7,973 valid records, 0 chemistry failures.
- Geometry: 7,973 attempted records, 7,180 successes, 793 failures, 0 skipped records.
- Coverage: 90.05%.
- Runtime: 305.20 seconds total, about 0.038 seconds per attempted record on this local run.
- Failure groups: all 793 failures were `embedding_failed` at the `embedding` stage.
- Failure messages: 631 RDKit ETKDG status `-1` failures and 162 RDKit bounds-matrix invariant
  violations.
- Successful records all produced SDF text. MMFF optimization status was `unavailable` for the
  successful wildcard-containing molecules, so this run primarily validates embeddable conformer
  generation rather than force-field-refined polymer endpoint geometry.

Coverage by selected-input heavy atom count:

| Heavy atoms | Total | Success | Failure | Coverage |
| --- | ---: | ---: | ---: | ---: |
| 1-10 | 675 | 599 | 76 | 88.74% |
| 11-20 | 1,660 | 1,583 | 77 | 95.36% |
| 21-40 | 3,393 | 3,288 | 105 | 96.91% |
| 41-60 | 1,659 | 1,417 | 242 | 85.41% |
| 61-80 | 467 | 272 | 195 | 58.24% |
| 81-100 | 97 | 20 | 77 | 20.62% |
| 101+ | 22 | 1 | 21 | 4.55% |

Failure records were materially larger than successes: failed molecules had a median of 52 heavy
atoms versus 28 for successful molecules, and a 95th percentile of 92 versus 59. Attachment-point
count alone was not a useful separator because nearly all records had two wildcard atoms.

## Coverage Follow-Ups

The highest-leverage next step is to separate endpoint representation effects from molecule-size
effects. The local run labeled its input as `capped_smiles`, but the upstream chemistry artifact was
uncapped, so all geometry inputs still contained wildcard atoms. A follow-up should rerun the
geometry workflow against a hydrogen-capped chemistry artifact and compare coverage, failure
messages, MMFF optimization availability, and runtime against the uncapped artifact.

Recommended focus areas:

- **Capping comparison**: use existing PRD 03 chemistry audit behavior plus PRD 04 geometry CLI to
  produce paired uncapped and hydrogen-capped geometry summaries. This can be handled as PRD 04
  review follow-up if required before acceptance, or recorded as a small new PRD if the comparison
  needs committed paired artifacts, docs, or automated report generation.
- **ETKDG retry policy**: add a geometry hardening slice that retries failed embeddings with larger
  attempt budgets and alternate RDKit distance-geometry settings, especially for 41+ heavy-atom
  molecules. This is likely a new PRD because it changes the method contract and cache identity.
- **Failure triage UI**: use PRD 13 structure viewer and validation workbench to inspect examples
  from `failures.json`, compare uncapped/capped representations, and decide whether failed cases are
  chemically meaningful polymer endpoints or representation artifacts.
- **Fallback methods**: use PRD 10 geometry-enabled representation/model work, or a preceding
  geometry-fallback PRD, to validate whether xTB/MLIP or another conformer backend improves coverage
  enough to justify runtime and dependency cost.
- **Coverage bias analysis**: PRD 10 should measure whether the 9.95% geometry failures are
  concentrated in target regimes or structural families that would bias geometry-aware model
  comparisons.

## Reviewer Workflow

For deterministic local review, run the default quality gate:

```bash
uv run pytest
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy
```

For artifact review, inspect `metadata.json` first to confirm dataset, chemistry, geometry config,
RDKit version, cache key, input representation, and output paths. Then inspect `summary.json` for
coverage, runtime, skipped counts, and failure groups. Use `failures.json` to triage representative
sample IDs, and open matching records in `records.json` when SDF text or chemistry provenance is
needed.

The interface discovery fixture now accepts geometry summary data and displays aggregate geometry
coverage/failure groups in the existing GUI/backend path. PRD 13 should consume the same geometry
artifact shapes for molecule-level SMILES, 2D, 3D, and validation workbench views rather than adding
parallel viewer-only fields.

## Deferred Choices

- xTB and MLIP are provenance-only fallback methods until a later PRD installs and validates real
  fallback runners.
- Uncapped wildcard-heavy inputs are allowed through `standardized_smiles`; failures are structured
  instead of being silently capped or filtered.
- Single-record SDF text is the first persisted conformer payload. Multi-conformer records, richer
  atom mapping, or split SDF/MolBlock payloads remain future extensions.
- Full-training-set geometry artifacts are opt-in because runtime and local data availability vary.
  The default CI-equivalent gate remains fixture-based and deterministic.
