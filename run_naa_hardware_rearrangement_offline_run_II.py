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

For BTC, the runner also saves the Python planner's intermediate and final predicted
occupations. These predictions exercise the same inputs used to build the QUA
program, but they are not OPX result streams and therefore do not prove that the QUA
program or physical atom transport produced the predicted result. For the measured
rearrangement result, run ``run_naa_hardware_rearrangement.py`` on the machine.

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
if context.get("sorter") != "btc" or "plan" not in context:
    raise RuntimeError(
        "This offline predicted-result figure requires the BTC 08 sorter. "
        "Set _BUILDER_FILE to 08_atom_btc_sorting.py."
    )

# Show the pack's layout AFTER sync (now reconciled to the platform's channels).
print(
    "[cfg AFTER  sync] "
    f"LF_COL={cfg.LF_COL} LF_ROW={cfg.LF_ROW} LF_TRIG={cfg.LF_TRIG} LF_RO={cfg.LF_RO} "
    f"LF_LOOPBACK={cfg.LF_LOOPBACK} total_tweezers={cfg.total_number_of_tweezers}"
)
print(f"col_AOD_1 port in cfg.config: {cfg.config['elements']['col_AOD_1']['singleInput']['port']}")

# 4) text: the BTC Python planner's inputs and predicted phase results.
plan = context["plan"]
print("\nTarget occupation:")
pack.print_2d(context["atom_target_occupation"])
print("Initial occupation:")
pack.print_2d(context["atom_initial_occupation"])
print("Predicted occupation after balance:")
pack.print_2d(plan["atom_intermediate_occupation"])
print("Predicted final occupation:")
pack.print_2d(plan["atom_final_occupation"])

# 5) image: requested BTC summary order. ``current`` preserves the established
#    colour encoding that distinguishes surplus atoms outside the target.
plt = pack.plt
predicted_current = pack.atom_occupation_matrix(
    "current",
    atom_initial_occupation=context["atom_initial_occupation"],
    atom_target_occupation=context["atom_target_occupation"],
    atom_final_occupation=np.minimum(
        np.asarray(plan["atom_final_occupation"]),
        1,
    ),
)
panels = (
    ("Target", context["atom_target_occupation"]),
    ("Initial", context["atom_initial_occupation"]),
    ("After balance", plan["atom_intermediate_occupation"]),
    ("Predicted Final", predicted_current),
)
fig, axes = plt.subplots(1, len(panels), figsize=(20, 5))
for ax, (title, occupation) in zip(np.atleast_1d(axes).ravel(), panels):
    pack.plot_atom_occupation_matrix(
        np.asarray(occupation),
        ax=ax,
        title=title,
    )
fig.tight_layout()
image_path = cfg.save_dir / "rearrangement_offline_II_initial_target_predicted.png"
fig.savefig(image_path, dpi=150)
print(f"\nSaved BTC predicted-result image to {image_path}")

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
print(
    "\nOffline dry-run (through sync) done. The displayed final occupation is "
    "Python-predicted; a measured result requires a real OPX run."
)
