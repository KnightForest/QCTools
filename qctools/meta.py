import qcodes as qc
import numpy as np
import time
class setparam_meta(qc.Parameter):
    def __init__(self, name, label, scale_param, instrument, maxVal, unit, inter_delay, step):
        super().__init__(name = name, unit=unit)
        self.label = label
        self._scale_param = float(scale_param)
        self._instrument_channel = instrument
        self._maxVal = float(maxVal)
        self.step = step
        self.inter_delay=inter_delay
        self.metadata = instrument.full_name
        #self.add_parameter('voltage', get_cmd=self.getx, set_cmd=self.setx)

    def get_raw(self):
        raw_getval = self._instrument_channel.get()
        getval = raw_getval * self._scale_param
        return getval
    
    def set_raw(self, setval):
        if abs(setval) > self._maxVal:
            raise Exception("Error: Set value is limited to {:f}".format(self._maxVal))
        else:
            raw_setval = setval / self._scale_param
            self._instrument_channel.set(raw_setval)

class getparam_meta(qc.Parameter):
    def __init__(self, name, label, scale_param, instrument, unit):
        super().__init__(name = name, unit=unit)
        self.label = label
        self._scale_param = float(scale_param)
        self._instrument_channel = instrument
        self.metadata = instrument.full_name

    def get_raw(self):
        raw_getval = self._instrument_channel.get()
        getval = raw_getval * self._scale_param
        return getval

# Define a class for reading out the lockin (read X,Y and convert to R and G) for voltage bias measurement
# dI/dV
# Returns the resistance (R), conductance (G), X, Y lockin values, AC current 
class diff_R_G_Vbias(qc.MultiParameter):
    def __init__(self, 
                 lockin_handle, 
                 V_div, 
                 IV_gain, 
                 V_ac=None, 
                 trans_gain=1,
                 suffix='', 
                 autosense=False, 
                 ntc=3, 
                 lim=1e-6):
        super().__init__('diff_resistance'+suffix,
                         names=('R'+suffix, 'G'+suffix, 'X'+suffix, 'Y'+suffix, 'I_ac'+suffix),
                         shapes=((), (), (), (), ()),
                         labels=('Differential resistance'+suffix, 'Differential conductance'+suffix, 'Raw voltage X'+suffix, 'Raw voltage Y'+suffix, 'I_ac'+suffix),
                         units=(r'$\Omega$', r'e$^2$/h', 'V', 'V', 'A'),
                         setpoints=((), (), (), (), ()),
                         docstring='Differential resistance and conductance from current -IVconv> voltage measurement')
        self._IV_gain = IV_gain
        self._V_div = V_div
        self._lockin_handle = lockin_handle
        self._autosense = autosense
        self._V_ac = V_ac
        if self._V_ac is not None:
            self._lockin_handle.amplitude.set(self._V_ac)
        self._ntc = ntc
        self._lim = lim
        self._trans_gain = trans_gain
    
    def get_raw(self):
        if self._autosense:
            auto_sensitivity(self._lockin_handle, self._ntc, self._lim)
        voltageX,voltageY=np.float64(self._lockin_handle.snap('x','y'))
        self._V_ac = np.float64(self._lockin_handle.amplitude.get())
        # some constants
        const_e = 1.60217662e-19
        const_h = 6.62607004e-34
        I_ac = voltageX/self._IV_gain
        diff_resistance = (self._V_ac*self._trans_gain/self._V_div )/ I_ac
        diff_conductance = 1/diff_resistance / const_e**2 * const_h        
        return (diff_resistance, diff_conductance, voltageX, voltageY, I_ac)

