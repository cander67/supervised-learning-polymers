# PRD: 2D Graph Representation And GNN Baseline

## Problem Statement

The benchmark needs to compare fixed-vector baselines with molecular graph representations without
jumping directly into many graph architectures.

## Solution

Build a versioned 2D graph representation and train the smallest useful graph baseline on frozen
splits.

## User Stories

1. As a modeler, I want graph artifacts generated independently from training, so that failures and
   model behavior can be separated.
2. As a reviewer, I want graph provenance, so that graph features are reproducible.
3. As a modeler, I want one simple GNN baseline, so that graph models can be compared to fixed-vector
   controls.

## Implementation Decisions

- Start with one simple GCN, GraphSAGE, or GIN baseline.
- Keep optional neural/GNN dependencies behind project extras.
- Record node features, edge features, capping indicators, wildcard handling, and provenance.

## Testing Decisions

- Test graph construction on fixtures.
- Add a tiny graph-training smoke test when dependencies are installed.

## Out Of Scope

- Geometric GNNs.
- Broad graph architecture search.
