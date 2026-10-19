#!/bin/bash
# One day of experiment 1: per device and optimisation level 5 hardware runs
# and 5 noise model runs, plus 1 ideal run per level. Results land in
# results/experiment1/runs/<date>/.

day=$(date +%Y%m%d)

# Hardware: the 5 runs of a level in parallel, so they share one calibration
for backend in kingston fez marrakesh; do
    for opt in 0 1 2 3; do
        for i in 1 2 3 4 5; do
            docker compose run --rm \
                -e BACKEND_MODE=hardware \
                -e BACKEND_NAME=ibm_$backend \
                -e OPTIMISATION_LEVEL=$opt \
                -e RUN_ID=$i \
                -e RESULT_DIR=results/experiment1/runs/$day \
                qiskit-shor src/circuits/shor15_compiled.py &
        done
        wait
    done
done

# Noise model: one after the other, the simulator needs the CPU
for backend in kingston fez marrakesh; do
    for opt in 0 1 2 3; do
        for i in 1 2 3 4 5; do
            docker compose run --rm \
                -e BACKEND_MODE=noisy \
                -e BACKEND_NAME=ibm_$backend \
                -e OPTIMISATION_LEVEL=$opt \
                -e RUN_ID=$i \
                -e RESULT_DIR=results/experiment1/runs/$day \
                qiskit-shor src/circuits/shor15_compiled.py
        done
    done
done

# Ideal: one run per level is enough, there is no noise to average out
for opt in 0 1 2 3; do
    docker compose run --rm \
        -e BACKEND_MODE=ideal \
        -e OPTIMISATION_LEVEL=$opt \
        -e RUN_ID=1 \
        -e RESULT_DIR=results/experiment1/runs/$day \
        qiskit-shor src/circuits/shor15_compiled.py
done
