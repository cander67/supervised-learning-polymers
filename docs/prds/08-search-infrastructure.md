# PRD: Search Infrastructure

## Problem Statement

Manual or ad hoc sweeps will make benchmark results hard to reproduce and compare.

## Solution

Wire grid, random, and Bayesian search into repeatable `mlbag`-tracked runs with validated search
spaces, explicit budgets, trial persistence, and resume behavior.

## User Stories

1. As a modeler, I want grid, random, and Bayesian search available through one contract, so that
   search strategies can be compared.
2. As a reviewer, I want every trial persisted, so that selected models are reproducible.
3. As a developer, I want interrupted searches to resume, so that long runs are not fragile.
4. As a modeler, I want tiny smoke budgets, so that search infrastructure can be verified cheaply.

## Implementation Decisions

- Use `mlbag` tuning helpers where they fit.
- Validate search spaces before runs start.
- Record trial parameters, fold metrics, aggregate metrics, runtime, status, failure reason, and
  best model reference.

## Testing Decisions

- Test search-space validation.
- Test one tiny search and resume behavior.

## Out Of Scope

- Full-scale benchmark studies.
- Deep-model-specific pruning unless required by a later PRD.
