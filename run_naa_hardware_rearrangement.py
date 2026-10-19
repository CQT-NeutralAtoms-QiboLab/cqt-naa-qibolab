"""Run NAA atom rearrangement ON REAL HARDWARE (Quantum Machines OPX1000).

Template for conducting a neutral-atom rearrangement through the qibolab NAA
platform via the ``rearrange_atoms`` command: the existing QUA sorting engine is
run over the platform's own connection (the controller seam), against the
platform-owned superset config. Requires the OPX1000 to be reachable on the
network (the address lives in ``naa/platform.py``).

Run (from the fork's environment, e.g. after
`source ../.venv-cqt-naa-qibolab/bin/activate`):

    python run_naa_hardware_rearrangement.py

Assumes `cqt-naa-qibolab` and `qibolab_platforms_naa` are sibling directories.
"""
import os
import pathlib
import sys

# Point qibolab at the platform repo (a sibling of this fork) and make its
# operations package importable. Set here so the script runs standalone.
_PLATFORMS = pathlib.Path(__file__).resolve().parents[1] / "qibolab_platforms_naa"
os.environ["QIBOLAB_PLATFORMS"] = str(_PLATFORMS)
sys.path.insert(0, str(_PLATFORMS / "operations"))

import numpy as np

from qibolab import create_platform
from platform_operations import _load_qm_sorting, rearrange_atoms

# Common post-processing helpers from whichever sorter _BUILDER_FILE selects.
_cfg, _pack = _load_qm_sorting()
nb_of_cols = _cfg.nb_of_cols
atom_occupation_matrix = _pack.atom_occupation_matrix
plot_atom_occupation_matrix = _pack.plot_atom_occupation_matrix
print_2d = _pack.print_2d
OCCUPATION_MATRIX_KINDS = _pack.OCCUPATION_MATRIX_KINDS
plt = _pack.plt

# 1) load the platform (create() also builds the superset config)
platform = create_platform("naa")
print(f"loaded platform '{platform.name}'")

# 2) connect to the OPX1000; always disconnect at the end
platform.connect()
try:
    # --- (optional) a normal execute() can run first, in the SAME open session ---
    # Because both paths run against the one superset config, an execute() and the
    # rearrangement below share a single open machine (no reopen in between):
    #
    #   from qibolab._core.pulses import Gaussian, Pulse
    #   from qibolab._core.sequence import PulseSequence
    #   seq = PulseSequence()
    #   seq.append(("col_selector_02", Pulse(
    #       duration=8000, amplitude=0.167,
    #       envelope=Gaussian(rel_sigma=0.5), chirp=(200e5, "Hz/nsec"))))
    #   platform.execute([seq], [], nshots=100, relaxation_time=1000)

    # 3) rearrangement: the existing QUA sorting engine, run via the seam against
    #    the platform's superset config. seed=42 -> reproducible initial random occupation for now.
    job, context = rearrange_atoms(platform, seed=42)

    # 4) fetch the sorting program's own result streams
    res = job.result_handles
    res.wait_for_all_values()
    data = res.get("data").fetch_all()["value"]
    count = res.get("count").fetch_all()["value"]
    raw = (
        res.get("raw_data").fetch_all()["value"]
        if context["raw_adc_acquisition"]
        else None
    )

    # 5) reconstruct through the common 07/08 result contract.
    reconstructed = _pack.reconstruct_platform_result(
        data=data,
        count=count,
        context=context,
    )
    atom_occupation = reconstructed["atom_final_occupation"]

    # 6a) text: initial / target / final occupation grids (0 = empty, 1 = atom)
    print("Initial occupation:")
    print_2d(context["atom_initial_occupation"])
    print("Target occupation:")
    print_2d(context["atom_target_occupation"])
    print("Final occupation:")
    print_2d(atom_occupation)
    if reconstructed["atom_intermediate_occupation"] is not None:
        print("Intermediate occupation (after BTC balance phase):")
        print_2d(reconstructed["atom_intermediate_occupation"])

    # 6b) image: initial / target / current occupation matrices
    occ = dict(
        atom_initial_occupation=context["atom_initial_occupation"],
        atom_target_occupation=context["atom_target_occupation"],
        atom_final_occupation=atom_occupation,
    )
    fig, axes = plt.subplots(1, len(OCCUPATION_MATRIX_KINDS), figsize=(15, 5))
    for ax, kind in zip(np.atleast_1d(axes).ravel(), OCCUPATION_MATRIX_KINDS):
        plot_atom_occupation_matrix(
            atom_occupation_matrix(kind, **occ), ax=ax, title=kind.capitalize()
        )
    fig.tight_layout()
    image_path = _cfg.save_dir / "rearrangement_occupation.png"
    fig.savefig(image_path, dpi=150)
    print(f"Saved occupation-matrix image to {image_path}")
    plt.show()  # uncomment for an interactive window instead of (or besides) the file

    # Raw ADC is a legacy transport diagnostic, not an occupation measurement.
    # To collect it explicitly, call rearrange_atoms(..., raw_adc_acquisition=True)
    # and inspect ``raw`` with sorter-specific diagnostic plotting helpers.
finally:
    platform.disconnect()
