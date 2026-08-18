# PRD: Deep Sequence And Transformer Extensions

## Problem Statement

SMILES CNNs and transformers may add value, but they should build on stable target, split, tracking,
and baseline contracts.

## Solution

Add tokenization, 1D CNN, and transformer experiments in narrow slices after simpler baselines are
working.

## User Stories

1. As a modeler, I want reusable SMILES tokenization, so that CNN and transformer inputs are
   consistent.
2. As a modeler, I want CNN and transformer runs tracked like other models, so that comparisons are
   fair.
3. As a reviewer, I want repeated-seed estimates, so that deep-model variance is visible.

## Implementation Decisions

- Cover capped and uncapped SMILES, unknown tokens, padding, truncation, canonical/randomized SMILES,
  and augmentation.
- Start with small or frozen-embedding approaches before fine-tuning larger models.
- Use pruning or early stopping and persisted best checkpoints.

## Testing Decisions

- Test tokenizer behavior on fixtures.
- Test tiny model smoke paths only when dependencies are installed.

## Out Of Scope

- Making deep models the first benchmark result.
- Final model-card packaging.
