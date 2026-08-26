# Qiskit Shor

Quantum circuits and experiments for the thesis.

## Run

Build:

```bash
docker build -t qiskit-shor .
```

Run a circuit on the simulator:

```bash
docker run --rm qiskit-shor src/bell_state.py
docker run --rm qiskit-shor src/shor15_general.py
docker run --rm qiskit-shor src/shor15_compiled.py
```

Run on a noise model of IBM hardware:

```bash
docker run --rm -e USE_NOISY=true qiskit-shor src/shor15_general.py
```

Run on IBM hardware (requires `.env` with `IBM_TOKEN=token`):

```bash
docker run --rm -e USE_HARDWARE=true --env-file .env qiskit-shor src/shor15_general.py
```

