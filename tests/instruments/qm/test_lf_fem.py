"""Tests for the LF-FEM tone and TTL/digital additions in cqt-naa-qibolab.

Level 1 — unit:    dataclass correctness (no hardware, no platform)
Level 2 — config:  configure_lf_fem_tone_line writes correct entries

The platform-level (Level 3) tests live with the platform they test, in
``qibolab_platforms_naa/_tests/``.

Run from the repo root:
    pytest tests/instruments/qm/test_lf_fem.py -v
"""

import pytest

from qibolab._core.components import DigitalChannel, ToneChannel, ToneConfig
from qibolab._core.instruments.qm.config.config import Configuration
from qibolab._core.instruments.qm.config.devices import LfFemOutput
from qibolab._core.instruments.qm.config.elements import DigitalElement, LfFemToneElement


def _lf_fem_config() -> Configuration:
    """Configuration with one LF-FEM controller pre-registered on con1/1."""
    cfg = Configuration()
    cfg.add_controller("con1/1", {"con1/1": "LF"})
    return cfg


# ===========================================================================
# LEVEL 1 — unit tests: do the dataclasses produce the right QUA fields?
# ===========================================================================

class TestLfFemToneElement:
    """LF-FEM tone element must be singleInput (analog) and carry a frequency."""

    def test_uses_single_input_not_mw_input(self):
        ch = ToneChannel(device="con1/1", path="5", core="c")
        el = LfFemToneElement.from_channel(ch, intermediate_frequency=50_000_000)
        assert "singleInput" in el.__dict__
        assert "MWInput" not in el.__dict__

    def test_carries_the_correct_frequency(self):
        ch = ToneChannel(device="con1/1", path="5", core="c")
        el = LfFemToneElement.from_channel(ch, intermediate_frequency=50_000_000)
        assert el.intermediate_frequency == 50_000_000

    def test_port_tuple_is_opx1000_form(self):
        # device="con1/1" + port 5  ->  ("con1", 1, 5)
        ch = ToneChannel(device="con1/1", path="5", core="c")
        el = LfFemToneElement.from_channel(ch, intermediate_frequency=50_000_000)
        assert el.singleInput["port"] == ("con1", 1, 5)

    def test_carries_the_core(self):
        ch = ToneChannel(device="con1/1", path="5", core="col_AOD_1")
        el = LfFemToneElement.from_channel(ch, intermediate_frequency=50_000_000)
        assert el.core == "col_AOD_1"

    def test_operations_dict_starts_empty(self):
        ch = ToneChannel(device="con1/1", path="5", core="c")
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
        # device="con1/1" + port 1  ->  ("con1", 1, 1)
        ch = DigitalChannel(device="con1/1", path="1")
        el = DigitalElement.from_channel(ch)
        assert el.digitalInputs["trigger"]["port"] == ("con1", 1, 1)

    def test_delay_and_buffer_default_to_zero(self):
        ch = DigitalChannel(device="con1/1", path="1")
        el = DigitalElement.from_channel(ch)
        assert el.digitalInputs["trigger"]["delay"] == 0
        assert el.digitalInputs["trigger"]["buffer"] == 0


