from qiskit import QuantumCircuit

from runner import run


def create_circuit():
    qc = QuantumCircuit(...)

    # Compiled Shor-15 circuit goes here

    qc.measure_all()
    return qc


if __name__ == "__main__":
    qc = create_circuit()

    counts, isa = run(qc)

    print(counts)