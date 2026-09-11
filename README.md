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
  qiskit-shor src/bell_state.py

docker compose run --rm \
  -e BACKEND_MODE=ideal \
  -e OPTIMIZATION_LEVEL=1 \
  qiskit-shor src/shor15_general.py

docker compose run --rm \
  -e BACKEND_MODE=ideal \
  -e OPTIMIZATION_LEVEL=1 \
  qiskit-shor src/shor15_compiled.py
```

Run on an IBM hardware noise model:

```bash
docker compose run --rm \
  -e BACKEND_MODE=noisy \
  -e BACKEND_NAME=ibm_kingston \
  -e OPTIMIZATION_LEVEL=1 \
  qiskit-shor src/shor15_general.py
```

Run on IBM hardware (requires `.env` with `IBM_TOKEN=token`):

```bash
docker compose run --rm \
  -e BACKEND_MODE=hardware \
  -e BACKEND_NAME=ibm_kingston \
  -e OPTIMIZATION_LEVEL=1 \
  qiskit-shor src/shor15_general.py
```

OPTIMIZATION_LEVEL can be set to values from 0 to 3:
```bash
-e OPTIMIZATION_LEVEL=0
-e OPTIMIZATION_LEVEL=1
-e OPTIMIZATION_LEVEL=2
-e OPTIMIZATION_LEVEL=3
```

Available backend modes:

* `ideal` - ideal Aer simulator
* `noisy` - noise model based on an IBM fake backend
* `hardware` - real IBM quantum hardware

Available fake backends:

* `ibm_kingston`
* `ibm_fez`
* `ibm_marrakesh`
