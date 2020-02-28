import qcodes as qc
from qcodes import Station, Measurement
import qctools
import time
import numpy as np
import datetime
from threading import Thread, current_thread
from multiprocessing import Process, Event
import warnings
import sys
from IPython.display import display, clear_output

warnings.simplefilter('always', DeprecationWarning)
do1d2ddeprecationwarning = '\'do1d\' and \'do2d\' are deprecated and call the general doNd function as a variable wrapper. Please consider directly calling \'doNd\'.'

# function to get unique values 
def unique(list1): 
  
    # intilize a null list 
    unique_list = [] 
      
    # traverse for all elements 
    for x in list1: 
        # check if exists in unique_list or not 
        if x not in unique_list: 
            unique_list.append(x) 
    # print list 
    return unique_list 

def fill_station(param_set, param_meas):
    station = Station()
    allinstr=qc.instrument.base.Instrument._all_instruments
    for key,val in allinstr.items():
        instr = qc.instrument.base.Instrument.find_instrument(key)
        station.add_component(instr)
    measparstring = ""
    for parameter in param_set:
        station.add_component(parameter)
        measparstring += parameter.name + ',' 
    for parameter in param_meas:
        try: # Prevent station crash when component of parameter is not unique
            station.add_component(parameter)
            measparstring += parameter.name + ',' 
        except Exception as e:
            print('Error ignored when filling station: \n', e)
            pass
    return measparstring

def fill_station_zerodim(param_meas):
    station = Station()
    allinstr=qc.instrument.base.Instrument._all_instruments
    for key,val in allinstr.items():
        instr = qc.instrument.base.Instrument.find_instrument(key)
        station.add_component(instr)
    measparstring = ""
    for parameter in param_meas:
        station.add_component(parameter)
        measparstring += parameter.name + ',' 
    return measparstring

def safetyratesdelays(param_set,spaces):
    #Sample blowup prevention, patent pending, checking and correcting step and inter_delay for all set parameters 
    for i in range(0,len(param_set)):
        if param_set[i].step == 0 or param_set[i].step == None:
            if len(spaces[i])>1:
                print('Warning, \'step\' attribute for set parameter ', param_set[i].name ,' undefined. Defaulting to minimum measurement stepsize :{}'.format(param_set[i].step) )
                param_set[i].step = np.min(np.absolute(np.diff(spaces[i])[np.where(np.diff(spaces[i])!=0)]))
        if param_set[i].inter_delay == 0 or param_set[i].inter_delay == None:
            print('Warning, \'inter_delay\' attribute for set parameter ', param_set[i].name ,' undefined. Defaulting to \'5e-2\' s.')
            param_set[i].inter_delay = 5e-2


def cartprod(*arrays):
    N = len(arrays)
    fullmesh = np.transpose(np.meshgrid(*arrays, indexing='ij'), 
                     np.roll(np.arange(N + 1), -1)).reshape(-1, N)
    return fullmesh

def cartprodmeander(*arrays):
    N = len(arrays)
    fullmesh = np.transpose(np.meshgrid(*arrays, indexing='ij'), 
                     np.roll(np.arange(N + 1), -1)).reshape(-1, N)
    s = int(len(fullmesh)/len(arrays[-1])/2)
    for i in range(0,s):
        fullmesh[:,-1][(2*i+1)*len(arrays[-1]):(2*i+2)*len(arrays[-1])]=fullmesh[:,-1][(2*i+1)*len(arrays[-1]):(2*i+2)*len(arrays[-1])][::-1]
    return fullmesh

