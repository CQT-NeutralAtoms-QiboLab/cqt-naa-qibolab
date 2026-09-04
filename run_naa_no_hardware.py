"""Run the NAA platform WITHOUT hardware.

Loads the `naa` platform, builds a chirped-Gaussian pulse plus a frequency sweep
(coupled to the tone's base frequency) on column tone 02, and calls
`platform.execute()`. With no OPX1000 connected, the QM driver returns the
compiled {"program", "config"} instead of executing on the instrument.

Run (from the fork's environment, e.g. after
`source ../.venv-cqt-naa-qibolab/bin/activate`):

    python run_naa_no_hardware.py

Assumes `cqt-naa-qibolab` and `qibolab_platforms_naa` are sibling directories.
"""
import os
import pathlib

# Point qibolab at the platform repo (a sibling of this fork). Set it here
# authoritatively so this script runs standalone — no terminal export needed, and
# any unrelated QIBOLAB_PLATFORMS in your shell profile is ignored (this only
# affects THIS process, not your environment).
_PLATFORMS = pathlib.Path(__file__).resolve().parents[1] / "qibolab_platforms_naa"
os.environ["QIBOLAB_PLATFORMS"] = str(_PLATFORMS)

import numpy as np

from qibolab import create_platform
from qibolab._core.pulses import Gaussian, Pulse
from qibolab._core.sequence import PulseSequence
from qibolab._core.sweeper import Parameter, Sweeper

# 1) load the platform
platform = create_platform("naa")
print(f"loaded platform '{platform.name}' "
      f"with {len(platform.instruments['con1'].channels)} channels")

# 2) build a sequence: a chirped Gaussian on column tone 02
sequence = PulseSequence()
sequence.append(("col_selector_02", Pulse(
    duration=8000,
    amplitude=0.167,
    envelope=Gaussian(rel_sigma=0.5),
    chirp=(200e5, "Hz/nsec"),
)))

# 3) frequency sweep that STARTS at the tone's base frequency
#    (base and sweep range are physically coupled — the base is where the tone rests)
base = platform.parameters.configs["col_selector_02"].frequency
sweeper = Sweeper(
    parameter=Parameter.frequency,
    channels=["col_selector_02"],
    values=np.linspace(base, base + 10e6, 5),
)

# 4) execute. NOT connected -> the QM driver returns the compiled program + config
result = platform.execute([sequence], [[sweeper]], nshots=100, relaxation_time=1000)
print("execute() returned:", list(result.keys()))
print("col_selector_02 base IF in generated config:",
      result["config"]["elements"]["col_selector_02"]["intermediate_frequency"])
