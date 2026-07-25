import os
import numpy as np
import qcodes as qc
from qcodes.validators import Arrays
from qcodes.dataset.experiment_container import load_by_id
from QCTools.qctools.doNd import doNd
import warnings
import json
from scipy.signal import detrend
import h5py
import pandas as pd


def _long_path(path):
    # Windows silently fails to open paths longer than MAX_PATH (260 chars)
    # with FileNotFoundError, even though every parent directory exists. The
    # \\?\ prefix opts a single call out of that limit without requiring the
    # LongPathsEnabled registry setting.
    path = os.path.abspath(path)
    if os.name == 'nt' and not path.startswith('\\\\?\\'):
        return '\\\\?\\' + path
    return path


def _write_placeholder_dat(folder, measid, meas_name, comment,
                           set_names, set_vals, set_units,
                           data_name, data_unit, exp_name, sample_name, snap_dict):
    # Writes a 2D placeholder .dat and run_snapshot.json into the folder so
    # tessierplot can display the entry. Uses the last 2 set axes with actual
    # setpoints and zeros as data values.
    ax_names  = set_names[-2:]  if len(set_names) >= 2 else set_names
    ax_units  = set_units[-2:]  if len(set_units) >= 2 else set_units
    # Downsample each axis to at most 10 points so the placeholder stays small
    _PLACEHOLDER_PTS = 10
    raw_vals = set_vals[-2:] if len(set_vals) >= 2 else set_vals
    ax_vals  = [np.linspace(v[0], v[-1], min(_PLACEHOLDER_PTS, len(v))) for v in raw_vals]

    # Build flat column arrays via meshgrid
    if len(ax_names) == 2:
        g0, g1 = np.meshgrid(ax_vals[0], ax_vals[1], indexing='ij')
        col0 = g0.ravel()
        col1 = g1.ravel()
        zeros = np.linspace(0, 1, len(col0))
        run_matrix = np.column_stack([col0, col1, zeros])
        # newline between slow-axis blocks
        slicearray = np.where(col0[:-1] != col0[1:])[0] + 1
        paramspecs = [
            {'name': ax_names[0], 'label': ax_names[0], 'unit': ax_units[0], 'depends_on': []},
            {'name': ax_names[1], 'label': ax_names[1], 'unit': ax_units[1], 'depends_on': []},
            {'name': data_name,   'label': data_name,   'unit': data_unit,   'depends_on': [ax_names[0], ax_names[1]]},
        ]
        headernames       = '\t'.join([ax_names[0], ax_names[1], data_name]) + '\t'
        headerlabelsunits = '\t'.join([f'{ax_names[0]} ({ax_units[0]})',
                                       f'{ax_names[1]} ({ax_units[1]})',
                                       f'{data_name} ({data_unit})']) + '\t'
    else:  # 1D
        col0   = ax_vals[0]
        zeros  = np.linspace(0, 1, len(col0))
        run_matrix  = np.column_stack([col0, zeros])
        slicearray  = np.array([], dtype=int)
        paramspecs  = [
            {'name': ax_names[0], 'label': ax_names[0], 'unit': ax_units[0], 'depends_on': []},
            {'name': data_name,   'label': data_name,   'unit': data_unit,   'depends_on': [ax_names[0]]},
        ]
        headernames       = '\t'.join([ax_names[0], data_name]) + '\t'
        headerlabelsunits = '\t'.join([f'{ax_names[0]} ({ax_units[0]})',
                                       f'{data_name} ({data_unit})']) + '\t'

    nvals  = len(run_matrix)
    header = (f'Run #{measid}: {meas_name}, Experiment: {exp_name}, '
              f'Sample name: {sample_name}, Number of values: {nvals}\n'
              f'Comment: {comment} \n'
              f'{headernames}\n'
              f'{headerlabelsunits}')

    dat_path  = os.path.join(folder, meas_name + '_placeholder.dat')
    json_path = os.path.join(folder, 'run_snapshot.json')

    with open(_long_path(dat_path), 'wb') as f:
        np.savetxt(f, np.array([]), header=header)
        vsliced = np.split(run_matrix, slicearray, axis=0)
        for k, block in enumerate(vsliced):
            np.savetxt(f, block, delimiter='\t')
            if k != len(vsliced) - 1:
                f.write(b'\n')

    # If db_extractor already wrote a full run_snapshot.json (station snapshot),
    # load it and only overwrite the interdependencies so tessierplot can parse
    # _placeholder.dat. Otherwise fall back to building from snap_dict.
    if os.path.isfile(_long_path(json_path)):
        with open(_long_path(json_path), 'r') as f:
            total_json = json.load(f)
        total_json['interdependencies'] = {'paramspecs': paramspecs}
    else:
        total_json = {'interdependencies': {'paramspecs': paramspecs}}
        total_json.update(snap_dict)
    with open(_long_path(json_path), 'w') as f:
        json.dump(total_json, f, indent=4)


