import numpy as np
import qcodes as qc
from qcodes.validators import Arrays
from qcodes.dataset.experiment_container import load_by_id
from QCTools.qctools.doNd import doNd
import warnings
import json
from scipy.signal import detrend

def saveNd(data=np.array([None]),meas_name='measurement_name',comment='',data_name='measured_data',data_unit='a.u.',set_names=None,set_vals=None,set_units=None,config_snap=None):
    # Function takes any numpy and saves it into the qcodes database.
    # The doNd function was modified to skip plotting if the matrix dimension n is larger than 2. It now takes the optional argument do_plot=True.
    
    #data numpy (np.complex128 or np.float64) array of any dimension. Plotting will be perforemd if n<3.
    #meas_name - string (name of the measurement, will be stored in metadata).
    #comment -string (comment that will be stored in the metadata)
    #data_name - string (name of the quantity that was measured to obtain data)
    #data_unit - string (unit of data)
    #set_names - list of length n of strings that contains the name of each set parameter
    #set_vals - list of length n of lists that contain the set points of each axis
    #set_units - list of length n of strings that contain the unit of each set paramter
    #config_snap - dict or string that will be added to the snapshot of the pseudo measurement (additional to all metadata that is automatically saved in the Qcodes station.
    
    n=len(data.shape)
    do_plot=True
    if n>2:
        do_plot=False
        
    if not type(set_vals)==np.ndarray:
        if set_vals==None:
            set_vals=[]
            for i in range(n):
                set_vals.append(np.arange(data.shape[i]))
    if not type(set_vals)==np.ndarray:
        if set_names==None:
            set_names=[]
            for i in range(n):
                set_names.append('Set_Param_'+str(i))
    if not type(set_vals)==np.ndarray:
        if set_units==None:
            set_units=[]
            for i in range(n):
                set_units.append('a.u.')
    if (not len(set_vals)==n) or (not len(set_names)==n) or (not len(set_units)==n):
        raise Exception('Shapes do not match.')
    def get_results():
        return data
    set_params=[]
    for i in range(n):
        set_params.append(qc.Parameter(set_names[i],unit=set_units[i],set_cmd=None,
                               vals=Arrays(shape=(len(set_vals[i]),))))
        set_params[i].set(set_vals[i])
    if type(data.flat[0])==np.complex128:
        ResA = qc.parameters.ParameterWithSetpoints('Abs_'+data_name,
                        setpoints=set_params,get_cmd=lambda: np.abs(data),
                                       vals=Arrays(shape=data.shape),unit=data_unit)
        ResPhi = qc.parameters.ParameterWithSetpoints('Arg_'+data_name,
                        setpoints=set_params,get_cmd=lambda: detrend(np.unwrap(2*(np.angle(data)%np.pi))/2,type='constant'),#For an unknown reason, the OPX returns only phases between 0 and pi. -> multiply by 2 before unwrap and divide by 2 after. Then subtract average (detrend)
                                       vals=Arrays(shape=data.shape),unit='rad')
        measid=doNd(param_set = [],
              param_meas = [ResA,ResPhi], 
              spaces = [],
              settle_times = [],
              comment=comment,
              name=meas_name,do_plot=do_plot)
    elif type(data.flat[0])==np.float64:
        Res = qc.parameters.ParameterWithSetpoints(data_name,
                        setpoints=set_params,get_cmd=lambda: data,
                                       vals=Arrays(shape=data.shape,valid_types=(np.complexfloating, np.floating, np.integer)),unit=data_unit)
        measid=doNd(param_set = [],
              param_meas = [Res], 
              spaces = [],
              settle_times = [],
              comment=comment,
              name=meas_name,do_plot=do_plot)
    else:
        print('Please supply data as nd array of type np.float64 or np.complex128.')
        return None
    if config_snap==None:
        warnings.warn('Config file is not saved in snapshot. Please supply config as parameter config_snap.')
    else:
        #if :
            #Add config_file (supplied by user) to the Qcodes snapshot
            dataset=load_by_id(measid)
            old_snap_json = dataset.snapshot_raw
            
            new_snap=old_snap_json[:-1]+', "config":' +json.dumps(config_snap)+ "}"
            #print(new_snap)
            dataset.add_metadata('snapshot',new_snap)
    
    return measid
    
def add_to_snapshot(measid,config_snap={}):
    #adds a dictionary to the json snapshot of the dataset with id measid
    if config_snap==None:
        warnings.warn('Config file is not saved in snapshot. Please supply config as parameter config_snap.')
    else:
        #if :
            #Add config_file (supplied by user) to the Qcodes snapshot
        dataset=load_by_id(measid)
        old_snap_json = dataset.snapshot_raw
        
        new_snap=old_snap_json[:-1]+', "config":' +json.dumps(config_snap)+ "}"
        print(new_snap)
        dataset.add_metadata('snapshot',new_snap)