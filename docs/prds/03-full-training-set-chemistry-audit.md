# PRD: Full-Training-Set Chemistry Audit

## Problem Statement

Small fixtures are not enough to reveal polymer chemistry failure modes. The project needs to process
the full training set early, log failures, and establish reproducible chemistry records before model
development depends on derived representations.

## Solution

Build a chemistry audit workflow that reads the available training data, parses and validates SMILES,
standardizes molecules, applies configurable capping, records provenance, and persists success and
failure artifacts.

## User Stories

1. As a benchmark developer, I want to run chemistry processing over the full training set, so that
   real failure modes appear early.
2. As a modeler, I want each failed molecule categorized, so that failures can be fixed or excluded
   deliberately.
3. As a reviewer, I want raw SMILES retained, so that derived chemistry can always be traced back to
   source input.
4. As a modeler, I want configurable standardization, so that salts, charges, tautomers, fragments,
   stereochemistry, and isotopes are handled intentionally.
5. As a modeler, I want versioned capping strategies, so that representation choices are
   reproducible.
6. As a developer, I want cache keys to include chemistry settings and RDKit version, so that stale
   features are not silently reused.

## Implementation Decisions

- Invalid molecules should produce structured failure records during batch runs.
- Source SMILES should never be overwritten by standardized or capped SMILES.
- Start with one reliable capping strategy plus an uncapped control path.
- Add more capping strategies only when the gold set or comparisons justify them.
- Persist audit summaries and detailed per-sample records.

## Testing Decisions

- Use fixture-sized behavior tests for valid, invalid, wildcard, charged, aromatic, disconnected,
  and stereochemical examples.
- Add an explicit slow/full-data audit command outside the default test suite.
- Test cache invalidation when chemistry config or RDKit version changes.

## Out Of Scope

- Full geometric GNN development.
- Broad model training and hyperparameter search.
- Final chemistry visualization tools.

## Further Notes

This PRD should use the detailed ignored plan in `.plans/implementation/` only after PRD 01 defines
the target and manifest contract.
