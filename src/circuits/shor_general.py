# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

# Modified: rewritten from qiskit/algorithms/factorizers/shor.py (Qiskit 0.21.2).
# Only the circuit construction is kept, as plain functions. The order of
# the gates is unchanged, checked against the original in ideal simulation.

import math
import os
import sys

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit.library import QFTGate
from qiskit.synthesis import synth_qft_full

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from runner import run


# Number to factor and base of the modular exponentiation.
# N must be odd, A must satisfy 1 < A < N and gcd(A, N) = 1.
N = 15
A = 2


# QFT without the final swaps. The adders below work in this Fourier basis,
# where bit i of the number is encoded as a phase on qubit i.
def qft_no_swaps(num_qubits):
    return synth_qft_full(num_qubits, do_swaps=False).to_gate()


# |phi(b)> -> |phi(b + a)>: adding a in the Fourier basis is a phase rotation
# on every qubit. Qubit i collects the bits of a up to bit i.
def add_in_fourier_basis(a, num_qubits):
    gate = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        angle = 0
        for j in range(i + 1):
            if (a >> j) & 1:
                angle += math.pi / 2 ** (i - j)
        gate.p(angle, i)
    gate = gate.to_gate()
    gate.name = f"add{a}"
    return gate


# |phi(b)> -> |phi((b + a) mod N)> for b < N, controlled by two qubits
# (Beauregard, figure 5). The b register has one extra qubit so b + a does
# not overflow; its top bit tells whether b + a - N went negative, the flag
# qubit stores that bit while N is added back.
def add_mod_N_in_fourier_basis(a, num_qubits):
    control = QuantumRegister(2, "control")
    b = QuantumRegister(num_qubits, "b")
    flag = QuantumRegister(1, "flag")
    circuit = QuantumCircuit(control, b, flag)

    add_a = add_in_fourier_basis(a, num_qubits).control(2)
    subtract_a = add_a.inverse()
    add_N = add_in_fourier_basis(N, num_qubits).control(1)
    subtract_N = add_in_fourier_basis(N, num_qubits).inverse()
    qft = qft_no_swaps(num_qubits)
    iqft = qft.inverse()

    # b + a - N, then copy the sign bit into the flag
    circuit.compose(add_a, qubits=[*control, *b], inplace=True)
    circuit.compose(subtract_N, qubits=b, inplace=True)
    circuit.compose(iqft, qubits=b, inplace=True)
    circuit.cx(b[-1], flag[0])
    circuit.compose(qft, qubits=b, inplace=True)

    # add N back if the result was negative
    circuit.compose(add_N, qubits=[flag[0], *b], inplace=True)

    # reset the flag: b - a is negative exactly when N was added back
    circuit.compose(subtract_a, qubits=[*control, *b], inplace=True)
    circuit.compose(iqft, qubits=b, inplace=True)
    circuit.x(b[-1])
    circuit.cx(b[-1], flag[0])
    circuit.x(b[-1])
    circuit.compose(qft, qubits=b, inplace=True)
    circuit.compose(add_a, qubits=[*control, *b], inplace=True)

    gate = circuit.to_gate()
    gate.name = f"add{a}mod{N}"
    return gate


# |x>|0> -> |a*x mod N>|0>, controlled by one qubit (Beauregard, figure 6).
# a*x is summed bit by bit into b, then x and b are swapped, then the old x
# is uncomputed by subtracting a^-1 times the new x.
def multiply_mod_N(a, n):
    control = QuantumRegister(1, "control")
    target = QuantumRegister(n, "target")
    b = QuantumRegister(n + 1, "b")
    flag = QuantumRegister(1, "flag")
    circuit = QuantumCircuit(control, target, b, flag)

    qft = qft_no_swaps(n + 1)
    iqft = qft.inverse()

    # b = a*x mod N: bit i of x contributes 2^i * a
    circuit.compose(qft, qubits=b, inplace=True)
    for i in range(n):
        summand = (pow(2, i, N) * a) % N
        adder = add_mod_N_in_fourier_basis(summand, n + 1)
        circuit.compose(
            adder, qubits=[control[0], target[i], *b, flag[0]], inplace=True
        )
    circuit.compose(iqft, qubits=b, inplace=True)

    for i in range(n):
        circuit.cswap(control[0], target[i], b[i])

    # b = 0: subtract a^-1 * (a*x) = x
    a_inv = pow(a, -1, N)
    circuit.compose(qft, qubits=b, inplace=True)
    for i in reversed(range(n)):
        subtrahend = (pow(2, i, N) * a_inv) % N
        subtractor = add_mod_N_in_fourier_basis(subtrahend, n + 1).inverse()
        circuit.compose(
            subtractor, qubits=[control[0], target[i], *b, flag[0]], inplace=True
        )
    circuit.compose(iqft, qubits=b, inplace=True)

    gate = circuit.to_gate()
    gate.name = f"mul{a}mod{N}"
    return gate


# Shor's algorithm for N with general modular arithmetic after Beauregard
# instead of hand-compiled swap networks. n is the bit length of N: 2n
# control qubits for the phase estimation, n target qubits for the values
# modulo N, n + 2 auxiliary qubits for the adders. 4n + 2 qubits in total.
def create_circuit():
    if N % 2 == 0 or A <= 1 or A >= N or math.gcd(A, N) != 1:
        raise ValueError("N must be odd and A must satisfy 1 < A < N and gcd(A, N) = 1")

    n = N.bit_length()

    control = QuantumRegister(2 * n, "control")
    target = QuantumRegister(n, "target")
    b = QuantumRegister(n + 1, "b")
    flag = QuantumRegister(1, "flag")
    output = ClassicalRegister(2 * n, "output")
    circuit = QuantumCircuit(control, target, b, flag, output)
    circuit.name = f"shor{N}_general"

    # Target register starts in |1>
    circuit.h(control)
    circuit.x(target[0])

    # Phase estimation: control qubit k multiplies the target by A^(2^k) mod N
    for k in range(2 * n):
        multiplier = pow(A, 2**k, N)
        circuit.compose(
            multiply_mod_N(multiplier, n),
            qubits=[control[k], *target, *b, *flag],
            inplace=True,
        )

    # Inverse QFT turns the phase into a measurable number
    circuit.compose(QFTGate(2 * n).inverse(), qubits=control, inplace=True)
    circuit.measure(control, output)

    return circuit


if __name__ == "__main__":
    counts, isa = run(create_circuit(), shots=64)
    print(counts)
