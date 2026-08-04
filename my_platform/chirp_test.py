# chirp_test.py
import os
os.environ["QIBOLAB_PLATFORMS"] = "/Users/dpsso/Desktop/cqt-naa-qibolab/my_platform"

from qibolab import create_platform
from qibolab._core.pulses import Pulse, Rectangular
from qibolab._core.sequence import PulseSequence
from qibolab._core.execution_parameters import (
    ExecutionParameters, AcquisitionType, AveragingMode,
)

platform = create_platform("my_platform")
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
    # acquisition_type=AcquisitionType.INTEGRATION,
    # averaging_mode=AveragingMode.CYCLIC,
)

results = platform.execute([sequence], options)
platform.disconnect()