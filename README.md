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
```

## Batch runs

Run on hardware with its noise model for optimisation levels 0–3
(5 runs each, plus 1 ideal run as reference), one container per run.
Set the backend at the top of the script.

```bash
./experiment.sh
```

Results land in `results/<date>/`

## Analysis

Experiment 1 consists of several days, one run of `experiment.sh` per day, each
with its own calibration of the devices. List the result folders of these
days in `RESULT_DAYS` in `src/analysis/experiment1/calculations.py`, which
loads the runs and computes every number; `outputs.py` turns them into the
figures and tables.

Figures and LaTeX tables are written to `results/experiment1/figures` and
`results/experiment1/tables`:

```bash
docker compose run --rm qiskit-shor src/analysis/experiment1/outputs.py
```
