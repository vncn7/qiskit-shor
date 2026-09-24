import os
import statistics

from qiskit_ibm_runtime.fake_provider import FakeFez, FakeKingston, FakeMarrakesh

from experiment_data import (
    DEVICES,
    OPTIMISATION_LEVELS,
    load_runs,
    pooled_counts,
    working_gate_errors,
)

OUTPUT_DIR = "src/analysis/experiment1/tables"

# The noise model of each device comes from this snapshot in qiskit-ibm-runtime.
NOISE_MODEL_BACKENDS = {
    "ibm_kingston": FakeKingston,
    "ibm_fez": FakeFez,
    "ibm_marrakesh": FakeMarrakesh,
}


def latex_table(caption, label, column_spec, header, rows):
    return "\n".join(
        [
            r"\begin{table}[h]",
            r"\centering",
            rf"\caption{{{caption}}}",
            rf"\label{{{label}}}",
            rf"\begin{{tabularx}}{{\textwidth}}{{{column_spec}}}",
            r"\toprule",
            *header,
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabularx}",
            r"\end{table}",
        ]
    )


# ---------------------------------------------------------------------------
# Table: calibration (calibration.tex)
#
# One number per device and quantity: the median over all qubits (T1, T2,
# readout) or over all gates (SX, CZ) of the device. The median is used
# because a few very bad qubits would pull a mean far off.
# Left out: qubits without T1 or T2 value, gates that are out of order.
# ---------------------------------------------------------------------------


def hardware_calibration_medians(device):
    runs = [
        run
        for level in OPTIMISATION_LEVELS
        for run in load_runs("hardware", device, level)
    ]
    timestamps = {run["calibration"]["calibration_timestamp"] for run in runs}
    assert len(timestamps) == 1, f"{device}: several calibrations {timestamps}"
    calibration = runs[0]["calibration"]

    qubits = [
        qubit
        for qubit in calibration["qubits"]
        if qubit["T1_us"] is not None and qubit["T2_us"] is not None
    ]
    sx_errors = working_gate_errors(calibration["single_qubit_gates"], "sx")
    cz_errors = working_gate_errors(calibration["two_qubit_gates"], "cz")

    return (
        statistics.median(qubit["T1_us"] for qubit in qubits),
        statistics.median(qubit["T2_us"] for qubit in qubits),
        statistics.median(qubit["readout_error"] for qubit in qubits),
        statistics.median(sx_errors),
        statistics.median(cz_errors),
    )


def noise_model_calibration_medians(device):
    properties = NOISE_MODEL_BACKENDS[device]().properties()

    t1_us, t2_us, readout_errors = [], [], []
    for qubit in range(len(properties.qubits)):
        try:
            t1, t2 = properties.t1(qubit), properties.t2(qubit)
        except Exception:  # qiskit raises if a qubit has no T1 or T2 value
            continue
        if t1 is None or t2 is None:
            continue
        t1_us.append(t1 * 1e6)  # qiskit gives seconds
        t2_us.append(t2 * 1e6)
        readout_errors.append(properties.readout_error(qubit))

    sx_errors, cz_errors = [], []
    for gate in properties.gates:
        error = next(
            (p.value for p in gate.parameters if p.name == "gate_error"), None
        )
        if error is None or error == 1:  # no value, or out of order
            continue
        if gate.gate == "sx":
            sx_errors.append(error)
        if gate.gate == "cz":
            cz_errors.append(error)

    return (
        statistics.median(t1_us),
        statistics.median(t2_us),
        statistics.median(readout_errors),
        statistics.median(sx_errors),
        statistics.median(cz_errors),
    )


def calibration_row(device_name, source, medians):
    t1, t2, readout, sx, cz = medians
    return (
        f"{device_name} & {source} & {t1:.0f} & {t2:.0f} & {readout:.4f}"
        f" & {sx:.5f} & {cz:.4f} \\\\"
    )


