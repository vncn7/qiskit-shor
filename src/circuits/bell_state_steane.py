import os
import sys
from collections import Counter

from qiskit import QuantumCircuit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from runner import run

# Steane code parity checks
CHECKS = [[0, 2, 4, 6], [1, 2, 5, 6], [3, 4, 5, 6]]


# Logical |0> on seven qubits
def encode_zero(qc, start):
    for check in CHECKS:
        qc.h(start + check[0])
    for check in CHECKS:
        for q in check[1:]:
            qc.cx(start + check[0], start + q)


# Logical Bell state
def create_circuit():
    qc = QuantumCircuit(14)
    qc.name = "steane_bell_state"
    encode_zero(qc, 0)
    encode_zero(qc, 7)
    qc.barrier()

    # Logical H
    for i in range(7):
        qc.h(i)
    qc.barrier()

    # Logical CNOT
    for i in range(7):
        qc.cx(i, 7 + i)

    qc.measure_all()
    return qc


# Fix one bit flip, return logical bit
def decode_block(bits):
    s = sum(2**i for i, check in enumerate(CHECKS) if sum(bits[q] for q in check) % 2)
    if s:
        bits[s - 1] ^= 1
    return sum(bits) % 2


# turns every 14-bit result into a 2-bit logical result
def decode_counts(counts):
    logical = Counter()
    for bitstring, n in counts.items():
        bits = [int(b) for b in reversed(bitstring.replace(" ", ""))]  # qubit 0 first
        logical[f"{decode_block(bits[7:])}{decode_block(bits[:7])}"] += n
    return dict(logical)


if __name__ == "__main__":
    counts, _ = run(create_circuit())
    print("Logical counts:", decode_counts(counts))
