# PRD: Frozen Splits And Leakage Checks

## Problem Statement

Model comparisons are not meaningful if splits leak duplicate, grouped, or structurally similar
molecules across train, validation, and test boundaries.

## Solution

Create persisted split artifacts for random, grouped, and structure-aware splits, with diagnostics
and automated leakage checks.

## User Stories

1. As a reviewer, I want split assignments saved as data, so that experiments can be reproduced.
2. As a modeler, I want grouped splits, so that repeated structures do not leak.
3. As a modeler, I want structure-aware splits, so that interpolation and extrapolation performance
   can be compared.
4. As a developer, I want sequential target prediction to use out-of-fold upstream predictions, so
   that downstream training does not leak labels.

## Implementation Decisions

- Persist split files with sample ID, target or target group, split, fold, group ID, split method,
  and split version.
- Keep locked test data out of feature selection, scaling, tuning, early stopping, and architecture
  selection.

## Testing Decisions

- Test random, grouped, and similarity-aware split behavior on fixtures.
- Test duplicate and group leakage rejection.

## Out Of Scope

- Final statistical comparison.
- Full model search.
