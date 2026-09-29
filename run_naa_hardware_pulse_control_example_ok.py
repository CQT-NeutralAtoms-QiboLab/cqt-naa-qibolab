"""Pulse-control showcase for the NAA platform ON REAL HARDWARE (QM OPX1000).

1 short, self-contained example of driving the neutral-atom AOD tones with
the normal Qibolab ``execute()`` path. This is an instructive script: the example
builds a ``PulseSequence``, runs it, and prints what came back. 

What each Qibolab piece is:
  - PulseSequence : an ordered list of (channel_name, pulse) items to play.
  - Pulse         : an analog waveform on a ToneChannel (envelope + amplitude +
                    duration, optionally chirped). Its NCO frequency comes from
                    the channel's ToneConfig in parameters.json.

Run (from the fork's environment, e.g. after
`source ../.venv-cqt-naa-qibolab/bin/activate`):

    python run_naa_hardware_pulse_control_examples.py

Assumes `cqt-naa-qibolab` and `qibolab_platforms_naa` are sibling directories.
The instrument address lives in the platform (`naa/platform.py`), so it is not
set here. Requires the OPX1000 to be reachable on the network.
"""
import os
import pathlib
import numpy as np

# Point qibolab at the platform repo (a sibling of this fork).
_PLATFORMS = pathlib.Path(__file__).resolve().parents[1] / "qibolab_platforms_naa"
os.environ["QIBOLAB_PLATFORMS"] = str(_PLATFORMS)

from qibolab import create_platform
from qibolab._core.pulses import Pulse, Gaussian, Rectangular
from qibolab._core.sequence import PulseSequence

def _print_results(results):
    """Pretty-print whatever execute() returned."""
    if results:
        print("results:", list(results.keys()))
        for handle, data in results.items():
            print(f"    {handle}: shape={np.asarray(data).shape}")
    else:
        print("  ran on hardware; no acquisitions in this sequence, nothing to read.")

def play_chirp(platform):
    """Play a chirped Gaussian on column tone 02. Drives the AOD; reads nothing.

    The simplest thing you can do: put one shaped, frequency-chirped
    pulse on one tone.
    """
    print("[1] drive-only: chirped Gaussian on col_selector_02")
    sequence = PulseSequence()
    sequence.append(("col_selector_02", Pulse(
        duration=8000,
        amplitude=0.167,
        envelope=Gaussian(rel_sigma=0.5),
        chirp=(200e5, "Hz/nsec"),
    )))
    results = platform.execute([sequence], nshots=100, relaxation_time=1000)
    _print_results(results)

def main():
    platform = create_platform("naa")
    print(f"loaded platform '{platform.name}'\n")

    # connect once; run pulses; disconnect.
    platform.connect()
    try:
        play_chirp(platform)
        # Add any other pulses here
    finally:
        platform.disconnect()


if __name__ == "__main__":
    main()
