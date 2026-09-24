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
  -e OPTIMIZATION_LEVEL=1 \
  qiskit-shor src/circuits/bell_state.py
```

Run on an IBM hardware noise model:

```bash
docker compose run --rm \
  -e BACKEND_MODE=noisy \
  -e BACKEND_NAME=ibm_kingston \
  -e OPTIMIZATION_LEVEL=1 \
  qiskit-shor src/circuits/shor15_compiled.py
```

Run on IBM hardware (requires `.env` with `IBM_TOKEN=token`):

```bash
docker compose run --rm \
  -e BACKEND_MODE=hardware \
  -e BACKEND_NAME=ibm_kingston \
  -e OPTIMIZATION_LEVEL=1 \
  qiskit-shor src/circuits/shor15_compiled.py
```

Parameters:

```
OPTIMIZATION_LEVEL   0 | 1 | 2 | 3

BACKEND_MODE         ideal       ideal Aer simulator
                     noisy       noise model based on an IBM fake backend
                     hardware    real IBM quantum hardware

BACKEND_NAME         ibm_kingston | ibm_fez | ibm_marrakesh
```

## Batch runs

Run on hardware with its noise model for optimization levels 0–3
(5 runs each, plus 1 ideal run as reference), one container per run.
Set the backend at the top of the script.

```bash
./experiment.sh
```

Results land in `results/<date>/`

## Analysis

Figures and LaTeX tables are written to `src/analysis/experiment1/`:

```bash
docker compose run --rm qiskit-shor src/analysis/experiment1/figures.py
docker compose run --rm qiskit-shor src/analysis/experiment1/tables.py
```
