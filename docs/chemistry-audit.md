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

## Cache Identity

Chemistry cache keys include:

- dataset contract fields;
- chemistry config ID;
- standardization settings;
- capping strategy and version;
- RDKit version.

This keeps standardization experiments from silently reusing stale chemistry artifacts.