def saveNd(data=np.array([None]),meas_name='measurement_name',comment='',data_name='measured_data',data_unit='a.u.',set_names=None,set_vals=None,set_units=None,config_snap=None,save_data_to_h5=False):
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
    #save_data_to_h5 - bool. If True, data is saved to an HDF5 file in the same folder db_extractor uses,
    #                  and the QCoDeS entry acts as a metadata-only placeholder with the h5 path in its snapshot.

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

    if save_data_to_h5:
        # Save data to HDF5 and create a metadata-only placeholder in QCoDeS.
        if type(data.flat[0]) not in (np.complex128, np.float64):
            raise TypeError(
                'save_data_to_h5=True requires data as an nd array of dtype '
                'np.float64 or np.complex128, got element type '
                f'{type(data.flat[0]).__name__} (data.dtype={data.dtype}).')

        # Step 1: Create QCoDeS placeholder entry first so we have measid, timestamp, exp info.
        # A dummy setpoint is required so depends_on is non-empty and db_extractor picks up the entry.
        meas_obj = qc.Measurement()
        meas_obj.name = meas_name
        idx_param = qc.Parameter('placeholder_idx', get_cmd=lambda: 0, set_cmd=None, unit='')
        h5_ref_param = qc.Parameter('h5_path_ref', get_cmd=lambda: 0.0, unit='')
        meas_obj.register_parameter(idx_param)
        meas_obj.register_parameter(h5_ref_param, setpoints=[idx_param])
        with meas_obj.run() as datasaver:
            measid = datasaver.run_id
            datasaver.dataset.add_metadata('Comment', comment)
            datasaver.add_result((idx_param, 0), (h5_ref_param, 0.0))

        # Step 2: Derive h5 save path using the same folder logic as db_extractor.
        dataset = load_by_id(measid)
        exp = qc.load_experiment(dataset.exp_id)
        dbloc = qc.dataset.sqlite.database.get_DB_location()
        dbpath = os.path.abspath(dbloc)
        folderstring = 'Exp{:02d}({})-Sample({})'.format(dataset.exp_id, exp.name, exp.sample_name)
        timestampcut = str(dataset.run_timestamp()).replace(':', '').replace('-', '').replace(' ', '-')
        filenamep1 = '{:03d}_{}_{}'.format(measid, timestampcut, meas_name)
        folder = os.path.join(dbpath.split('.')[0], folderstring, filenamep1)
        os.makedirs(_long_path(folder), exist_ok=True)
        h5_filepath = os.path.join(folder, meas_name + '.h5')

        # Step 3: Save data to HDF5.
        with h5py.File(_long_path(h5_filepath), 'w') as f:
            f.attrs['meas_name'] = meas_name
            f.attrs['comment'] = comment
            f.attrs['data_name'] = data_name
            f.attrs['data_unit'] = data_unit
            sp_grp = f.create_group('setpoints')
            for i in range(n):
                ds = sp_grp.create_dataset(set_names[i], data=set_vals[i])
                ds.attrs['unit'] = set_units[i]
            if type(data.flat[0]) == np.complex128:
                f.create_dataset('Abs_' + data_name, data=np.abs(data), compression='gzip')
                phase = detrend(np.unwrap(2 * (np.angle(data) % np.pi)) / 2, type='constant')
                ds_phase = f.create_dataset('Arg_' + data_name, data=phase, compression='gzip')
                f['Abs_' + data_name].attrs['unit'] = data_unit
                ds_phase.attrs['unit'] = 'rad'
            else:
                ds = f.create_dataset(data_name, data=data, compression='gzip')
                ds.attrs['unit'] = data_unit
            if config_snap is not None:
                f.attrs['config'] = json.dumps(config_snap)

        # Step 4: Update QCoDeS snapshot with h5 path and all metadata.
        snap_dict = json.loads(dataset.snapshot_raw)
        snap_dict['h5_path'] = os.path.relpath(h5_filepath, os.path.dirname(dbpath))
        snap_dict['data_name'] = data_name
        snap_dict['data_unit'] = data_unit
        snap_dict['set_names'] = set_names
        snap_dict['set_units'] = set_units
        if config_snap is not None:
            snap_dict['config'] = config_snap
        dataset.add_metadata('snapshot', json.dumps(snap_dict))

        # Step 5: Run db_extractor on the placeholder entry to write the full
        # QCoDeS station snapshot to run_snapshot.json.
        import qctools
        qctools.db_extraction.db_extractor(
            dbloc=qc.dataset.sqlite.database.get_DB_location(),
            ids=[measid],
            overwrite=True,
            newline_slowaxes=True,
            no_folders=False,
            suppress_output=True,
            useopendbconnection=True)
        # Remove the .dat file db_extractor wrote for the placeholder entry
        # (placeholder_idx / h5_path_ref columns); _placeholder.dat replaces it.
        db_extractor_dat = os.path.join(
            folder, meas_name.replace(' ', '_').replace('?', '_') + '.dat')
        if os.path.isfile(_long_path(db_extractor_dat)):
            os.remove(_long_path(db_extractor_dat))

        # Step 6: Write the placeholder .dat and overwrite run_snapshot.json with
        # correct interdependencies so tessierplot can parse _placeholder.dat.
        _write_placeholder_dat(folder, measid, meas_name, comment,
                               set_names, set_vals, set_units,
                               data_name, data_unit,
                               exp.name, exp.sample_name, snap_dict)
        return measid

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
        raise TypeError(
            'saveNd requires data as an nd array of dtype np.float64 or '
            f'np.complex128, got element type {type(data.flat[0]).__name__} '
            f'(data.dtype={data.dtype}).')
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
    
