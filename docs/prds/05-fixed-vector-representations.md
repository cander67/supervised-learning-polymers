# PRD: Fixed-Vector Representations

## Problem Statement

The benchmark needs reproducible descriptor and fingerprint features before broad model comparison
can begin.

## Solution

Build versioned fixed-vector representation generation from validated chemistry records, including
descriptor sets, Morgan-style fingerprints, feature metadata, hashes, and failure reporting.

## User Stories

1. As a modeler, I want descriptor features, so that cheap baselines can run quickly.
2. As a modeler, I want fingerprint features, so that classical models have strong molecular inputs.
3. As a reviewer, I want feature dimensions and hashes persisted, so that representations are
   reproducible.
4. As a developer, I want representation failures separate from chemistry failures, so that the
   source of issues is clear.

## Implementation Decisions

- Consume validated chemistry records rather than reparsing raw files.
- Use `capped_smiles` from the chemistry artifact as the default molecular input, with
  `standardized_smiles` available as an explicit configurable alternative.
- Start with an `rdkit_2d` descriptor feature set built from RDKit named molecular descriptors.
- Start with a Morgan-style fingerprint feature set using radius 2, 2048-bit vectors, and chirality
  enabled by default.
- Persist feature matrices as compressed NumPy `.npz` files, with JSON sidecars for sample IDs,
  feature names, metadata, summaries, hashes, and failures.
- Persist feature metadata, dimensions, names where available, and config hashes.
- Keep fold-learned preprocessing out of global feature generation.

## Documentation Requirements

- Document how to create representation artifacts from a chemistry audit artifact.
- Document how to choose the molecular input representation, including the default `capped_smiles`
  path and the configurable `standardized_smiles` path.
- Document how to select one or more feature sets for generation, including the initial `rdkit_2d`
  descriptor set and Morgan fingerprint set.
- Document the config fields needed to define a new feature set: stable feature-set ID, family,
  version, input representation, RDKit method/settings, output shape, feature-name policy, and hash
  identity.
- Document the expected artifact bundle layout and how downstream split/model workflows should
  reference feature-set IDs and matrix metadata without recomputing features.

## Testing Decisions

- Test determinism, dimensions, failure reporting, and config validation.
- Use fixture records for default tests.

## Out Of Scope

- Graph representations.
- Model search and final model comparison.
