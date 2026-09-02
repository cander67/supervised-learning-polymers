# Project Backlog

This backlog tracks the current and planned PRDs for the polymer property benchmark. The roadmap
describes the durable sequence; this file is the review surface for status, dependencies, and next
actions. The `Order` column is execution order and may differ from the PRD number when a later PRD is
pulled forward.

Status legend:

- **Accepted**: PRD-level review has closed out and the work is available as project baseline.
- **Active**: implementation is underway locally or on a PRD branch.
- **Ready for review**: implemented locally and ready for PRD-level review.
- **Planned**: PRD exists, but implementation has not started.
- **Blocked by**: should wait for named earlier backlog items.

## Accepted Work

| Order | Status | PRD | Scope | Notes |
| --- | --- | --- | --- | --- |
| 1 | Accepted | [Benchmark Contract And Target Config](prds/01-benchmark-contract-and-target-config.md) | Typed target, dataset, manifest, and sequential leakage contract. | Closed out as the baseline contract for dataset, target, and manifest work. |
| 2 | Accepted | [Public Interface Discovery](prds/02-public-interface-discovery.md) | Compare notebook, CLI/report, and GUI/backend options against actual artifact workflows. | Closed out with the GUI/backend path selected in [Public Interface Discovery Decision](interface-discovery-decision.md). |
| 3 | Accepted | [Full-Training-Set Chemistry Audit](prds/03-full-training-set-chemistry-audit.md) | Parse, validate, standardize, cap, and persist chemistry audit artifacts for the full training set. | Closed out with the final review gate passing locally, including fixture tests, default tests, full-data audit, chemistry docs, and GUI/backend fixture alignment. |
| 4 | Accepted | [Early 3D Geometry Groundwork](prds/04-early-3d-geometry-groundwork.md) | Measure conformer feasibility, provenance, fallback behavior, coverage, and runtime. | Closed out with the final review gate passing locally, including fixture tests, default tests, full-training-set geometry results, geometry docs, and GUI/backend fixture alignment. |

## Current Work

| Order | Status | PRD | Scope | Notes |
| --- | --- | --- | --- | --- |
| 5 | Ready for review | [Structure Viewer And Validation Workbench](prds/13-structure-viewer-and-validation-workbench.md) | Add GUI panels for SMILES, 2D structures, 3D conformers, and 2D/3D graph representations. | Implemented with deterministic fixture coverage plus direct launch from local chemistry and geometry artifact bundles. |

PRD 01 establishes the contract that later items should consume. The implemented public surfaces are
documented in [Benchmark Contract](benchmark-contract.md), and target context is documented in
[Open Polymer Target Properties](target-properties.md).

## Planned Backlog

| Order | Status | PRD | Scope | Blocked by |
| --- | --- | --- | --- | --- |
| 6 | Planned | [Fixed-Vector Representations](prds/05-fixed-vector-representations.md) | Generate versioned descriptor and fingerprint artifacts from validated chemistry records. | None |
| 7 | Planned | [Frozen Splits And Leakage Checks](prds/06-frozen-splits-and-leakage-checks.md) | Persist random, grouped, and structure-aware split artifacts with leakage diagnostics. | None |
| 8 | Planned | [First Reproducible Baseline Run](prds/07-first-reproducible-baseline-run.md) | Train cheap leakage-safe baselines with tracked configs, metrics, predictions, and artifacts. | PRDs 05 and 06 |
| 9 | Planned | [Search Infrastructure](prds/08-search-infrastructure.md) | Add grid, random, and Bayesian search with trial persistence and resume behavior. | PRD 07 baseline path |
| 10 | Planned | [2D Graph Representation And GNN Baseline](prds/09-2d-graph-representation-and-gnn-baseline.md) | Build 2D/3D-renderable graph artifacts and one small GNN baseline. | PRDs 06 and 07; extends PRD 13 graph panel |
| 11 | Planned | [Geometry-Enabled Representation And Model Slice](prds/10-geometry-enabled-representation-and-model-slice.md) | Compare one geometry-aware representation/model against 2D and fixed-vector controls. | PRDs 04, 05, 06, 07, and PRD 13 diagnostics links |
| 12 | Planned | [Cytoscape 3D Projection Controls](prds/14-cytoscape-3d-projection-controls.md) | Add optional rotation controls for Cytoscape-backed projected 3D graph inspection. | PRDs 07, 09, 10, and enough real ML diagnostics to shape the interaction |
| 13 | Planned | [Deep Sequence And Transformer Extensions](prds/11-deep-sequence-and-transformer-extensions.md) | Add SMILES CNN and transformer experiments after core contracts and baselines are stable. | PRDs 06, 07, and 08 |
| 14 | Planned | [Final Scientific Comparison](prds/12-final-scientific-comparison.md) | Produce leaderboards, statistical comparisons, applicability-domain analysis, and model cards. | Earlier model and artifact PRDs |

## Review Notes

- Keep implementation plans in `.plans/implementation/`; they are local working memory and are not
  committed.
- Keep this backlog committed because it records project-visible status and sequencing.
- Move planned items to active implementation only after the preceding contract or artifact they
  depend on exists.
- Update this backlog when a PRD enters implementation, reaches review, or is split into smaller
  PRDs.
- Keep PRD 13 at ready-for-review status until PRD-level review closes; later accepted status should
  follow only after review, not merely after implementation.
