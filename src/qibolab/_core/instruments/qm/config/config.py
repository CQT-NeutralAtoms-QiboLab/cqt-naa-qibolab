from dataclasses import asdict, dataclass, field
import dataclasses
from typing import Optional, Union

import numpy as np

from qibolab._core.components import (
    AcquisitionChannel,
    DcChannel,
    IqChannel,
    IqConfig,
    OscillatorConfig,
)
from qibolab._core.identifier import ChannelId
from qibolab._core.pulses import Custom, Pulse, Readout

from ..components import MwFemOscillatorConfig, OpxOutputConfig, QmAcquisitionConfig
from .devices import (
    AnalogInput,
    Controller,
    ControllerId,
    Controllers,
    LfFemOutput,
    ModuleTypes,
    MwFemInput,
    MwFemOutput,
    Octave,
    OctaveInput,
    OctaveOutput,
)
from .elements import (
    AcquireLfFemToneElement,
    AcquireMwFemElement,
    AcquireOctaveElement,
    DcElement,
    Element,
    DigitalElement,
    LfFemToneElement,
    MwFemElement,
    RfOctaveElement,
)
from .pulses import (
    QmAcquisition,
    QmPulse,
    Waveform,
    integration_weights,
    operation,
    waveforms_from_pulse,
)

__all__ = ["Configuration"]

DEFAULT_DIGITAL_WAVEFORMS = {"ON": {"samples": [(1, 0)]}}
"""Required to be registered in the config for QM to work.

Also used as triggering that allows the Octave LO signal to pass only
when we are executing something.
"""
def _omit_none(fields):
    return {k: v for k, v in fields if v is not None}


