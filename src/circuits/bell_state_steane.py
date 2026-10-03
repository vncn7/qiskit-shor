import os
import sys
from collections import Counter

from qiskit import QuantumCircuit
from qiskit.quantum_info import Pauli, StabilizerState

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from runner import run


# Bell state encoded in the Steane code: two blocks in |0_L>, transversal H_L
# on the first, transversal CNOT_L between both, then all 14 qubits measured
# and decoded classically into two logical bits.
#
# This is only the encoded preparation. The QEC rounds between the gadgets
# (Figure 2.7 in the thesis) are not implemented; errors are corrected once,
# classically, from the final measurement.

# The Steane code has three X-type and three Z-type parity checks on the same
# groups of qubits, the checks of the [7,4,3] Hamming code: qubit q is in
# check i exactly if bit i of (q + 1) is set. So the three check results, read
# as a binary number, give the index of a flipped qubit plus one.
CHECKS = [
    [3, 4, 5, 6],  # check 2 (bit value 4)
    [1, 2, 5, 6],  # check 1 (bit value 2)
    [0, 2, 4, 6],  # check 0 (bit value 1)
]

# One qubit per check that lies in no other check. It starts in |+> during
# encoding and its CNOTs spread the superposition over the rest of the check.
CHECK_LEADERS = [3, 1, 0]

BLOCK_SIZE = 7


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


# |0_L> on qubits first_qubit .. first_qubit + 6: the equal superposition of
# all even-weight Hamming codewords. Not fault-tolerant, a single error here
# can spread within the block.
def encode_zero_logical(qc, first_qubit):
    for leader in CHECK_LEADERS:
        qc.h(first_qubit + leader)
    for leader, check in zip(CHECK_LEADERS, CHECKS):
        for target in check:
            if target != leader:
                qc.cx(first_qubit + leader, first_qubit + target)


# Transversal H_L: one Hadamard per physical qubit
def logical_hadamard(qc, first_qubit):
    for i in range(BLOCK_SIZE):
        qc.h(first_qubit + i)


# Transversal CNOT_L: qubit i of one block controls qubit i of the other
def logical_cnot(qc, control_block, target_block):
    for i in range(BLOCK_SIZE):
        qc.cx(control_block + i, target_block + i)


# Encoded version of bell_state.py: H on qubit 0, CNOT 0 -> 1
def create_circuit():
    block_0 = 0
    block_1 = BLOCK_SIZE

    qc = QuantumCircuit(2 * BLOCK_SIZE)
    qc.name = "steane_bell_state"

    encode_zero_logical(qc, block_0)
    encode_zero_logical(qc, block_1)
    qc.barrier()

    logical_hadamard(qc, block_0)
    qc.barrier()

    logical_cnot(qc, block_0, block_1)
    qc.measure_all()

    return qc


# ---------------------------------------------------------------------------
# Classical decoding of the measurement results
# ---------------------------------------------------------------------------


# Hamming syndrome (0 .. 7) of one measured 7-bit block
def syndrome(bits):
    value = 0
    for bit_position, check in enumerate(reversed(CHECKS)):  # check 0 -> bit 0
        parity = sum(bits[q] for q in check) % 2
        value += parity << bit_position
    return value


# Corrects at most one bit flip, then returns the logical bit: Z_L is Z on
# all seven qubits, so the logical bit is the parity of the block
def decode_block(bits):
    bits = list(bits)
    s = syndrome(bits)
    if s != 0:
        bits[s - 1] ^= 1  # syndrome s means qubit s - 1 was flipped
    return sum(bits) % 2


# 14-bit measurement outcomes -> 2-bit logical outcomes
def decode_counts(counts):
    logical = Counter()
    for bitstring, n in counts.items():
        # Qiskit prints the highest qubit first, so reverse to get qubit order
        bits = [int(b) for b in reversed(bitstring.replace(" ", ""))]
        logical_0 = decode_block(bits[0:BLOCK_SIZE])
        logical_1 = decode_block(bits[BLOCK_SIZE : 2 * BLOCK_SIZE])
        logical[f"{logical_1}{logical_0}"] += n  # same order as Qiskit
    return dict(logical)


# ---------------------------------------------------------------------------
# Self-check: does the encoder really produce |0_L> in the N&C convention?
# ---------------------------------------------------------------------------


# Pauli string with `kind` (X or Z) on the given qubits of one block
def pauli_on(kind, qubits):
    label = ["I"] * BLOCK_SIZE
    for q in qubits:
        label[BLOCK_SIZE - 1 - q] = kind  # Qiskit orders labels highest qubit first
    return Pauli("".join(label))


# Aborts if encoder or decoder do not match the code convention
def verify_encoder():
    qc = QuantumCircuit(BLOCK_SIZE)
    encode_zero_logical(qc, 0)
    state = StabilizerState(qc)

    # All six parity checks give +1: it is a codeword
    for check in CHECKS:
        for kind in "XZ":
            assert state.expectation_value(pauli_on(kind, check)) == 1, (
                f"parity check {kind} on {check} failed"
            )

    # Z_L gives +1: it is |0_L>, not |1_L>
    assert state.expectation_value(pauli_on("Z", range(BLOCK_SIZE))) == 1, "state is not |0_L>"

    # A single bit flip on any qubit is corrected by the decoder
    for q in range(BLOCK_SIZE):
        flipped = [1 if i == q else 0 for i in range(BLOCK_SIZE)]
        assert decode_block(flipped) == 0, f"decoder does not correct a flip on qubit {q}"


if __name__ == "__main__":
    verify_encoder()
    counts, isa = run(create_circuit())
    print("Physical counts:", len(counts), "distinct outcomes")
    print("Logical counts: ", decode_counts(counts))
