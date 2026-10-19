import glob
import json

import mthree

RESULT_DIR = "results/experiment2/runs"


# mthree readout correction of the hardware runs of raw (-> "readout") and both
# (-> "all"), written into the run file next to the counts; already corrected
# files are skipped
corrected = 0
for config in ["raw", "both"]:
    for path in sorted(glob.glob(f"{RESULT_DIR}/{config}/shor15_compiled_hardware_*.json")):
        with open(path) as f:
            data = json.load(f)
        if "quasi_probabilities" in data["results"]:
            continue

        execution = data["execution"]
        day = data["timestamp"][:10].replace("-", "")
        cals_file = f"{RESULT_DIR}/m3_cals_{execution['backend_mode']}_{execution['backend_name']}_{day}.json"
        mit = mthree.M3Mitigation()
        mit.cals_from_file(cals_file)
        qubits = data["circuit"]["transpiled"]["physical_qubits"][:8]
        quasi = mit.apply_correction(data["results"]["counts"], qubits)

        data["results"]["quasi_probabilities"] = {k: float(v) for k, v in quasi.items()}
        data["readout_mitigation"] = {
            "method": "mthree",
            "version": mthree.__version__,
            "cals_file": cals_file,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
        corrected += 1

print("corrected", corrected, "files")
