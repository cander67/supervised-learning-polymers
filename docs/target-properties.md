# Open Polymer Target Properties

This benchmark predicts five polymer properties from polymer SMILES strings. The competition frames
these labels as molecular-dynamics-derived material properties for multi-task polymer property
prediction, with sparse labels and distribution shift across train, public, and private splits.

Sources:

- Kaggle competition data page:
  <https://www.kaggle.com/competitions/neurips-open-polymer-prediction-2025/data>
- Kaggle competition overview:
  <https://www.kaggle.com/competitions/neurips-open-polymer-prediction-2025/overview>
- Official challenge site:
  <https://open-polymer-challenge.github.io/>
- Post-competition report:
  <https://www.researchgate.net/publication/398513185_Open_Polymer_Challenge_Post-Competition_Report>

## Property Summary

| Column | Property | Unit | Benchmark note |
| --- | --- | --- | --- |
| `Tg` | Glass transition temperature | deg C | Thermal transition point estimated from density-temperature behavior during simulated cooling. |
| `FFV` | Fractional free volume | Dimensionless | Geometric free-volume fraction computed from equilibrated structures. |
| `Tc` | Thermal conductivity | W/(m*K) | Heat-transport property computed from non-equilibrium molecular dynamics. |
| `Density` | Mass density | g/cm^3 | Time-averaged density from equilibrated amorphous polymer simulations. |
| `Rg` | Radius of gyration | Angstrom | Chain-size/conformation measure averaged over equilibrated polymer chains. |

## Modeling Implications

- Labels are sparse by target. In `data/train/train.csv`, non-null counts are currently `Tg`: 511,
  `FFV`: 7030, `Tc`: 737, `Density`: 613, and `Rg`: 614.
- Missing target values are unknown labels, not zeros or imputed values. Config and validation code
  should preserve missingness so later sequential prediction can add predictions without confusing
  predicted values with observed labels.
- Valid ranges should be permissive. The hidden and released evaluation splits may have different
  distributions from the training split, so train-set minima and maxima are useful for data profiling
  but should not be hard validation bounds.
- `FFV` is naturally dimensionless and normally expected between 0 and 1. The initial contract can
  treat non-finite values as invalid while keeping value-range policy configurable.
- `Tg` deserves extra care in reporting because the competition discussion notes generation-method
  and distribution-shift issues around glass-transition estimates.

## Sequential Prediction Context

The initial proof-of-concept sequential target order is:

```text
FFV -> Density -> Tc -> Tg -> Rg
```

This order should be represented explicitly in config. Later search infrastructure should be able to
treat the order as either a user-specified setting or a grid, random, or Bayesian hyperparameter.
