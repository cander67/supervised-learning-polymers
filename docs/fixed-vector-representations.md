# Fixed-Vector Representations

Fixed-vector representation artifacts are generated from persisted chemistry audit artifacts. They
do not reparse raw CSV files and they do not fit model-time preprocessing. The output is a versioned
bundle of descriptor and fingerprint matrices, sample IDs, feature metadata, hashes, summaries, and
representation failures.

## Generate Artifacts

The default command reads a chemistry artifact directory, uses `capped_smiles`, and generates both
initial fixed-vector feature sets:

```bash
slp-representations artifacts/chemistry/chemistry-audit-hydrogen \
  --output-root artifacts \
  --representation-config-id fixed-vector-hydrogen
```

The command also accepts a direct `records.json` path:

```bash
slp-representations artifacts/chemistry/chemistry-audit-hydrogen/records.json \
  --output-root artifacts \
  --representation-config-id fixed-vector-hydrogen
```

By default, outputs are written under:

```text
artifacts/representations/<representation-config-id>/
```

The command processes only chemistry records with `status = valid`. Invalid upstream chemistry
records remain chemistry failures and are reported as `skipped_chemistry_failed` in the command
output and `skipped_upstream_chemistry_records` in the representation summary.

## Input Representation

Use the default `capped_smiles` input for normal fixed-vector generation:

```bash
slp-representations artifacts/chemistry/chemistry-audit-hydrogen \
  --representation-config-id fixed-vector-hydrogen \
  --input-representation capped_smiles
```

Use `standardized_smiles` for uncapped chemistry-review experiments or when comparing endpoint
representation effects:

```bash
slp-representations artifacts/chemistry/chemistry-audit-hydrogen \
  --representation-config-id fixed-vector-standardized \
  --input-representation standardized_smiles
```

The selected input representation is recorded in every feature-set config, per-sample attempt, and
feature metadata sidecar.

## Feature Sets

The initial feature sets are:

- `rdkit_2d`: RDKit named molecular descriptors from `rdkit.Chem.Descriptors`.
- `morgan_radius2_2048_chiral`: Morgan-style fingerprints using radius 2, 2048 dimensions,
  chirality enabled, and bit mode by default.

Generate descriptors only:

```bash
slp-representations artifacts/chemistry/chemistry-audit-hydrogen \
  --representation-config-id fixed-vector-rdkit-2d \
  --feature-set-ids rdkit_2d
```

Generate fingerprints only:

```bash
slp-representations artifacts/chemistry/chemistry-audit-hydrogen \
  --representation-config-id fixed-vector-morgan \
  --feature-set-ids morgan_radius2_2048_chiral
```

Generate multiple feature sets in one run:

```bash
slp-representations artifacts/chemistry/chemistry-audit-hydrogen \
  --representation-config-id fixed-vector-hydrogen \
  --feature-set-ids rdkit_2d,morgan_radius2_2048_chiral
```

Morgan settings can be changed explicitly:

```bash
slp-representations artifacts/chemistry/chemistry-audit-hydrogen \
  --representation-config-id fixed-vector-morgan-count \
  --feature-set-ids morgan_radius2_2048_chiral \
  --morgan-radius 2 \
  --morgan-size 2048 \
  --morgan-mode count \
  --no-morgan-chirality
```

The feature-set ID stays stable, while the representation cache key changes when settings change.

## Artifact Layout

A generated representation bundle has this layout:

```text
artifacts/representations/<representation-config-id>/
  metadata.json
  summary.json
  failures.json
  records.json
  features/
    <feature-set-id>/
      matrix.npz
      sample_ids.json
      feature_names.json
      metadata.json
```

`matrix.npz` contains a compressed NumPy array named `features`. Rows follow `sample_ids.json`.
Descriptor feature names are RDKit descriptor names. Morgan feature names are deterministic bit
labels such as `bit_0`, `bit_1`, and so on.

Top-level `metadata.json` records:

- dataset version;
- chemistry config ID and chemistry cache key;
- representation config ID and representation cache key;
- RDKit version;
- selected feature-set settings;
- created-at timestamp;
- output paths;
- matrix and feature-name content hashes.

Top-level `summary.json` records total chemistry-valid inputs, attempted feature records,
successful feature records, failed representation records, skipped upstream chemistry records,
dimensions per feature set, and grouped representation failures.

Top-level `failures.json` contains representation failures only. Chemistry failures remain in the
upstream chemistry artifact.

## Downstream Consumption

Downstream split and model workflows should select feature sets by stable feature-set ID and read
the persisted matrix metadata, sample IDs, dimensions, and hashes. They should not recompute
descriptors or fingerprints during split/model runs.

Fold-learned preprocessing is intentionally outside global representation generation. Imputation,
scaling, variance filtering, target-derived transforms, and feature selection belong in split/model
pipelines after frozen splits exist.

## Add A Feature Set

To add another fixed-vector feature set, define and test:

- a stable feature-set ID;
- feature family and version;
- molecular input policy, including supported `capped_smiles` or `standardized_smiles` behavior;
- RDKit or library method identity;
- validated settings;
- expected output shape;
- feature-name policy;
- hash identity fields;
- generator behavior, including sample order, metadata, failures, and deterministic hashes;
- fixture tests for dimensions, determinism, config validation, and failure reporting.

New feature generators should return the same in-memory feature bundle shape used by `rdkit_2d` and
`morgan_radius2_2048_chiral` so persistence and downstream consumers remain feature-set agnostic.
