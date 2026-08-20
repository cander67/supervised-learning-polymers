# Interface Discovery CLI Report

Phase 3 adds a lightweight generated-report path for PRD 02 discovery. It reads the same committed
artifact fixture used by later prototypes and emits a reviewer-friendly Markdown report.

Generate the fixture report with:

```bash
slp-interface-report tests/fixtures/interface_discovery_run.json --output tmp/interface-report.md
```

The command can also print to standard output when `--output` is omitted.

## Tradeoffs

- **Usability**: Markdown output is easy to inspect in pull requests and generated artifacts, but it
  remains less approachable than a GUI for collaborators who do not use terminals.
- **Maintainability**: The report path is thin because it reads `InterfaceDiscoveryArtifact` and
  shared manifest contracts. It does not own chemistry, split, model, target-mode, or reporting
  rules.
- **Extensibility**: The report format can absorb future chemistry audit, run, metric, and
  leaderboard fields as persisted artifacts mature, but richer filtering and repeated monitoring
  will likely need notebook or GUI surfaces.
