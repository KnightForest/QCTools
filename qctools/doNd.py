import qcodes as qc
from qcodes import Station, Measurement
import qctools
import time
import numpy as np

#Basic do1d
def do1d(param_set, start, stop, num_points, delay, param_meas, name='', comment=''):
    import numpy as np
    meas = Measurement()
    
    ### Creating and filling station for snapshotting:
    meas.name = name
    station = Station()
    station.add_component(param_set)
    allinstr = qc.instrument.base.Instrument._all_instruments
    for key,val in allinstr.items():
        instr = qc.instrument.base.Instrument.find_instrument(key)
        station.add_component(instr)
    measparstring = ""
    for parameter in param_meas:
        station.add_component(parameter)
        measparstring += parameter.name + ', '
    
    #Sample blowup prevention, patent pending
    if param_set.step == 0 or param_set.step == None:
        param_set.step = abs(start-stop)/(num_points-1)
        print('Warning, \'step\' attribute for set parameter undefined. Defaulting to measurement stepsize :{}'.format(param_set.step) )
    if param_set.inter_delay == 0 or param_set.inter_delay == None:
        param_set.inter_delay = 0.05
        print('Warning, \'inter_delay\' attribute for set parameter undefined. Defaulting to \'0.05\'')
    
    ### Printing some useful metadata:
    import datetime
    print('Starting run:', name)
    print('Comment:', comment)
    print('Set axis: ', str(param_set.name), 
          '\nReadout parameters: ', str(measparstring), '\n')
    starttime = datetime.datetime.now()
    print('Started: ', starttime)
    sweeptime = (delay+param_set.inter_delay)*(1+abs(start-stop)/param_set.step)
    meastime = num_points*(max(delay,param_set.inter_delay))
    if sweeptime<meastime:
        esttime = 1.15*sweeptime+meastime
    else:
        esttime = 1.15*2*sweeptime
    print('Estimated duration:', str(datetime.timedelta(seconds=esttime)))
    print('ETA:', str(datetime.timedelta(seconds=esttime)+starttime))
    meas.write_period = 0.5
    ###
    
    meas.register_parameter(param_set)  # register the first independent parameter
    output = []
    param_set.post_delay = delay
    # do1D enforces a simple relationship between measured parameters
    # and set parameters. For anything more complicated this should be reimplemented from scratch
    for parameter in param_meas:
        meas.register_parameter(parameter, setpoints=(param_set,))
        output.append([parameter, None])
        
    with meas.run() as datasaver:
        #Uncomment the next two lines if you use the old plottr
        #datasaver.dataset.subscribe(LivePlotSubscriber(datasaver.dataset), state=[], 
        #                        min_wait=0, min_count=1)
        for set_point in np.linspace(start, stop, num_points):
            param_set.set(set_point)
            for i, parameter in enumerate(param_meas):
                output[i][1] = parameter.get()
            datasaver.add_result((param_set, set_point),
                                 *output)
    ###
    datasaver.dataset.add_metadata('Comment', comment)
    endtime = datetime.datetime.now()
    print('Final duration: ', endtime-starttime)
    print('Finished: ', endtime)
    ###
    qctools.db_extraction.db_extractor(dbloc = qc.dataset.sqlite.database.get_DB_location(), 
                                       ids=[datasaver.run_id], 
                                       overwrite=True,
                                       newline_slowaxes=True,
                                       no_folders=False,
                                       suppress_output=False)
    return datasaver.run_id  # convenient to have for plotting

