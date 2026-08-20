# Public Interface Discovery Criteria

This document defines the Phase 1 rubric for PRD 02, Public Interface Discovery. It compares four
candidate first-interface directions against the benchmark workflows that must eventually become
easy to operate without duplicating pipeline logic.

Candidate interface directions:

- **Notebook report**: a Jupyter notebook that reads persisted artifacts and renders the review
  workflow for analysts and developers.
- **CLI/generated report**: a command-line path that reads artifacts and emits reviewable Markdown,
  JSON, or terminal output.
- **Static GUI**: a local static application that reads exported artifact files.
- **Thin backend plus GUI**: a local backend serving persisted artifacts to a focused browser UI.

## Scoring

Each candidate should be scored from 1 to 5 for every criterion:

- **1**: Poor fit; high risk or major workflow gaps.
- **2**: Weak fit; possible with awkward process or duplicated rules.
- **3**: Adequate fit; usable for a narrow version of the workflow.
- **4**: Strong fit; handles the workflow cleanly with modest tradeoffs.
- **5**: Excellent fit; clear, maintainable, and likely to scale with later PRD artifacts.

Scores are discovery evidence, not final architecture by themselves. The recommendation should also
record implementation complexity, risks, and what prototype code is worth keeping.

## Criteria

| Criterion | What To Evaluate |
| --- | --- |
| Full-dataset chemistry failure triage | Can the interface display full-training-set parse, validation, standardization, and capping failures with enough grouping, filtering, and provenance for a modeler to prioritize fixes? |
| Target-mode configuration and review | Can it represent single-target, target-group, all-target, and sequential target modes using the PRD 01 target contract without reimplementing target rules? |
| Artifact reproducibility | Does it read persisted manifests, configs, metrics, predictions, and reports as the source of truth, preserving artifact identity and reviewability? |
| Experiment launch fit | Can it guide a user from selected dataset, target mode, representation, split, and model configuration to a launchable run shape, even if long-running orchestration remains out of scope? |
| Run progress visibility | Can it show run status, step progress, warnings, failures, and artifact locations in a way that supports repeated monitoring? |
| Leaderboard review | Can it compare completed runs by target, metric, split, model family, and artifact identity without hiding missing or failed results? |
| Model comparison | Can it support side-by-side model interpretation, tradeoffs, applicability notes, and future model-card links? |
| Thin artifact-driven boundary | Does the interface stay thin by consuming artifacts and shared config contracts rather than owning chemistry, split, model, target-mode, or reporting logic? |
| Non-notebook and non-CLI usability | Is it usable by reviewers and collaborators who are not comfortable editing notebooks or reading CLI-only output? |
| Maintenance and extensibility | Can it evolve as later PRDs add chemistry audits, split artifacts, baseline runs, search, graph models, geometry, and final scientific comparisons? |

## Local Data Assumptions

Committed tests and prototype behavior should use tiny fixture artifacts. Local source-data checks
may be run during discovery to understand realistic row counts, missingness patterns, failure
volume, and artifact scale, but those observations must be documented separately from fixture-backed
behavior and must not become required for the default test suite.
