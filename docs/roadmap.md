# Polymer Property Benchmark Roadmap

This roadmap tracks the durable product and scientific capabilities for the polymer property
prediction benchmark. Each item below should have a committed PRD in `docs/prds/` and an ignored
implementation plan in `.plans/implementation/` when active.

Implementation plans use tracer-bullet phases: each phase should be a narrow, verifiable path
through config, data/model code, artifacts, tests, and docs.

## Operating Model

- Commit roadmap and PRDs because they capture durable intent, scope, and scientific decisions.
- Keep `.plans/` ignored because implementation plans are local working memory.
- Promote each roadmap item into implementation only after its PRD is clear enough to slice.
- Prefer behavior tests through public interfaces over tests coupled to private helper structure.
- Use full-dataset chemistry and data audits early to expose real failure modes.
- Use small fixtures for fast deterministic tests, not as the only discovery mechanism.
- Keep domain-specific chemistry and modeling code in this repo.
- Add only broadly reusable infrastructure to `mlbag` after proving it in project context.

## Roadmap

The numeric list below is execution order. PRD identifiers remain stable even when a later PRD is
pulled forward because it becomes useful earlier than originally planned.

1. **Benchmark Contract And Target Config**
   Define observations, target modes, sequential prediction semantics, sample identity, manifests,
   and validation rules.

2. **Public Interface Discovery**
   Decide whether the first usable interface is a notebook report, CLI artifact flow, local GUI, or
   a thin backend plus GUI.

3. **Full-Training-Set Chemistry Audit**
   Process the full training set early, log chemistry failures, and establish standardization,
   capping, provenance, and cache identity.

4. **Early 3D Geometry Groundwork**
   Generate conformer feasibility artifacts early so 3D coverage, cost, and failure modes are known
   before geometry-aware models depend on them. Persist viewer-ready conformer artifacts for every
   valid SMILES where possible, with structured failures where geometry cannot be generated.

5. **Structure Viewer And Validation Workbench** (`PRD 13`)
   Add the GUI structure page as soon as PRD 04 produces useful conformer artifacts. Start with
   SMILES, 2D depiction, and 3D conformer/failure panels, then complete 2D/3D graph rendering as PRD
   09 graph artifacts mature.

6. **Fixed-Vector Representations**
   Build versioned descriptor and fingerprint features from validated chemistry records.

7. **Frozen Splits And Leakage Checks**
   Create reproducible random, grouped, and structure-aware split artifacts with leakage tests.

8. **First Reproducible Baseline Run**
   Train cheap leakage-safe regressors from raw inputs through persisted metrics and predictions.

9. **Search Infrastructure**
   Wire grid, random, and Bayesian search through tracked, resumable `mlbag` runs.

10. **2D Graph Representation And GNN Baseline**
   Build 2D graph artifacts and train the smallest useful graph model against fixed-vector controls.
   Keep graph artifacts renderable in both 2D and 3D viewer contexts and use PRD 13 as the visual
   validation surface.

11. **Geometry-Enabled Representation And Model Slice**
    Compare one geometry-aware representation/model against equivalent 2D and fixed-vector controls.

12. **Deep Sequence And Transformer Extensions**
    Add SMILES CNN and transformer experiments only after target, split, and baseline semantics are
    stable.

13. **Final Scientific Comparison**
    Produce final leaderboards, statistical comparisons, applicability-domain analysis, and model
    cards.

## Current Status

- Accepted PRDs: PRD 01 benchmark contract, PRD 02 public interface discovery, and PRD 03
  full-training-set chemistry audit.
- Active PRD: none at this checkpoint.
- Next planned PRD: `docs/prds/04-early-3d-geometry-groundwork.md`
- Next interface PRD after geometry groundwork:
  `docs/prds/13-structure-viewer-and-validation-workbench.md`
- Chemistry audit docs: `docs/chemistry-audit.md`
- Interface alignment docs: `docs/interface-discovery-gui-backend.md`
- Review status: PRD 03 has been accepted after the final review gate passed locally with the
  chemistry audit contract, artifacts, opt-in full-data script, and GUI/backend summary fixture in
  place.
