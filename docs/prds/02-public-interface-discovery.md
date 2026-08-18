# PRD: Public Interface Discovery

## Problem Statement

The project needs a usable public interface for configuring runs, inspecting full-dataset failures,
and reviewing results. It is not yet clear whether the best first interface is a notebook report,
CLI-generated artifacts, a local GUI, or a thin backend plus GUI.

## Solution

Run a short discovery effort that compares the interface options against actual project workflows:
target-mode configuration, full-training-set chemistry error triage, experiment launch, run progress,
leaderboards, and model comparison.

## User Stories

1. As a modeler, I want to inspect full-dataset chemistry failures, so that I can prioritize fixes.
2. As a modeler, I want to configure target modes, so that experiments match the scientific question.
3. As a reviewer, I want to inspect persisted artifacts, so that results can be reproduced.
4. As a developer, I want interface code to read artifacts rather than own pipeline logic, so that
   interfaces stay thin.
5. As a user, I want a clear path from run configuration to result review, so that the benchmark can
   be operated without spelunking through notebooks.

## Implementation Decisions

- Compare notebook, CLI/report, and GUI/backend options before building a full interface.
- Prefer a thin interface over one that duplicates pipeline rules.
- Ensure the chosen first interface can display full-dataset failure summaries.
- Ensure the chosen first interface can represent target modes and experiment metadata.

## Testing Decisions

- Test any prototype through artifact inputs and rendered/output behavior.
- Avoid tests that depend on internal display details.
- Keep interface discovery separate from core pipeline correctness tests.

## Out Of Scope

- Building the complete final GUI.
- Long-running experiment orchestration.
- Authentication, deployment, or multi-user collaboration.

## Further Notes

The likely first interface may be a notebook-backed report plus CLI artifacts, but the PRD keeps the
decision open until early artifacts exist.
