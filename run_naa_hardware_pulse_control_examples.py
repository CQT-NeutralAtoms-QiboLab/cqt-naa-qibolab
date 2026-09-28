"""Pulse-control showcase for the NAA platform ON REAL HARDWARE (QM OPX1000).

Three short, self-contained examples of driving the neutral-atom AOD tones with
the normal Qibolab ``execute()`` path (the same path the chirp in
`run_naa_hardware_original.py` uses). This is an instructive script: each example
builds a ``PulseSequence``, runs it, and prints what came back. Read them top to
bottom — they go from "just drive a tone" to "drive + read data" to "sweep and
read a curve".

  Example 1 — drive only:        a chirped Gaussian on one column tone (no data)
  Example 2 — drive + acquire:   drive a tone, then read it back on 'detector'
  Example 3 — sweep + acquire:   step a tone's frequency and read at each point

What each Qibolab piece is:
  - PulseSequence : an ordered list of (channel_name, pulse) items to play.
  - Pulse         : an analog waveform on a ToneChannel (envelope + amplitude +
                    duration, optionally chirped). Its NCO frequency comes from
                    the channel's ToneConfig in parameters.json.
  - Readout       : a probe Pulse plus an Acquisition, played on an
                    AcquisitionChannel; this is what produces returned data.
  - Sweeper       : repeat the sequence while stepping one parameter (here the
                    channel frequency) over a list of values.

Run (from the fork's environment, e.g. after
`source ../.venv-cqt-naa-qibolab/bin/activate`):

    python run_naa_hardware_pulse_control_examples.py

Assumes `cqt-naa-qibolab` and `qibolab_platforms_naa` are sibling directories.
The instrument address lives in the platform (`naa/platform.py`), so it is not
set here. Requires the OPX1000 to be reachable on the network.
"""
import os
import pathlib

# Point qibolab at the platform repo (a sibling of this fork). Set here
# authoritatively so the script runs standalone — no terminal export needed, and
# any unrelated QIBOLAB_PLATFORMS in your shell is ignored (this process only).
_PLATFORMS = pathlib.Path(__file__).resolve().parents[1] / "qibolab_platforms_naa"
os.environ["QIBOLAB_PLATFORMS"] = str(_PLATFORMS)

import numpy as np

from qibolab import create_platform
from qibolab._core.pulses import Acquisition, Gaussian, Pulse, Readout, Rectangular
from qibolab._core.sequence import PulseSequence
from qibolab._core.sweeper import Parameter, Sweeper


def _print_results(results):
    """Pretty-print whatever execute() returned."""
    if results:
        print("  got acquisitions:", list(results.keys()))
        for handle, data in results.items():
            print(f"    {handle}: shape={np.asarray(data).shape}")
    else:
        print("  ran on hardware; no acquisitions in this sequence, nothing to read.")

# --- Example 1: drive one tone (no acquisition) ------------------------------
def example_1_drive_only(platform):
    """Play a chirped Gaussian on column tone 02. Drives the AOD; reads nothing.

    The simplest thing you can do: put one shaped, frequency-chirped pulse on one tone.
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

# --- Example 2: drive + acquire (read data back) -----------------------------
def example_2_drive_and_acquire(platform):
    """Drive a column tone, then read it back on the 'detector' channel.

    A Readout = a probe Pulse + an Acquisition, played on an AcquisitionChannel.
    'detector' probes 'col_selector_01' (see naa/platform.py), so this actually
    returns data, keyed by the acquisition's handle.
    """
    print("[2] drive+acquire: rectangular probe read on 'detector'")
    sequence = PulseSequence()
    # Drive: a plain rectangular pulse on a column tone.
    sequence.append(("col_selector_01", Pulse(
        duration=1000,
        amplitude=0.1,
        envelope=Rectangular(),
    )))
    # Read: probe + acquisition on the detector (same duration = measure window).
    sequence.append(("detector", Readout(
        probe=Pulse(duration=172, amplitude=0.1, envelope=Rectangular()),
        acquisition=Acquisition(duration=172),
    )))
    results = platform.execute([sequence], nshots=100, relaxation_time=1000)
    _print_results(results)

# --- Example 3: sweep a frequency + acquire ----------------------------------
def example_3_frequency_sweep(platform):
    """Step a tone's frequency over 5 points and read the detector at each.

    A Sweeper repeats the sequence while walking one channel's frequency; the
    returned array's leading axis is the sweep. Start at the tone's base
    frequency (from parameters.json) and step up 10 MHz.
    """
    print("[3] sweep+acquire: 5-point frequency sweep on col_selector_01")
    sequence = PulseSequence()
    sequence.append(("col_selector_01", Pulse(
        duration=1000, amplitude=0.1, envelope=Rectangular(),
    )))
    sequence.append(("detector", Readout(
        probe=Pulse(duration=172, amplitude=0.1, envelope=Rectangular()),
        acquisition=Acquisition(duration=172),
    )))
    base = platform.parameters.configs["col_selector_01"].frequency
    sweeper = Sweeper(
        parameter=Parameter.frequency,
        channels=["col_selector_01"],
        values=np.linspace(base, base + 10e6, 5),
    )
    results = platform.execute(
        [sequence], [[sweeper]], nshots=100, relaxation_time=1000
    )
    _print_results(results)

def main():
    platform = create_platform("naa")
    print(f"loaded platform '{platform.name}'\n")

    # connect once; run all three examples; always disconnect.
    platform.connect()
    try:
        example_1_drive_only(platform)
        example_2_drive_and_acquire(platform)
        example_3_frequency_sweep(platform)
    finally:
        platform.disconnect()


if __name__ == "__main__":
    main()
