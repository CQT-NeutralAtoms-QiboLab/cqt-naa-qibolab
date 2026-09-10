"""Run the NAA platform ON REAL HARDWARE (Quantum Machines OPX1000).

Same experiment as `run_naa_no_hardware.py`, but connects to the instrument and
actually executes, returning acquired results. The instrument address is defined
in the platform itself (`naa/platform.py`, the `QmController(address=...)`), so it
does not need to be set here. Requires the OPX1000 to be reachable on the network.

Run (from the fork's environment, e.g. after
`source ../.venv-cqt-naa-qibolab/bin/activate`):

    python run_naa_hardware.py

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
from qibolab._core.sequence import PulseSequence

# 1) load the platform
platform = create_platform("naa")
print(f"loaded platform '{platform.name}'")

# 2) build a sequence: all 8 col + 8 row tones playing simultaneously, each
# optionally chirped at its own rate (Hz/nsec). Omit a channel here (or set its
# rate to None) to play it unchirped at its base frequency.
CHIRP_RATES = {
    "col_selector_01": 50_000,
    "col_selector_02": -50_000,
    "col_selector_03": 30_000,
    "col_selector_04": -30_000,
    "col_selector_05": 20_000,
    "col_selector_06": -20_000,
    "col_selector_07": 10_000,
    "col_selector_08": -10_000,
    "row_selector_01": 40_000,
    "row_selector_02": -40_000,
    "row_selector_03": 25_000,
    "row_selector_04": -25_000,
    "row_selector_05": 15_000,
    "row_selector_06": -15_000,
    "row_selector_07": 5_000,
    "row_selector_08": -5_000,
}

sequence = PulseSequence()
for i in range(1, 9):
    for axis in ("col", "row"):
        channel = f"{axis}_selector_{i:02d}"
        pulse = platform.parameters.pulses[channel]
        rate = CHIRP_RATES.get(channel)
        if rate is not None:
            pulse = pulse.model_copy(update={"chirp": (rate, "Hz/nsec")})
        sequence.append((channel, pulse))

# NOTE: this sequence only DRIVES tones; it contains no acquisition, so there is
# nothing to read back. To get data, add a readout on an acquisition channel, e.g.
#   from qibolab._core.pulses import Readout, Acquisition, Rectangular
#   sequence.append(("detector", Readout(
#       probe=Pulse(duration=172, amplitude=0.1, envelope=Rectangular()),
#       acquisition=Acquisition(duration=172))))

# 3) frequency sweep that starts at the tone's base frequency
# base = platform.parameters.configs["col_selector_02"].frequency
# sweeper = Sweeper(
#     parameter=Parameter.frequency,
#     channels=["col_selector_02"],
#     values=np.linspace(base, base + 10e6, 5),
# )

# 4) connect to the OPX1000, execute on hardware, then always disconnect
platform.connect()
try:
    results = platform.execute(
        [sequence], nshots=100, relaxation_time=1000
    )
    if results:
        print("execute() returned results for acquisitions:", list(results.keys()))
        for handle, data in results.items():
            print(f"  {handle}: shape={np.asarray(data).shape}")
    else:
        print("execute() ran on hardware; no acquisitions in the sequence "
              "(add a readout on 'detector'/'loopback' to get data).")
finally:
    platform.disconnect()
