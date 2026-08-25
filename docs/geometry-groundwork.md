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
