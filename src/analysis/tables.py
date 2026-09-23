import glob
import json
import os
import statistics as st

from qiskit_ibm_runtime.fake_provider import FakeFez, FakeKingston, FakeMarrakesh

RESULTS = "results/20260911"
OUT = "src/analysis/exp1/tables"

CHIPS = [
    ("ibm_kingston", "Kingston", FakeKingston),
    ("ibm_fez", "Fez", FakeFez),
    ("ibm_marrakesh", "Marrakesh", FakeMarrakesh),
]


# ---------------------------------------------------------------------------
# Calibration: medians over all qubits and couplers of a device.
# Excluded: qubits without T1 or T2, gates with error rate 1 (defective).
# ---------------------------------------------------------------------------


def hardware(chip):
    """Calibration of 11 September 2026, from the exported file."""
    path = glob.glob(f"{RESULTS}/calibration/{chip}_*.json")[0]
    data = json.load(open(path))

    qubits = [
        q for q in data["qubits"] if q["T1_us"] is not None and q["T2_us"] is not None
    ]
    sx = [
        g["gate_error"]
        for g in data["single_qubit_gates"]
        if g["gate"] == "sx" and g["gate_error"] != 1
    ]
    cz = [
        g["gate_error"]
        for g in data["two_qubit_gates"]
        if g["gate"] == "cz" and g["gate_error"] != 1
    ]

    return (
        st.median(q["T1_us"] for q in qubits),
        st.median(q["T2_us"] for q in qubits),
        st.median(q["readout_error"] for q in qubits),
        st.median(sx),
        st.median(cz),
    )


def noise_model(fake_backend):
    """Calibration snapshot shipped with qiskit-ibm-runtime."""
    props = fake_backend().properties()

    t1, t2, readout = [], [], []
    for q in range(len(props.qubits)):
        try:
            qubit_t1, qubit_t2 = props.t1(q), props.t2(q)
        except Exception:
            continue
        if qubit_t1 is None or qubit_t2 is None:
            continue
        t1.append(qubit_t1 * 1e6)  # seconds -> microseconds
        t2.append(qubit_t2 * 1e6)
        readout.append(props.readout_error(q))

    sx, cz = [], []
    for gate in props.gates:
        error = next((p.value for p in gate.parameters if p.name == "gate_error"), None)
        if error is None or error == 1:
            continue
        if gate.gate == "sx":
            sx.append(error)
        if gate.gate == "cz":
            cz.append(error)

    return (
        st.median(t1),
        st.median(t2),
        st.median(readout),
        st.median(sx),
        st.median(cz),
    )


def calibration_row(device, source, values):
    t1, t2, readout, sx, cz = values
    return f"{device} & {source} & {t1:.0f} & {t2:.0f} & {readout:.4f} & {sx:.5f} & {cz:.4f} \\\\"


def calibration_table():
    rows = []
    for chip, name, fake in CHIPS:
        rows.append(calibration_row(name, "Hardware", hardware(chip)))
        rows.append(calibration_row("", "Noise model", noise_model(fake)))
        rows.append(r"\addlinespace")
    rows.pop()  # no space after the last device

    return "\n".join(
        [
            r"\begin{table}[h]",
            r"\centering",
            r"\caption{Experiment 1: calibration data of hardware and noise models}",
            r"\label{tab:exp1_calibration}",
            r"\begin{tabularx}{\textwidth}{@{}p{2.2cm}p{2.4cm}*{5}{>{\centering\arraybackslash}X}@{}}",
            r"\toprule",
            r" & & & & \multicolumn{3}{c}{Error rate} \\",
            r"\cmidrule(l){5-7}",
            r"Device & Source & $T_1$ (\si{\micro\second}) & $T_2$ (\si{\micro\second}) & Readout & SX, X & CZ \\",
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabularx}",
            r"\end{table}",
        ]
    )


# ---------------------------------------------------------------------------
# Transpiled circuits: gate counts of the hardware runs per optimisation level.
# If a value differs between the devices, the range min--max is shown.
# ---------------------------------------------------------------------------


def cell(values):
    low, high = min(values), max(values)
    return f"${low}$" if low == high else f"${low}$--${high}$"


def transpiled_table():
    rows = []
    for level in range(4):
        depth, cz, sx, x, rz = set(), set(), set(), set(), set()
        for path in glob.glob(f"{RESULTS}/*/*hardware*opt{level}_*.json"):
            circuit = json.load(open(path))["circuit"]["transpiled"]
            gates = circuit["gate_counts"]
            depth.add(circuit["depth"])
            cz.add(gates.get("cz", 0))
            sx.add(gates.get("sx", 0))
            x.add(gates.get("x", 0))
            rz.add(gates.get("rz", 0))
        rows.append(
            f"{level} & {cell(depth)} & {cell(cz)} & {cell(sx)} & {cell(x)} & {cell(rz)} \\\\"
        )

    return "\n".join(
        [
            r"\begin{table}[h]",
            r"\centering",
            r"\caption{Experiment 1: size of the transpiled circuit per optimisation level}",
            r"\label{tab:exp1_transpiled}",
            r"\begin{tabularx}{\textwidth}{@{}l*{5}{>{\centering\arraybackslash}X}@{}}",
            r"\toprule",
            r"Optimisation level & Depth & CZ & SX & X & RZ \\",
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabularx}",
            r"\end{table}",
        ]
    )


os.makedirs(OUT, exist_ok=True)
for name, text in (
    ("calibration", calibration_table()),
    ("transpiled", transpiled_table()),
):
    with open(f"{OUT}/{name}.tex", "w", encoding="utf-8") as file:
        file.write(text + "\n")
    print(text, "\n")
