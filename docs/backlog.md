# Project Backlog

This backlog tracks the current and planned PRDs for the polymer property benchmark. The roadmap
describes the durable sequence; this file is the review surface for status, dependencies, and next
actions.

Status legend:

- **Ready for review**: implemented locally and ready for PRD-level review.
- **Planned**: PRD exists, but implementation has not started.
- **Blocked by**: should wait for named earlier backlog items.

## Current Work

| Order | Status | PRD | Scope | Notes |
| --- | --- | --- | --- | --- |
| 1 | Ready for review | [Benchmark Contract And Target Config](prds/01-benchmark-contract-and-target-config.md) | Typed target, dataset, manifest, and sequential leakage contract. | Implemented with fixture-sized behavior tests and docs. |
| 2 | Ready for review | [Public Interface Discovery](prds/02-public-interface-discovery.md) | Compare notebook, CLI/report, and GUI/backend options against actual artifact workflows. | GUI/backend selected in [Public Interface Discovery Decision](interface-discovery-decision.md); branch retains only the GUI/backend survivor path. |

PRD 01 establishes the contract that later items should consume. The implemented public surfaces are
documented in [Benchmark Contract](benchmark-contract.md), and target context is documented in
[Open Polymer Target Properties](target-properties.md).

## Planned Backlog

| Order | Status | PRD | Scope | Blocked by |
| --- | --- | --- | --- | --- |
| 3 | Planned | [Full-Training-Set Chemistry Audit](prds/03-full-training-set-chemistry-audit.md) | Parse, validate, standardize, cap, and persist chemistry audit artifacts for the full training set. | PRD 01 contract |
| 4 | Planned | [Early 3D Geometry Groundwork](prds/04-early-3d-geometry-groundwork.md) | Measure conformer feasibility, provenance, fallback behavior, coverage, and runtime. | PRD 03 chemistry audit |
| 5 | Planned | [Fixed-Vector Representations](prds/05-fixed-vector-representations.md) | Generate versioned descriptor and fingerprint artifacts from validated chemistry records. | PRD 03 chemistry audit |
| 6 | Planned | [Frozen Splits And Leakage Checks](prds/06-frozen-splits-and-leakage-checks.md) | Persist random, grouped, and structure-aware split artifacts with leakage diagnostics. | PRD 01 contract; PRD 03 chemistry audit |
| 7 | Planned | [First Reproducible Baseline Run](prds/07-first-reproducible-baseline-run.md) | Train cheap leakage-safe baselines with tracked configs, metrics, predictions, and artifacts. | PRDs 03, 05, and 06 |
| 8 | Planned | [Search Infrastructure](prds/08-search-infrastructure.md) | Add grid, random, and Bayesian search with trial persistence and resume behavior. | PRD 07 baseline path |
| 9 | Planned | [2D Graph Representation And GNN Baseline](prds/09-2d-graph-representation-and-gnn-baseline.md) | Build 2D graph artifacts and one small GNN baseline. | PRDs 03, 06, and 07 |
| 10 | Planned | [Geometry-Enabled Representation And Model Slice](prds/10-geometry-enabled-representation-and-model-slice.md) | Compare one geometry-aware representation/model against 2D and fixed-vector controls. | PRDs 04, 05, 06, and 07 |
| 11 | Planned | [Deep Sequence And Transformer Extensions](prds/11-deep-sequence-and-transformer-extensions.md) | Add SMILES CNN and transformer experiments after core contracts and baselines are stable. | PRDs 06, 07, and 08 |
| 12 | Planned | [Final Scientific Comparison](prds/12-final-scientific-comparison.md) | Produce leaderboards, statistical comparisons, applicability-domain analysis, and model cards. | Earlier model and artifact PRDs |

## Review Notes

- Keep implementation plans in `.plans/implementation/`; they are local working memory and are not
  committed.
- Keep this backlog committed because it records project-visible status and sequencing.
- Move planned items to active implementation only after the preceding contract or artifact they
  depend on exists.
- Update this backlog when a PRD enters implementation, reaches review, or is split into smaller
  PRDs.
