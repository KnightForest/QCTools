import qcodes as qc
from typing import Tuple
import numpy as np
from qcodes.instrument.parameter import (
    MultiParameter,
    ManualParameter,
    ArrayParameter,
    ParamRawDataType,
)

def generate_flat_top_gaussian(
    frequencies, pulse_duration, rise_fall_time, sampling_rate, scaling=0.9
):
    """Returns complex flat top Gaussian waveforms modulated with the given frequencies.

    Arguments:

        frequencies (array): array specifying the modulation frequencies applied to each
                             output wave Gaussian

        pulse_duration (float): total duration of each Gaussian in seconds

        rise_fall_time (float): rise-fall time of each Gaussian edge in seconds

        sampling_rate (float): sampling rate in samples per second based on which to
                               generate the waveforms

        scaling (optional float): scaling factor applied to the generated waveforms (<=1);
                                  use a scaling factor <= 0.9 to avoid overshoots

    Returns:

        pulses (dict): dictionary containing the flat top Gaussians as values

    """
    if scaling > 1:
        raise ValueError(
            "The scaling factor has to be <= 1 to ensure the generated waveforms lie within the \
                unit circle."
        )

    from scipy.signal import gaussian

    rise_fall_len = int(rise_fall_time * sampling_rate)
    pulse_len = int(pulse_duration * sampling_rate)

    std_dev = rise_fall_len // 10

    gauss = gaussian(2 * rise_fall_len, std_dev)
    flat_top_gaussian = np.ones(pulse_len)
    flat_top_gaussian[0:rise_fall_len] = gauss[0:rise_fall_len]
    flat_top_gaussian[-rise_fall_len:] = gauss[-rise_fall_len:]

    flat_top_gaussian *= scaling

    pulses = {}
    time_vec = np.linspace(0, pulse_duration, pulse_len)

    for i, f in enumerate(frequencies):
        pulses[i] = flat_top_gaussian * np.exp(2j * np.pi * f * time_vec)

    return pulses

