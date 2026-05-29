import numpy as np
import qcodes as qc
from qcodes.validators import Arrays

from QCTools.qctools.doNd import doNd

def saveNd(data=np.array([None]),meas_name='measurement_name',comment='',data_name='measured_data',data_unit='a.u.',set_names=None,set_vals=None,set_units=None):
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

    n=len(data.shape)
    do_plot=True
    if n>2:
        do_plot=False
        
    if set_vals==None:
        set_vals=[]
        for i in range(n):
            set_vals.append(np.arange(data.shape[i]))
    if set_names==None:
        set_names=[]
        for i in range(n):
            set_names.append('Set_Param_'+str(i))
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
                        setpoints=set_params,get_cmd=lambda: np.angle(data),
                                       vals=Arrays(shape=data.shape),unit='rad')
        return doNd(param_set = [],
              param_meas = [ResA,ResPhi], 
              spaces = [],
              settle_times = [],
              name=meas_name,do_plot=do_plot)
    elif type(data.flat[0])==np.float64:
        Res = qc.parameters.ParameterWithSetpoints(data_name,
                        setpoints=set_params,get_cmd=lambda: data,
                                       vals=Arrays(shape=data.shape,valid_types=(np.complexfloating, np.floating, np.integer)),unit=data_unit)
        return doNd(param_set = [],
              param_meas = [Res], 
              spaces = [],
              settle_times = [],
              name=meas_name,do_plot=do_plot)
    else:
        print('Please supply data as nd array of type np.float64 or np.complex128.')
        return None