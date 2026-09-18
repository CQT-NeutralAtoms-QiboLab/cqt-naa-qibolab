"""Offline dry-run of the NAA rearrangement (NO hardware, NO connection).

Builds the rearrangement QUA program and its context, prints the initial and target
occupation grids, saves an initial/target image, and confirms the superset config
assembles — all on your laptop, without reaching the OPX.

It CANNOT show the FINAL occupation: that is reconstructed from a real run's result
streams (``data``/``count``), which only exist after executing on the OPX. For the
full rearrangement (including the final matrix and spectrograms) run
``run_naa_hardware_rearrangement.py`` on the machine.

Run:  python run_naa_hardware_rearrangement_offline_run.py
"""
import os
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")  # headless-safe: this is an offline dry-run, images are saved

# Point qibolab at the platform repo (sibling of this fork) and make its operations
# package importable. Set here so the script runs standalone.
_PLATFORMS = pathlib.Path(__file__).resolve().parents[1] / "qibolab_platforms_naa"
os.environ["QIBOLAB_PLATFORMS"] = str(_PLATFORMS)
sys.path.insert(0, str(_PLATFORMS / "operations"))

import numpy as np

from qibolab import create_platform
from qm import generate_qua_script

import platform_operations as ops

SEED = 42

# 1) load the platform (create() builds the superset config; no connection needed)
platform = create_platform("naa")
controller = ops._get_qm_controller(platform)
print(f"loaded platform '{platform.name}'")
print(f"superset_config set at build: {controller.superset_config is not None}")

# 2) build the rearrangement program + context (no connection, no hardware)
cfg, pack = ops._load_qm_sorting()
col_names, row_name, det_name = ops._platform_element_names(controller)
program, context = ops.build_qm_sorting_program(
    cfg,
    pack,
    col_element_names=col_names,
    row_element_name=row_name,
    detector_element_name=det_name,
    seed=SEED,
)

# 3) text: initial and target occupation grids (0 = empty, 1 = atom).
#    The FINAL grid is intentionally absent — it needs a real run on the OPX.
print("\nInitial occupation:")
pack.print_2d(context["atom_initial_occupation"])
print("Target occupation:")
pack.print_2d(context["atom_target_occupation"])

# 4) image: initial and target occupation matrices (two panels; no final offline)
plt = pack.plt
fig, axes = plt.subplots(1, 2, figsize=(10, 5))
pack.plot_atom_occupation_matrix(
    np.asarray(context["atom_initial_occupation"]), ax=axes[0], title="Initial"
)
pack.plot_atom_occupation_matrix(
    np.asarray(context["atom_target_occupation"]), ax=axes[1], title="Target"
)
fig.tight_layout()
image_path = cfg.save_dir / "rearrangement_offline_initial_target.png"
fig.savefig(image_path, dpi=150)
print(f"\nSaved initial/target image to {image_path}")

# 5) confirm the superset assembles (grammar check only, NOT a QOP compile)
text = generate_qua_script(program, controller.superset_config)
cores = {
    e.get("core")
    for e in controller.superset_config["elements"].values()
    if e.get("core")
}
print(
    f"superset assembles: generate_qua_script OK ({len(text.splitlines())} lines); "
    f"distinct cores = {len(cores)} (LF-FEM budget 16)"
)
print("\nOffline dry-run done. Final occupation requires a real run on the OPX.")