def run_measurement(event, param_set, param_meas, spaces, settle_times, name, comment, meander, extra_cmd, extra_cmd_val):
    # Local reference of THIS thread object
    t = current_thread()
    # Thread is alive by default
    t.alive = True

    # Create measurement object
    meas = Measurement() 
    # Apply name
    meas.name = name

    #Generating setpoints
    if meander == True:
        setpoints = cartprodmeander(*spaces)
    else:
        setpoints = cartprod(*spaces)
    
    ### Filling station for snapshotting
    fill_station(param_set,param_meas)
    ### Checking and setting safety rates and delays
    safetyratesdelays(param_set,spaces)    
    
    meas.write_period = 0.5
       
    #Make array showing changes between setpoints on axes
    changesetpoints = setpoints - np.roll(setpoints, 1, axis=0)

    #Forcing the first setpoint in changesetpoints to 1 to make sure it is always set.
    changesetpoints[0,:] = 1
   
    # Registering set parameters
    param_setstring = ''
    for parameter in param_set:
        meas.register_parameter(parameter)
        param_setstring += parameter.name + ', '
    output = [] 
    
    # Registering readout parameters
    param_measstring = ''
    for parameter in param_meas:
        meas.register_parameter(parameter, setpoints=(*param_set,))
        output.append([parameter, None])   
        param_measstring += parameter.name + ', '
    
    # Start measurement routine
    with meas.run() as datasaver:  
        global measid
        measid = datasaver.run_id

        # Start various timers
        starttime = datetime.datetime.now()
        lastwrittime = starttime
        lastprinttime = starttime

        # Getting dimensions and array dimensions and lengths
        ndims = int(len(spaces))
        lenarrays = np.zeros(len(spaces))
        for i in range(0,len(spaces)):
            lenarrays[i] = int(len(spaces[i]))
        
        # Main loop for setting values
        for i in range(0,len(setpoints)):
            #Check for nonzero axis to apply new setpoints by looking in changesetpoints arrays
            resultlist = [None]*ndims
            for j in reversed(range(0,ndims)):
                if not np.isclose(changesetpoints[i,j] , 0, atol=0): # Only set set params that need to be changed
                    param_set[j].set(setpoints[i,j])
                    time.sleep(settle_times[j]) # Apply appropriate settle_time
                for k, parameter in enumerate(param_meas): # Readout all measurement parameters at this setpoint i
                    if extra_cmd is not None: # Optional extra command + value that is run before each measurement paremeter is read out.
                        if extra_cmd_val[k] is not None:
                            (extra_cmd[k])(extra_cmd_val[k])
                        else:
                            (extra_cmd[k])()
                    output[k][1] = parameter.get()                
                resultlist[j] = (param_set[j],setpoints[i,j]) # Make a list of result
            datasaver.add_result(*resultlist, # Add everything to the database
                                 *output)
            
            if not t.alive: # Check if user tried to kill the thread by keyboard interrupt, if so kill it
                event.set() # Trigger closing of run_dbextractor
                qctools.db_extraction.db_extractor(dbloc = qc.dataset.sqlite.database.get_DB_location(),  # Run db_extractor once more
                                   ids=[measid], 
                                   overwrite=True,
                                   newline_slowaxes=True,
                                   no_folders=False,
                                   suppress_output=True)
                raise KeyboardInterrupt('User interrupted doNd. All data flushed to database and extracted to *.dat file.')
                # Break out of for loop
                break
            #Time estimation
            printinterval = .05 # Reduce printinterval to save CPU
            if (datetime.datetime.now()-lastprinttime).total_seconds() > printinterval: # Calculate and print time estimation
                frac_complete = (i+1)/len(setpoints)
                duration_in_sec = (datetime.datetime.now()-starttime).total_seconds()/frac_complete
                elapsed_in_sec = (datetime.datetime.now()-starttime).total_seconds()
                remaining_in_sec = duration_in_sec-elapsed_in_sec
                perc_complete = np.round(100*frac_complete,2)
                progressstring = 'Setpoint ' + str(i+1) + ' of ' + str(len(setpoints)) + ', ' + str(perc_complete) + ' % complete.'
                durationstring = '      Total duration - ' + str(datetime.timedelta(seconds=np.round(duration_in_sec)))
                elapsedstring =  '        Elapsed time - ' +  str(datetime.timedelta(seconds=np.round(elapsed_in_sec)))
                remainingstring ='      Remaining time - ' + str(datetime.timedelta(seconds=np.round(remaining_in_sec)))
                etastring =      '     ETA - ' + str((datetime.timedelta(seconds=np.round(duration_in_sec))+starttime).strftime('%Y-%m-%d %H:%M:%S'))

                startstring = ' Started - ' + starttime.strftime('%Y-%m-%d %H:%M:%S')
                runidstring =             '    Starting runid: [' + str(measid) + ']'
                runnameandcommentstring = '              Name: ' + name + ', Comment: ' + comment
                setparameterstring =      '  Set parameter(s): ' + str(param_setstring)
                readoutparameterstring =  'Readout parameters: ' + str(param_measstring)
                totalstring = runidstring + '\n' + runnameandcommentstring + '\n' + setparameterstring + '\n' + readoutparameterstring + '\n\n' + progressstring + '\n' + startstring + '\n' +  etastring + '\n' + durationstring + '\n' + elapsedstring + '\n' + remainingstring 
                clear_output(wait=True)
                print(totalstring)
                lastprinttime = datetime.datetime.now()

            datasaver.dataset.add_metadata('Comment', comment) # Add comment to metadata in database
        finishstring =   'Finished - ' + str((datetime.datetime.now()).strftime('%Y-%m-%d %H:%M:%S')) # Print finishing time
        print(finishstring)
        event.set() # Trigger closing of run_dbextractor