def load_h5_as_dict(measid):
    # Loads the HDF5 file associated with a QCoDeS run ID saved via saveNd(save_data_to_h5=True).
    # Returns a dict with keys: data, setpoints, data_name, data_unit, set_names, set_units, h5_path.
    dataset = load_by_id(measid)
    snap = json.loads(dataset.snapshot_raw)
    h5_path_rel = snap['h5_path']
    db_dir = os.path.dirname(os.path.abspath(qc.dataset.sqlite.database.get_DB_location()))
    h5_path = os.path.join(db_dir, h5_path_rel)
    with h5py.File(h5_path, 'r') as f:
        data_name = f.attrs['data_name']
        data_unit = f.attrs['data_unit']
        set_names = list(f['setpoints'].keys())
        setpoints = {key: f['setpoints'][key][:] for key in set_names}
        set_units = {key: f['setpoints'][key].attrs['unit'] for key in set_names}
        if 'Abs_' + data_name in f:
            data = f['Abs_' + data_name][:]
            phase = f['Arg_' + data_name][:]
            return dict(data=data, phase=phase, setpoints=setpoints,
                        data_name=data_name, data_unit=data_unit,
                        set_names=set_names, set_units=set_units, h5_path=h5_path)
        else:
            data = f[data_name][:]
            return dict(data=data, setpoints=setpoints,
                        data_name=data_name, data_unit=data_unit,
                        set_names=set_names, set_units=set_units, h5_path=h5_path)


def load_h5_as_dataframe(measid):
    # Loads the HDF5 file associated with a QCoDeS run ID and returns a flat pandas DataFrame.
    # Setpoints are meshgridded to match the data shape, mimicking QCoDeS get_parameter_data() style.
    result = load_h5_as_dict(measid)
    set_names = result['set_names']
    grids = np.meshgrid(*[result['setpoints'][k] for k in set_names], indexing='ij')
    df_dict = {name: grid.ravel() for name, grid in zip(set_names, grids)}
    df_dict[result['data_name']] = result['data'].ravel()
    if 'phase' in result:
        df_dict['Arg_' + result['data_name']] = result['phase'].ravel()
        df_dict['Abs_' + result['data_name']] = df_dict.pop(result['data_name'])
    return pd.DataFrame(df_dict)



def plot_h5(measid):
    import matplotlib.pyplot as plt
    d = load_h5_as_dict(measid)
    set_names = d['set_names']
    setpoints = d['setpoints']
    set_units = d['set_units']
    data_name = d['data_name']
    data_unit = d['data_unit']
    is_complex = 'phase' in d

    datasets = {'Abs_' + data_name: (d['data'], data_unit),
                'Arg_' + data_name: (d['phase'], 'rad')} if is_complex else \
               {data_name: (d['data'], data_unit)}

    n = len(set_names)
    for name, (arr, unit) in datasets.items():
        fig, ax = plt.subplots()
        if n == 1:
            x = setpoints[set_names[0]]
            ax.plot(x, arr)
            ax.set_xlabel(f'{set_names[0]} ({set_units[set_names[0]]})')
            ax.set_ylabel(f'{name} ({unit})')
        elif n == 2:
            x = setpoints[set_names[1]]   # fast axis
            y = setpoints[set_names[0]]   # slow axis
            im = ax.pcolormesh(x, y, arr, shading='auto')
            fig.colorbar(im, ax=ax, label=f'{name} ({unit})')
            ax.set_xlabel(f'{set_names[1]} ({set_units[set_names[1]]})')
            ax.set_ylabel(f'{set_names[0]} ({set_units[set_names[0]]})')
        else:
            print(f'Plotting not supported for {n}-dimensional data.')
            plt.close(fig)
            continue
        ax.set_title(f'Run {measid}: {name}')
        plt.tight_layout()
        plt.show()


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