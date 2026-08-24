# Benchmark Contract

PRD 01 defines the typed configuration contract that later benchmark work should use for targets,
source data, and run manifests. The implementation lives in
`supervised_learning_polymers.targets` and `supervised_learning_polymers.manifest`.

## Target Modes

The target contract is represented by `TargetConfig`. It contains target metadata, optional named
groups, and one selected target mode.

Supported modes:

- `single`: model exactly one known target, such as `FFV`.
- `group`: model one named group of one or more known targets, such as `thermal = [Tg, Tc]`.
- `all`: model all configured targets in metadata order.
- `sequential`: model an explicit ordered dependency chain.

The initial Open Polymer target order is:

```text
Tg, FFV, Tc, Density, Rg
```

The initial sequential proof-of-concept order is:

```text
FFV -> Density -> Tc -> Tg -> Rg
```

Named groups may overlap with one another, but a single group cannot contain the same target more
than once. For example, `thermal = [Tg, Tc]` and
`sequential_poc = [FFV, Density, Tc, Tg, Rg]` may both include `Tc`.

## Target Metadata

Each target has:

- `name`: target column name.
- `unit`: reporting unit.
- `valid_range`: optional permissive numeric range metadata.
- `missing_value_policy`: currently `preserve`.
- `transform`: optional per-target transform name.

Target groups inherit each target's own metadata. Groups do not define transform defaults.

Open Polymer units:

| Target | Unit |
| --- | --- |
| `Tg` | deg C |
| `FFV` | dimensionless |
| `Tc` | W/(m*K) |
| `Density` | g/cm^3 |
| `Rg` | Angstrom |

Ranges are intentionally permissive. Hidden/evaluation distributions may differ from training data,
so train-set minima and maxima should be treated as profiling information, not hard validation
bounds. Missing target cells are unknown labels, not zeros or imputed values.

## Sequential Leakage Rules

Sequential prediction may use upstream predicted properties as downstream features only when the
prediction source is explicit and leakage-safe.

`SequentialTargetMode` requires:

- an ordered target chain with at least two known targets;
- no duplicate target names;
- `prediction_source.training = out_of_fold_predictions`;
- `prediction_source.validation = upstream_model_predictions`;
- `prediction_source.test = upstream_model_predictions`.

Validation and test rows must never consume true labels as predicted-property features. Training rows
use out-of-fold predictions so a downstream model does not see upstream predictions made by a model
trained on the same row.

Later search infrastructure can treat the sequential order as a manual setting or as a grid, random,
or Bayesian hyperparameter.

## Dataset Contract

`DatasetConfig` records source-data identity and schema before chemistry or features are derived.

Stable fields:

- `dataset_version`: source dataset identity.
- `sample_id_column`: source sample ID column, defaulting to `id` when present.
- `missing_sample_id_strategy`: `error` or `split_row_index`.
- `smiles_column`: molecular input column, defaulting to `SMILES`.
- `target_columns`: source target columns.
- `grouping_columns`: optional source grouping columns.

For train data, use `id` as the sample ID column. For public/private test split files without an
explicit sample ID, generate deterministic IDs from `split + row_index`.

Sample IDs, SMILES, target columns, and grouping columns are intentionally separate. Dataset
validation rejects duplicate target/grouping columns and rejects sample IDs that reuse SMILES,
target, or grouping columns.

## Manifest Contract

`BenchmarkManifest` is the first single typed manifest object for this project. It embeds the source
dataset config and selected target config, and it references future component configs by stable
identity.

Required manifest fields:

- `manifest_version`
- `dataset`
- `target`
- `chemistry`
- `representation`
- `split`
- `model`
- `reporting`

The component fields use `ConfigReference(config_id=...)`. They name future configuration/artifact
families without implementing those systems yet.

Manifest validation requires:

- every component identity to be present;
- target metadata names to exist in `dataset.target_columns`;
- derived component identities to be separate from `dataset.dataset_version`.

This keeps source data identity separate from derived chemistry, representation, split, model, and
reporting artifacts.

## Downstream Dependencies

Later PRDs should depend on the contract as follows:

- Chemistry code should read `DatasetConfig.smiles_column`, preserve `dataset_version`, and write
  derived artifacts under a distinct chemistry config identity.
- Representation code should consume validated chemistry artifacts and write descriptors,
  fingerprints, graphs, or geometry features under a representation config identity.
- Split code should use stable sample IDs and optional grouping columns, then write split artifacts
  under a split config identity.
- Model code should consume `TargetConfig.resolve_targets()` and target metadata, including
  missing-value and transform policy.
- Reporting code should use target units and manifest component identities for traceable tables,
  plots, and comparisons.

Fixture-sized examples live in `tests/fixtures/benchmark_contract_cases.json` and are validated by
the default pytest suite.

## Interface Discovery Fixtures

PRD 02 discovery prototypes should read small committed artifact fixtures instead of inventing
display data or duplicating benchmark rules. The initial fixture bundle lives in
`tests/fixtures/interface_discovery_run.json` and validates through
`load_interface_discovery_artifact`.

The fixture bundle includes:

- a `BenchmarkManifest` using the PRD 01 contract;
- a display-ready target-mode summary;
- a chemistry-failure summary shaped for triage before the full chemistry audit exists;
- experiment metadata, run status, progress steps, and artifact paths;
- result metrics, leaderboard rows, and notes for review surfaces.

The first generated-report and GUI paths are documented in
[Interface Discovery CLI Report](interface-discovery-cli-report.md),
[Interface Discovery Notebook Report](interface-discovery-notebook-report.md), and
[Interface Discovery GUI Backend](interface-discovery-gui-backend.md).

The PRD 02 decision record selects the GUI/backend path and records weighted-MAE display/filtering as
required follow-up before final review. The interface fixture records weighted-MAE values and
weighting metadata as persisted artifact fields; benchmark metric computation remains an evaluation
layer responsibility.
