# PRD: Geometry-Enabled Representation And Model Slice

## Problem Statement

The project needs to determine whether 3D geometry improves prediction under fair, controlled
conditions.

## Solution

Use early geometry artifacts to build one geometry-enabled representation or model and compare it
against equivalent 2D and fixed-vector controls.

## User Stories

1. As a modeler, I want geometry-aware features or graphs, so that 3D information can be evaluated.
2. As a reviewer, I want coverage differences reported, so that performance is not inflated by
   changing the sample subset.
3. As a modeler, I want geometry diagnostics in reports, so that cost and failure modes are visible.

## Implementation Decisions

- Reuse conformer provenance from the early geometry groundwork.
- Compare against controls using the same target and split setup.
- Report coverage, runtime, and quality diagnostics.

## Testing Decisions

- Test geometry-aware artifact creation on fixtures.
- Keep expensive geometry model training outside default tests.

## Out Of Scope

- Multiple geometry architectures.
- Final scientific comparison.