class flat_top_gaussian_pulsed_readout_trace(qc.MultiParameter):
    """
    A class for readout with the SHFQA with flat top gaussian pulse sequences.
    
    DEFINITION:
    scan: A time sequence which manipulation and readout happen in. For example,
          the scan of a Rabi or T1 measurement is different.
    probe tone: A pulsed microwave signal to readout the resonator. It is a product
                of the envelop function and the carrier.
    carrier: A continous microwave signal close to the resonator frequency.
    loopback: Internally connect the marker 1A to trigger 1A and generate a marker tone at 1KHz.
    
    INPUT:
    sampling_rate: sampling rate of the envelope (default: 2e9)
    delay_probe: time delay between receiving the trigger and the start of the scan (default: 1e-6)
    scope_length: time of one scope scan in s (default: 5e-6)
    pulse_duration: duration of the envelope in s (default: 500e-9)
    num_rep: number of scans to average (default: 1)
    f_probe: the carrier frequency in Hz (default: 5e9)
    output_power: microwave power at the output
    input_power: max microwave power at the input
    loopback: enable loopback triggering (default: True)
    
    OUTPUT:
    A trace of demodulated transmitted signal from output 1 to input 1 as a function of time.
    The total time is set by num_rep*period.
    
    TO DO:
    buggy if sampling_rate != 2e9. Need to check
    """
    def __init__(self,
                 SHFQA_handle,
                 AWG_handle = None,
                 name='SHFQA_flat_top_gaussian_pulsed_readout_trace',
                 sampling_rate = 2e9,
                 delay_probe = 1e-6,
                 scope_length = 5e-6,
                 pulse_duration = 500e-9,
                 num_rep = 1,
                 f_center = 5e9,
                 f_osc = 1e6,
                 output_power = -30,
                 input_power = -20,
                 loopback = True):
        super().__init__(name,
                        names=("Real", "Imag"),
                        labels=(f"$\Re$", f"$\Im$"),
                        units=("V", "V"),
                        setpoint_names=(
                            (f"SHFQA_f_probe",),
                            (f"SHFQA_f_probe",),
                        ),
                        setpoint_units=(("s",), ("s",)),
                        setpoint_labels=(("time",), ("time",)),
                        shapes=((int(scope_length*sampling_rate),), (int(scope_length*sampling_rate),),),
                        )
        self._set_time_axis(scope_length,sampling_rate)        
        
        # store some useful parameters
        self._SHFQA_handle = SHFQA_handle
        self._channel = SHFQA_handle.qachannels[0]
        self._AWG_handle = AWG_handle
        self._loopback = loopback
        
        # set up SHFQA for pulse readout
        self._set_up_measurement(sampling_rate,
                delay_probe,
                scope_length,
                pulse_duration,
                num_rep,
                f_center,
                f_osc,
                output_power,
                input_power,
                self._SHFQA_handle,
                self._AWG_handle,
                self._channel,
                self._loopback)
        

    def _set_up_measurement(self, 
                            sampling_rate: float,
                            delay_probe: float,
                            scope_length: float,
                            pulse_duration: float,
                            num_rep: int,
                            f_center: float,
                            f_osc: float,
                            output_power: float,
                            input_power: float,
                            SHFQA_handle,
                            AWG_handle,
                            channel,
                            loopback: bool) -> None:
        """
        set up the AWG
        """
        if AWG_handle.ch1_state.get():
            AWG_handle.stop()
            AWG_handle.ch1_state(0)                                   
                            
        """
        set up the SHFQA for pulse readout
        """
        # Select channel to use for readout
        scope = SHFQA_handle.scope
        generator = channel.generator
        sweeper = channel.sweeper

        # use marker 1A to trigger trigger 1A
        SHFQA_handle.clear_trigger_loopback()
        if loopback:
            SHFQA_handle.set_trigger_loopback()

        # set up channel
        channel.input_range.set(input_power)
        channel.output_range.set(output_power)
        channel.center_freq.set(f_center)
        channel.mode.set('readout')
        channel.input.set('on')
        channel.output.set('on')
        
        # setup sweeper
        sweeper.oscillator_freq.set(f_osc)    

        # set up scope
        scope.channel1.set('on')
        scope.trigger_source.set('channel0_sequencer_trigger0')
        scope.input_select1.set('chan0sigin')
        scope.trigger_delay.set(0)
        scope.length.set(round(scope_length*sampling_rate))
        scope.time.set(0)
        scope.averaging(True, count=num_rep)
        scope.segments(False, count=1)

        # set up generator
        generator.dig_trigger1_source.set('channel0_trigger_input0')
        generator.playback_delay.set(0)
        generator.single.set(True)

        generator.reset_queue()
        custom_program="""
        repeat ($param1$){
          waitDigTrigger(1);
          setTrigger(1);
          wait(round((5e-6+$param2$)/4e-9));
          startQA(QA_GEN_0, QA_INT_0, true,  0, 0x0);
          setTrigger(0);
        }
        """
        generator.set_sequence_params(sequence_type='Custom',
                                     program = custom_program,
                                     custom_params = [num_rep, delay_probe]
                                     )

        readout_pulse = generate_flat_top_gaussian(
            frequencies=[0],
            pulse_duration=pulse_duration,
            rise_fall_time=25e-9,
            sampling_rate=sampling_rate,
            scaling = 0.9)
        generator.queue_waveform(readout_pulse[0],delay = 0)
        generator.compile_and_upload_waveforms()
        

    def _set_time_axis(self,scope_length,sampling_rate) -> None:
        t = tuple(np.linspace(0, scope_length, num=int(sampling_rate*scope_length)))
        self.setpoints = ((t,), (t,))
        self.shapes = ((int(scope_length*sampling_rate),), (int(scope_length*sampling_rate),))
        
        
    def get_raw(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        get the raw real and imag parts of the scope 
        """
        # stop service
        if self._SHFQA_handle.scope.is_running:
            self._SHFQA_handle.scope.stop()
            self._channel.generator.stop()
        
        # Run service
        self._SHFQA_handle.scope.run()
        self._channel.generator.run()
        
        if not self._loopback:
            if self._AWG_handle.ch1_state.get():
                self._AWG_handle.stop()
                self._AWG_handle.ch1_state(0)
            self._AWG_handle.ch1_state(1)
            self._AWG_handle.run()
        
        result=self._SHFQA_handle.scope.read(channel=0,timeout=10)
        self._channel.generator.stop()
        self._SHFQA_handle.scope.stop()
        real = np.real(result['data'])
        imag = np.imag(result['data'])
        
        if not self._loopback:
            self._AWG_handle.stop()
            self._AWG_handle.ch1_state(0)
        return real, imag
        
        
class pulsed_spectroscopy(qc.MultiParameter):
    """
    A class for pulsed spectroscopy with the SHFQA.
    
    DEFINITION:
    
    
    INPUT:
    
    
    OUTPUT:
    
    
    TO DO:
    # not ready. DO NOT USE THIS CLASS
    
    """
    def __init__(self,
                 SHFQA_handle,
                 name='SHFQA_pulsed_spectroscopy',
                 integration_duration = 1e-6,
                 num_pts = 101,
                 num_avg = 1,
                 f_center = 5e9,
                 f_start = -50e6,
                 f_stop = 50e6,
                 output_power = -30,
                 input_power = -20):
        super().__init__(name,
                        names=("Power", "Phase"),
                        labels=(r"$P$", r"$\phi$",),
                        units=("dBm", "rad"),
                        setpoint_names=(
                            (r"SHFQA_f_probe",),
                            (r"SHFQA_f_probe",),
                        ),
                        setpoint_units=(("Hz",), ("Hz",)),
                        setpoint_labels=((r"$f_{probe}$",), (r"$f_{probe}$",),),
                        shapes=((num_pts,), (num_pts,),),
                        )
        self._set_frequency_axis(num_pts,f_center,f_start,f_stop)        
        
        # set up SHFQA for pulse readout
        self._SHFQA_handle = SHFQA_handle
        self._channel = SHFQA_handle.qachannels[0]
        self._set_up_measurement(self._SHFQA_handle,
                                 self._channel,
                                 integration_duration,
                                 num_pts,
                                 num_avg,
                                 f_center,
                                 f_start,
                                 f_stop,
                                 output_power,
                                 input_power)
        

    def _set_up_measurement(self,
                             SHFQA_handle,
                             channel,
                             integration_duration: float,
                             num_pts: int,
                             num_avg: int,
                             f_center: float,
                             f_start: float,
                             f_stop: float,
                             output_power: int,
                             input_power: int,
                             ) -> None:
        """
        set up the SHFQA for pulsed spectroscopy
        """
        # Select channel to use
        sweeper = channel.sweeper

        # use marker 1A to trigger trigger 1A
        SHFQA_handle.set_trigger_loopback()

        # set up channel
        channel.input_range.set(input_power)
        channel.output_range.set(output_power)
        channel.center_freq.set(f_center)
        channel.mode.set('spectroscopy')
        channel.input.set('on')
        channel.output.set('on')

        # set sweeper trigger to listen to trigger 1A, trigger impedance = 1kOhm
        sweeper.trigger_source("channel0_trigger_input0")
        sweeper.trigger_level(0)
        sweeper.trigger_imp50(0)

        # set up sweeper
        sweeper.oscillator_gain(1)
        sweeper.start_frequency(f_start)
        sweeper.stop_frequency(f_stop)
        sweeper.num_points(num_pts)
        sweeper.mapping("linear")
        sweeper.integration_time(integration_duration)
        sweeper.num_averages(num_avg)
        sweeper.averaging_mode("sequential")
        

    def _set_frequency_axis(self,
                            num_pts: int,
                            f_center: float,
                            f_start: float,
                            f_stop: float) -> None:
        f = tuple(np.linspace(f_center-f_start, f_center+f_stop, num=num_pts))
        self.setpoints = ((f,), (f,))
        self.shapes = ((num_pts,), (num_pts,))
        
        
    def get_raw(self) -> Tuple[ParamRawDataType, ...]:
        """
        get the raw power and phase
        """
        # Run and get result
        self._channel.sweeper.run()

        result = self._channel.sweeper.read()
        power = 10*np.log10(np.abs(result['vector']))
        phase = np.angle(result['vector'])
        return power, phase
        
        
class flat_top_gaussian_pulsed_readout_point(qc.MultiParameter):
    """
    A class for readout with the SHFQA with flat top gaussian pulse sequences. The mean value is 
    taken from the scope trace.

    DEFINITION:
    scan: A time sequence which manipulation and readout happen in. For example,
      the scan of a Rabi or T1 measurement is different.
    probe tone: A pulsed microwave signal to readout the resonator. It is a product
            of the envelop function and the carrier.
    carrier: A continous microwave signal close to the resonator frequency.
    loopback: Internally connect the marker 1A to trigger 1A and generate a marker tone at 1KHz.

    INPUT:
    sampling_rate: sampling rate of the envelope (default: 2e9)
    delay_probe: time delay between receiving the trigger and the start of the scan (default: 1e-6)
    scope_length: time of one scope scan in s (default: 5e-6)
    scope_delay: delay between scope trigger and scope start in s (default: 5e-6)
    pulse_duration: duration of the envelope in s (default: 500e-9)
    num_rep: number of scans to average (default: 1)
    f_center: the carrier frequency in Hz (default: 5e9)
    f_osc: digital oscillator frequency in Hz (default: 1e6)
    output_power: microwave power at the output
    input_power: max microwave power at the input
    loopback: enable loopback triggering (default: True)

    OUTPUT:
    A trace of demodulated transmitted signal from output 1 to input 1 as a function of time.
    The total time is set by num_rep*period.

    TO DO:
    buggy if sampling_rate != 2e9. Need to check
    """
    def __init__(self,
             SHFQA_handle,
             AWG_handle = None,
             name='SHFQA_flat_top_gaussian_pulsed_readout_point',
             sampling_rate = 2e9,
             delay_probe = 0,
             scope_delay = 5e-6,
             scope_length = 5e-6,
             pulse_duration = 500e-9,
             num_rep = 1,
             f_center = 5e9,
             f_osc = 1e6,
             output_power = -30,
             input_power = -20,
             loopback = True):
        super().__init__(name,
                        names=("Real", "Imag"),
                        labels=(f"$\Re$", f"$\Im$"),
                        units=("V", "V"),
                        setpoints=((),(),),
                        shapes=((),(),),
                        )

        # store some useful parameters
        self._SHFQA_handle = SHFQA_handle
        self._channel = SHFQA_handle.qachannels[0]
        self._AWG_handle = AWG_handle
        self._loopback = loopback

        # set up SHFQA for pulse readout
        self._set_up_measurement(sampling_rate,
                delay_probe,
                scope_delay,
                scope_length,
                pulse_duration,
                num_rep,
                f_center,
                f_osc,
                output_power,
                input_power,
                self._SHFQA_handle,
                self._AWG_handle,
                self._channel,
                self._loopback)


    def _set_up_measurement(self, 
                        sampling_rate: float,
                        delay_probe: float,
                        scope_delay: float,
                        scope_length: float,
                        pulse_duration: float,
                        num_rep: int,
                        f_center: float,
                        f_osc: float,
                        output_power: float,
                        input_power: float,
                        SHFQA_handle,
                        AWG_handle,
                        channel,
                        loopback: bool) -> None:
        """
        set up the AWG
        """
        if not AWG_handle == None:
            if AWG_handle.ch1_state.get():
                AWG_handle.stop()
                AWG_handle.ch1_state(0)                                   
                            
        """
        set up the SHFQA for pulse readout
        """
        # Select channel to use for readout
        scope = SHFQA_handle.scope
        generator = channel.generator
        sweeper = channel.sweeper

        # use marker 1A to trigger trigger 1A
        SHFQA_handle.clear_trigger_loopback()
        if loopback:
            SHFQA_handle.set_trigger_loopback()

        # set up channel
        channel.input_range.set(input_power)
        channel.output_range.set(output_power)
        channel.center_freq.set(f_center)
        channel.mode.set('readout')
        channel.input.set('on')
        channel.output.set('on')
        
        # set up the sweeper
        sweeper.oscillator_freq.set(f_osc)  

        # set up scope
        scope.channel1.set('on')
        scope.trigger_source.set('channel0_sequencer_trigger0')
        scope.input_select1.set('chan0sigin')
        scope.trigger_delay.set(scope_delay)
        scope.length.set(round(scope_length*sampling_rate))
        scope.time.set(0)
        scope.averaging(True, count=num_rep)
        scope.segments(False, count=1)

        # set up generator
        generator.dig_trigger1_source.set('channel0_trigger_input0')
        generator.playback_delay.set(0)
        generator.single.set(True)

        generator.reset_queue()
        custom_program="""
        repeat ($param1$){
          waitDigTrigger(1);
          setTrigger(1);
          wait(round((5e-6+$param2$)/4e-9));
          startQA(QA_GEN_0, QA_INT_0, true,  0, 0x0);
          setTrigger(0);
        }
        """
        generator.set_sequence_params(sequence_type='Custom',
                                     program = custom_program,
                                     custom_params = [num_rep, delay_probe]
                                     )

        readout_pulse = generate_flat_top_gaussian(
            frequencies=[0],
            pulse_duration=pulse_duration,
            rise_fall_time=25e-9,
            sampling_rate=sampling_rate,
            scaling = 0.9)
        generator.queue_waveform(readout_pulse[0],delay = 0)
        generator.compile_and_upload_waveforms()


    def get_raw(self) -> Tuple[float,float]:
        """
        get the raw real and imag parts of the scope 
        """
        # stop service
        if self._SHFQA_handle.scope.is_running:
            self._SHFQA_handle.scope.stop()
            self._channel.generator.stop()

        # Run service
        self._SHFQA_handle.scope.run()
        self._channel.generator.run()

        if not self._loopback:
            if self._AWG_handle.ch1_state.get():
                self._AWG_handle.stop()
                self._AWG_handle.ch1_state(0)
            self._AWG_handle.ch1_state(1)
            self._AWG_handle.run()

        result=self._SHFQA_handle.scope.read(channel=0,timeout=10)
        self._channel.generator.stop()
        self._SHFQA_handle.scope.stop()
        real = np.real(result['data'])
        imag = np.imag(result['data'])

        if not self._loopback:
            self._AWG_handle.stop()
            self._AWG_handle.ch1_state(0)
        return np.mean(real), np.mean(imag)