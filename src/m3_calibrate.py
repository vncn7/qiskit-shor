import glob
import json
import os
from datetime import date

import mthree

from runner import BACKEND_MODE, BACKEND_NAME, get_backend

RESULT_DIR = "results/experiment2/runs"
TODAY = date.today()


# mthree readout calibration
def measured_qubits():
    layouts = set()
    for path in glob.glob(
        f"{RESULT_DIR}/*/shor15_compiled_{BACKEND_MODE}_{BACKEND_NAME}_*.json"
    ):
        with open(path) as f:
            data = json.load(f)
        if data["timestamp"].startswith(TODAY.isoformat()):
            layouts.add(tuple(data["circuit"]["transpiled"]["physical_qubits"][:8]))
    if len(layouts) != 1:
        raise ValueError(f"{len(layouts)} layouts found for today")
    return list(layouts.pop())


if __name__ == "__main__":
    cals_file = (
        f"{RESULT_DIR}/m3_cals_{BACKEND_MODE}_{BACKEND_NAME}_{TODAY:%Y%m%d}.json"
    )
    if os.path.exists(cals_file):  # never overwrite a calibration, like write_result
        raise FileExistsError(cals_file)
    backend, fake_backend = get_backend()
    mit = mthree.M3Mitigation(fake_backend if BACKEND_MODE == "noisy" else backend)
    # async_cal=False: wait for the job here, otherwise errors end up in a thread
    mit.cals_from_system(measured_qubits(), shots=10000, async_cal=False, cals_file=cals_file)
    print("saved", cals_file)
