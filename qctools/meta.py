import qcodes as qc
import numpy as np
import time
class setparam_meta(qc.Parameter):
    def __init__(self, name, label, scale_param, instrument, maxVal, unit, inter_delay, step):
        super().__init__(name = "setparam_meta", unit=unit)
        self.name = name
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
        super().__init__(name = "setparam_meta", unit=unit)
        self.name = name
        self.label = label
        self._scale_param = float(scale_param)
        self._instrument_channel = instrument
        self.metadata = instrument.full_name
        #self.add_parameter('voltage', get_cmd=self.getx, set_cmd=self.setx)

    def get_raw(self):
        raw_getval = self._instrument_channel.get()
        getval = raw_getval * self._scale_param
        return getval

# Define a class for reading out the lockin (read X,Y and convert to R and G) for voltage bias measurement
# dI/dV
# Returns the resistance (R), conductance (G), X, Y lockin values, AC current 
class diff_R_G_Vbias(qc.MultiParameter):
    def __init__(self, lockin_handle, IV_gain, V_div, V_ac=None, suffix='', autosense=False, ntc=3, lim=1e-6):
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
    
    def get_raw(self):
        if self._autosense:
            auto_sensitivity(self._lockin_handle, self._ntc, self._lim)
        voltageXY = self._lockin_handle.visa_handle.query("SNAP? 1,2")    
        voltageX, voltageY = voltageXY.split(",")
        voltageX = np.float64(voltageX)
        voltageY = np.float64(voltageY)
        self._V_ac = np.float64(self._lockin_handle.visa_handle.query("SLVL?"))
        print(self._V_ac)
        # some constants
        const_e = 1.60217662e-19
        const_h = 6.62607004e-34
        I_ac = voltageX/self._IV_gain
        diff_resistance = (self._V_ac/self._V_div )/ I_ac
        diff_conductance = 1/diff_resistance / const_e**2 * const_h        
        return (diff_resistance, diff_conductance, voltageX, voltageY, I_ac)
#diff_resistance = diff_R_G_Vbias(V_ac = 10e-3, IV_gain = 1e6, V_div = 4*1000, lockin_handle=lockin, suffix="_8", autosense=False)
#diff_resistance = diff_R_G_Vbias(IV_gain = 1e6, V_div = 4*1000, lockin_handle=lockin, suffix="_8", autosense=True)

# Define a class for reading out the lockin (X,Y at the same time and convert to R and G)
# dV/dI
# Returns the resistance (R), conductance (G), X and Y lockin values
class diff_R_G_Ibias(qc.MultiParameter):
    def __init__(self, lockin_handle, R_pre, V_gain, V_ac=None, suffix='', autosense=False, ntc=3, lim=1e-6):
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
    
    def get_raw(self):
        if self._autosense:
            auto_sensitivity(self._lockin_handle, self._ntc, self._lim)
        voltageXY = self._lockin_handle.visa_handle.ask("SNAP? 1,2")    
        voltageX, voltageY = voltageXY.split(",")
        voltageX = np.float64(voltageX)
        voltageY = np.float64(voltageY)
        self._V_ac = np.float64(self._lockin_handle.visa_handle.query("SLVL?"))
        # some constants
        const_e = 1.60217662e-19
        const_h = 6.62607004e-34        
        diff_resistance = (voltageX/self._V_gain)/(self._V_ac/self._R_pre)
        diff_conductance = 1/diff_resistance / const_e**2 * const_h
        return (diff_resistance, diff_conductance, voltageX, voltageY)
#diff_resistance = diff_R_G_Ibias(V_ac = 10e-3, R_pre=1e6, V_gain = 100, lockin_handle=lockin, suffix="_8", autosense=False)


#Lock-in auto_sensitivity functions
# def change_sensitivity_AP(self, dn):
    # _ = self.sensitivity.get()
    # n = int(self.raw_value)
    # if self.input_config() in ['a', 'a-b']:
        # n_to = self._N_TO_VOLT
    # else:
        # n_to = self._N_TO_CURR

    # if n + dn > max(n_to.keys()) or n + dn < min(n_to.keys()):
        # return False

    # self.sensitivity.set(n_to[n + dn])
    # time.sleep(3*self.time_constant()) #Wait to read the correct value
    # return True

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
