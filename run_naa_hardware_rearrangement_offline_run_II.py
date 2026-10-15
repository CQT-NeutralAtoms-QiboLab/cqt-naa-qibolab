"""Offline dry-run of NAA rearrangement THROUGH ``rearrange_atoms()`` (NO hardware).

Companion to ``run_naa_hardware_rearrangement_offline_run.py``. That script calls the
low-level ``build_qm_sorting_program`` directly, so it exercises the pack's DEFAULT
(import-time) config and never runs ``sync_cfg_from_platform``. This one instead calls
the real ``rearrange_atoms(platform)`` command, whose first step is
``sync_cfg_from_platform`` — so it is the offline gate that actually goes THROUGH sync.

``rearrange_atoms`` ends by executing on the OPX via
``controller.execute_raw_qua(program, config)``, which needs a live connection. To stay
offline we replace ONLY that final execute step with a stub that validates the program
against the superset config (``generate_qua_script``) and returns a placeholder job.
Everything before it — the sync and the program build — runs for real.

It CANNOT show the FINAL occupation (that needs a real run's result streams). For the
full rearrangement run ``run_naa_hardware_rearrangement.py`` on the machine.

Run:  python run_naa_hardware_rearrangement_offline_run_II.py
"""
import os
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")  # headless-safe: offline dry-run, images are saved

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
cfg, pack = ops._load_qm_sorting()
print(f"loaded platform '{platform.name}'")
print(f"superset_config set at build: {controller.superset_config is not None}")

# Show the pack's layout BEFORE sync (these are configuration.py defaults).
print(
    "\n[cfg BEFORE sync] "
    f"LF_COL={cfg.LF_COL} LF_ROW={cfg.LF_ROW} LF_RO={cfg.LF_RO} "
    f"LF_LOOPBACK={cfg.LF_LOOPBACK} total_tweezers={cfg.total_number_of_tweezers}"
)

# 2) stub ONLY the hardware-execute step so rearrange_atoms() runs offline. The stub
#    still validates the built program against the config it would run on.
_assembled = {}


def _offline_execute_raw_qua(program, config=None):
    cfg_used = config if config is not None else controller.superset_config
    _assembled["text"] = generate_qua_script(program, cfg_used)
    return "<offline-no-job>"


controller.execute_raw_qua = _offline_execute_raw_qua

# 3) run the REAL command. Its first step is sync_cfg_from_platform(platform); the
#    final execute is our offline stub.
job, context = ops.rearrange_atoms(platform, seed=SEED)
print(f"selected sorter: {context['sorter']}")

# Show the pack's layout AFTER sync (now reconciled to the platform's channels).
print(
    "[cfg AFTER  sync] "
    f"LF_COL={cfg.LF_COL} LF_ROW={cfg.LF_ROW} LF_TRIG={cfg.LF_TRIG} LF_RO={cfg.LF_RO} "
    f"LF_LOOPBACK={cfg.LF_LOOPBACK} total_tweezers={cfg.total_number_of_tweezers}"
)
print(f"col_AOD_1 port in cfg.config: {cfg.config['elements']['col_AOD_1']['singleInput']['port']}")

# 4) text: initial and target occupation grids (0 = empty, 1 = atom).
#    The FINAL grid is intentionally absent — it needs a real run on the OPX.
print("\nInitial occupation:")
pack.print_2d(context["atom_initial_occupation"])
print("Target occupation:")
pack.print_2d(context["atom_target_occupation"])

# 5) image: initial and target occupation matrices (two panels; no final offline)
plt = pack.plt
fig, axes = plt.subplots(1, 2, figsize=(10, 5))
pack.plot_atom_occupation_matrix(
    np.asarray(context["atom_initial_occupation"]), ax=axes[0], title="Initial"
)
pack.plot_atom_occupation_matrix(
    np.asarray(context["atom_target_occupation"]), ax=axes[1], title="Target"
)
fig.tight_layout()
image_path = cfg.save_dir / "rearrangement_offline_II_initial_target.png"
fig.savefig(image_path, dpi=150)
print(f"\nSaved initial/target image to {image_path}")

# 6) confirm the superset assembles (grammar check only, NOT a QOP compile). The stub
#    already ran generate_qua_script; report its size and the distinct cores.
text = _assembled["text"]
cores = {
    e.get("core")
    for e in controller.superset_config["elements"].values()
    if e.get("core")
}
print(
    f"superset assembles (via rearrange_atoms): generate_qua_script OK "
    f"({len(text.splitlines())} lines); distinct cores = {len(cores)} (LF-FEM budget 16)"
)
print("\nOffline dry-run (through sync) done. Final occupation requires a real run on the OPX.")
