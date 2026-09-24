import os
import sys

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit.library import QFTGate

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from runner import run


# Modular multiplication by 2 modulo 15.
# The swaps implement |y> -> |2y mod 15>.
def M2mod15():
    gate = QuantumCircuit(4)

    gate.swap(2, 3)
    gate.swap(1, 2)
    gate.swap(0, 1)

    gate = gate.to_gate()
    gate.name = "M2"

    return gate


# Modular multiplication by 4 modulo 15.
# The swaps implement |y> -> |4y mod 15>.
def M4mod15():
    gate = QuantumCircuit(4)

    gate.swap(1, 3)
    gate.swap(0, 2)

    gate = gate.to_gate()
    gate.name = "M4"

    return gate


def create_circuit():
    # Shor's algorithm for N = 15 with a = 2.
    # Eight control qubits provide the precision for phase estimation.
    # Four target qubits are sufficient to represent the values modulo 15.
    num_control = 8
    num_target = 4

    # Create quantum and classical registers.
    control = QuantumRegister(num_control, "control")
    target = QuantumRegister(num_target, "target")
    output = ClassicalRegister(num_control, "output")

    circuit = QuantumCircuit(control, target, output)

    # Initialize the target register to |1>.
    circuit.x(target[0])

    # Apply phase estimation.
    # Each control qubit is put into a superposition and controls
    # a modular multiplication by 2^(2^k) mod 15.
    for k in range(num_control):
        circuit.h(control[k])

        # Calculate 2^(2^k) mod 15.
        b = pow(2, 2**k, 15)

        # Apply the corresponding controlled modular multiplication.
        if b == 2:
            circuit.compose(
                M2mod15().control(), qubits=[control[k]] + list(target), inplace=True
            )

        elif b == 4:
            circuit.compose(
                M4mod15().control(), qubits=[control[k]] + list(target), inplace=True
            )

    # Apply the inverse Quantum Fourier Transform to the control register.
    # This converts the encoded phase information into measurable values.
    circuit.compose(QFTGate(num_control).inverse(), qubits=control, inplace=True)

    # Measure the control register to obtain the estimated phase.
    circuit.measure(control, output)

    return circuit


if __name__ == "__main__":
    qc = create_circuit()
    qc.name = "shor15_compiled"
    counts, isa = run(qc, shots=1024)

    print(counts)