def run_zerodim(event, param_meas, name, comment):
    # Local reference of THIS thread object
    print('Running 0-dimensional measurement, time estimation not available.')
    t = current_thread()
    # Thread is alive by default
    t.alive = True

    # Create measurement object
    meas = Measurement() 
    # Apply name
    meas.name = name

    ### Filling station for snapshotting
    fill_station_zerodim(param_meas)
    
    meas.write_period = 0.5
    
    output = [] 
    # Registering readout parameters
    param_measstring = ''
    for parameter in param_meas:
        meas.register_parameter(parameter)
        output.append([parameter, None])   
        param_measstring += parameter.name + ', '
    
    # Start measurement routine
    with meas.run() as datasaver:  
        global measid
        measid = datasaver.run_id

        # Start various timers
        starttime = datetime.datetime.now()
        lastwrittime = starttime
        lastprinttime = starttime

        # Getting dimensions and array dimensions and lengths
        # Main loop for setting values
        #Check for nonzero axis to apply new setpoints by looking in changesetpoints arrays
        resultlist = [None]*1
        for k, parameter in enumerate(param_meas): # Readout all measurement parameters at this setpoint i
                output[k][1] = parameter.get()                
        datasaver.add_result(*output)
        datasaver.dataset.add_metadata('Comment', comment) # Add comment to metadata in database
        finishstring =   'Finished - ' + str((datetime.datetime.now()).strftime('%Y-%m-%d %H:%M:%S')) # Print finishing time
        print(finishstring)
        event.set() # Trigger closing of run_dbextractor

def run_dbextractor(event,dbextractor_write_interval):
    #Controls how often the measurement is written to *.dat file
    lastwrittime = datetime.datetime.now()
    while event.is_set()==False:
        if (datetime.datetime.now()-lastwrittime).total_seconds() > dbextractor_write_interval and measid is not None:
            try:
                qctools.db_extraction.db_extractor(dbloc = qc.dataset.sqlite.database.get_DB_location(), 
                                                   ids=[measid], 
                                                   overwrite=True,
                                                   newline_slowaxes=True,
                                                   no_folders=False,
                                                   suppress_output=True)
                lastwrittime = datetime.datetime.now()
            except:
                pass
        time.sleep(5)

# doNd: Generalised measurement function able to handle an arbitrary number of param_set axes. 
# Example:
# param_set = [set_param1, set_param2, ... etc]
# spaces = [space1, space2, ... etc]
# settle_times = [settle_time1, settle_time2, ... etc]
# param_meas = [meas_param1, .. etc]
# name = 'Name of this measurement'
# comment = 'More explanation'
# meander = False/True  ##Sets meandering on first 'slow' axis.
# extra_cmd = Optional extra command that is run before each measurement paremeter is read out.
# extra_cmd_val = Optional extra value that of extra_cmd, it will be evaluated as extra_cmd(extra_cmd_val). If extra_cmd_val is not given, extra_cmd() will be run.
# doNd(param_set, spaces, settle_times, param_meas, name='', comment='', meander=False, extra_cmd=None, extra_cmd_val=None)

