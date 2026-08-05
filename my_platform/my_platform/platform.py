import pathlib

from qibolab import ConfigKinds
from qibolab._core.components import DigitalChannel, IqChannel
from qibolab._core.instruments.qm import QmController
from qibolab._core.instruments.qm.components import OpxOutputConfig, QmAcquisitionConfig
from qibolab._core.platform import Platform

FOLDER = pathlib.Path(__file__).parent

# FEM slot assignments matching reference config (configuration_opx1000_mwfem_lffem.py)
CON = "con1"
LF_FEM1 = 1    # LF-FEM: col AOD (port 1) + row AOD (port 2) + readout + trigger
LF_FEM2 = 2    # LF-FEM: spare / additional DC outputs

# Analog output ports on LF_FEM1 (matching reference)
COL_CHANNEL = 1
ROW_CHANNEL = 2

# Digital (TTL) trigger output ports on LF_FEM1 — must not collide with the
# analog COL/ROW ports above.
TRIG_CHANNELS = [3, 4]

# Number of tweezers per axis (reference uses 8; 3 here for testing)
N_TWEEZERS = 3

# ConfigKinds.extend([OpxOutputConfig, QmAcquisitionConfig])


def create() -> Platform:
    channels = {}

    # Col AOD — all N_TWEEZERS tones share the SAME physical port (COL_CHANNEL).
    # Each tone element gets its own intermediate_frequency from parameters.json.
    # Pulses are addressed directly via parameters.pulses[channel_id] — no
    # Qubit/native-gate wrapping needed.
    for i in range(N_TWEEZERS):
        ch_id = f"col_selector_{i + 1:02d}"
        channels[ch_id] = IqChannel(
            device=f"{CON}/{LF_FEM1}",
            path=str(COL_CHANNEL),
            mixer=None,
            lo=None,
            core=f"col_AOD_{i + 1}",
        )

    # Row AOD — same pattern, all tones share port ROW_CHANNEL
    for i in range(N_TWEEZERS):
        ch_id = f"row_selector_{i + 1:02d}"
        channels[ch_id] = IqChannel(
            device=f"{CON}/{LF_FEM1}",
            path=str(ROW_CHANNEL),
            mixer=None,
            lo=None,
            core=f"row_AOD_{i + 1}",
        )

    # Trigger — TTL outputs, one dedicated port each (no sharing, so no core needed).
    for i, port in enumerate(TRIG_CHANNELS):
        ch_id = f"trig_{i + 1:02d}"
        channels[ch_id] = DigitalChannel(
            device=f"{CON}/{LF_FEM1}",
            path=str(port),
        )

    instruments = {
        CON: QmController(
            address="192.168.88.249",
            fems={
                f"{CON}/{LF_FEM1}": "LF",
                f"{CON}/{LF_FEM2}": "LF",
            },
            channels=channels,
        )
    }

    return Platform.load(
        path=FOLDER,
        instruments=instruments,
        qubits={},
    )


def build_config(platform: Platform) -> dict:
    """Drive every channel through the QM config-builder.

    Mirrors what ``QmController.play()`` does internally to populate
    ``controller.config``, without needing a real instrument connection.
    """
    from qibolab._core.sequence import PulseSequence

    controller = platform.instruments[CON]
    configs = platform.parameters.configs

    # elements first: register_pulses (below) attaches operations onto
    # elements that must already exist in controller.config.elements.
    for ch_id in controller.channels:
        if ch_id in configs:
            controller.configure_channel(ch_id, configs)

    sequence = PulseSequence(
        (ch_id, pulse)
        for ch_id, pulse in platform.parameters.pulses.items()
        if ch_id in controller.channels
    )
    controller.register_pulses(configs, sequence)

    return controller.config.asdict()


if __name__ == "__main__":
    import json

    from qibolab._core.execution_parameters import ExecutionParameters
    from qibolab._core.pulses import Pulse, Rectangular
    from qibolab._core.sequence import PulseSequence

    platform = create()

    qua_config = build_config(platform)
    out = FOLDER / "generated_qua_config.json"
    out.write_text(json.dumps(qua_config, indent=2, default=str))
    print(f"QUA config written to: {out}")

    platform.connect()

    sequence = PulseSequence()

    # Option A: re-use the pulse defined in parameters.json
    # (platform.parameters.pulses is the dict loaded from the json)
    col1_pulse = platform.parameters.pulses["col_selector_01"].model_copy(
        update={"chirp": (1e6, "Hz/nsec")}
    )
    sequence.append(("col_selector_01", col1_pulse))

    # Option B: build a fresh Pulse inline
    col2_pulse = Pulse(
        duration=800,
        amplitude=0.167,
        envelope=Rectangular(),
        chirp=(2e6, "Hz/nsec"),
    )
    sequence.append(("col_selector_02", col2_pulse))

    # Fire them on a few tones in parallel
    sequence.append(("row_selector_01", platform.parameters.pulses["row_selector_01"]))

    options = ExecutionParameters(
        nshots=200,
        relaxation_time=500_000,
    )

    results = platform.execute([sequence], options)
    platform.disconnect()
