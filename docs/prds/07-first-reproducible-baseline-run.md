# PRD: First Reproducible Baseline Run

## Problem Statement

Before complex models are useful, the project needs one reproducible path from raw inputs to trained
baseline regressors, persisted metrics, predictions, failures, and artifacts.

## Solution

Train cheap leakage-safe baselines using validated chemistry, fixed-vector features, frozen splits,
configured target modes, and `mlbag` run tracking.

## User Stories

1. As a modeler, I want dummy and simple regressors, so that complex models have a baseline.
2. As a reviewer, I want configs, metrics, predictions, and artifacts persisted, so that runs are
   reproducible.
3. As a developer, I want baseline runs to exercise the full data path, so that integration failures
   appear before deep modeling.
4. As a modeler, I want at least one multi-target or grouped-target baseline, so that target-mode
   configuration is proven.

## Implementation Decisions

- Start with `DummyRegressor`, Ridge or Elastic Net, Random Forest, XGBoost, and SVR.
- Use `mlbag` for run tracking, config persistence, and artifacts.
- Record runtime, inference time, metrics, and failure counts.

## Testing Decisions

- Test raw SMILES to fitted sklearn model on fixtures.
- Keep expensive full-data baseline runs outside default tests.

## Out Of Scope

- Neural models.
- Broad hyperparameter optimization.
