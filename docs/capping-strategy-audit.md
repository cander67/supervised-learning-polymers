# Capping Strategy Audit

This audit compares uncapped, hydrogen-capped, and carbon-capped chemistry inputs on the full
`open-polymer-train-v1` training set. All 7,973 source records contain wildcard attachment points.
Each geometry run used RDKit `2026.03.3`, `rdkit_etkdg_mmff`, `capped_smiles` input, 20 embedding
attempts, seed `61453`, 200 MMFF optimization iterations, and no fallback methods.

| Strategy | Chemistry valid | Chemistry failures | Geometry successes | Geometry failures | Geometry coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| Uncapped | 7,973 / 7,973 | 0 | 7,180 | 793 | 90.05% |
| Hydrogen capped | 7,953 / 7,973 | 20 | 7,354 | 599 | 92.47% |
| Carbon capped | 7,973 / 7,973 | 0 | 7,169 | 804 | 89.92% |

## Outcome

Hydrogen capping gives the best downstream RDKit geometry coverage, despite losing 20 records during
chemistry capping. It removes wildcard atoms from successful chemistry records and reduces geometry
failures by 194 relative to the uncapped control.

Uncapped chemistry is the safest audit control because it preserves every row and leaves wildcard
attachment points untouched. Its geometry run is less clean: all geometry failures are embedding
failures, including 631 normal ETKDG `status -1` failures and 162 RDKit bounds-matrix invariant
violations. This makes uncapped useful as provenance, but weaker as the default geometry input.

Carbon capping preserves all 7,973 chemistry records and removes wildcard atoms, but it has the
lowest geometry coverage. Its 804 geometry failures are ordinary ETKDG `status -1` failures, so the
strategy avoids the uncapped invariant failure mode but appears to make more molecules difficult for
RDKit embedding.

## Next Steps

Keep `uncapped` as the chemistry provenance control. Use hydrogen capping as the preferred current
geometry-input candidate when a capped representation is needed. Keep carbon capping opt-in until
model or geometry validation shows that its terminal-carbon approximation improves downstream
behavior despite lower RDKit conformer coverage.