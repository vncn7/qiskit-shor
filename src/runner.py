import os

from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import SamplerV2 as Sampler


USE_HARDWARE = os.environ.get("USE_HARDWARE", "false").lower() == "true"
USE_NOISY = os.environ.get("USE_NOISY", "false").lower() == "true"
BACKEND_NAME = os.environ.get("BACKEND_NAME", "ibm_kingston")


FAKE_BACKENDS = {
    "ibm_kingston": "FakeKingston",
    "ibm_fez": "FakeFez",
    "ibm_marrakesh": "FakeMarrakesh",
}


def get_backend():
    if USE_HARDWARE and USE_NOISY:
        raise ValueError("USE_HARDWARE and USE_NOISY cannot both be true.")

    if USE_HARDWARE:
        from qiskit_ibm_runtime import QiskitRuntimeService

        service = QiskitRuntimeService(
            channel="ibm_quantum_platform",
            token=os.environ["IBM_TOKEN"],
        )
        backend = service.backend(BACKEND_NAME)

        print(f"Running on: {backend.name}")
        print(f"Calibration timestamp: {backend.properties().last_update_date}")

        return backend

    if USE_NOISY:
        from qiskit_ibm_runtime import fake_provider

        if BACKEND_NAME not in FAKE_BACKENDS:
            raise ValueError(
                f"Unknown backend: {BACKEND_NAME}. "
                f"Choose one of: {sorted(FAKE_BACKENDS)}"
            )

        fake_backend = getattr(
            fake_provider,
            FAKE_BACKENDS[BACKEND_NAME]
        )()

        print(f"Running on noise model of: {fake_backend.name}")

        return AerSimulator.from_backend(fake_backend)

    return AerSimulator()


def run(qc, shots=1024, optimization_level=1):
    backend = get_backend()

    pm = generate_preset_pass_manager(
        backend=backend,
        optimization_level=optimization_level,
    )

    isa = pm.run(qc)

    sampler = Sampler(mode=backend)
    job = sampler.run([isa], shots=shots)

    if USE_HARDWARE:
        print(f"Job ID: {job.job_id()}")

    counts = job.result()[0].data.meas.get_counts()

    return counts, isa