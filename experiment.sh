#!/bin/bash

backend=fez

# Hardware runs in parallel
for opt in 0 1 2 3; do
    for i in 1 2 3 4 5; do
        docker compose run --rm \
            -e BACKEND_MODE=hardware \
            -e BACKEND_NAME=ibm_$backend \
            -e OPTIMIZATION_LEVEL=$opt \
            -e RUN_ID=$i \
            qiskit-shor src/shor15_compiled.py &
    done
    wait
done

# Noisy runs: sequential
for opt in 0 1 2 3; do
    for i in 1 2 3 4 5; do
        docker compose run --rm \
            -e BACKEND_MODE=noisy \
            -e BACKEND_NAME=ibm_$backend \
            -e OPTIMIZATION_LEVEL=$opt \
            -e RUN_ID=$i \
            qiskit-shor src/shor15_compiled.py
    done
done

# Ideal runs: sequential
for opt in 0 1 2 3; do
        docker compose run --rm \
            -e BACKEND_MODE=ideal \
            -e OPTIMIZATION_LEVEL=$opt \
            -e RUN_ID=$i \
            qiskit-shor src/shor15_compiled.py
done