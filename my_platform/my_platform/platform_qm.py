import pathlib
import numpy as np #TODO: Shouldn't numpy be imported from qibo?
from qibolab import ConfigKinds, Parameter, Sweeper
from qibolab._core.components import AcquisitionChannel, DigitalChannel, IqChannel
from qibolab._core.instruments.qm import QmController
from qibolab._core.instruments.qm.components import OpxOutputConfig, QmAcquisitionConfig
from qibolab._core.platform import Platform

FOLDER = pathlib.Path(__file__).parent

# TODO: SUPER CLARIFY what FEM and analog and trig channels are.
# FEM = Front-End Module: a plug-in card. The FEM is what actually
# has the physical I/O ports (the analog/digital connectors you wire to your hardware). 
# FEM slot assignments matching reference config (configuration_opx1000_mwfem_lffem.py)
# One LF-FEM has enough ports for everything he needs right now (col AOD, row AOD, 
# readout, trigger all fit on FEM1's connectors), so he put them all there. FEM2 is 
# declared in fems={...} but nothing is routed to it — a placeholder for "additional 
# DC outputs" if he later runs out of ports. It's a choice, not a constraint.
# One LF-FEM has 8 analog output channels (plus analog inputs and several
# digital/TTL lines) on a single card. 
CON = "con1"   # the controller, ie. the box that holds the FEM cards 
LF_FEM1 = 1    # LF-FEM: col AOD (port 1) + row AOD (port 2) + readout + trigger
LF_FEM2 = 2    # LF-FEM: spare / additional DC outputs


# Analog output ports on LF_FEM1 (matching reference)
COL_CHANNEL = 3
ROW_CHANNEL = 2

# Digital (TTL) trigger output ports on LF_FEM1 — must not collide with the
# analog COL/ROW ports above.
TRIG_CHANNELS = [3, 4] 
#TODO: isn't col_channel number 3 not colliding here with trig_channels number 3 precisely??
# No, it's not colliding coz analog outputs and digital outputs are separate port banks 
# on the FEM, each numbered independently from 1. So "analog port 3" and "digital port 3" 
# are different physical connectors — no conflict between them.

# Number of tweezers per axis (reference uses 8; 3 here for testing)
# "Per axis": A neutral-atom tweezer array is made with two AODs (acousto-optic deflectors)
#  — one for the X/column axis, one for the Y/row axis. Each AOD is driven by a multi-tone RF
#  signal, and each tone = one tweezer position along that axis. Crossing N column tones with
#  N row tones gives an N×N grid of traps. So "tweezers per axis" = how many tones on each 
# AOD: reference uses 8 per axis (→ 8×8 grid); here N_TWEEZERS = 3 (→ 3×3) just for testing.
#  That's why the code builds col_selector_01..03 on the COL port and row_selector_01..03 
# on the ROW port — 3 tones each, one shared physical port per axis.
# The three tones are separated elsewhere (as QUA "elements" with different intermediate 
# frequencies), not by port. That's the "N tones share one physical port" design in action.
N_TWEEZERS = 3


# Elis extra note for Elis:
# - qm/config/ folder: is qibolab's translation layer — the code that turns
#  abstract qibolab Channels into the concrete dict that QM's QUA compiler expects.
# - devices.py: defines the shape of that dict (the FEM/port model), and config.py fills it in. 
#  cqt-naa-qibolab/my_platform/my_platform/platform_qm.py

# Appends the two QM classes to the ConfigKinds global registry which holds the "kind"s in 
# parameters.json. It does so before Platform.load() runs, so the QM config params for
#  "opx-output" → OpxOutputConfig and "qm-acquisition" → QmAcquisitionConfig resolve correctly
ConfigKinds.extend([OpxOutputConfig, QmAcquisitionConfig])


