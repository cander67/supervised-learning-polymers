# PRD: Structure Viewer And Validation Workbench

## Problem Statement

The project will produce several chemistry-derived representations for the same polymer sample:
raw and derived SMILES, 2D depictions, 3D conformers, and graph artifacts. Modelers and
chemistry-proficient reviewers need a single GUI surface for validating those representations before
they are trusted in training, comparison, and final scientific reporting.

## Solution

Build a structure viewer page in the local GUI/backend interface. The page should let users search
or filter chemistry records, then inspect four coordinated panels for the selected sample: SMILES,
2D, 3D, and graph. The viewer consumes persisted artifacts from chemistry audit, geometry, graph,
model, and result workflows rather than owning chemistry or modeling rules itself.

Implement the viewer as soon as PRD 04 produces real conformer artifacts. The first useful slice can
ship with SMILES, 2D depiction, and 3D conformer/failure review, while the graph panel supports
fixture or available graph artifacts and becomes complete after PRD 09.

## User Stories

1. As a chemistry-proficient reviewer, I want to inspect raw, canonical, standardized, and capped
   SMILES side by side, so that I can validate how the benchmark transforms source structures.
2. As a modeler, I want every valid SMILES to have an attempted 3D view or a structured 3D failure,
   so that I can see what non-geometry-aware models ignore.
3. As a reviewer, I want 2D and 3D structure panels for the same sample, so that I can compare
   depiction, conformer generation, and provenance without leaving the GUI.
4. As a graph-modeling user, I want graph panels that can render both 2D and 3D graph artifacts, so
   that node, edge, coordinate, and feature choices are inspectable.
5. As a modeler, I want atom and bond identity to be stable across panels where feasible, so that
   highlighted atoms or failures can be traced across SMILES, 2D, 3D, and graph representations.
6. As a reviewer, I want structure records linked to downstream model artifacts, so that predictions,
   failures, and coverage differences can be traced back to the exact chemistry representation.

## Implementation Decisions

- Add a GUI page or route named around structures, monomers, or validation; it should be reachable
  from the existing thin local backend plus GUI selected by PRD 02.
- Organize the selected record view into four primary panels: SMILES, 2D, 3D, and graph.
- Sequence this PRD immediately after PRD 04 in the implementation backlog because early visual
  validation will make later representation and model artifacts easier to trust.
- Keep the GUI artifact-driven. Chemistry parsing, capping, conformer generation, graph creation,
  descriptor generation, and model scoring remain in backend/pipeline artifacts owned by their
  respective PRDs.
- Use Python RDKit as the authoritative chemistry backend for parsing, standardization,
  conformer generation, MolBlock/SDF export, and optional server-side 2D SVG generation.
- Prefer 3Dmol.js for the browser 3D molecule panel because it is embeddable, WebGL-based, and can
  load molecular coordinate formats such as SDF, MOL2, XYZ, and PDB.
- Start the 2D panel with RDKit-generated SVG from persisted chemistry artifacts. Evaluate RDKit.js,
  OpenChemLib JS, SmilesDrawer, or Kekule.js only if client-side rendering, editing, or highlighting
  becomes necessary.
- Render graph artifacts from project-owned node/edge JSON so the viewer reflects exactly what
  model inputs consumed. The graph panel should support both 2D layout coordinates and 3D conformer
  coordinates. Before PRD 09 lands, the graph panel may be limited to fixture-backed or
  geometry-derived preview graphs.
- Make 3D status explicit for every valid SMILES: successful conformer, attempted but failed,
  skipped by unavailable optional fallback, or not yet generated.
- Keep third-party viewer assets optional or vendored/pinned in a documented way before depending on
  them in default tests.

## Testing Decisions

- Test the structure-viewer artifact contract with fixture records that include successful 3D,
  failed 3D, 2D graph, and 3D graph examples.
- Test backend endpoints through public artifact inputs rather than private GUI helper details.
- Add a browser smoke test only when the GUI stack supports reliable local rendering checks.
- Keep full-dataset visual review outside the default suite; default tests should use small
  deterministic fixtures.

## Out Of Scope

- Chemical structure editing.
- Manual correction workflows that write back to source chemistry artifacts.
- Multiple-conformer ensemble visualization beyond showing the selected or primary conformer.
- Production deployment, authentication, or collaborative annotation.
- Training graph or geometry-aware models; PRDs 09 and 10 own model work.

## Further Notes

This PRD depends on viewer-ready artifacts from PRD 04 for its first practical implementation and
should stay compatible with graph artifacts from PRD 09 and geometry-linked model diagnostics from
PRD 10. It should be implemented incrementally: first as a read-only chemistry/geometry artifact
browser, then as a full structure and graph validation workbench once graph artifacts exist.

## Implementation Review Notes

Status: ready for PRD-level review. The local GUI/backend now exposes searchable structure records,
coordinated SMILES, RDKit 2D, 3Dmol conformer/failure, Cytoscape graph-inspection, failure triage,
optional downstream-reference panels, and direct launch from persisted local chemistry and geometry
artifact bundles.

The implementation keeps current interface summary path keys and discovers detailed chemistry and
geometry bundle siblings from those paths. Optional graph and downstream links are direct artifact
paths, and missing optional records are displayed as unavailable rather than as errors.

Deferred geometry-groundwork follow-ups remain out of scope: capping rerun comparison, ETKDG retry
policy, fallback method execution or selection, chemistry correction workflows, molecule-size bins,
and coverage-bias analysis. Those should be handled by later model or geometry-hardening PRDs after
more real ML diagnostics exist.

Phase 9 added a real-local-artifact launcher so reviewers can start the same GUI directly from
existing chemistry and geometry artifact bundles without manually creating an interface wrapper
JSON. The current local artifact smoke path uses `artifacts/chemistry/chemistry-audit-v1` and
`artifacts/geometry/geometry-rdkit-v1`, which contain 7,973 chemistry-valid records, 7,180 geometry
successes, 793 geometry failures, and 90.05% geometry coverage.