class TestLfFemOutput:
    """LfFemOutput reads its LF-FEM analog-output knobs directly from ToneConfig."""

    def test_from_config_uses_tone_config_defaults(self):
        out = LfFemOutput.from_config(ToneConfig(frequency=100e6))
        assert out.offset == 0.0
        assert out.sampling_rate == 1e9
        assert out.output_mode == "direct"
        assert out.upsampling_mode == "mw"

    def test_from_config_reads_explicit_values(self):
        out = LfFemOutput.from_config(
            ToneConfig(frequency=1e6, offset=0.1, sampling_rate=2_000_000_000,
                       output_mode="amplified", upsampling_mode="pulse")
        )
        assert out.offset == 0.1
        assert out.sampling_rate == 2e9
        assert out.output_mode == "amplified"
        assert out.upsampling_mode == "pulse"

    def test_update_accepts_matching_settings(self):
        out = LfFemOutput(offset=0.0, sampling_rate=1e9, output_mode="direct")
        out.update(ToneConfig(frequency=100e6))  # matching defaults -> must not raise

    def test_update_rejects_conflicting_sampling_rate(self):
        out = LfFemOutput(offset=0.0, sampling_rate=2e9, output_mode="direct")
        with pytest.raises(AssertionError):
            out.update(ToneConfig(frequency=100e6))  # default 1 GS/s -> conflict

    def test_update_rejects_conflicting_output_mode(self):
        out = LfFemOutput(offset=0.0, sampling_rate=1e9, output_mode="amplified")
        with pytest.raises(AssertionError):
            out.update(ToneConfig(frequency=100e6))  # default "direct" -> conflict


# ===========================================================================
# LEVEL 2 — config tests: configure_lf_fem_tone_line writes correct entries
# ===========================================================================

class TestConfigureLfFemToneLine:

    def test_creates_element_with_correct_frequency(self):
        cfg = _lf_fem_config()
        ch = ToneChannel(device="con1/1", path="5", core="c")
        cfg.configure_lf_fem_tone_line("atom_0/drive", ch, ToneConfig(frequency=50e6))
        assert "atom_0/drive" in cfg.elements
        assert cfg.elements["atom_0/drive"].intermediate_frequency == 50_000_000

    def test_analog_output_registered_for_port(self):
        cfg = _lf_fem_config()
        ch = ToneChannel(device="con1/1", path="5", core="c")
        cfg.configure_lf_fem_tone_line("atom_0/drive", ch, ToneConfig(frequency=50e6))
        assert 5 in cfg.controllers["con1/1"].analog_outputs

    def test_output_knobs_come_from_tone_config(self):
        cfg = _lf_fem_config()
        ch = ToneChannel(device="con1/1", path="5", core="c")
        cfg.configure_lf_fem_tone_line(
            "atom_0/drive", ch,
            ToneConfig(frequency=50e6, upsampling_mode="pulse", output_mode="amplified"),
        )
        ao = cfg.controllers["con1/1"].analog_outputs[5]
        assert ao["upsampling_mode"] == "pulse"
        assert ao["output_mode"] == "amplified"

    def test_element_uses_single_input(self):
        cfg = _lf_fem_config()
        ch = ToneChannel(device="con1/1", path="5", core="c")
        cfg.configure_lf_fem_tone_line("atom_0/drive", ch, ToneConfig(frequency=50e6))
        el = cfg.elements["atom_0/drive"]
        assert hasattr(el, "singleInput")
        assert not hasattr(el, "MWInput")

    def test_multitone_same_port_distinct_frequencies(self):
        """3 tones on port 5 -> 1 analog_outputs entry, 3 elements."""
        cfg = _lf_fem_config()
        ch = ToneChannel(device="con1/1", path="5", core="c")
        tones = {"aod/tone_0": 50_000_000, "aod/tone_1": 40_000_000, "aod/tone_2": 30_000_000}
        for name, freq in tones.items():
            cfg.configure_lf_fem_tone_line(name, ch, ToneConfig(frequency=freq))

        assert list(cfg.controllers["con1/1"].analog_outputs.keys()) == [5]
        for name, freq in tones.items():
            assert cfg.elements[name].intermediate_frequency == freq

    def test_multitone_port_tuple_correct_for_each_element(self):
        cfg = _lf_fem_config()
        ch = ToneChannel(device="con1/1", path="5", core="c")
        for i, freq in enumerate([50e6, 40e6, 30e6]):
            cfg.configure_lf_fem_tone_line(f"aod/tone_{i}", ch, ToneConfig(frequency=freq))
        for i in range(3):
            assert cfg.elements[f"aod/tone_{i}"].singleInput["port"] == ("con1", 1, 5)
