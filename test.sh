#!/bin/bash

backend=fez

for opt in 0 1 2 3; do

    for i in 1 2 3 4 5; do

        docker compose run --rm \
            -e BACKEND_MODE=noisy \
            -e BACKEND_NAME=ibm_$backend \
            -e OPTIMIZATION_LEVEL=$opt \
            -e RUN_ID=$i \
            qiskit-shor src/shor15_compiled.py &

    done

    wait

done