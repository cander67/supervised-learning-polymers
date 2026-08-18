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
- Persist feature metadata, dimensions, names where available, and config hashes.
- Keep fold-learned preprocessing out of global feature generation.

## Testing Decisions

- Test determinism, dimensions, failure reporting, and config validation.
- Use fixture records for default tests.

## Out Of Scope

- Graph representations.
- Model search and final model comparison.
