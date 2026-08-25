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

Wildcard-heavy uncapped inputs may fail or produce limited optimization behavior. Those outcomes are
recorded as structured geometry results rather than blocking non-geometry model work.

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

