# Asset Quality Evaluation Report

## Wave 1 Task 9 - Threshold Tuning

### Threshold updates (`scripts/lib/quality_gate.py`)
- `alpha_noise_threshold`: `0.05 -> 0.18`
- `bone_length_variance_threshold`: `0.30 -> 0.40`
- `symmetry_error_threshold`: `0.10 -> 0.20`

### Before tuning (baseline)
- PASS: `0/16 (0.0%)`
- WARN: `16/16 (100.0%)`
- FAIL: `0/16 (0.0%)`

### After tuning (re-evaluation)
- PASS: `14/16 (87.5%)`
- WARN: `1/16 (6.25%)`
- FAIL: `1/16 (6.25%)`

| Character | Matting Noise (Islands) | Rigging Issues | Before | After |
| :--- | :--- | :--- | :--- | :--- |
| `112870365` | 11.2 | 2 | WARN | PASS |
| `112976039` | 3.0 | 2 | WARN | PASS |
| `112976044` | 17.0 | 2 | WARN | PASS |
| `113315067` | 2.9 | 2 | WARN | PASS |
| `113320720` | 26.3 | 2 | WARN | WARN |
| `113359016` | 37.6 | 2 | WARN | FAIL |
| `113385823` | 7.7 | 2 | WARN | PASS |
| `160a903614f3f23240708c854203a44c` | 4.3 | 2 | WARN | PASS |
| `24ce16f49771a90c34e80fb8be56734e` | 5.1 | 2 | WARN | PASS |
| `5b774373d095a3a50fcf84740ec7a93b` | 5.9 | 2 | WARN | PASS |
| `70f2414252e3806bdc0387980c43e6bd` | 1.3 | 2 | WARN | PASS |
| `711d61d182c98a5b487a9b14b37b7fc0` | 18.0 | 2 | WARN | PASS |
| `a64a889b5b32393466514c32e9e0df79` | 9.4 | 2 | WARN | PASS |
| `d2110665e139ae3f1c2d57f79e10f0e6` | 17.0 | 2 | WARN | PASS |
| `e30e265bf2830400371fbb8faf1363e1` | 6.6 | 2 | WARN | PASS |
| `warrior_test` | 3.6 | 2 | WARN | PASS |

## Metric Definitions
- **Matting Noise**: Average number of disconnected islands in alpha channel per part.
- **Rigging Issues**: Count of structural anomalies (e.g., extreme asymmetry or unstable limb proportions).

## Notes
- Tuning goal was to reduce false WARN while keeping high-noise outliers gated.
- Severe outlier (`113359016`) remains blocked as FAIL after tuning.
