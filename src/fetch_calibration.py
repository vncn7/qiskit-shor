import glob
import json
import os
import sys

from qiskit import qpy
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.fake_provider.backend_encoder import BackendEncoder

from runner import FAKE_BACKENDS

RUNS_DIR = "results/experiment1/runs"
CALIBRATION_DIR = "results/experiment1/calibration"
LEVELS = [0, 1, 2, 3]


# job id of the first hardware run of a device (and level) on a day
def first_job_id(day, device, level="*"):
    paths = sorted(
        glob.glob(
            f"{RUNS_DIR}/{day}/shor15_compiled_hardware_{device}_opt{level}_*.json"
        )
    )
    with open(paths[0]) as file:
        return json.load(file)["execution"]["job_id"]


# Fetches calibration and hardware circuits of a measurement day from IBM for the
# daily noise model, uses no QPU time:
#   <device>_<day>.json             calibration, one per device
#   <device>_<day>_opt<level>.qpy   circuit as run on the hardware, one per device and level
#
#   fetch_calibration.py <day>
if __name__ == "__main__":
    day = sys.argv[1]
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=os.environ["IBM_TOKEN"],
    )
    os.makedirs(CALIBRATION_DIR, exist_ok=True)

    for device in FAKE_BACKENDS:
        properties = service.job(first_job_id(day, device)).properties()
        with open(f"{CALIBRATION_DIR}/{device}_{day}.json", "x") as file:
            json.dump(properties.to_dict(), file, cls=BackendEncoder)

        for level in LEVELS:
            circuit = service.job(first_job_id(day, device, level)).inputs["pubs"][0][0]
            with open(f"{CALIBRATION_DIR}/{device}_{day}_opt{level}.qpy", "xb") as file:
                qpy.dump(circuit, file)
