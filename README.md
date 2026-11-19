# Qiskit Shor

Circuits, experiments and analysis for the bachelor's thesis on Shor's algorithm on IBM Heron r2 QPUs.

## Structure

```
src/circuits/    circuits (compiled Shor circuit for N = 15, Bell states)
src/runner.py    transpiles and runs a circuit, writes one JSON file per run
src/analysis/    figures and tables of the thesis
results/         measured runs, calibration data, figures, tables
```

## Run a circuit

```bash
docker compose build
docker compose run --rm \
  -e BACKEND_MODE=hardware \
  -e BACKEND_NAME=ibm_kingston \
  -e OPTIMISATION_LEVEL=2 \
  qiskit-shor src/circuits/shor15_compiled.py
```

| Variable | Values | Default |
|---|---|---|
| `BACKEND_MODE` | `ideal`, `noisy`, `hardware` | `ideal` |
| `BACKEND_NAME` | `ibm_kingston`, `ibm_fez`, `ibm_marrakesh` | `ibm_kingston` |
| `OPTIMISATION_LEVEL` | `0`–`3` | `1` |

Hardware runs require a `.env` file with `IBM_TOKEN=<token>`.

## Experiments

```bash
./experiment1.sh   # one measurement day: 3 QPUs, levels 0–3, hardware and both simulations
./experiment2.sh   # one measurement day: Kingston, level 2, error suppression and M3
```

Results are written to `results/experiment1/` and `results/experiment2/`.

## Analysis

```bash
docker compose run --rm qiskit-shor src/analysis/experiment1.py
docker compose run --rm qiskit-shor src/analysis/experiment2.py
```

The figures and tables of the thesis are written to the `figures/` and `tables/` folders of each experiment.