# Qiskit Shor

Quantum circuits and experiments for the thesis.

## Run

Build:

```bash
docker compose build
```

Run a circuit on the ideal simulator:

```bash
docker compose run --rm \
  -e BACKEND_MODE=ideal \
  -e OPTIMISATION_LEVEL=1 \
  qiskit-shor src/circuits/bell_state.py
```

Run on an IBM hardware noise model:

```bash
docker compose run --rm \
  -e BACKEND_MODE=noisy \
  -e BACKEND_NAME=ibm_kingston \
  -e OPTIMISATION_LEVEL=1 \
  qiskit-shor src/circuits/shor15_compiled.py
```

Run on IBM hardware (requires `.env` with `IBM_TOKEN=token`):

```bash
docker compose run --rm \
  -e BACKEND_MODE=hardware \
  -e BACKEND_NAME=ibm_kingston \
  -e OPTIMISATION_LEVEL=1 \
  qiskit-shor src/circuits/shor15_compiled.py
```

Parameters:

```
OPTIMISATION_LEVEL   0 | 1 | 2 | 3

BACKEND_MODE         ideal       ideal Aer simulator
                     noisy       noise model based on an IBM fake backend
                     hardware    real IBM quantum hardware

BACKEND_NAME         ibm_kingston | ibm_fez | ibm_marrakesh

RESULT_DIR           where the result file goes, default results/<date>
MITIGATION           experiment 2 only: raw | twirling | dd | both
```

## Batch runs

One measurement day of experiment 1, one container per run: on all three
devices at optimisation levels 0–3, 5 hardware runs and 5 noise model runs
each, plus 1 ideal run per level as reference.

```bash
./experiment1.sh
```

One measurement day of experiment 2 on one device and optimisation level
(set at the top of the script): 5 hardware runs per configuration (`raw`,
`twirling`, `dd`, `both`, see `MITIGATIONS` in `src/runner.py`) plus 5 noise
model runs of `raw`. Results land in `results/experiment2/runs/<config>/`.

```bash
./experiment2.sh
```

Readout mitigation is post-processing with [mthree](https://github.com/Qiskit/qiskit-addon-mthree):
`src/m3_calibrate.py` calibrates the measured qubits once per day and writes
`results/experiment2/runs/m3_cals_<mode>_<device>_<date>.json`,
`src/m3_correct.py` adds `results.quasi_probabilities` to every run of `raw`
and `both`. The counts stay as they are.

## Analysis

`src/analysis/experiment1.py` reads the result files in `results/experiment1/runs/<date>/` and
writes the figures and tables of the thesis to `results/experiment1/`.
`src/analysis/plot.py` holds the shared helpers (style, table writer, save).

```bash
docker compose run --rm qiskit-shor src/analysis/experiment1.py
```

Every output has its own function with the same three steps: collect the
values from the runs, calculate, write.

| Function | File | Thesis label |
|---|---|---|
| `table_transpiled` | `tables/transpiled.tex` | `tab:exp1_transpiled` |
| `figure_outcomes` | `figures/outcomes.pdf` | `fig:exp1_outcomes` |
| `figure_error_budget` | `figures/error_budget.pdf` | `fig:exp1_error_budget` |
| `figure_distribution` (one day) | `figures/distribution.pdf` | `fig:exp1_distribution` |
| `figure_distribution` (all days) | `figures/distribution_all_days.pdf` | `fig:exp1_distribution_days` |
| `table_share_per_day` | `tables/share_per_day.tex` | `tab:exp1_share_per_day` |
| `table_calibration` | `tables/calibration.tex` | `tab:exp1_calibration` |
