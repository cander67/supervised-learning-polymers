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

## Quick Start

### Smoke Test

For a deterministic check of your setup, you can launch the committed artifact viewer with:

```bash
slp-interface-gui tests/fixtures/interface_discovery_run.json --port 8765
```

Then open `http://127.0.0.1:8765` in your web browser.

### Structure Viewer and Workbench

Once the smoke test has passed, you can begin inspecting the input data and explore capping strategies by using the structure viewer and workbench.

First, create the necessary local data directories if they do not already exist and add your data files:

```bash
mkdir -p data/train data/test
```

Next, create the necessary local chemistry and geometry artifact directories if they do not already exist:

```bash
mkdir -p artifacts/chemistry artifacts/geometry
```

Then perform a chemistry audit and generate the corresponding geometry artifacts with:

```bash
slp-chemistry-audit data/train/train.csv \
  --output-root artifacts \
  --dataset-version open-polymer-train-v1 \
  --chemistry-config-id chemistry-audit-hydrogen \
  --capping-strategy hydrogen
```

and:

```bash
slp-geometry-feasibility artifacts/chemistry/chemistry-audit-hydrogen \
  --output-root artifacts \
  --geometry-config-id geometry-rdkit-hydrogen \
  --input-representation capped_smiles
```

Then launch the artifact viewer and structure workbench against existing local chemistry and
geometry artifacts with:

```bash
slp-structure-viewer \
  --chemistry-artifact artifacts/chemistry/chemistry-audit-hydrogen \
  --geometry-artifact artifacts/geometry/geometry-rdkit-hydrogen \
  --port 8765
```

Then open `http://127.0.0.1:8765` in your web browser.

## License

MIT — see [LICENSE](LICENSE).
