from qcodes.dataset.sqlite.database import connect, get_DB_location
from qcodes.dataset import get_default_experiment_id
import qcodes as qc
from qcodes import initialise_database
import qcodes.dataset.descriptions.versioning.serialization as sz
import os
import numpy as np
import json
import datetime


def db_extractor(dbloc=None,
                 extractpath=None,
                 ids=None,
                 overwrite=False,
                 timestamp=True,
                 paramtofilename=False,
                 newline_slowaxes=True,
                 no_folders=False,
                 suppress_output=False,
                 useopendbconnection=False,
                 checktimes=False):
    """
    Extract a QCoDeS *.db file into a folder structure with descriptive filenames.
    Also extracts measurement snapshots to JSON where available.

    Parameters
    ----------
    dbloc : str
        Full path to the .db file.
    extractpath : str, optional
        Folder to extract into. Defaults to the directory of dbloc.
    ids : list, optional
        List of run IDs to extract (e.g. list(range(2,10))). Extracts all if empty.
    overwrite : bool
        If False, skips files that already exist. Default: False.
    timestamp : bool
        If True, prepends a timestamp to each run folder. Default: True.
    paramtofilename : bool
        If True, appends parameter names to the .dat filename. Useful when runs
        are all named 'results'. Default: False.
    newline_slowaxes : bool
        Inserts a blank line whenever a slow axis steps, enabling 2D plotting in
        e.g. gnuplot. Works for arbitrary dimensionality. Default: True.
    no_folders : bool
        If True, suppresses per-run subfolders and puts all files in one directory
        prefixed with the run ID. Default: False.
    suppress_output : bool
        If True, silences all print output. Default: False.
    useopendbconnection : bool
        If True, uses the already-open QCoDeS database connection instead of
        opening dbloc. Default: False.
    checktimes : bool
        If True, prints timing info for each internal step (debug only). Default: False.
    """
    if ids is None:
        ids = []

    # Validate the database file
    if not suppress_output:
        if os.path.isfile(dbloc) and dbloc.endswith('.db'):
            print('*.db file found, continuing to unpack...')
        else:
            print('*.db file location cannot be found.')
            return
    # Save active experiment from the current (user's) database before switching
    conn = connect(get_DB_location())
    active_exp_id = get_default_experiment_id(conn)
    conn.close()

    # Point QCoDeS at the requested database, saving the previously open one to restore later
    if not useopendbconnection:
        configuration = qc.config
        previously_opened_db = configuration['core']['db_location']
        configuration['core']['db_location'] = dbloc
        configuration.save_to_home()
        initialise_database()

    times = [datetime.datetime.now()]
        
    # --- Outer loop: iterate over all experiments in the database ---
    for i in range(1, len(qc.dataset.experiment_container.experiments()) + 1):
        exp = qc.load_experiment(i)
        expname = exp.name
        samplename = exp.sample_name
        folderstring = f'Exp{i:02d}({expname})-Sample({samplename})'
        nmeas = exp.last_counter
        dbpath = os.path.abspath(extractpath if extractpath is not None else dbloc)

        if checktimes:
            times.append(datetime.datetime.now())
            print('Loaded db and exp', times[-1] - times[-2])

        # --- Inner loop: iterate over all runs in the experiment ---
        for j in range(1, nmeas + 1):
            run = exp.data_set(j)
            runid = run.run_id
            runname = run.name

            # Compute sample rate for potential use; fall back if run is incomplete
            try:
                runduration = run.completed_timestamp_raw - run.run_timestamp_raw
                samplerate = run.number_of_results / runduration
            except (TypeError, ZeroDivisionError):
                samplerate = 10  # Default fallback if timestamps are missing

            # Skip runs not in the requested ID list, or runs with no data
            if (ids and runid not in ids) or run.number_of_results == 0:
                continue

            # Build optional filename components
            timestampcut = (str(run.run_timestamp())
                            .replace(":", "").replace("-", "").replace(" ", "-")
                            if timestamp else '')
            runparams = ('_' + run.parameters) if paramtofilename else ''

            # --- Classify parameters into set axes (independent) and meas axes (dependent) ---
            parameters = run.get_parameters()
            num_of_parameters = len(parameters)
            param_names = [p.name for p in parameters]
            depends = [p.depends_on if p.depends_on else [] for p in parameters]
            meas_params = [k for k, p in enumerate(parameters) if p.depends_on]

            # Group measurement parameters by their shared set of dependencies.
            # Each unique dependency set becomes a separate .dat file.
            # result_dict[n] = list of meas param indices sharing the same depends
            # depend_dict[n] = list of set param indices for that group
            result_dict = {}
            depend_dict = {}
            n = 0
            for l in meas_params:
                params_with_equal_depends = [idx for idx, e in enumerate(depends) if e == depends[l]]
                if params_with_equal_depends not in result_dict.values():
                    result_dict[n] = params_with_equal_depends
                    dep_names = parameters[l].depends_on.split(', ')
                    depend_dict[n] = [param_names.index(d) for d in dep_names]
                    n += 1

            if checktimes:
                times.append(datetime.datetime.now())
                print('Determined meas and set params', times[-1] - times[-2])

            # --- Loop over independent measurement groups (one .dat file each) ---
            filenamep1 = f'{runid:03d}_{timestampcut}_{runname}'
            for l in range(len(result_dict)):

                # Build filenames depending on whether multiple files are produced per run
                multi = len(result_dict) > 1
                if no_folders:
                    filenamep2 = (f'{runid:03d}-{l}_{runname}{runparams}.dat' if multi
                                  else f'{runid:03d}-{runname}{runparams}.dat')
                    filenamejson = f'{runid:03d}-run_snapshot.json'
                    folder = dbpath.split('.')[0]
                else:
                    filenamep2 = (f'{l}_{runname}{runparams}.dat' if multi
                                  else f'{runname}{runparams}.dat')
                    filenamejson = 'run_snapshot.json'
                    folder = os.path.join(dbpath.split('.')[0], folderstring, filenamep1)

                # Sanitise paths (replace characters that are invalid on some filesystems)
                folder = folder.replace('?', '_')
                filenamep2 = filenamep2.replace(' ', '_').replace('?', '_')
                filenamejson = filenamejson.replace(' ', '_').replace('?', '_')

                fullpath = os.path.join(folder, filenamep2)
                fullpathjson = os.path.join(folder, filenamejson)
                os.makedirs(folder, exist_ok=True)

                if checktimes:
                    times.append(datetime.datetime.now())
                    print('Constructing file and folder names', times[-1] - times[-2])

                # Skip if file exists and overwrite is disabled
                if os.path.isfile(fullpath) and not overwrite:
                    n += 1
                    continue

                # --- Build the .dat file header ---
                header = (f'Run #{runid}: {runname}, Experiment: {expname}, '
                          f'Sample name: {samplename}, '
                          f'Number of values: {run.number_of_results}, '
                          f'Samplingrate (n/s): {samplerate},\n')
                try:
                    comment = run.get_metadata('Comment')
                    header += f'Comment: {comment}\n'
                except Exception:
                    header += '\n'

                if checktimes:
                    times.append(datetime.datetime.now())
                    print('Before reading from db', times[-1] - times[-2])

                all_param_data = run.get_parameter_data()

                if checktimes:
                    times.append(datetime.datetime.now())
                    print('run.get_parameter_data()', times[-1] - times[-2])

                meas_params_l = result_dict[l]  # Measurement param indices for this file
                set_params = depend_dict[l]      # Set (independent) param indices for this file

                # Replace lines 202-208 with:
                meas_params_l = result_dict[l]
                set_params = depend_dict[l]

                # Determine number of rows from already-fetched all_param_data
                lval = len(all_param_data[param_names[meas_params_l[0]]][param_names[set_params[0]]].flatten())
                lset = len(set_params)
                lmeas = len(meas_params_l)
                run_matrix = np.full([lval, lset + lmeas], np.nan)

                headernames = ''
                headerlabelsandunits = ''
                colcounter = 0

                # Fill set (independent) axis columns first
                for j in set_params:
                    run_matrix[:len(all_param_data[param_names[meas_params_l[0]]][param_names[j]].flatten()), colcounter] = \
                        all_param_data[param_names[meas_params_l[0]]][param_names[j]].flatten()
                    headernames += parameters[j].name + '\t'
                    headerlabelsandunits += f'{parameters[j].label} ({parameters[j].unit})\t'
                    colcounter += 1

                if checktimes:
                    times.append(datetime.datetime.now())
                    print('Set_params in runmatrix', times[-1] - times[-2])

                # Fill measurement (dependent) axis columns
                for k in meas_params_l:
                    measdata = all_param_data[param_names[k]][param_names[k]].flatten()
                    run_matrix[:len(measdata), colcounter] = measdata
                    headernames += parameters[k].name + '\t'
                    headerlabelsandunits += f'{parameters[k].label} ({parameters[k].unit})\t'
                    colcounter += 1

                if checktimes:
                    times.append(datetime.datetime.now())
                    print('Meas_params in runmatrix', times[-1] - times[-2])

                header += headernames + '\n' + headerlabelsandunits

                if not suppress_output:
                    print(f'Saving measurement with id {runid} to {fullpath}')

                # --- Write the .dat file ---
                with open(fullpath, 'wb') as f:
                    # Write header with no data rows (np.savetxt handles the comment prefix)
                    np.savetxt(f, np.array([]), header=header)

                    if checktimes:
                        times.append(datetime.datetime.now())
                        print('Opening txt file and saving header', times[-1] - times[-2])

                    # Find row indices where a slow axis changes value, so we can insert
                    # blank lines between sweeps (enables surface/image plots in gnuplot etc.)
                    slicearray = np.array([], dtype=int)
                    if newline_slowaxes:
                        for h in range(len(set_params) - 1):
                            slicearray = np.unique(np.concatenate((
                                slicearray,
                                np.where(run_matrix[:-1, h] != run_matrix[1:, h])[0] + 1
                            )))

                    if checktimes:
                        times.append(datetime.datetime.now())
                        print('newline_slowaxes time consumption', times[-1] - times[-2])

                    # Write data, inserting blank lines at slow-axis steps
                    vsliced = np.split(run_matrix, slicearray, axis=0)
                    for h, chunk in enumerate(vsliced):
                        np.savetxt(f, chunk, delimiter='\t')
                        if h != len(vsliced) - 1:
                            f.write(b'\n')

                if checktimes:
                    times.append(datetime.datetime.now())
                    print('Writing of the textfile', times[-1] - times[-2])

                # --- Save run snapshot and description to JSON ---
                total_json = {}
                with open(fullpathjson, 'w') as f:
                    if run.description:
                        total_json.update(json.loads(sz.to_json_for_storage(run.description)))
                    if run.snapshot:
                        total_json.update(run.snapshot)
                    else:
                        if run.description:
                            print(f'Warning: Measurement {runid} has no snapshot.')
                        else:
                            print(f'Warning: Measurement {runid} has no snapshot or run '
                                  f'description. Axes for plotting cannot be extracted.')
                    json.dump(total_json, f, indent=4)

                n += 1

                if checktimes:
                    times.append(datetime.datetime.now())
                    print('Total time', times[-1] - times[0])

    # Restore the previously open database connection first
    if not useopendbconnection:
        configuration['core']['db_location'] = previously_opened_db
        configuration.save_to_home()
        initialise_database()

    # Then restore experiment context against the now-correct database
    if active_exp_id is not None:
        qc.load_experiment(active_exp_id)
