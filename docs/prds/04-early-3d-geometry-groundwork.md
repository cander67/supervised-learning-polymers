# PRD: Early 3D Geometry Groundwork

## Problem Statement

3D geometry is central to the project direction, but geometry-aware models should not be built before
geometry coverage, quality, runtime, and failure modes are understood.

## Solution

Build an early conformer feasibility workflow that attempts 3D geometry generation for capped
molecules, records method and fallback provenance, and writes coverage and failure summaries. This
creates the foundation for later 3D representations and geometric models.

## User Stories

1. As a modeler, I want conformer attempts recorded early, so that I know whether 3D representations
   are viable for the dataset.
2. As a developer, I want geometry failures to be structured, so that non-geometry models can still
   proceed.
3. As a reviewer, I want method provenance, so that 3D results are reproducible.
4. As a modeler, I want optional fallback methods represented in config, so that xTB or MLIP paths
   can be enabled when available.
5. As a modeler, I want coverage and runtime summaries, so that model comparisons account for cost.

## Implementation Decisions

- Implement RDKit ETKDG plus MMFF as the first local baseline.
- Represent xTB and MLIP fallbacks in config and provenance even if they are skipped locally.
- Keep geometry feasibility independent from graph model training.
- Do not let geometry failures block non-geometry features.

## Testing Decisions

- Test deterministic small-molecule conformer behavior.
- Test optional fallback skip behavior when external dependencies are unavailable.
- Keep full-dataset geometry feasibility outside the default test suite.

## Out Of Scope

- Training a geometric GNN.
- Multiple-conformer ensemble modeling.
- Installing external quantum chemistry tools by default.

## Further Notes

This work should happen early, but its output is a feasibility and provenance layer, not the final 3D
modeling layer.
