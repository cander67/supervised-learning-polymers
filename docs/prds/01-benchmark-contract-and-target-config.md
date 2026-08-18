# PRD: Benchmark Contract And Target Config

## Problem Statement

The benchmark needs a stable contract before modeling begins. Without clear definitions for
observations, targets, target groups, sequential target prediction, sample identity, and artifacts,
later chemistry, splitting, modeling, and reporting work can drift or leak information across folds.

## Solution

Define a typed benchmark contract that describes the dataset, target metadata, supported target
modes, sequential prediction semantics, grouping keys, artifact identity, and validation behavior.
This contract should be usable from tests, notebooks, CLI workflows, and any later GUI/backend.

## User Stories

1. As a benchmark developer, I want each row to have a stable sample identity, so that artifacts can
   be traced across chemistry, features, splits, models, and reports.
2. As a benchmark developer, I want target metadata to include units and valid ranges, so that bad
   values can fail early.
3. As a modeler, I want to configure a single target, so that I can run focused experiments.
4. As a modeler, I want to configure target groups, so that related properties can be modeled
   together.
5. As a modeler, I want to configure all available targets, so that broad benchmark runs are
   reproducible.
6. As a modeler, I want sequential target prediction, so that predicted properties can be used as
   downstream features when scientifically justified.
7. As a reviewer, I want sequential prediction to prevent leakage, so that downstream target scores
   are defensible.
8. As a future interface user, I want the same config contract to drive notebooks, CLI, or GUI flows,
   so that interfaces do not duplicate business logic.

## Implementation Decisions

- Build the benchmark contract around typed configuration and validated manifests.
- Support target modes named `single`, `group`, `all`, and `sequential`.
- Treat sequential prediction as a first-class mode with explicit dependency order and leakage
  constraints.
- Keep source SMILES, targets, grouping fields, and sample identifiers separate from derived
  chemistry or feature artifacts.
- Defer exact file and function names to implementation planning.
- Use `mlbag` conventions for later run identity and persisted configs.

## Testing Decisions

- Test public config-loading and validation behavior rather than private helper structure.
- Cover accepted and rejected examples for every target mode.
- Include failure tests for missing target metadata, invalid dependency order, unknown targets,
  duplicate target definitions, and invalid sample identifiers.
- Add fixture-sized tests now; reserve full-dataset validation for later chemistry and data-audit
  PRDs.

## Out Of Scope

- Chemistry parsing, standardization, capping, and geometry generation.
- Model training and hyperparameter search.
- Final report rendering or GUI implementation.
- Choosing final scientific target groupings when the source data has not yet been audited.

## Further Notes

This PRD is the first implementation item because it defines the language that later PRDs depend on.
The implementation plan should resolve only the contract needed to let subsequent PRDs compose cleanly.
