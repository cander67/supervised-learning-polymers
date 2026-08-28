# PRD: Cytoscape 3D Projection Controls

## Problem Statement

The structure viewer can display graph artifacts with 2D coordinates and geometry-gated 3D
coordinates, but Cytoscape.js renders those graphs on a 2D canvas. This means the current 3D graph
mode is an inspectable projection, not a rotatable 3D view. Reviewers who compare graph artifacts to
3D conformers may need to rotate the projected graph to understand whether atom, bond, and geometry
features align with model inputs.

This should wait until the project has actual ML artifacts and graph/geometry model context. The
first graph inspection surface should stay simple until fixed-vector, baseline, search, graph, and
geometry-aware model slices clarify which 3D graph questions matter in practice.

## Solution

Add a small custom projection layer on top of Cytoscape.js for structure-viewer graph panels. The
layer should preserve the project-owned graph artifact contract, read 3D node coordinates when
available, and project them into Cytoscape's 2D preset layout. Users can rotate the projected 3D
coordinates around stable axes, reset the view, and continue selecting atoms and bonds through the
existing Cytoscape inspection workflow.

The projection layer should be intentionally modest: it should make 3D graph coordinates easier to
inspect inside the existing validation workbench, without turning the graph panel into a general
3D renderer or molecular visualization engine.

## User Stories

1. As a graph-modeling user, I want to rotate a projected 3D graph, so that I can inspect whether
   graph coordinates match the geometry artifact used by later model slices.
2. As a chemistry-proficient reviewer, I want rotation to preserve atom and bond identity, so that
   selected graph elements remain traceable across graph, SMILES, 2D, and 3D panels.
3. As a modeler, I want projection controls to work only when valid 3D coordinates are available,
   so that unavailable geometry is not confused with a broken graph viewer.
4. As a reviewer, I want reset controls for projection orientation and zoom/pan, so that I can return
   to a stable default view after exploring a molecule.
5. As a developer, I want projection math isolated behind a small tested interface, so that future
   graph artifacts can reuse the viewer without coupling model code to browser rendering details.
6. As a project maintainer, I want this feature deferred until after meaningful ML runs exist, so
   that the controls are shaped by real model-inspection needs rather than speculative UI polish.

## Implementation Decisions

- Keep Cytoscape.js as the graph interaction layer for pan, zoom, selection, styling, and detail
  inspection.
- Add a custom projection module that accepts stable node identities and 3D coordinates, applies
  rotation and projection transforms, and returns Cytoscape-compatible 2D preset positions.
- Preserve the existing graph artifact contract: do not require production graph artifacts to store
  browser-specific projection state.
- Store projection UI state in the local viewer session only. Do not persist reviewer rotation,
  zoom, or pan settings to graph artifacts.
- Expose controls only for graph records with geometry-gated 3D coordinates. 2D-only records should
  keep the existing explicit state.
- Include at least reset orientation, reset fit, and one ergonomic rotation interaction such as
  sliders, drag-to-rotate, or small axis controls.
- Keep the 3D conformer panel as the authoritative true 3D molecular renderer. The graph panel
  remains a Cytoscape-backed graph inspector.
- Avoid adding a frontend build step or framework migration unless a later interface PRD replaces
  the static GUI shell.

## Testing Decisions

- Test projection math as a deterministic module with fixture coordinates, including identity
  projection, axis rotations, reset behavior, and stable atom identity.
- Test the public GUI behavior with fixture-backed graph records rather than private helper details.
- Keep geometry-gated states covered: projection controls appear for 3D graph records and remain
  absent for unavailable, missing-artifact, and 2D-only graph states.
- Add browser smoke coverage for rotation controls, selection after rotation, reset behavior, and
  mode switching between 2D and projected 3D.
- Use small deterministic graph fixtures for default tests; do not require full-dataset graph or
  model artifacts in the default suite.

## Out Of Scope

- True WebGL 3D network rendering.
- Replacing the 3Dmol conformer viewer.
- Graph editing, atom relabeling, bond editing, or artifact mutation.
- Production graph generation or PRD 09 model-pipeline integration.
- Learned embeddings, path queries, neighbor algorithms, subgraph extraction, or force-layout
  exploration.
- Persisting reviewer annotations or projection camera state.

## Further Notes

This PRD should be considered after the project has run enough ML work to know which graph and
geometry artifacts need deeper visual inspection. A good implementation point is after baseline,
search, 2D graph/GNN, and geometry-aware model slices have produced real diagnostics that reviewers
want to trace back to structure-level graph coordinates.