def doNd(param_set, spaces, settle_times, param_meas, name='', comment='', meander=False, extra_cmd=None, extra_cmd_val=None):
    # Register measid as global parameter
    global measid
    measid = None

    # Useless if statement, because why not        
    if __name__ is not '__main__':
        #Create Event
        event = Event() # Create event shared by threads
        
        # Define p1 (run_measurement) and p2 (run_dbextractor) as two function to thread
        if param_set:
            p1 = Thread(target = run_measurement, args=(event, param_set, param_meas, spaces, settle_times, name, comment, meander, extra_cmd, extra_cmd_val))
        else:
            p1 = Thread(target = run_zerodim, args=(event, param_meas, name, comment))
        # Set writeinterval db_extractor
        dbextractor_write_interval = 30 #sec
        p2 = Thread(target = run_dbextractor, args=(event,dbextractor_write_interval))
        
        # Kill main thread is subthreads are killed, not necessary here I think..
        p1.daemon = True
        p2.daemon = True
        
        #Starting the threads in a try except to catch kernel interrupts
        try:
            # Start the threads
            p1.start()
            p2.start()
            # If the child thread is still running
            while p1.is_alive():
                # Try to join the child thread back to parent for 0.5 seconds
                p1.join(0.5)
                p2.join(0.5)
        # When kernel interrupt is received (as keyboardinterrupt)
        except KeyboardInterrupt as e:
            # Set the alive attribute to false
            p1.alive = False
            p2.alive = False
            # Block until child thread is joined back to the parent
            p1.join()
            p2.join()
            # Exit with error code
            sys.exit(e)
    qctools.db_extraction.db_extractor(dbloc = qc.dataset.sqlite.database.get_DB_location(), 
                                       ids=[measid], 
                                       overwrite=True,
                                       newline_slowaxes=True,
                                       no_folders=False,
                                       suppress_output=True)
    return measid

# Old do1d/2d functions are now only wrappers converting the parameters to a format compatible with the new doNd function.
def do1d(param_set, start, stop, num_points, delay=None, param_meas=[], name='', comment=''):
    warnings.warn(do1d2ddeprecationwarning, DeprecationWarning)
    param_set = [param_set]
    param_meas = param_meas
    spaces = [np.linspace(start,stop,num_points)]
    if delay is not None:
        warnings.warn('Use of \'delay\' is deprecated and is used as \'settle_time\' in this function.', DeprecationWarning)
        settle_times = [delay]
    else:
        settle_times = [1e-3]
    measid = doNd(param_set, spaces, settle_times, param_meas, name='', comment='', meander=False)
    return measid

def do2d(param_set1, start1, stop1, num_points1, param_set2,  start2, stop2, num_points2,delay1=None, delay2=None, 
    param_meas=[], name='', comment='', fasttozero=None):
    warnings.warn(do1d2ddeprecationwarning, DeprecationWarning)
    param_set = [param_set1, param_set2]
    param_meas = param_meas
    spaces = [np.linspace(start1, stop1, num_points1), np.linspace(start1, stop1, num_points1)]
    if delay1 or delay2 is not None:
        warnings.warn('Use of \'delay\' is deprecated and is used as \'settle_time\' in this function.', DeprecationWarning)
        settle_times = [delay1,delay2]
    else:
        settle_times = [1e-3,1e-3]
    measid = doNd(param_set, spaces, settle_times, param_meas, name='', comment='', meander=False)
    return measid

def do1d_settle(param_set, space, settle_time, delay=None, param_meas=[], name='', comment=''):
    warnings.warn(do1d2ddeprecationwarning, DeprecationWarning)
    param_set = [param_set]
    param_meas = param_meas
    spaces = [space]
    settle_times = [settle_time]
    if delay is not None:
        warnings.warn('Use of \'delay\' is deprecated, sweep rates are controlled by instruments and \'settle_time\' is used for measurement delays.')
    measid = doNd(param_set, spaces, settle_times, param_meas, name='', comment='', meander=False)
    return measid

#More advanced do2d
#Modified for custom resolution and to wait for settle_time time after every time set_point is set
#e.g.    space1 = np.concatenate(([1, 2], np.arange(2.5,6.1,0.5), [6.1, 6.2, 6.25, 6.3, 6.5]))
#        space2 = np.linspace(-2e-6, 2e-6, 1000)
def do2d_settle(param_set1, space1, settle_time1, param_set2, space2, settle_time2, delay1=None, delay2=None, param_meas=[], name='', comment='', fasttozero=None):
    warnings.warn(do1d2ddeprecationwarning, DeprecationWarning)
    param_set = [param_set1, param_set2]
    param_meas = param_meas
    spaces = [space1, space2]
    settle_times = [settle_time1, settle_time2]
    if delay1 or delay2 is not None:
        warnings.warn('Use of \'delay\' is deprecated, sweep rates are controlled by instruments and \'settle_time\' is used for measurement delays.', DeprecationWarning)
    measid = doNd(param_set, spaces, settle_times, param_meas, name='', comment='', meander=False)
    return measid