# Define a class for reading out the lockin (X,Y at the same time and convert to R and G)
# dV/dI
# Returns the resistance (R), conductance (G), X and Y lockin values
class diff_R_G_Ibias(qc.MultiParameter):
    def __init__(self, 
                 lockin_handle, 
                 R_pre, 
                 V_gain, 
                 V_ac=None, 
                 trans_gain=1,
                 suffix='', 
                 autosense=False, 
                 ntc=3, 
                 lim=1e-6):
        super().__init__('diff_resistance'+suffix,
                         names=('R'+suffix, 'G'+suffix, 'X'+suffix, 'Y'+suffix),
                         shapes=((), (), (), ()),
                         labels=('Differential resistance'+suffix, 'Differential conductance'+suffix,'Raw voltage X'+suffix, 'Raw voltage Y'+suffix),
                         units=(r'$\Omega$', r'e$^2$/h', 'V', 'V'),
                         setpoints=((), (), (), ()),
                         docstring='Differential resistance and conductance converted from raw voltage measurement')
        self._R_pre = R_pre
        self._V_gain = V_gain
        self._lockin_handle = lockin_handle
        self._autosense = autosense
        self._V_ac = V_ac
        if self._V_ac is not None:
            self._lockin_handle.amplitude.set(self._V_ac)
        self._ntc = ntc
        self._lim = lim
        self._trans_gain = trans_gain
    
    def get_raw(self):
        if self._autosense:
            auto_sensitivity(self._lockin_handle, self._ntc, self._lim)
        voltageX,voltageY=np.float64(self._lockin_handle.snap('x','y'))
        self._V_ac = np.float64(self._lockin_handle.amplitude.get())
        # some constants
        const_e = 1.60217662e-19
        const_h = 6.62607004e-34        
        diff_resistance = (voltageX/self._V_gain)/(self._V_ac*self._trans_gain/(self._R_pre))
        diff_conductance = 1/diff_resistance / const_e**2 * const_h
        return (diff_resistance, diff_conductance, voltageX, voltageY)

def auto_sensitivity(self, ntc, lim):
    sens = self.sensitivity.get()
    X_val = self.X.get()
    tc  = self.time_constant()
    while np.abs(X_val) <= 0.2*sens or np.abs(X_val) >= 0.9*sens:
        if np.abs(X_val) <= 0.2*sens:
            if sens == lim:
                break
            self._change_sensitivity(-1)
            time.sleep(ntc*tc) #Wait to read the correct value
        else:
            self._change_sensitivity(1)
            time.sleep(ntc*tc)
        sens = self.sensitivity.get()
        X_val = self.X.get()  
# Multigate parameter class

class setparam_meta_multigate(qc.Parameter):
    def __init__(self, 
                 name, 
                 label, 
                 scale_param, 
                 instrument, 
                 slope, 
                 offset, 
                 maxVal, 
                 unit, 
                 inter_delay, 
                 step, 
                 metaname, 
                 step_meta = 1e-3, 
                 interdelay_meta = 1e-5):
        super().__init__(name = name, unit=unit)
        self.name = name
        self.label = label
        self._scale_param = np.array(scale_param, dtype=float)
        self._instrument_channel = np.array(instrument)
        self._step_meta = step_meta     ###actual step size of meta, set to "None" if you want the instrument to sweep seperately
        self.step=None                  ###step size for first use or after exceeding maxVal
        self.inter_delay=interdelay_meta
        self._slope = np.array(slope, dtype=float)
        self._offset = np.array(offset, dtype=float)
        self._maxVal = np.array(maxVal, dtype=float)
        self._length = len(self._instrument_channel)
        self.metadata = self._instrument_channel[0].full_name
        self._once = False
        for k in range(self._length):           ###step size and inter delay for each instrument
            instrument[k].step = step[k]
            instrument[k].inter_delay = inter_delay[k]

    def get_raw(self):
        return 0
    
    def set_raw(self, setval):
        ### Initialisation for first run after definition, so that gates are swept seperately
        if (self._once == False):
            self._once = True
            self.step =self._step_meta
        
        ### Calculate the values to set for all instruments
        raw_setval = np.divide((self._slope*setval+self._offset),self._scale_param)

        ### Check maxVal and then set
        can_set = True
        for k in range(self._length):
            if abs(raw_setval[k]) > self._maxVal[k]:
                can_set = False
                break
        if can_set == False:
            raise Exception("Error: One of the set values is limited")
            self._once = False
        else: 
            for k in range(self._length):
                self._instrument_channel[k].set(raw_setval[k])
                                
class get_multigate(qc.MultiParameter):
    def __init__(self, names, labels, scale_param, instrument, units):
        super().__init__(name = 'Your_Multigate', names = names, units = units, labels = labels, shapes = ( (),)*len(instrument), setpoints =( (),)*len(instrument) ) 
        #self.names = names
        #self.label = label
        self._scale_param = np.array(scale_param, dtype=float)
        self._instrument_channel = instrument
        self._length = len(self._instrument_channel)
        self.metadata = 'Multigate_Get'
        
    def get_raw(self):
        get_val = np.zeros(self._length)
        for k in range(self._length):
            get_val[k] = self._instrument_channel[k].get() * self._scale_param[k]
        return get_val