#More advanced do1d
#Waits for a time given by settle_time after setting the setpoint
#Delay is the time taken to ramp to the next setpoint
def do1d_settle(param_set, space, delay, settle_time, param_meas, name='', comment=''):
    import numpy as np
    meas = Measurement()    
    
    ### Creating and filling station for snapshotting:
    meas.name = name
    station = Station()
    station.add_component(param_set)
    allinstr = qc.instrument.base.Instrument._all_instruments
    for key,val in allinstr.items():
        instr = qc.instrument.base.Instrument.find_instrument(key)
        station.add_component(instr)
    measparstring = ""
    for parameter in param_meas:
        station.add_component(parameter)
        measparstring += parameter.name + ', '
    
    #Sample blowup prevention, patent pending
    if param_set.step == 0 or param_set.step == None:
        param_set.step = min(abs(np.diff(space)))
        print('Warning, \'step\' attribute for set parameter undefined. Defaulting to measurement stepsize :{}'.format(param_set.step) )
    if param_set.inter_delay == 0 or param_set.inter_delay == None:
        param_set.inter_delay = 0.05
        print('Warning, \'inter_delay\' attribute for set parameter undefined. Defaulting to \'0.05\'')
        
    ### Printing some useful metadata:
    import datetime
    print('Starting run:', name)
    print('Comment:', comment)
    print('Set axis: ', str(param_set.name), 
          '\nReadout parameters: ', str(measparstring), '\n')
    starttime = datetime.datetime.now()
    print('Started: ', starttime)
    sweeptime = (max(delay,param_set.inter_delay))*(1+abs(space[0]-space[-1])/param_set.step)
    meastime = len(space)*(max(delay,param_set.inter_delay)+settle_time)
    if sweeptime<meastime:
        esttime = 1.15*sweeptime+meastime
    else:
        esttime = 1.15*2*sweeptime
    print('Estimated duration:', str(datetime.timedelta(seconds=esttime)))
    print('ETA:', str(datetime.timedelta(seconds=esttime)+starttime))
    meas.write_period = 0.5
    ###
    
    meas.register_parameter(param_set)  # register the first independent parameter
    output = [] 
    param_set.post_delay = delay
    # do1D enforces a simple relationship between measured parameters
    # and set parameters. For anything more complicated this should be reimplemented from scratch
    for parameter in param_meas:
        meas.register_parameter(parameter, setpoints=(param_set,))
        output.append([parameter, None])        
    
    with meas.run() as datasaver:
        #Uncomment the next two lines if you use the old plottr
        #datasaver.dataset.subscribe(LivePlotSubscriber(datasaver.dataset), state=[], 
        #                            min_wait=0, min_count=1)
        for set_point in space:
            param_set.set(set_point)
            time.sleep(settle_time)
            for i, parameter in enumerate(param_meas):
                output[i][1] = parameter.get()
            datasaver.add_result((param_set, set_point),
                                 *output)
    ###
    datasaver.dataset.add_metadata('Comment', comment)
    endtime = datetime.datetime.now()
    print('Final duration: ', endtime-starttime)
    print('Finished: ', endtime)
    ###
    qctools.db_extraction.db_extractor(dbloc = qc.dataset.sqlite.database.get_DB_location(), 
                                       ids=[datasaver.run_id], 
                                       overwrite=True,
                                       newline_slowaxes=False,
                                       no_folders=False,
                                       suppress_output=False)
    return datasaver.run_id

    #Basic do2d
