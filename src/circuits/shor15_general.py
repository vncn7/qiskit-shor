import os
import sys

from qiskit import QuantumCircuit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from runner import run


def create_circuit():
    qc = QuantumCircuit(...)

    # general Shor-15 circuit goes here

    qc.measure_all()
    return qc


if __name__ == "__main__":
    qc = create_circuit()

    counts, isa = run(qc)

    print(counts)
