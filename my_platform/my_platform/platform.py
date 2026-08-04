import pathlib

from qibolab import ConfigKinds
from qibolab._core.components import IqChannel
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
        )

    # Row AOD — same pattern, all tones share port ROW_CHANNEL
    for i in range(N_TWEEZERS):
        ch_id = f"row_selector_{i + 1:02d}"
        channels[ch_id] = IqChannel(
            device=f"{CON}/{LF_FEM1}",
            path=str(ROW_CHANNEL),
            mixer=None,
            lo=None,
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
