"""
Tests for the LF-FEM tone and TTL/digital additions in cqt-naa-qibolab.

Level 1 — unit:    dataclass correctness (no hardware, no platform)
Level 2 — config:  configure_lf_fem_tone_line writes correct entries
Level 3 — platform: neutral_atom_array platform loads and is coherent

Run from the repo root:
    pytest tests/instruments/qm/test_lf_fem.py -v
"""

import importlib.util
import json
import pathlib
from dataclasses import asdict

import pytest

from qibolab._core.components import IqChannel, IqConfig
from qibolab._core.components.channels import DigitalChannel
from qibolab._core.instruments.qm.config.config import Configuration
from qibolab._core.instruments.qm.config.devices import LfFemOutput
from qibolab._core.instruments.qm.config.elements import DigitalElement, LfFemToneElement

PLATFORM_DIR = pathlib.Path(__file__).parents[3] / "platforms" / "neutral_atom_array"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _lf_fem_config() -> Configuration:
    """Configuration with one LF-FEM controller pre-registered on con1/1."""
    cfg = Configuration()
    cfg.add_controller("con1/1", {"con1/1": "LF"})
    return cfg


def _load_platform():
    """Load platforms/neutral_atom_array without needing QIBOLAB_PLATFORMS."""
    spec = importlib.util.spec_from_file_location(
        "neutral_atom_array_platform", PLATFORM_DIR / "platform.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.create()


# ===========================================================================
# LEVEL 1 — unit tests: do the dataclasses produce the right QUA fields?
# ===========================================================================

class TestLfFemToneElement:
    """LF-FEM tone element must be singleInput (analog) and carry a frequency."""

    def test_uses_single_input_not_mw_input(self):
        ch = IqChannel(device="con1/1", path="5", mixer=None, lo=None)
        el = LfFemToneElement.from_channel(ch, intermediate_frequency=50_000_000)
        assert "singleInput" in el.__dict__
        assert "MWInput" not in el.__dict__

    def test_carries_the_correct_frequency(self):
        ch = IqChannel(device="con1/1", path="5", mixer=None, lo=None)
        el = LfFemToneElement.from_channel(ch, intermediate_frequency=50_000_000)
        assert el.intermediate_frequency == 50_000_000

    def test_port_tuple_is_opx1000_form(self):
        # device="con1/1" + port 5  →  ("con1", 1, 5)
        ch = IqChannel(device="con1/1", path="5", mixer=None, lo=None)
        el = LfFemToneElement.from_channel(ch, intermediate_frequency=50_000_000)
        assert el.singleInput["port"] == ("con1", 1, 5)

    def test_operations_dict_starts_empty(self):
        ch = IqChannel(device="con1/1", path="5", mixer=None, lo=None)
        el = LfFemToneElement.from_channel(ch, intermediate_frequency=50_000_000)
        assert el.operations == {}


class TestDigitalElement:
    """TTL/digital element must use digitalInputs and carry NO frequency."""

    def test_uses_digital_inputs(self):
        ch = DigitalChannel(device="con1/1", path="1")
        el = DigitalElement.from_channel(ch)
        assert "digitalInputs" in el.__dict__
        assert "singleInput" not in el.__dict__
        assert "MWInput" not in el.__dict__

    def test_has_no_intermediate_frequency(self):
        ch = DigitalChannel(device="con1/1", path="1")
        el = DigitalElement.from_channel(ch)
        assert not hasattr(el, "intermediate_frequency")

    def test_port_embedded_in_digital_inputs(self):
        # device="con1/1" + port 1  →  ("con1", 1, 1)
        ch = DigitalChannel(device="con1/1", path="1")
        el = DigitalElement.from_channel(ch)
        port = el.digitalInputs["trigger"]["port"]
        assert port == ("con1", 1, 1)

    def test_delay_and_buffer_default_to_zero(self):
        ch = DigitalChannel(device="con1/1", path="1")
        el = DigitalElement.from_channel(ch)
        assert el.digitalInputs["trigger"]["delay"] == 0
        assert el.digitalInputs["trigger"]["buffer"] == 0


class TestLfFemOutput:
    """LfFemOutput must default-fill when given an IqConfig (no LO fields)."""

    def test_from_config_uses_defaults_for_iq_config(self):
        out = LfFemOutput.from_config(IqConfig(frequency=100e6))
        assert out.sampling_rate == 1e9
        assert out.output_mode == "direct"
        assert out.offset == 0.0
        assert out.upsampling_mode == "mw"

    def test_update_accepts_matching_settings(self):
        out = LfFemOutput(offset=0.0, sampling_rate=1e9, output_mode="direct")
        # IqConfig has no sampling_rate/output_mode; getattr returns matching defaults
        out.update(IqConfig(frequency=100e6))  # must not raise

    def test_update_rejects_conflicting_sampling_rate(self):
        # port already registered at 2 GSps; new tone at 1 GSps default → conflict
        out = LfFemOutput(offset=0.0, sampling_rate=2e9, output_mode="direct")
        with pytest.raises(AssertionError):
            out.update(IqConfig(frequency=100e6))

    def test_update_rejects_conflicting_output_mode(self):
        out = LfFemOutput(offset=0.0, sampling_rate=1e9, output_mode="amplified")
        with pytest.raises(AssertionError):
            out.update(IqConfig(frequency=100e6))  # default is "direct"


# ===========================================================================
# LEVEL 2 — config tests: configure_lf_fem_tone_line writes correct entries
# ===========================================================================

class TestConfigureLfFemToneLine:

    def test_creates_element_with_correct_frequency(self):
        cfg = _lf_fem_config()
        ch = IqChannel(device="con1/1", path="5", mixer=None, lo=None)
        cfg.configure_lf_fem_tone_line("atom_0/drive", ch, IqConfig(frequency=50e6))
        assert "atom_0/drive" in cfg.elements
        assert cfg.elements["atom_0/drive"].intermediate_frequency == 50_000_000

    def test_analog_output_registered_for_port(self):
        cfg = _lf_fem_config()
        ch = IqChannel(device="con1/1", path="5", mixer=None, lo=None)
        cfg.configure_lf_fem_tone_line("atom_0/drive", ch, IqConfig(frequency=50e6))
        controller = cfg.controllers["con1/1"]
        assert 5 in controller.analog_outputs

    def test_element_uses_single_input(self):
        cfg = _lf_fem_config()
        ch = IqChannel(device="con1/1", path="5", mixer=None, lo=None)
        cfg.configure_lf_fem_tone_line("atom_0/drive", ch, IqConfig(frequency=50e6))
        el = cfg.elements["atom_0/drive"]
        assert hasattr(el, "singleInput")
        assert not hasattr(el, "MWInput")

    def test_multitone_same_port_distinct_frequencies(self):
        """THE multitone check: 3 tones on port 5 → 1 analog_outputs entry, 3 elements."""
        cfg = _lf_fem_config()
        ch = IqChannel(device="con1/1", path="5", mixer=None, lo=None)
        tones = {
            "aod/tone_0": 50_000_000,
            "aod/tone_1": 40_000_000,
            "aod/tone_2": 30_000_000,
        }
        for name, freq in tones.items():
            cfg.configure_lf_fem_tone_line(name, ch, IqConfig(frequency=freq))

        # one shared analog_outputs entry on port 5
        controller = cfg.controllers["con1/1"]
        assert list(controller.analog_outputs.keys()) == [5]

        # three separate elements, each with its own frequency
        for name, freq in tones.items():
            assert cfg.elements[name].intermediate_frequency == freq

    def test_multitone_port_tuple_correct_for_each_element(self):
        cfg = _lf_fem_config()
        ch = IqChannel(device="con1/1", path="5", mixer=None, lo=None)
        for i, freq in enumerate([50e6, 40e6, 30e6]):
            cfg.configure_lf_fem_tone_line(f"aod/tone_{i}", ch, IqConfig(frequency=freq))
        for i in range(3):
            el = cfg.elements[f"aod/tone_{i}"]
            assert el.singleInput["port"] == ("con1", 1, 5)


# ===========================================================================
# LEVEL 3 — platform tests: neutral_atom_array loads and is coherent
# ===========================================================================

N_TWEEZERS = 3   # must match platforms/neutral_atom_array/platform.py

COL_IDS = [f"col_selector_{i + 1:02d}" for i in range(N_TWEEZERS)]
ROW_IDS = [f"row_selector_{i + 1:02d}" for i in range(N_TWEEZERS)]


class TestNeutralAtomPlatform:

    @pytest.fixture(scope="class")
    def platform(self):
        return _load_platform()

    def test_platform_loads(self, platform):
        assert platform is not None

    def test_no_qubits_registered(self, platform):
        # Pulses are addressed directly via parameters.pulses[channel_id];
        # there is no Qubit/native-gate wrapping in this platform.
        assert platform.qubits == {}

    def test_has_correct_pulse_count(self, platform):
        # col_selector_01..N + row_selector_01..N, one default Pulse each
        assert len(platform.parameters.pulses) == 2 * N_TWEEZERS
        for ch_id in COL_IDS + ROW_IDS:
            assert ch_id in platform.parameters.pulses

    def test_all_channels_have_no_lo(self, platform):
        for inst in platform.instruments.values():
            if not hasattr(inst, "channels"):
                continue
            for ch_id, ch in inst.channels.items():
                if isinstance(ch, IqChannel):
                    assert ch.lo is None, f"{ch_id}: LF-FEM tone must have lo=None"

    def test_all_channels_on_lf_fem(self, platform):
        for inst in platform.instruments.values():
            if not hasattr(inst, "fems"):
                continue
            for ch_id, ch in inst.channels.items():
                if isinstance(ch, IqChannel):
                    assert inst.fems.get(ch.device) == "LF", (
                        f"{ch_id}: expected LF FEM, got {inst.fems.get(ch.device)}"
                    )

    def test_col_tones_all_on_same_port(self, platform):
        inst = next(i for i in platform.instruments.values() if hasattr(i, "channels"))
        ports = {inst.channels[ch_id].port for ch_id in COL_IDS}
        assert len(ports) == 1, f"all col tones must share one port, got {ports}"

    def test_row_tones_all_on_same_port(self, platform):
        inst = next(i for i in platform.instruments.values() if hasattr(i, "channels"))
        ports = {inst.channels[ch_id].port for ch_id in ROW_IDS}
        assert len(ports) == 1, f"all row tones must share one port, got {ports}"

    def test_col_row_on_different_ports(self, platform):
        inst = next(i for i in platform.instruments.values() if hasattr(i, "channels"))
        col_port = inst.channels[COL_IDS[0]].port
        row_port = inst.channels[ROW_IDS[0]].port
        assert col_port != row_port, "col and row AOD must be on different ports"

    def test_col_frequencies_match_reference(self, platform):
        # 100, 90, 80 MHz — 10 MHz spacing downward from 100 MHz
        expected = [100e6 - 10e6 * i for i in range(N_TWEEZERS)]
        for ch_id, exp_f in zip(COL_IDS, expected):
            got = platform.parameters.configs[ch_id].frequency
            assert got == exp_f, f"{ch_id}: expected {exp_f} Hz, got {got} Hz"

    def test_row_frequencies_match_reference(self, platform):
        # 50, 40, 30 MHz — 10 MHz spacing downward from 50 MHz
        expected = [50e6 - 10e6 * i for i in range(N_TWEEZERS)]
        for ch_id, exp_f in zip(ROW_IDS, expected):
            got = platform.parameters.configs[ch_id].frequency
            assert got == exp_f, f"{ch_id}: expected {exp_f} Hz, got {got} Hz"

    def test_dump_qua_config(self, platform):
        """Build the full QUA config dict and write it next to this file for inspection.

        Open tests/instruments/qm/generated_qua_config.json after running and
        compare elements / analog_outputs / intermediate_frequencies against
        configuration_opx1000_mwfem_lffem.py — structure should match.
        """
        controller = next(
            inst for inst in platform.instruments.values()
            if hasattr(inst, "fems")
        )
        configs = platform.parameters.configs

        # Drive every channel through configure_channel to populate the
        # Configuration object (mirrors what play() does internally).
        for ch_id in controller.channels:
            if ch_id in configs:
                controller.configure_channel(ch_id, configs)

        qua_config = asdict(controller.config)

        out = pathlib.Path(__file__).parent / "generated_qua_config.json"
        out.write_text(json.dumps(qua_config, indent=2, default=str))
        print(f"\nQUA config written to: {out}")

        elements = qua_config["elements"]
        assert elements, "elements section must not be empty"

        # All col/row selectors must appear as singleInput elements
        for ch_id in COL_IDS + ROW_IDS:
            assert ch_id in elements, f"missing element: {ch_id}"
            assert "singleInput" in elements[ch_id], f"{ch_id} must be singleInput"

        # Col tones all share one port; row tones share a different port
        col_ports = {tuple(elements[c]["singleInput"]["port"]) for c in COL_IDS}
        row_ports = {tuple(elements[r]["singleInput"]["port"]) for r in ROW_IDS}
        assert len(col_ports) == 1, f"col tones must share one port, got {col_ports}"
        assert len(row_ports) == 1, f"row tones must share one port, got {row_ports}"
        assert col_ports != row_ports, "col and row must be on different ports"

        # Each element has a distinct, non-zero intermediate_frequency
        col_freqs = [elements[c]["intermediate_frequency"] for c in COL_IDS]
        row_freqs = [elements[r]["intermediate_frequency"] for r in ROW_IDS]
        assert len(set(col_freqs)) == N_TWEEZERS, f"col IFs not distinct: {col_freqs}"
        assert len(set(row_freqs)) == N_TWEEZERS, f"row IFs not distinct: {row_freqs}"
        assert all(f != 0 for f in col_freqs + row_freqs), "IFs must be non-zero"