@dataclass
class Configuration:
    """Configuration for communicating with the ``QuantumMachinesManager``.

    Contains nested ``dataclass`` objects and is serialized using ``asdict``
    to be sent to the instrument.
    """

    version: int = 1
    controllers: Controllers = field(default_factory=Controllers)
    octaves: dict[str, Octave] = field(default_factory=dict)
    elements: dict[str, Element] = field(default_factory=dict)
    pulses: dict[str, QmPulse | QmAcquisition] = field(default_factory=dict)
    waveforms: dict[str, Waveform] = field(default_factory=dict)
    digital_waveforms: dict = field(
        default_factory=lambda: DEFAULT_DIGITAL_WAVEFORMS.copy()
    )
    integration_weights: dict = field(default_factory=dict)
    mixers: dict = field(default_factory=dict)

    def add_controller(self, device: ControllerId, modules: dict[str, ModuleTypes]):
        if device not in self.controllers:
            self.controllers[device] = Controller(type=modules[device])

    def add_octave(
        self, device: str, connectivity: ControllerId, modules: dict[str, ModuleTypes]
    ):
        if device not in self.octaves:
            self.add_controller(connectivity, modules)
            self.octaves[device] = Octave(connectivity)
            
    def asdict(self) -> dict:
        return dataclasses.asdict(self, dict_factory=_omit_none)


    def configure_dc_line(
        self, id: ChannelId, channel: DcChannel, config: OpxOutputConfig
    ):
        controller = self.controllers[channel.device]
        if controller.type == "opx1":
            keys = ["offset"]
        else:
            keys = list(config.model_dump().keys())
            keys.remove("kind")
            keys.remove("filters")
        config_values = config.model_dump()
        values = {k: config_values[k] for k in keys}
        values.update({"filter": config.filter(controller.type)})
        if config.sampling_rate > 1e9:
            del values["upsampling_mode"]
        controller.analog_outputs[channel.port] = values
        self.elements[id] = DcElement.from_channel(channel)
    

    def configure_lf_fem_tone_line(
    self,
    id: "ChannelId",  
    channel: "IqChannel", 
    config: "IqConfig",    
    ):
        controller = self.controllers[channel.device]
        if channel.port in controller.analog_outputs:
            output = LfFemOutput(**controller.analog_outputs[channel.port])
            output.update(config)                     
        else:
            output = LfFemOutput.from_config(config)  
        controller.analog_outputs[channel.port] = asdict(output)
        intermediate_frequency = int(config.frequency)
        self.elements[id] = LfFemToneElement.from_channel(
            channel, intermediate_frequency
        )

    def configure_lf_fem_acquire_line(
        self,
        id: "ChannelId",  
        acquire_channel: "AcquisitionChannel", 
        probe_channel: "IqChannel", 
        acquire_config: "QmAcquisitionConfig",    
        probe_config: "IqConfig",    
    ):
        controller = self.controllers[acquire_channel.device]
        controller.analog_inputs[acquire_channel.port] = AnalogInput.from_config(acquire_config)
        self.configure_lf_fem_tone_line(id, probe_channel, probe_config)
        intermediate_frequency = 0
        time_of_flight = int(acquire_config.delay)
        smearing = int(acquire_config.smearing)
        self.elements[id] = AcquireLfFemToneElement.from_channel(
            probe_channel, acquire_channel, intermediate_frequency, time_of_flight, smearing
        )

    def configure_mw_fem_line(
        self,
        channel: IqChannel,
        config: IqConfig,
        lo_config: MwFemOscillatorConfig,
        id: ChannelId | None = None,
    ):
        controller = self.controllers[channel.device]
        if channel.port in controller.analog_outputs:
            output = MwFemOutput(**controller.analog_outputs[channel.port])
            output.update(lo_config)
        else:
            output = MwFemOutput.from_config(lo_config)
        controller.analog_outputs[channel.port] = asdict(output)
        if id is not None:
            intermediate_frequency = config.frequency - lo_config.frequency
            self.elements[id] = MwFemElement.from_channel(
                channel, lo_config.upconverter, intermediate_frequency
            )

    def configure_iq_line(
        self,
        channel: IqChannel,
        config: IqConfig,
        lo_config: OscillatorConfig,
        id: ChannelId | None = None,
    ):
        port = channel.port
        octave = self.octaves[channel.device]
        octave.RF_outputs[port] = OctaveOutput.from_config(lo_config)
        self.controllers[octave.connectivity].add_octave_output(port)

        if id is not None:
            intermediate_frequency = config.frequency - lo_config.frequency
            self.elements[id] = RfOctaveElement.from_channel(
                channel, octave.connectivity, intermediate_frequency
            )

    def configure_mw_fem_acquire_line(
        self,
        acquire_channel: AcquisitionChannel,
        probe_channel: IqChannel,
        acquire_config: QmAcquisitionConfig,
        probe_config: IqConfig,
        lo_config: MwFemOscillatorConfig,
        id: ChannelId,
    ):
        port = acquire_channel.port
        controller = self.controllers[acquire_channel.device]
        controller.analog_inputs[port] = MwFemInput.from_config(lo_config)

        self.configure_mw_fem_line(probe_channel, probe_config, lo_config)

        intermediate_frequency = probe_config.frequency - lo_config.frequency
        self.elements[id] = AcquireMwFemElement.from_channel(
            probe_channel,
            lo_config.upconverter,
            acquire_channel,
            intermediate_frequency=intermediate_frequency,
            time_of_flight=acquire_config.delay,
            smearing=acquire_config.smearing,
        )

    def configure_acquire_line(
        self,
        acquire_channel: AcquisitionChannel,
        probe_channel: IqChannel,
        acquire_config: QmAcquisitionConfig,
        probe_config: IqConfig,
        lo_config: OscillatorConfig,
        id: ChannelId,
    ):
        port = acquire_channel.port
        octave = self.octaves[acquire_channel.device]
        octave.RF_inputs[port] = OctaveInput(lo_config.frequency)
        self.controllers[octave.connectivity].add_octave_input(port, acquire_config)

        self.configure_iq_line(probe_channel, probe_config, lo_config)

        intermediate_frequency = probe_config.frequency - lo_config.frequency
        self.elements[id] = AcquireOctaveElement.from_channel(
            probe_channel,
            acquire_channel,
            octave.connectivity,
            intermediate_frequency,
            time_of_flight=acquire_config.delay,
            smearing=acquire_config.smearing,
        )

    def register_waveforms(
        self,
        pulse: Pulse,
        sampling_rate: int,
        max_voltage: float,
        element: str | None = None,
        dc: bool = False,
    ):
        if dc:
            qmpulse = (
                QmPulse.from_dc_pulse(pulse, sampling_rate)
                if element is None
                else QmAcquisition.from_dc_pulse(pulse, sampling_rate)
            )
        else:
            if element is None:
                qmpulse = QmPulse.from_pulse(pulse, sampling_rate)
            else:
                qmpulse = QmAcquisition.from_pulse(pulse, element)
        waveforms = waveforms_from_pulse(pulse, sampling_rate, max_voltage)
        if dc:
            self.waveforms[qmpulse.waveforms["single"]] = waveforms["I"]
        else:
            for mode in ["I", "Q"]:
                self.waveforms[getattr(qmpulse.waveforms, mode)] = waveforms[mode]
        return qmpulse

    def register_iq_pulse(
        self,
        element: str,
        pulse: Pulse,
        sampling_rate: int,
        max_voltage: float,
        dc: bool = False,
    ):
        op = operation(pulse)
        if op not in self.pulses:
            self.pulses[op] = self.register_waveforms(
                pulse, sampling_rate, max_voltage, dc=dc
            )
        self.elements[element].operations[op] = op
        return op

    def register_dc_pulse(
        self, element: str, pulse: Pulse, sampling_rate: int, max_voltage: float
    ):
        op = operation(pulse)
        if op not in self.pulses:
            self.pulses[op] = self.register_waveforms(
                pulse, sampling_rate, max_voltage, dc=True
            )
        self.elements[element].operations[op] = op
        return op

    def register_acquisition_pulse(
        self,
        element: str,
        readout: Readout,
        sampling_rate: int,
        max_voltage: float,
        dc: bool = False,
    ):
        """Registers pulse, waveforms and integration weights in QM config."""
        op = operation(readout)
        acquisition = f"{op}_{element}"
        if acquisition not in self.pulses:
            new_probe = readout.probe.model_copy(
                update={
                    "duration": readout.acquisition.duration,
                    "envelope": Custom(
                        i_=np.pad(
                            readout.probe.envelope.i(int(readout.probe.duration)),
                            (
                                0,
                                int(
                                    readout.acquisition.duration
                                    - readout.probe.duration
                                ),
                            ),
                            mode="constant",
                            constant_values=0,
                        ),
                        q_=np.pad(
                            readout.probe.envelope.q(int(readout.probe.duration)),
                            (
                                0,
                                int(
                                    readout.acquisition.duration
                                    - readout.probe.duration
                                ),
                            ),
                            mode="constant",
                            constant_values=0,
                        ),
                    ),
                }
            )
            self.pulses[acquisition] = self.register_waveforms(
                new_probe,
                sampling_rate,
                max_voltage,
                element,
                dc=dc,
            )
        self.elements[element].operations[op] = acquisition
        return op

    def register_integration_weights(self, element: str, duration: int, kernel):
        self.integration_weights.update(integration_weights(element, duration, kernel))

    
    def configure_digital_line(self, id, channel):
        """Configure a TTL/digital output line (AOM gate / trigger).
    
        CONTRAST with configure_lf_fem_tone_line:
        • writes digital_outputs (not analog_outputs)
        • creates a DigitalElement (not LfFemToneElement)
        • NO frequency computation (TTL has none)
        • NO output 'offset/rate/mode' config — a digital port is just on/off
    
        Args:
        id      : ChannelId — element name, e.g. "0/aom_gate" or "0/artiq_trigger"
        channel : DigitalChannel — carries .device ("con1/1") and .port
        """
        # 1. Resolve the FEM (same mechanism as analog).
        controller = self.controllers[channel.device]
    
        # 2. Register the DIGITAL output port. digital_outputs already exists on
        #    Controller; an empty dict per port is the minimal registration.
        controller.digital_outputs[channel.port] = {}
    
        # 3. Create the digital element (digitalInputs routing, no frequency).
        self.elements[id] = DigitalElement.from_channel(channel)
    
    def register_digital_waveform(self, name, samples):
        """Register a TTL on/off pattern in digital_waveforms.
    
        Args:
        name    : str — the marker name (referenced by a pulse's digital_marker)
        samples : list[tuple[int, int]] — (value, duration_ns) pairs.
                    value is 1 (high) or 0 (low); duration in ns; duration 0 means
                    "hold to the end of the pulse".
                    e.g. [(1, 0)]        → stay HIGH the whole pulse (the default "ON")
                        [(1, 200)]      → HIGH for 200 ns
                        [(0, 50),(1,100)] → LOW 50 ns then HIGH 100 ns
    
        CONTRAST with analog waveforms_from_pulse: that builds VOLTAGE samples;
        this builds (value, duration) on/off pairs — there are no voltage levels,
        only HIGH/LOW timing.
        """
        self.digital_waveforms[name] = {"samples": samples}
    
    
    def register_digital_pulse(self, element, pulse, marker_name="ON"):
        """Register a digital pulse and attach it to an element's operations.

        A digital pulse has a length and a digital_marker (which on/off pattern).
        QmPulse already supports digital_marker — we just build one with no analog
        waveform (or an empty one), driven purely by the marker.

        CONTRAST with register_iq_pulse/register_dc_pulse: those build analog
        waveforms; this one is digital-only (the marker is the signal).
        """
        op = operation(pulse)
        length = int(pulse.duration)
        # QmPulse already has digital_marker (default "ON"); for a pure digital
        # pulse the waveform may be empty/zero and the marker carries the signal.
        self.pulses[op] = {
            "operation": "control",
            "length": length,
            "digital_marker": marker_name,   # ← links to digital_waveforms[marker_name]
            # "waveforms": {...}  # often omitted or zero for a pure trigger
        }
        self.elements[element].operations[op] = op
        return op  
