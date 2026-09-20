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
```

Run on an IBM hardware noise model:

```bash
docker compose run --rm \
  -e BACKEND_MODE=noisy \
  -e BACKEND_NAME=ibm_kingston \
  -e OPTIMIZATION_LEVEL=1 \
  qiskit-shor src/shor15_compiled.py
```

Run on IBM hardware (requires `.env` with `IBM_TOKEN=token`):

```bash
docker compose run --rm \
  -e BACKEND_MODE=hardware \
  -e BACKEND_NAME=ibm_kingston \
  -e OPTIMIZATION_LEVEL=1 \
  qiskit-shor src/shor15_compiled.py
```

Parameters:

```
OPTIMIZATION_LEVEL   0 | 1 | 2 | 3

BACKEND_MODE         ideal       ideal Aer simulator
                     noisy       noise model based on an IBM fake backend
                     hardware    real IBM quantum hardware

BACKEND_NAME         ibm_kingston | ibm_fez | ibm_marrakesh
                     (only used for noisy and hardware)
```

## Batch runs

`experiment.sh` runs `shor15_compiled.py` for one backend over all
optimization levels (0 to 3) with five runs each: on hardware (in
parallel), on the noise model and on the ideal simulator. The backend is
set at the top of the script. Every run gets a `RUN_ID`, which ends up in
the result filename.

```bash
./experiment.sh
```

Results land in `results/<date>/` and are moved into a backend subfolder
by hand afterwards.

## Calibration data

Pull the current calibration of the hardware backends (T1, T2, readout error
per qubit; error per two-qubit gate). Writes one dated JSON per backend to
`results/calibration/`:

```bash
docker compose run --rm qiskit-shor src/calibration.py
docker compose run --rm qiskit-shor src/calibration.py ibm_fez
```

`BACKEND_MODE=noisy` reads the fake backends' snapshot instead of live
hardware.
