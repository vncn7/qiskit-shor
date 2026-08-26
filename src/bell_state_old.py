import os

from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import SamplerV2 as Sampler

USE_HARDWARE = os.environ.get("USE_HARDWARE", "false").lower() == "true"
USE_NOISY = os.environ.get("USE_NOISY", "false").lower() == "true"

# Shared config: USE_HARDWARE connects to exactly this device, and USE_NOISY
# builds its noise model from the matching fake backend, so both modes are
# always simulating/running on the same hardware.
BACKEND_NAME = os.environ.get("BACKEND_NAME", "ibm_kingston")

FAKE_BACKENDS = {
    "ibm_kingston": "FakeKingston",
    "ibm_fez": "FakeFez",
    "ibm_marrakesh": "FakeMarrakesh",
}

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
    backend = service.backend(BACKEND_NAME)
    print(f"Running on: {backend.name}")
    props = backend.properties()
    print(f"Calibration timestamp: {props.last_update_date}")
elif USE_NOISY:
    from qiskit_ibm_runtime import fake_provider
    if BACKEND_NAME not in FAKE_BACKENDS:
        raise ValueError(
            f"No fake backend available for '{BACKEND_NAME}'. "
            f"Choose one of: {sorted(FAKE_BACKENDS)}"
        )
    device = getattr(fake_provider, FAKE_BACKENDS[BACKEND_NAME])()
    backend = AerSimulator.from_backend(device)
    print(f"Running on: noise model of {device.name} ({BACKEND_NAME})")
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