# PRD: Final Scientific Comparison

## Problem Statement

The project needs a defensible final comparison across target modes, representations, and model
families, not a collection of isolated scores.

## Solution

Produce final leaderboards, paired statistical comparisons, applicability-domain analysis,
sample-level predictions, and model cards for selected models.

## User Stories

1. As a reviewer, I want a final leaderboard with run metadata, so that results can be audited.
2. As a modeler, I want sample-level predictions, so that errors can be analyzed.
3. As a scientist, I want paired comparisons and confidence intervals, so that small score
   differences are not overclaimed.
4. As a future user, I want model cards, so that intended use and limitations are clear.

## Implementation Decisions

- Compare models using paired folds or paired test predictions where possible.
- Include runtime, memory, failure rates, artifact paths, git commits, and environment hashes.
- Analyze applicability domain using chemical similarity, descriptor or embedding distance, target
  range, molecular size, and chemical group.

## Testing Decisions

- Test report schema and aggregation behavior.
- Test statistical comparison helpers on deterministic fixtures.

## Out Of Scope

- Adding new model families.
- Revising earlier chemistry or split assumptions except through new PRDs.
