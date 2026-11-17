import glob
import json
import os
import sys

from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.fake_provider.backend_encoder import BackendEncoder

from runner import FAKE_BACKENDS

RUNS_DIR = "results/experiment1/runs"
CALIBRATION_DIR = "results/experiment1/calibration"


# IBM calibration of a measurement day of experiment 1, one file per device:
#   results/experiment1/calibration/<backend_name>_<day>.json
#
# The calibration (backend properties) is the one of the first hardware job of that
# device and day, in the format of the properties JSON of the fake backends. The
# runner loads it in mode noisy_day (CALIBRATION_FILE). Needs IBM_TOKEN, uses no
# QPU time.
#
#   fetch_calibration.py <day>     e.g. fetch_calibration.py 20260911
if __name__ == "__main__":
    day = sys.argv[1]
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=os.environ["IBM_TOKEN"],
    )

    os.makedirs(CALIBRATION_DIR, exist_ok=True)
    for device in FAKE_BACKENDS:
        calibration_file = f"{CALIBRATION_DIR}/{device}_{day}.json"
        if os.path.exists(calibration_file):  # never overwrite a calibration, like write_result
            raise FileExistsError(calibration_file)

        # first hardware run of the device on that day
        paths = sorted(glob.glob(f"{RUNS_DIR}/{day}/shor15_compiled_hardware_{device}_*.json"))
        with open(paths[0]) as file:
            job_id = json.load(file)["execution"]["job_id"]

        properties = service.job(job_id).properties()
        if properties is None:
            raise ValueError(f"IBM returned no properties for job {job_id}")

        # same encoding as the fake backends use for their properties JSON
        with open(calibration_file, "x") as file:
            json.dump(properties.to_dict(), file, cls=BackendEncoder)
        print("saved", calibration_file)
