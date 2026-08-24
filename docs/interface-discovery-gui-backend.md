# Interface Discovery GUI Backend

Phase 5 adds a thin local backend plus static GUI prototype for PRD 02 discovery. It serves the same
committed fixture artifact used by the CLI and notebook reports, then lets reviewers inspect target
mode, provenance, chemistry failures, run progress, metrics, and leaderboard data in a browser.

After user review, this is the selected first-interface direction for the project. The GUI/backend
should evolve into an organized artifact viewer and search tool as experiment, model, metric, and
test artifacts grow in volume.

Start the prototype with:

```bash
slp-interface-gui tests/fixtures/interface_discovery_run.json --port 8765
```

Then open `http://127.0.0.1:8765`.

Backend endpoints:

- `GET /api/health`: server health check.
- `GET /api/artifact`: validated `InterfaceDiscoveryArtifact` JSON.
- `GET /api/report`: Markdown report rendered by the shared CLI/report path.
- `GET /`, `/app.js`, `/styles.css`: static GUI assets.

## Tradeoffs

- **Maintainability**: The backend is a small artifact adapter built on Python's standard library.
  It does not introduce a database, frontend build system, or pipeline-specific rules.
- **User fit**: The static GUI is more approachable than notebook or CLI output for collaborators
  who need to review artifacts, filter chemistry failures, and scan leaderboards.
- **Future integration**: The prototype can point at later chemistry, split, model, and reporting
  artifacts if their JSON shapes remain compatible with `InterfaceDiscoveryArtifact` or an evolved
  successor contract.
- **Metric review**: The GUI should support filtering or toggling between ordinary MAE and the Open
  Polymer weighted-MAE competition metric once metric artifacts include both values and the
  associated weighting metadata.
- **Limits**: The prototype is not a long-running experiment orchestrator, authentication layer, or
  production web app. Phase 6 should decide whether to keep this path, replace it with a richer app
  stack, or retain it only as a local review utility.