def create() -> Platform:
    channels = {}

    # Col AOD — all N_TWEEZERS tones share the SAME physical port (COL_CHANNEL). #TODO: SUPERCLARIFY how does that affect setup
    # Each tone element gets its own intermediate_frequency from parameters.json. --> Elis. here the intermediate IF freq is
    #      directly the baseband freq of the AOD coz LO and mixer are 0. Intermediate freq is the sine wave that the hardware of Quantum Machines generates for an 'element'. Here the elements are the tones of the AOD and these have frequencies that are directly the baseband.
    # Pulses are addressed directly via parameters.pulses[channel_id] — no
    #      What this means is here we are skipping the Qubit/native-gate layer; a 
    #      channel's pulse is fetched straight from the pulses dict keyed by the channel's name, not via the normal qibolab way where pulses 
    #      live inside Qubit objects and native gates (e.g. qubit.RX)
    # Qubit/native-gate wrapping needed. #TODO: That's my point 6 in architecture, we still don't have a qubit definition. Is that right?

    # TODO: WHhat is this 1st block for? Is this a COLumn AOD? is CON = constant and thus this some tipe of block pulse?
    for i in range(N_TWEEZERS):
        ch_id = f"col_selector_{i + 1:02d}" # column tones: col_selector_01, col_selector_02, col_selector_03 column tones — the 3 tones on the column AOD. Each is a separate QUA element with its own intermediate frequency (ie position), but all three share the same physical port/jack (path="3"), summed together onto the one col-AOD cable.
        channels[ch_id] = IqChannel(        # TODO:IqChannel? -->  it's the object that declares one tone as an analog-output channel...it's an "adaptation" with no mixer no LO
            device=f"{CON}/{LF_FEM1}",      # device= the controller (CON) and which FEM card on it (LF_FEM1)
            path=str(COL_CHANNEL),
            mixer=None,
            lo=None,
            core=f"col_AOD_{i + 1}", # core= a QM real-time processing-core (thread) for the element. Each tone is given its own core name so the tones can be driven/updated in parallel rather than serialized on one processor.
        )                            # the actual parallel execution on separate cores happens inside QM's compiler/FPGA at runtime — qibolab just emits the core hint and lets QM schedule it.


    # Row AOD — same pattern, all tones share port ROW_CHANNEL
    for i in range(N_TWEEZERS):
        ch_id = f"row_selector_{i + 1:02d}"
        channels[ch_id] = IqChannel(
            device=f"{CON}/{LF_FEM1}",
            path=str(ROW_CHANNEL),
            mixer=None,
            lo=None,
            core=f"row_AOD_{i + 1}",
        )

    # Trigger — TTL outputs, one dedicated port each (no sharing, so no core needed).
    # Important note on Triggers: 
    # Triggers genuinely have no core (trig_01 -> <none>). Digital elements use a different shape
    # entirely (digitalInputs + operations, no core, no intermediate_frequency) — the core/thread 
    # concept doesn't apply to a TTL on/off line.

    for i, port in enumerate(TRIG_CHANNELS):
        ch_id = f"trig_{i + 1:02d}"
        channels[ch_id] = DigitalChannel(
            device=f"{CON}/{LF_FEM1}",
            path=str(port),
        )


    # Important note about AcquisitionChannels: 
    # Acquisition elements inherit core from their probe, not from themselves. In elements.py:194, AcquireLfFemToneElement.from_channel does
    # core=getattr(probe_channel, "core", None). The probe is col_selector_01, whose IqChannel has core="col_AOD_1" — so detector and
    # loopback both come out with col_AOD_1. They land on the same real-time core as the tone they measure, which makes sense: the 
    # readout must run on the same thread as the pulse it's acquiring, so play and acquire stay time-synchronized.
    channels["detector"] = AcquisitionChannel(
        device=f"{CON}/{LF_FEM1}", 
        path="2",               #TODO: Why are the path and probe hardcoded, should they and what are the implications of these being currently hardcoded?
        probe="col_selector_01" #TODO: in a production platform this should come from parameters.json/config like the tones do,
    )
    channels["loopback"] = AcquisitionChannel(#TODO: What is a loopback and what for?--> to get outputs as inputs to for eg. calibrate that what you emit is what you wanted
        device=f"{CON}/{LF_FEM1}",
        path="2",               #TODO: Same here as above, hardcoded needs to be properly replaced
        probe="col_selector_01" #TODO: Same here as above, hardcoded needs to be properly replaced
    )



    # TODO: Architecture: are instruments supposed to be defined here inside platform_qm.py? 
    # Isn't there a dedicated place for QM instruments in their drivers side in qibolab or directly 
    # inside the qibolab instruments? I am not saying this here is wrong, just that I've seen the word instruments
    #  in other places too, so wondering what each place holds to decide where this should go.
    instruments = {             
        CON: QmController(
            address="192.168.88.247:80",
            fems={
                f"{CON}/{LF_FEM1}": "LF",
                f"{CON}/{LF_FEM2}": "LF",
            },
            channels=channels,
        )
    }

    # TODO: Investigate the issue between Hardware vs Platform syntax in qibolab upstream to decide whcih one should be here
    return Platform.load(
        path=FOLDER,                #TODO: This probably wrong in real life since hte parent folder ie qibolab fork should not be the one holding the platform
        instruments=instruments,
        qubits={},
    )


