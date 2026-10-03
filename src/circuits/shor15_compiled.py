import os
import sys

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit.library import QFTGate

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from runner import run


# |y> -> |2y mod 15>: multiplying by 2 rotates the four bits by one place
def multiply_by_2_mod_15():
    gate = QuantumCircuit(4)
    gate.swap(2, 3)
    gate.swap(1, 2)
    gate.swap(0, 1)
    gate = gate.to_gate()
    gate.name = "M2"
    return gate


# |y> -> |4y mod 15>: multiplying by 4 rotates the four bits by two places
def multiply_by_4_mod_15():
    gate = QuantumCircuit(4)
    gate.swap(1, 3)
    gate.swap(0, 2)
    gate = gate.to_gate()
    gate.name = "M4"
    return gate


# Shor's algorithm for N = 15 with base a = 2, compiled by hand: the modular
# multiplications are swap networks instead of general modular arithmetic.
# 8 control qubits set the precision of the phase estimation, 4 target
# qubits hold the values modulo 15.
def create_circuit():
    num_control = 8
    num_target = 4

    control = QuantumRegister(num_control, "control")
    target = QuantumRegister(num_target, "target")
    output = ClassicalRegister(num_control, "output")
    circuit = QuantumCircuit(control, target, output)
    circuit.name = "shor15_compiled"

    # Target register starts in |1>
    circuit.x(target[0])

    # Phase estimation: control qubit k multiplies the target by 2^(2^k) mod 15.
    # From k = 2 on that is 16 mod 15 = 1, so nothing is left to apply.
    for k in range(num_control):
        circuit.h(control[k])
        multiplier = pow(2, 2**k, 15)
        if multiplier == 2:
            circuit.compose(
                multiply_by_2_mod_15().control(), qubits=[control[k]] + list(target), inplace=True
            )
        elif multiplier == 4:
            circuit.compose(
                multiply_by_4_mod_15().control(), qubits=[control[k]] + list(target), inplace=True
            )

    # Inverse QFT turns the phase into a measurable number
    circuit.compose(QFTGate(num_control).inverse(), qubits=control, inplace=True)
    circuit.measure(control, output)

    return circuit


if __name__ == "__main__":
    counts, isa = run(create_circuit(), shots=1024)
    print(counts)
