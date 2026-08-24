# Chemistry Audit

PRD 3 introduces the chemistry audit contract and fixture-sized processing path used before feature
generation or model training. The audit consumes the PRD 01 dataset contract, preserves source
SMILES, and records derived chemistry fields separately.

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