def build_config(platform: Platform) -> dict:
    """ Take every channel you declared and feed it through the QM config-building code, so each one produces its entry in the QUA config.

    Mirrors what ``QmController.play()`` does internally to populate
    ``controller.config``, without needing a real instrument connection. 

    The config is the map of your system, written in QUA's vocabulary. It's the translation of your physical setup (chassis, FEM, jacks, tones, cables, readout) into the dict of terms QM understands: controllers / fems / analog_outputs / digital_outputs / analog_inputs / elements / pulses / waveforms.

    During a real run (platform.execute(...), :166): the same controller.config gets populated internally by QmController.play() and handed to the QM compiler over the network — it is not routed through this JSON file. The file is a convenience for humans; the live path passes the config object straight to the hardware.
    """
    from qibolab._core.sequence import PulseSequence

    controller = platform.instruments[CON]      
    configs = platform.parameters.configs       #This is a dictionary mapping each channel/component 

    # elements first: register_pulses (below) attaches operations onto
    # elements that must already exist in controller.config.elements.
    for ch_id in controller.channels:
        if ch_id in configs:
            controller.configure_channel(ch_id, configs)

    sequence = PulseSequence(
        (ch_id, pulse)
        for ch_id, pulse in platform.parameters.pulses.items()
        if ch_id in controller.channels
    )
    controller.register_pulses(configs, sequence)

    return controller.config.asdict() # Where is the controller config dict that gets generated here either going or get written to ? Is this later what becomes the auto generated 'generated_qua_config.json' ?? Yes it becomes that file. However, see the note at the docstring, this file is not used for actual talking with the qua hardware.


if __name__ == "__main__":
    import json

    from qibolab._core.pulses import Pulse, Rectangular, Gaussian
    from qibolab._core.sequence import PulseSequence

    platform = create()

    qua_config = build_config(platform)
    # This part is not strictly necessary-------------
    out = FOLDER / "generated_qua_config.json"
    out.write_text(json.dumps(qua_config, indent=2, default=str))  
    print(f"QUA config written to: {out}")
    #--------------------------------------------------
    platform.connect()

    sequence = PulseSequence()

    # TODO: OPTION A OR OPTION B? I think I lean towards A no? Reason being why would one hardcode manually 
    # potentially different pulses than the ones we know are allowed given the platform and the config of attached instruments?
    # that manual hardcoding of pulses in main could create error if pulses defined are not viable given the setup or simply not
    # code in the correct format. Both things are guaranteed to have passed the green check when you load the pulses from the ones
    # defined in parameters.json no? Should there be an option C that is somewhere like a specific storage of pulses akin to parameters.json
    # but only for pulses? tbh i think that either exists already (underdeveloped) in qibolab or for us is overkill and should stay in parameters.json
    # INVESTIGATE.


    # Option A: re-use the pulse defined in parameters.json
    # (platform.parameters.pulses is the dict loaded from the json)
    # col1_pulse = platform.parameters.pulses["col_selector_01"].model_copy(
    #     update={"chirp": (1e6, "Hz/nsec")}
    # )
    # sequence.append(("col_selector_01", col1_pulse))

    # Option B: build a fresh Pulse inline
    col2_pulse_a = Pulse(
        duration=8000,
        amplitude=0.167,
        envelope=Gaussian(rel_sigma = 0.5),
        chirp=(200e5, "Hz/nsec"),
    )
    col2_pulse_b = Pulse(
        duration=8000,
        amplitude=0.167,
        envelope=Gaussian(rel_sigma = 3.0),
        chirp=(600e5, "Hz/nsec"),
    )
    frequency_sweeper = Sweeper(
        parameter=Parameter.frequency,
        channels=["col_selector_02"],
        values=np.linspace(10e6, 20e6, 5),
    )
    sequence.append(("col_selector_02", col2_pulse_a))
    sequence.append(("col_selector_02", col2_pulse_b))

    #TODO: What are the tones exactly and what is their relationship with channels?
    # TODO: Where are we guaranteeing that the firing is in PARALLEL?
    # # Fire them on a few tones in parallel 
    # sequence.append(("row_selector_01", platform.parameters.pulses["row_selector_01"]))

    results = platform.execute([sequence], [[frequency_sweeper]], nshots=200, relaxation_time=500_000) # relaxation time is 500 µs. It's the wait between shots to let the system reset/relax before the next repetition.
    platform.disconnect()