def calibration_table():
    rows = []
    for device, name in DEVICES:
        rows.append(calibration_row(name, "Hardware", hardware_calibration_medians(device)))
        rows.append(calibration_row("", "Noise model", noise_model_calibration_medians(device)))
        rows.append(r"\addlinespace")
    rows.pop()  # no extra space after the last device

    return latex_table(
        caption="Experiment 1: calibration data of hardware and noise models",
        label="tab:exp1_calibration",
        column_spec=r"@{}p{2.2cm}p{2.4cm}*{5}{>{\centering\arraybackslash}X}@{}",
        header=[
            r" & & & & \multicolumn{3}{c}{Error rate} \\",
            r"\cmidrule(l){5-7}",
            r"Device & Source & $T_1$ (\si{\micro\second}) & $T_2$ (\si{\micro\second}) & Readout & SX, X & CZ \\",
        ],
        rows=rows,
    )


# ---------------------------------------------------------------------------
# Table: transpiled circuit (transpiled.tex)
#
# Depth and gate counts of the circuit the hardware ran, per optimisation
# level. The transpiler adapts the circuit to each device, so a number can
# differ between the devices; then the range "min--max" is shown.
# ---------------------------------------------------------------------------


def value_or_range(values):
    low, high = min(values), max(values)
    return f"${low}$" if low == high else f"${low}$--${high}$"


def transpiled_row(level):
    # all values seen for this level, over all devices and runs
    depth, cz, sx, x, rz = set(), set(), set(), set(), set()
    for device, _ in DEVICES:
        for run in load_runs("hardware", device, level):
            circuit = run["circuit"]["transpiled"]
            gate_counts = circuit["gate_counts"]
            depth.add(circuit["depth"])
            cz.add(gate_counts.get("cz", 0))
            sx.add(gate_counts.get("sx", 0))
            x.add(gate_counts.get("x", 0))
            rz.add(gate_counts.get("rz", 0))
    cells = [value_or_range(values) for values in (depth, cz, sx, x, rz)]
    return f"{level} & " + " & ".join(cells) + " \\\\"


def transpiled_table():
    return latex_table(
        caption="Experiment 1: size of the transpiled circuit per optimisation level",
        label="tab:exp1_transpiled",
        column_spec=r"@{}l*{5}{>{\centering\arraybackslash}X}@{}",
        header=[r"Optimisation level & Depth & CZ & SX & X & RZ \\"],
        rows=[transpiled_row(level) for level in OPTIMISATION_LEVELS],
    )


# ---------------------------------------------------------------------------
# Table: most frequent outcomes on Kingston, level 2 vs. level 3
# (top_outcomes.tex)
#
# Outcomes as numbers: the 8 counting bits read as a binary number,
# "01000000" -> 64. The ideal outcomes are 0, 64, 128 and 192.
# ---------------------------------------------------------------------------


def top_outcomes(device, level, how_many=4):
    counts = pooled_counts(load_runs("hardware", device, level))
    all_shots = sum(counts.values())
    most_frequent = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [
        (int(bits, 2), 100 * shots / all_shots)
        for bits, shots in most_frequent[:how_many]
    ]


def top_outcomes_table():
    level2 = top_outcomes("ibm_kingston", 2)
    level3 = top_outcomes("ibm_kingston", 3)

    rows = []
    for rank, ((outcome2, share2), (outcome3, share3)) in enumerate(
        zip(level2, level3), start=1
    ):
        rows.append(
            f"{rank} & {outcome2} & {share2:.1f} & {outcome3} & {share3:.1f} \\\\"
        )

    return latex_table(
        caption=r"Experiment 1: most frequent outcomes on ibm\_kingston at optimisation levels 2 and 3, all five runs combined",
        label="tab:exp1_top_outcomes",
        column_spec=r"@{}l*{4}{>{\centering\arraybackslash}X}@{}",
        header=[
            r" & \multicolumn{2}{c}{Level 2} & \multicolumn{2}{c}{Level 3} \\",
            r"\cmidrule(l){2-3}\cmidrule(l){4-5}",
            r"Rank & Outcome & Share (\%) & Outcome & Share (\%) \\",
        ],
        rows=rows,
    )


os.makedirs(OUTPUT_DIR, exist_ok=True)
for name, text in (
    ("calibration", calibration_table()),
    ("transpiled", transpiled_table()),
    ("top_outcomes", top_outcomes_table()),
):
    with open(f"{OUTPUT_DIR}/{name}.tex", "w", encoding="utf-8") as file:
        file.write(text + "\n")
    print(text, "\n")
