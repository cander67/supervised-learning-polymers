# Interface Discovery GUI Backend

Phase 5 adds a thin local backend plus static GUI prototype for PRD 02 discovery. It serves the
committed fixture artifact, then lets reviewers inspect target mode, provenance, chemistry failures,
run progress, metrics, and leaderboard data in a browser.

After user review, this is the selected first-interface direction for the project. The GUI/backend
should evolve into an organized artifact viewer and search tool as experiment, model, metric, and
test artifacts grow in volume.

PRD 13 extends this direction with a structure validation workbench. That page should remain
artifact-driven and expose coordinated panels for SMILES, 2D depiction, 3D conformer review, and
2D/3D graph rendering rather than duplicating chemistry or modeling logic inside the browser.

Start the prototype with:

```bash
slp-interface-gui tests/fixtures/interface_discovery_run.json --port 8765
```

Then open `http://127.0.0.1:8765`.

Backend endpoints:

- `GET /api/health`: server health check.
- `GET /api/artifact`: validated `InterfaceDiscoveryArtifact` JSON.
- `GET /api/structure-failures`: normalized chemistry and geometry failure triage groups and
  examples loaded from `failures.json` where available.
- `GET /api/structures`: searchable structure summaries, with optional `query` and `status`
  parameters.
- `GET /api/structures/<sample-id>`: selected structure detail payload with SMILES, 2D, 3D,
  chemistry, geometry, and provenance states.
- `GET /api/structures/<sample-id>/depiction.svg`: on-demand RDKit 2D SVG depiction for valid
  chemistry records.
- `GET /api/structures/<sample-id>/geometry.sdf`: persisted SDF conformer payload for successful
  geometry records.
- `GET /api/structures/<sample-id>/graph.json`: selected graph node/edge JSON when graph artifacts
  are available for the sample.
- `GET /`, `/app.js`, `/styles.css`: static GUI assets.

## Chemistry Artifacts

The interface fixture's `chemistry_failure_summary` now validates through the PRD 3
`ChemistryAuditSummary` contract. The browser-facing JSON still uses the same total, valid, failed,
and failure-group fields, but the failure taxonomy is the chemistry audit taxonomy:
`missing_smiles`, `parse_error`, `standardization_error`, `capping_error`, and
`unsupported_polymer_notation`.

When real chemistry audit outputs are available, `run_metadata.artifact_paths` should point at the
PRD 3 bundle under `artifacts/chemistry/<config-id>/`, including `records.json`, `failures.json`,
`summary.json`, and `metadata.json`.

## Geometry Artifacts

The interface fixture can now include `geometry_summary`, validated through the PRD 4
`GeometrySummary` contract. The backend exposes geometry totals, successful and failed attempt
counts, coverage, runtime, and representative failure groups from the artifact JSON.

When real geometry outputs are available, `run_metadata.artifact_paths` should point at the PRD 4
bundle under `artifacts/geometry/<geometry-config-id>/`, including `records.json`, `failures.json`,
`summary.json`, and `metadata.json`. The current GUI displays only aggregate feasibility and failure
summary fields; PRD 13 should consume the same artifact identities when it adds molecule-level
SMILES, 2D, and 3D structure review panels.

## Structure Viewer

PRD 13 adds a structure browser inside the same local GUI shell. It consumes chemistry
`records.json` and geometry `records.json` through `run_metadata.artifact_paths`, joins records by
`sample_id`, and keeps each panel artifact-driven:

- SMILES: raw, canonical, standardized, capped, selected geometry input, and attachment points.
- 2D: on-demand RDKit SVG from the selected validated SMILES representation.
- 3D: persisted SDF text from PRD 4 geometry artifacts.
- Graph: project-owned node/edge JSON with optional 2D and 3D coordinates.

Geometry status semantics are visible per selected sample:

- `success`: a conformer attempt succeeded and SDF text is available.
- `failed`: a conformer attempt ran and produced structured failure provenance.
- `not_generated`: chemistry is valid, but no geometry record exists for the sample.
- `artifact_missing`: the referenced geometry records artifact cannot be resolved.
- `chemistry_failed`: upstream chemistry failed before geometry review was possible.

The failure triage panel starts from aggregate chemistry and geometry failure groups, then opens
representative examples from `failures.json`. Examples include raw, canonical, standardized, capped,
and selected geometry-input SMILES when artifact data exists. Geometry examples also include method,
stage, runtime, recommended action, and fallback provenance. A triage example can be marked
`failure file only` when it is available in `failures.json` but does not have a loaded joined
structure record, which keeps large-run failure inspection distinct from the current paged/searchable
structure list.

The triage pattern guide keeps the PRD 04 full-run failure taxonomy visible: embedding failures,
parse errors, optimization failures, unsupported wildcard atoms, and method-unavailable failures are
displayed as distinct categories when present. The viewer does not implement retry policy, fallback
backend execution, chemistry correction workflows, molecule-size bins, or coverage-bias modeling.

Graph records are optional. When available, `run_metadata.artifact_paths.graph_records` points at a
JSON list keyed by `sample_id`. Each graph record contains:

- `sample_id`, source `smiles`, and `graph_config_id`.
- `coordinate_modes`, currently `2d` and/or `3d`.
- `nodes` keyed by stable `atom_index`, with `element`, optional `coordinates_2d`,
  optional `coordinates_3d`, and feature dictionaries.
- `edges` keyed by source/target atom indices, with `bond_order` and feature dictionaries.
- `missing_features` for feature families intentionally absent from a pre-PRD09 graph artifact.

The committed PRD 13 fixture graph uses sample `1125785790` and the selected 35-heavy-atom polymer
SMILES from the implementation plan. RDKit reports 37 graph nodes because the persisted viewer graph
keeps the two wildcard attachment atoms as explicit nodes. PRD 09 should preserve stable atom
indices, node/edge feature dictionaries, and optional 2D/3D coordinate fields so this viewer can
consume production graph artifacts without changing the panel contract.

The 3D panel uses a vendored 3Dmol.js browser build:

- Package: `3dmol`
- Version: `2.5.5`
- Source: `https://unpkg.com/3dmol@2.5.5/build/3Dmol-min.js`
- Vendored path: `src/supervised_learning_polymers/static/interface_gui/vendor/3dmol/3Dmol-min.js`
- SHA-256: `f7cc78921ae72e7623e89cdd111434f58c2efddd2ffda1cd212644b406fb8016`
- License files: `vendor/3dmol/LICENSE` and `vendor/3dmol/3Dmol-min.js.LICENSE.txt`

The checksum is pinned in the backend/static tests so accidental vendored-file changes are visible
during the default test suite.

## Tradeoffs

- **Maintainability**: The backend is a small artifact adapter built on Python's standard library.
  It does not introduce a database, frontend build system, or pipeline-specific rules.
- **User fit**: The static GUI is more approachable than notebook or CLI output for collaborators
  who need to review artifacts, filter chemistry failures, and scan leaderboards.
- **Future integration**: The prototype can point at later chemistry, split, model, and reporting
  artifacts if their JSON shapes remain compatible with `InterfaceDiscoveryArtifact` or an evolved
  successor contract.
- **Structure review**: The GUI should eventually let chemistry-proficient users inspect every
  SMILES-derived representation encountered in the project, including conformer attempts for
  records used by non-geometry-aware models.
- **Metric review**: The GUI should support filtering or toggling between ordinary MAE and the Open
  Polymer weighted-MAE competition metric once metric artifacts include both values and the
  associated weighting metadata. The Phase 7 prototype reads these metric values, target weights,
  ranges, and available-label counts from persisted fixture artifacts; it does not compute wMAE in
  the browser or backend.
- **Limits**: The prototype is not a long-running experiment orchestrator, authentication layer, or
  production web app. Phase 6 should decide whether to keep this path, replace it with a richer app
  stack, or retain it only as a local review utility.
