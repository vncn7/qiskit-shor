#!/bin/bash
# One day of experiment 2 on one device and level: 5 hardware runs per
# configuration, 5 noise model runs of raw, then the mthree readout correction.
# Results land in results/experiment2/runs/<config>/.

backend=kingston
opt=2

# Hardware: the 5 runs of a configuration in parallel, so they share one calibration
for config in raw twirling dd both; do
    for i in 1 2 3 4 5; do
        docker compose run --rm \
            -e BACKEND_MODE=hardware \
            -e BACKEND_NAME=ibm_$backend \
            -e OPTIMISATION_LEVEL=$opt \
            -e RUN_ID=$i \
            -e MITIGATION=$config \
            -e RESULT_DIR=results/experiment2/runs/$config \
            qiskit-shor src/circuits/shor15_compiled.py &
    done
    wait
done

# Noise model: only raw, the sampler options have no effect in local mode
for i in 1 2 3 4 5; do
    docker compose run --rm \
        -e BACKEND_MODE=noisy \
        -e BACKEND_NAME=ibm_$backend \
        -e OPTIMISATION_LEVEL=$opt \
        -e RUN_ID=$i \
        -e MITIGATION=raw \
        -e RESULT_DIR=results/experiment2/runs/raw \
        qiskit-shor src/circuits/shor15_compiled.py
done

# Readout mitigation: calibrate the measured qubits once, then correct raw and both
docker compose run --rm \
    -e BACKEND_MODE=hardware \
    -e BACKEND_NAME=ibm_$backend \
    qiskit-shor src/m3_calibrate.py
docker compose run --rm qiskit-shor src/m3_correct.py
