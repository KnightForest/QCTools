import qcodes as qc
class setparam_meta(qc.Parameter):
    def __init__(self, name, label, scale_param, instrument, maxVal, unit):
        super().__init__(name = "setparam_meta", unit=unit)
        self.name = name
        self.label = label
        self._scale_param = float(scale_param)
        self._instrument_channel = instrument
        self._maxVal = float(maxVal)
        #self.add_parameter('voltage', get_cmd=self.getx, set_cmd=self.setx)

    def get_raw(self):
        raw_getval = self._instrument_channel.get()
        getval = raw_getval * self._scale_param
        return getval
    
    def set_raw(self, setval):
        if abs(gate_voltage) > self._maxVal:
            print("Cannot set a gate voltage that is larger than {:f}".format(self._maxVal))
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
        self._maxVal = float(maxVal)
        #self.add_parameter('voltage', get_cmd=self.getx, set_cmd=self.setx)

    def get_raw(self):
        raw_getval = self._instrument_channel.get()
        getval = raw_getval * self._scale_param
        return getval