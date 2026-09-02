# supervised-learning-polymers

Evaluation of supervised learning models trained on data from the [Open Polymer Prediction](https://www.kaggle.com/competitions/neurips-open-polymer-prediction-2025) dataset. Includes optimization strategies, model evaluation, and performance benchmarking for different supervised learning approaches on polymer datasets.

Reliable models can be deployed for predicting polymer properties, aiding in material design and product development by providing accurate predictions based on supervised learning models trained on polymer datasets.

## Documentation

- Current status: PRDs 01, 02, 03, 04, and 13 are accepted. No PRD is active while the structure
  workbench gets a user-testing round before the next implementation PRD is selected.
- [Project backlog](docs/backlog.md)
- [Benchmark contract](docs/benchmark-contract.md)
- [Chemistry audit](docs/chemistry-audit.md)
- [Geometry groundwork](docs/geometry-groundwork.md)
- [Interface discovery GUI backend](docs/interface-discovery-gui-backend.md)
- [Public interface discovery decision](docs/interface-discovery-decision.md)
- [Public interface discovery criteria](docs/interface-discovery-criteria.md)
- [Target properties](docs/target-properties.md)

## Local GUI

Launch the artifact viewer and PRD 13 structure workbench against existing local chemistry and
geometry artifacts with:

```bash
slp-structure-viewer \
  --chemistry-artifact artifacts/chemistry/chemistry-audit-v1 \
  --geometry-artifact artifacts/geometry/geometry-rdkit-v1 \
  --port 8765
```

Then open `http://127.0.0.1:8765`.

For deterministic fixture review, launch the committed interface artifact with:

```bash
slp-interface-gui tests/fixtures/interface_discovery_run.json --port 8765
```

## License

MIT — see [LICENSE](LICENSE).
