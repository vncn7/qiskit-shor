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

Run on the fixed noise model: the noise model of an IBM fake backend, built from
the calibration snapshot that ships with `qiskit-ibm-runtime`. It is the same on
every day:

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

Run on the daily noise model: the same fake backend, but its calibration is
replaced by the IBM calibration of a measurement day (see `src/fetch_calibration.py`
below). The daily noise model simulates the circuit of the hardware job instead
of transpiling it again, so physical qubits and gates are those of the hardware run:

```bash
docker compose run --rm \
  -e BACKEND_MODE=noisy_day \
  -e BACKEND_NAME=ibm_kingston \
  -e OPTIMISATION_LEVEL=1 \
  -e CALIBRATION_FILE=results/experiment1/calibration/ibm_kingston_20260911.json \
  -e CIRCUIT_FILE=results/experiment1/calibration/ibm_kingston_20260911_opt1.qpy \
  qiskit-shor src/circuits/shor15_compiled.py
```

Parameters:

```
OPTIMISATION_LEVEL   0 | 1 | 2 | 3

BACKEND_MODE         ideal       ideal Aer simulator
                     noisy       fixed noise model of an IBM fake backend
                     noisy_day   daily noise model: fake backend with the IBM calibration of a day
                     hardware    real IBM quantum hardware

BACKEND_NAME         ibm_kingston | ibm_fez | ibm_marrakesh

RESULT_DIR           where the result file goes, default results/<date>
CALIBRATION_FILE     noisy_day only: calibration file of the same device, written by
                     src/fetch_calibration.py
CIRCUIT_FILE         noisy_day only: circuit of the hardware job of the same device
                     and level, written by src/fetch_calibration.py
MITIGATION           experiment 2 only: raw | twirling | dd | both
```

## Batch runs

One measurement day of experiment 1, one container per run: on all three
devices at optimisation levels 0–3, 5 hardware runs, 5 runs on the fixed noise
model and 5 runs on the daily noise model each, plus 1 ideal run per level as
reference.

```bash
./experiment1.sh
```

After the hardware runs the script calls `src/fetch_calibration.py <date>`. It
fetches the IBM calibration (backend properties) of the first hardware job of
every device on that day and writes it, in the format of the properties JSON of
the fake backends, to `results/experiment1/calibration/<device>_<date>.json`.
It also saves the circuit of the first hardware job of every device and level
(transpiled, with its layout) as `<device>_<date>_opt<level>.qpy` next to it.
It requires `IBM_TOKEN` and uses no QPU time. The runs on the daily noise model
(`noisy_day`) load these files. All runs land in `results/experiment1/runs/<date>/`.

The `noisy_day` runs of the five measurement days (2026-09-11, 2026-09-24,
2026-10-12, 2026-10-27, 2026-11-10) were added after the measurement period, on
2026-11-17. Their calibration files were fetched on that day from IBM for the
hardware jobs of the measurement days.

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
`src/analysis/figures.py` writes the estimates figure
(`estimates.pdf`) to `results/other/`.
`src/analysis/plot.py` holds the shared helpers (style, table writer, save).

```bash
docker compose run --rm qiskit-shor src/analysis/experiment1.py
```

Every output has its own function with the same three steps: collect the
values from the runs, calculate, write.

| Function | File | Thesis label |
|---|---|---|
| `table_transpiled` | `tables/transpiled.tex` | `tab:exp1_transpiled` |
| `figure_outcomes` | `figures/exp1_outcomes.pdf` | `fig:exp1_outcomes` |
| `figure_error_budget` | `figures/exp1_error_budget.pdf` | `fig:exp1_error_budget` |
| `figure_distribution` | `figures/exp1_distribution_all_days.pdf` | `fig:exp1_distribution_days` |
| `table_share_per_day` | `tables/share_per_day.tex` | `tab:exp1_share_per_day` |
| `table_calibration` | `tables/calibration.tex` | `tab:exp1_calibration` |
