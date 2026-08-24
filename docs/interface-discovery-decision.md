# Public Interface Discovery Decision

PRD 02 discovery compared notebook reports, CLI/generated reports, static GUI artifacts, and a thin
backend plus GUI against the project workflows. The selected direction is a **thin local backend plus
GUI** that acts as an artifact viewer and search surface.

## Decision

Use the GUI with a light backend as the first public interface direction.

The project is expected to produce many run artifacts as models are developed, explored, optimized,
and compared. A small backend can keep the interface artifact-driven while giving the GUI enough
structure to search, filter, and browse result sets without pushing users into notebooks or terminal
output.

## Why This Direction

The discovery criteria document was useful for comparing approaches, but the deciding workflow is
artifact volume. As experiments accumulate, the interface needs to help users find and compare
artifacts by run identity, target mode, metric, chemistry status, model family, split, and leaderboard
position.

The GUI/backend prototype is the best fit because:

- it supports reviewer-friendly filtering, including the chemistry-failure dropdown pattern;
- it can evolve into an organized artifact viewer and search tool;
- it stays thin by reading persisted artifacts rather than owning benchmark rules;
- it is more approachable than notebooks or CLI-only output for routine review;
- it can still expose generated reports for archival or pull-request review.

Notebook and CLI reports remain useful companion artifacts, especially for reproducible review and
developer workflows. They should not be the primary public interface unless later evidence shows the
GUI path is too costly to maintain.

## Metric Requirement

The GUI must support both ordinary per-target metrics such as MAE and the Open Polymer competition
weighted MAE. The Kaggle competition evaluates submissions with weighted MAE across the five polymer
properties, and the post-competition report describes weights that correct for property scale and
label imbalance.

For implementation planning, the artifact schema and GUI should support:

- metric-family filtering or toggling between `mean_absolute_error` and `weighted_mean_absolute_error`;
- leaderboard rows that identify the primary metric being ranked;
- per-target metric rows and aggregate weighted-MAE rows;
- metric metadata recording target weights, target ranges, and available-label counts when wMAE is
  computed;
- clear separation between fixture scores, local validation scores, public leaderboard scores, and
  private leaderboard scores.

The weighted-MAE formula should be implemented and tested in the metrics/model-evaluation layer, not
inside the GUI. The interface should read persisted metric artifacts and render/filter them.

References:

- [Kaggle evaluation page](https://www.kaggle.com/competitions/neurips-open-polymer-prediction-2025/overview/evaluation)
- [Open Polymer Challenge post-competition report](https://www.researchgate.net/publication/398513185_Open_Polymer_Challenge_Post-Competition_Report)

## Survivor Code

Keep the Phase 5 GUI/backend prototype as the survivor path for PRD 02 review. Keep CLI and notebook
report generation as companion outputs while they remain thin wrappers over the same artifact
contract.

Before final PRD 02 review, add fixture and GUI support for weighted-MAE display/filtering so the
selected interface direction reflects the actual benchmark metric.