def do2d(param_set1, start1, stop1, num_points1, delay1,
         param_set2, start2, stop2, num_points2, delay2,
         param_meas, name='', comment='', fasttozero=False):
    # And then run an experiment
    import numpy as np
    meas = Measurement()
    
    ### Creating and filling station for snapshotting:
    meas.name = name
    station = Station()
    station.add_component(param_set1)
    station.add_component(param_set2)
    allinstr=qc.instrument.base.Instrument._all_instruments
    for key,val in allinstr.items():
        instr = qc.instrument.base.Instrument.find_instrument(key)
        station.add_component(instr)
    measparstring = ""
    for parameter in param_meas:
        station.add_component(parameter)
        measparstring += parameter.name + ', '
    
    #Sample blowup prevention, patent pending
    if param_set1.step == 0 or param_set1.step == None:
        param_set1.step = abs(start1-stop1)/(num_points1-1)
        print('Warning, \'step\' attribute for set parameter 1 undefined. Defaulting to measurement stepsize :{}'.format(param_set1.step) )
    if param_set1.inter_delay == 0 or param_set1.inter_delay == None:
        param_set1.inter_delay = 0.05
        print('Warning, \'inter_delay\' attribute for set parameter 1 undefined. Defaulting to \'0.05\'')
    if param_set2.step == 0 or param_set2.step == None:
        param_set2.step = abs(start2-stop2)/(num_points2-1)
        print('Warning, \'step\' attribute for set parameter 2 undefined. Defaulting to measurement stepsize :{}'.format(param_set2.step) )
    if param_set2.inter_delay == 0 or param_set2.inter_delay == None:
        param_set2.inter_delay = 0.05
        print('Warning, \'inter_delay\' attribute for set parameter 2 undefined. Defaulting to \'0.05\'')
    
    ### Printing some useful metadata:
    import datetime
    print('Starting run:', name)
    print('Comment:', comment)
    print('Fast set axis: ', str(param_set2.name), '\nSlow set axis: ', str(param_set1.name), 
          '\nReadout parameters: ', str(measparstring), '\n')
    starttime = datetime.datetime.now()
    print('Started: ', starttime)
    sweeptimefast = (max(delay2,param_set2.inter_delay))*(1+abs(start2-stop2)/param_set2.step)
    meastimefast = num_points2*(max(delay2,param_set2.inter_delay))
    if sweeptimefast<meastimefast:
        esttimefast = sweeptimefast+meastimefast
    else:
        esttimefast = 2*sweeptimefast
    esttime = 1.15*esttimefast*num_points1+(max(delay1,param_set1.inter_delay))*num_points1
    print('Estimated duration:', str(datetime.timedelta(seconds=esttime)))
    print('ETA:', str(datetime.timedelta(seconds=esttime)+starttime))
    meas.write_period = 0.5
    ###
    meas.register_parameter(param_set1)
    param_set1.post_delay = delay1
    meas.register_parameter(param_set2)
    param_set2.post_delay = delay2
    output = [] 
    for parameter in param_meas:
        meas.register_parameter(parameter, setpoints=(param_set1,param_set2))
        output.append([parameter, None])

    with meas.run() as datasaver:
        #Uncomment the next two lines if you use the old plottr
        #datasaver.dataset.subscribe(LivePlotSubscriber(datasaver.dataset), state=[], 
        #                        min_wait=0, min_count=1)
        for set_point1 in np.linspace(start1, stop1, num_points1):
            param_set1.set(set_point1)
            for set_point2 in np.linspace(start2, stop2, num_points2):
                param_set2.set(set_point2)
                for i, parameter in enumerate(param_meas):
                    output[i][1] = parameter.get()
                datasaver.add_result((param_set1, set_point1),
                                    (param_set2, set_point2),
                                     *output)
            #Puts the fast axis back to zero before stepping slow axis.
            if fasttozero == True:
                param_set2.set(0.0)
            #Run db_extractor after fast axes is finished
            qctools.db_extraction.db_extractor(dbloc = qc.dataset.sqlite.database.get_DB_location(), 
                                       ids=[datasaver.run_id], 
                                       overwrite=True,
                                       newline_slowaxes=True,
                                       no_folders=False,
                                       suppress_output=True)
    dataid = datasaver.run_id  # convenient to have for plotting
    ###
    datasaver.dataset.add_metadata('Comment', comment)
    endtime = datetime.datetime.now()
    print('Final duration: ', endtime-starttime)
    print('Finished: ', endtime)

    ###
    qctools.db_extraction.db_extractor(dbloc = qc.dataset.sqlite.database.get_DB_location(), 
                                       ids=[datasaver.run_id], 
                                       overwrite=True,
                                       newline_slowaxes=True,
                                       no_folders=False,
                                       suppress_output=False)
    return dataid


