"""
Bell State Circuit

Creates and measures a Bell state - the simplest demonstration of quantum
entanglement using Qiskit. Runs on a local simulator or a real IBM QPU.

Two qubits start at |0>. A Hadamard gate puts qubit 0 into superposition,
then a CNOT gate entangles both qubits, producing:

    |Phi+> = (|00> + |11>) / sqrt(2)

    qubit 0: --[H]--*--[M]
                     |
    qubit 1: --------X--[M]

Measuring will always give 00 or 11, never 01 or 10. The circuit runs 1024
times to confirm the ~50/50 split.
"""

import os

from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import SamplerV2 as Sampler

USE_HARDWARE = os.environ.get("USE_HARDWARE", "false").lower() == "true"

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()

if USE_HARDWARE:
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=os.environ["IBM_TOKEN"],
    )
    backend = service.least_busy(operational=True, simulator=False)
    print(f"Running on: {backend.name}")
    props = backend.properties()
    print(f"Calibration timestamp: {props.last_update_date}")
else:
    backend = AerSimulator()

pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
isa = pm.run(qc)

sampler = Sampler(mode=backend)
job = sampler.run([isa], shots=1024)
if USE_HARDWARE:
    print(f"Job ID: {job.job_id()}")
result = job.result()
print(result[0].data.meas.get_counts())

