import qcodes as qc
from qcodes import initialise_database
import qcodes.dataset.descriptions.versioning.serialization as sz
import os
import numpy as np
import json
import datetime

# Extract *.db file into conventient folder structure with proper naming. Extracts measurement snapshots if available

# You can pass the function the following attributes:
# dbloc: give it a full database location
# extractpath: optional, give it a folder to extract to. If empty it uses the dbloc path.
# ids: optional, array of run ids to extract (i.e. ids = np.arange(2,10) extracts runs 2 to 10). If empty it extracts all
# overwrite: If False, it does not overwrite files when extracting. Default: False
# timestamp: If True, adds timestamp to foldername per run. Default: True
# paramtofilename: If True, adds all parameter names to the run filename. Especially handy for people who named their
#                  measurements only 'results', makes it more descriptive. Default: False
# newline_slowaxes: Adds a newline on all slowaxes, works in infinte dimensions, i.e., cube measurements and higher. Default: True
# no_folders: Creation of folders is supressed. All measurements are put in the same folder with their measurement IDs.
# suppress_output: Suppresses all print commands
def db_extractor(dbloc=None, 
                 extractpath=None, 
                 ids = [],
                 overwrite = False,
                 timestamp = True, 
                 paramtofilename = False,
                 newline_slowaxes = True,
                 no_folders = False,
                 suppress_output = False,
                 useopendbconnection = False,
                 checktimes = False): # Only for debugging purposes

    
    if not suppress_output:
        if os.path.isfile(dbloc) and dbloc.endswith('.db'):
            print('*.db file found, continue to unpack...')
        else:
            print('*.db file location cannot be found..')
            return;
    
    if useopendbconnection == False:
        configuration = qc.config
        previously_opened_db = configuration['core']['db_location']
        configuration['core']['db_location'] = dbloc
        configuration.save_to_home()
        initialise_database()
 
    starttime = datetime.datetime.now()

    times = []
    times.append(datetime.datetime.now())
    #Looping through all exps inside database
    for i in range(1,len(qc.dataset.experiment_container.experiments())+1,1):
        #print('Expid:',i)
        exp = qc.load_experiment(i)
        expname = exp.name
        samplename = exp.sample_name
        folderstring = f'Exp' + '{:02d}'.format(i) + f'({expname})' + '-Sample' + f'({samplename})'
        nmeas = exp.last_counter
        if extractpath != None:
            dbpath = os.path.abspath(extractpath)
        else:
            dbpath = os.path.abspath(dbloc)
        #Looping through all runs inside experiment
        if checktimes:
            times.append(datetime.datetime.now())
            print('Loaded db and exp ',times[-1]-times[-2])
        for j in range(1,nmeas+1):
            run = exp.data_set(j)
            runid = run.run_id
            #print('Runid',runid)
            runname = run.name
            
            #Loadin a new run
            if (not ids or runid in ids) and (run.number_of_results > 0):
            
                # Adding optional file folder settings
                if timestamp:
                    timestampcut = str(run.run_timestamp()).replace(":", "").replace("-", "").replace(" ","-")
                else:
                    timestampcut = ''
                
                if paramtofilename:
                    runparams = '_' + run.parameters
                else:
                    runparams = ''                
                
                parameters = run.get_parameters()
                num_of_parameters = len(parameters)
               
                # Getting info on parameters used in the run
                meas_params = []
                param_names = [[]] * num_of_parameters
                depends = [[]] * num_of_parameters
                for k in range(0,num_of_parameters):                           
                    param_names[k] = parameters[k].name
                    if parameters[k].depends_on: #Check if measure parameter (i.e. if it has depends), then collect
                        depends[k] = parameters[k].depends_on
                        meas_params.append(k)
                    
                #Compare depends of meas_params and prepare two dicts which describes how the datasaver should process the run
                result_dict = {} # Meas axes dict, rows are independent measurements, values per row are dependent measurements
                depend_dict = {} # Depends (i.e. set axes) belonging to the measurements in the same column of above dict.
                
                n = 0
                #Filling the dicts:
                for l in meas_params: 
                    params_with_equal_depends = [i for i, e in enumerate(depends) if e == depends[l]]
                    if params_with_equal_depends not in result_dict.values():
                    #if 1 == 1: #comment this line and uncomment above line
                        result_dict.update([(n, params_with_equal_depends)])
                        deps = parameters[l].depends_on #Split dependecy string
                        deps = deps.split(', ')
                        depsind = []
                        for o in range(0,len(deps)):
                            depsind.append(param_names.index(deps[o]))
                        depend_dict.update([(n, depsind)])
                        n = n + 1
                if checktimes:
                    times.append(datetime.datetime.now())
                    print('Determined meas and set params ',times[-1]-times[-2])
                #Length of final result_dict determines number of files
                n=0                 
                for i in range(0,len(result_dict)): # len(result_dict) gives number of independent measurement, i.e. .dat files
                    
                    #If number of files > 1, add a number in front
                    if len(result_dict) > 1:
                        filenamep2 = str(n) + "_" + run.name + runparams + ".dat"
                        filenamejson = "run_snapshot.json"
                    else:
                        filenamep2 = run.name + "_" + runparams + ".dat"
                        filenamejson = "run_snapshot.json"
                    
                    #Constructing final filepath
                    filenamep1 = "{:03d}".format(runid) + '_' + timestampcut + '_' + run.name 
                    if no_folders == True:
                        #If number of files > 1, add a number in front
                        if len(result_dict) > 1:
                            filenamep2 = '{:03d}'.format(runid) + '-' + str(n) + "_" + run.name + runparams + ".dat"
                            filenamejson = '{:03d}'.format(runid) + '-' + "run_snapshot.json"
                        else:
                            filenamep2 = '{:03d}'.format(runid) + '-' + run.name + runparams + ".dat"
                            filenamejson = '{:03d}'.format(runid) + '-' + "run_snapshot.json"
                        folder = (dbpath.split('.')[0])
                    else:
                        #If number of files > 1, add a number in front
                        if len(result_dict) > 1:
                            filenamep2 = str(n) + "_" + run.name + runparams + ".dat"
                            filenamejson = "run_snapshot.json"
                        else:
                            filenamep2 = run.name + runparams + ".dat"
                            filenamejson = "run_snapshot.json"
                        folder = os.path.join((dbpath.split('.')[0]),folderstring,filenamep1)
                    
                    folder = folder.replace(" ", "_").replace('?','_')
                    filenamep2 = filenamep2.replace(" ", "_").replace('?','_')
                    filenamejson = filenamejson.replace(" ", "_").replace('?','_')
                    fullpath = os.path.join(folder,filenamep2)
                    fullpathjson = os.path.join(folder,filenamejson)
                    if not os.path.exists(folder):
                        os.makedirs(folder) 

                    if checktimes:
                        times.append(datetime.datetime.now())
                        print('Constructing file and folder names ' ,times[-1]-times[-2])
                    
                    #Check if file exists already
                    if os.path.isfile(fullpath) and overwrite == False:
                        #print('File found, skipping extraction')
                        pass
                    else:
                        #Construct dat file header                     
                        header = ''
                        header += f"Run #{runid}: {runname}, Experiment: {expname}, Sample name: {samplename}, Number of values: " + str(run.number_of_results) + "\n"
                        try:
                            comment = run.get_metadata('Comment')
                            header += f"Comment: {comment} \n"
                        except:
                            header += "\n"
                        
                        if checktimes:
                            times.append(datetime.datetime.now())
                            print('Before reading from db ',times[-1]-times[-2])
                                                
                        all_param_data = run.get_parameter_data()
                        if checktimes:
                            times.append(datetime.datetime.now())
                            print('run.get_parameter_data() ',times[-1]-times[-2])
                        
                        #run_matrix2 = []    
                        meas_params = result_dict[i] # Collect measurement params
                        set_params = depend_dict[i]  # Collect depend params
                        setdata = run.get_parameter_data(param_names[meas_params[0]])
                        
                        if checktimes:
                            times.append(datetime.datetime.now())
                            print('run.get_parameter_data(), only setdata ',times[-1]-times[-2])

                        headernames = ''
                        headerlabelsandunits = ''
                        
                        if checktimes:
                            times.append(datetime.datetime.now())
                            print('Db read out ',times[-1]-times[-2])

                        # Pre-allocate data array                       
                        lset = len(set_params)
                        lmeas = len(meas_params)
                        lval = len(setdata[param_names[meas_params[0]]][param_names[0]])
                        #print(lset,lmeas,lval)
                        run_matrix=np.empty([len(setdata[param_names[meas_params[0]]][param_names[0]]),lset+lmeas])
                        run_matrix.fill(np.nan)
                        # Collect depends (set axes) columns
                        colcounter=0
                        for j in set_params: 
                            #run_matrix2.append(setdata[param_names[meas_params[0]]][param_names[j]])
                            #print(setdata[param_names[meas_params[0]]][param_names[j]])
                            #print((all_param_data[param_names[meas_params[0]]][param_names[j]]))
                            #run_matrix[:,colcounter]=setdata[param_names[meas_params[0]]][param_names[j]]
                            setdata = all_param_data[param_names[meas_params[0]]][param_names[j]]
                            run_matrix[0:len(setdata),colcounter]= setdata
                            headernames += parameters[j].name + "\t"
                            headerlabelsandunits += parameters[j].label + " (" + parameters[j].unit +")" + "\t"
                            colcounter=colcounter+1
                        # Collect measurement (meas axes) columns
                        if checktimes:
                            times.append(datetime.datetime.now())
                            print('Set_params in runmatrix ',times[-1]-times[-2])
                        
                        for k in meas_params:
                            #measdata = run.get_parameter_data(param_names[k])
                            #print(param_names[k])
                            #print(measdata)
                            #print(all_param_data)
                            #run_matrix2.append(measdata[param_names[k]][param_names[k]])
                            #print(measdata[param_names[k]][param_names[k]])
                            #print(all_param_data[param_names[k]][param_names[k]])
                            #run_matrix[:,colcounter]=measdata[param_names[k]][param_names[k]]
                            measdata = all_param_data[param_names[k]][param_names[k]]
                            run_matrix[0:len(measdata),colcounter]=measdata
                            headernames += parameters[k].name + "\t"
                            headerlabelsandunits += parameters[k].label + " (" + parameters[k].unit +")" + "\t"
                            colcounter=colcounter+1
                        
                        if checktimes:
                            times.append(datetime.datetime.now())
                            print('Meas_params in runmatrix ',times[-1]-times[-2])
                        
                        header += headernames + '\n'
                        header += headerlabelsandunits
                        # Stick'em together
                        #run_matrix2 = np.vstack(run_matrix2)
                        #run_matrix2 = np.flipud(np.rot90(run_matrix2, k=-1, axes=(1,0)))
                        #print(run_matrix,run_matrix.shape)
                        #print(run_matrix2,run_matrix2.shape)
                        # Confirming function is a good boy
                        if not suppress_output:
                            print("Saving measurement with id " + str(runid) +  " to  "+ fullpath)
                        
                        # Actual saving of file
                        file = fullpath                      
                        f = open(file, "wb")
                        np.savetxt(f,np.array([]), header = header)

                        if checktimes:
                            times.append(datetime.datetime.now())
                            print('Opening txt file and saving header ',times[-1]-times[-2])
                        # Routine for properly slicing the slow axes (works for infinite dimensions)
                        slicearray = np.array([]).astype(int)
                        if newline_slowaxes == True:
                            for i in range(0,len(set_params)-1):
                                slicearray = np.concatenate((slicearray, np.where(run_matrix[:-1,i] != run_matrix[1:,i])[0]+1))
                                slicearray = np.unique(slicearray)
                        if checktimes:
                            times.append(datetime.datetime.now())
                            print('newline_slowaxes time consumption ',times[-1]-times[-2])
                        
                        vsliced=np.split(run_matrix,slicearray, axis=0)
                        for i in range(0,len(vsliced)): # This is just one write action if newline_slowaxes is turned off (and a bit faster then)
                            np.savetxt(f,vsliced[i],delimiter='\t')
                            if i != len(vsliced)-1:
                                linestr = "\n"
                                f.write(linestr.encode())
                        f.close()
                        if checktimes:
                            times.append(datetime.datetime.now())
                            print('Writing of the textfile ',times[-1]-times[-2])

                        # Saving of snapshot + run description to JSON file
                        with open(fullpathjson, 'w') as f:
                            if run.snapshot and run.description:
                                total_json = {**json.loads(sz.to_json_for_storage(run.description)), **run.snapshot}
                            if not run.snapshot:
                                if run.description:
                                    total_json = {**json.loads(sz.to_json_for_storage(run.description))}
                                    print('Warning: Measurement {ruinid} has no snapshot.')
                                else:
                                    print('Warning: Measurement {ruinid} has no snapshot or run description. Axes for plotting cannot be extracted.')
                            json.dump(total_json, f, indent = 4)
                    n = n + 1
                    if checktimes:
                        times.append(datetime.datetime.now())
                        print('Total time ',times[-1]-times[0])

    if useopendbconnection == False:
        configuration['core']['db_location'] = previously_opened_db
        configuration.save_to_home()
        initialise_database()