#More advanced do2d
#Modified for custom resolution and to wait for settle_time time after every time set_point is set
#e.g.    space1 = np.concatenate(([1, 2], np.arange(2.5,6.1,0.5), [6.1, 6.2, 6.25, 6.3, 6.5]))
#        space2 = np.linspace(-2e-6, 2e-6, 1000)
def do2d_settle(param_set1, space1, delay1, settle_time1, 
                param_set2, space2, delay2, settle_time2, 
                param_meas, name='', comment='', fasttozero=False):
    # And then run an experiment
    import numpy as np
    meas = Measurement()
    
    ### Creating and filling station for snapshotting:
    meas.name = name
    station = Station()
    station.add_component(param_set1)
    station.add_component(param_set2)
    allinstr=qc.instrument.base.Instrument._all_instruments
    for key,val in allinstr.items():
        instr = qc.instrument.base.Instrument.find_instrument(key)
        station.add_component(instr)
    measparstring = ""
    for parameter in param_meas:
        station.add_component(parameter)
        measparstring += parameter.name + ', '
    
    #Sample blowup prevention, patent pending
    if param_set1.step == 0 or param_set1.step == None:
        param_set1.step = min(abs(np.diff(space1)))
        print('Warning, \'step\' attribute for set parameter 1 undefined. Defaulting to measurement stepsize :{}'.format(param_set1.step) )
    if param_set1.inter_delay == 0 or param_set1.inter_delay == None:
        param_set1.inter_delay = 0.05
        print('Warning, \'inter_delay\' attribute for set parameter 1 undefined. Defaulting to \'0.05\'')
    if param_set2.step == 0 or param_set2.step == None:
        param_set2.step = min(abs(np.diff(space2)))
        print('Warning, \'step\' attribute for set parameter 2 undefined. Defaulting to measurement stepsize :{}'.format(param_set2.step) )
    if param_set2.inter_delay == 0 or param_set2.inter_delay == None:
        param_set2.inter_delay = 0.05
        print('Warning, \'inter_delay\' attribute for set parameter 2 undefined. Defaulting to \'0.05\'')
    
    ### Printing some useful metadata:
    import datetime
    print('Starting run:', name)
    print('Comment:', comment)
    print('Fast set axis: ', str(param_set2.name), '\nSlow set axis: ', str(param_set1.name), 
          '\nReadout parameters: ', str(measparstring), '\n')
    starttime = datetime.datetime.now()
    print('Started: ', starttime)
    sweeptimefast = (max(delay2,param_set2.inter_delay))*(1+abs(space2[0]-space2[-1])/param_set2.step)
    meastimefast = len(space2)*(max(delay2,param_set2.inter_delay)+settle_time2)
    if sweeptimefast<meastimefast:
        esttimefast = sweeptimefast+meastimefast
    else:
        esttimefast = 2*sweeptimefast
    esttime = 1.15*esttimefast*len(space1)+(max(delay1,param_set1.inter_delay)+settle_time1)*len(space1)
    #esttime = len(space2)*(delay2+settle_time2)*len(space1)+len(space1)*(delay1+settle_time1)
    print('Estimated duration:', str(datetime.timedelta(seconds=esttime)))
    print('ETA:', str(datetime.timedelta(seconds=esttime)+starttime))
    meas.write_period = 0.5
    ###
    
    meas.register_parameter(param_set1)
    param_set1.post_delay = delay1
    meas.register_parameter(param_set2)
    param_set2.post_delay = delay2
    output = [] 
    for parameter in param_meas:
        meas.register_parameter(parameter, setpoints=(param_set1,param_set2))
        output.append([parameter, None])
    print('Started at ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    with meas.run() as datasaver:
        #Uncomment the next two lines if you use the old plottr
        #datasaver.dataset.subscribe(LivePlotSubscriber(datasaver.dataset), state=[], 
        #                        min_wait=0, min_count=1)
        for set_point1 in space1:
            param_set1.set(set_point1)
            if space1.tolist().index(set_point1) is not 0: #Do not wait after the first setpoint
                time.sleep(settle_time1) #Wait for settle_time1 time (s) after setting the set_point1
                           
            for set_point2 in space2:
                param_set2.set(set_point2)
                time.sleep(settle_time2) #Wait for settle_time2 time (s) after setting the set_point2
                for i, parameter in enumerate(param_meas):
                    output[i][1] = parameter.get()
                datasaver.add_result((param_set1, set_point1),
                                     (param_set2, set_point2),
                                     *output)
            if fasttozero == True:
                param_set2.set(0.0)
            if space1.tolist().index(set_point1) is 0: #Print the time taken for the first inner run
                print('First Inner Run Finished at ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            #Run db_extractor after fast axes is finished
            qctools.db_extraction.db_extractor(dbloc = qc.dataset.sqlite.database.get_DB_location(), 
                                       ids=[datasaver.run_id], 
                                       overwrite=True,
                                       newline_slowaxes=False,
                                       no_folders=False,
                                       suppress_output=True)
    ###
    datasaver.dataset.add_metadata('Comment', comment)
    endtime = datetime.datetime.now()
    print('Final duration: ', endtime-starttime)
    print('Finished: ', endtime)
    qctools.db_extraction.db_extractor(dbloc = qc.dataset.sqlite.database.get_DB_location(), 
                                       ids=[datasaver.run_id], 
                                       overwrite=True,
                                       newline_slowaxes=False,
                                       no_folders=False,
                                       suppress_output=True)
    return datasaver.run_id

# Define a class for reading out the lockin (read X,Y and convert to R and G) for voltage bias measurement
# dI/dV
# Returns the resistance (R), conductance (G), X, Y lockin values, AC current 
class diff_R_G_Vbias(qc.MultiParameter):
    def __init__(self, IV_gain, V_div, lockin_handle, V_ac='', suffix='', autosense=False):
        super().__init__('diff_resistance'+suffix,
                         names=('R'+suffix, 'G'+suffix, 'X'+suffix, 'Y'+suffix, 'I_ac'+suffix),
                         shapes=((), (), (), (), ()),
                         labels=('Differential resistance '+suffix, 'Differential conductance '+suffix, 'Raw voltage X'+suffix, 'Raw voltage Y'+suffix, 'I_ac'+suffix),
                         units=('Ohm', 'e^2/h', 'V', 'V', 'A'),
                         setpoints=((), (), (), (), ()),
                        docstring='Differential resistance and conductance from current -IVconv> voltage measurement')
        self._IV_gain = IV_gain
        self._V_div = V_div
        self._lockin_handle = lockin_handle
        self._autosense = autosense
        self._V_ac = V_ac
        if V_ac == '':
            self._V_ac = np.float64(self._lockin_handle.visa_handle.query("SLVL?"))
    
    def get_raw(self):
        if self._autosense:
                    auto_sensitivity(self._lockin_handle)
        voltageXY = self._lockin_handle.visa_handle.query("SNAP? 1,2")    
        voltageX, voltageY = voltageXY.split(",")
        voltageX = np.float64(voltageX)
        voltageY = np.float64(voltageY)
        
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
    def __init__(self, R_pre, V_gain, lockin_handle, V_ac='', suffix='', autosense=False):
        super().__init__('diff_resistance'+suffix,
                         names=('R'+suffix, 'G'+suffix, 'X'+suffix, 'Y'+suffix),
                         shapes=((), (), (), ()),
                         labels=('Differential resistance '+suffix, 'Differential conductance '+suffix,'Raw voltage X'+suffix, 'Raw voltage Y'+suffix),
                         units=('Ohm', 'e^2/h', 'V', 'V'),
                         setpoints=((), (), (), ()),
                        docstring='Differential resistance and conductance converted from raw voltage measurement')
        self._R_pre = R_pre
        self._V_gain = V_gain
        self._lockin_handle = lockin_handle
        self._autosense = autosense
        self._V_ac = V_ac
        if V_ac == '':
            self._V_ac = np.float64(self._lockin_handle.visa_handle.query("SLVL?"))
    
    def get_raw(self):
        if self._autosense:
                    auto_sensitivity(self._lockin_handle)
        voltageXY = self._lockin_handle.visa_handle.ask("SNAP? 1,2")    
        voltageX, voltageY = voltageXY.split(",")
        voltageX = np.float64(voltageX)
        voltageY = np.float64(voltageY)
        
        # some constants
        const_e = 1.60217662e-19
        const_h = 6.62607004e-34        
        diff_resistance = (voltageX/self._V_gain)/(self._V_ac/self._R_pre)
        diff_conductance = 1/diff_resistance / const_e**2 * const_h
        return (diff_resistance, diff_conductance, voltageX, voltageY)
#diff_resistance = diff_R_G_Ibias(V_ac = 10e-3, R_pre=1e6, V_gain = 100, lockin_handle=lockin, suffix="_8", autosense=False)


#Lock-in auto_sensitivity functions
def change_sensitivity_AP(self, dn):
    _ = self.sensitivity.get()
    n = int(self.sensitivity.raw_value)
    if self.input_config() in ['a', 'a-b']:
        n_to = self._N_TO_VOLT
    else:
        n_to = self._N_TO_CURR

    if n + dn > max(n_to.keys()) or n + dn < min(n_to.keys()):
        return False

    self.sensitivity.set(n_to[n + dn])
    time.sleep(3*self.time_constant()) #Wait to read the correct value
    return True

def auto_sensitivity(self, lim=1000e-9):
    sens = self.sensitivity.get()
    X_val = self.X.get()
    while np.abs(X_val) <= 0.2*sens or np.abs(X_val) >= 0.9*sens:
        if np.abs(X_val) <= 0.2*sens:
            if sens == lim:
                break
            change_sensitivity_AP(self, -1) 
        elif np.abs(X_val) >= 0.9*sens:
            change_sensitivity_AP(self, 1)
        sens = self.sensitivity.get()
        X_val = self.X.get()  