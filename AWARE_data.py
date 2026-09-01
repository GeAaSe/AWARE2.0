"""
This module contains the AWARE_data class.
This data class is used to create objects that contain the entire data that was obtained from a GHM/GCM combination for further use with AWARE.
"""

import pandas as pd
import pickle
import matplotlib.pyplot as plt
import os

class AWARE_data:
    """Container for all discharge, runoff, consumption, and EWR/EFR data for one GHM/GCM/scenario.

    The class stores the full AWARE input data in nested dictionaries keyed by variable name,
    manages long-term averaging periods, and provides methods for saving/loading, adding new
    variables, and computing inland-sink and delta-adjusted outputs.
    """

    def __init__(self, descriptor, GHM:dict|str, GCM:dict|str, scenario: str):
        """Initialize a database object for a specific model input setup.

        Parameters
        ----------
        descriptor : str
            Human-readable label describing the database or experiment.
        GHM : dict, optional
            Global hydrological model identifier.
        GCM : dict, optional
            Global climate model identifier.
        scenario : str, optional
            Scenario name, such as "hist".
        """
        #creates the dictionary and attributes the AWARE_data object contains
        self.descriptor_short = descriptor #until now this most of the time is "tests" because nothing else was specified when first creating the AWARE_DBs
        self.GCM = GCM
        self.GHM = GHM
        self.SCE = scenario

        self.consumption = {"content":[]}
        self.discharge = {"content":[]}
        self.EWR = {"content":[]}
        self.EFR = {"content":[]}
        self.runoff = {"content":[]}
        self.AMDs = {"content":[]}
        self.CFs = {"content":[]}
        self.Mon_List = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        self.LongtermAveragePeriods = {}
        self.RegressionYearPath = None
        self.IrrigationAreas = None
        self.Area = None
        self.AreaDeltaAllocated = False
        self.searchTable = {}
        self.DefaultVariableCategories = {"atotuse":"cons","ptotuse":"cons",
                                          "atotuse_MAINTABLE":"cons",
                                          "ptotuse_MAINTABLE":"cons"}
        self.Path = ""
        self.averagetype = "mean" # note that this only applies to availability variables, not consumption 


        print("created AWARE data object",self.descriptor_short,
              " for GHM:",self.GHM, ", GCM:",self.GCM, "scenario:", self.SCE)
        return
    
    def change_LT_average_type(self,to):
        if to == "median":
            self.averagetype = "median"
            print("longterm average type is now: MEDIAN")
        elif to == "mean":
            self.averagetype = "mean"
            print("longterm average type is now: MEAN")
        else:
            raise ValueError
        
    
    def __repr__(self):
        """
        Returns a string representation of the AWARE_data object.
        The string includes the GHM, GCM, and scenario information,
        as well as a summary of the contents of the various data attributes.
        """
        try:
            returnstring = " ".join(['AWARE Database\nGHM',self.GHM["L"],"\nGCM:",self.GCM["L"],"\nscenario:",self.SCE,"\ndescriptor:",self.descriptor_short])
        except TypeError:
            returnstring = " ".join(['AWARE Database\nGHM',str(self.GHM),"\nGCM:",str(self.GCM),"\nscenario:",str(self.SCE),"\ndescriptor:",self.descriptor_short])
        returnstring = returnstring + "\n"+"-"*10

        returnstring += "\ncontent:\n"
        for variable_type in [self.consumption,self.discharge,self.EWR,self.EFR,self.runoff,self.AMDs,self.CFs]:
            if type(variable_type) ==str: pass
            elif len(variable_type["content"])>0: returnstring = returnstring + "\n" + str(variable_type["content"])
        return returnstring
    
    def return_subfolder_path(self,path):
        if path[-7:]!="_parts/":
            subfolder = path+"_parts/"
        else:
            subfolder = path
        if  os.path.exists(subfolder) is False and subfolder[-7:]=="_parts/": #check whether a new folder was specified as path
            try:
                os.makedirs(subfolder)
            except OSError:
                print (f"Creation of directory {subfolder} failed. Continue.")
        return subfolder

    def return_separate_dump_dict(self,data,parentpath):
        return {
                "data":data,
                "longterm_average_periods":self.LongtermAveragePeriods,
                "descriptor_short":self.descriptor_short,
                "GCM":self.GCM,
                "GHM": self.GHM,
                "SCE": self.SCE,
                "main_path":parentpath
                }

    def split_mainvariable_into_types(self,data_object:dict,parentpath:str):
        all_variables = data_object["content"]
        all_variable_pathdict = {x:None for x in all_variables}
        print("saving separately:", end=" ")
        for variable in all_variables:
            print(variable, end=" ")
            filepath = f"{parentpath}_{variable}"
            file = open(filepath, 'wb')
            pickle.dump(self.return_separate_dump_dict(data=data_object[variable],
                                                parentpath=parentpath),
                        file)
            file.close()
            all_variable_pathdict[variable] = filepath
        all_variable_pathdict["dictionary_type"] = "links to separately dumped childs of a main variable" 
        print("")
        return all_variable_pathdict


    def save(self, path,*, dump_seperately=False,entire_DB=True, remove_from_main_DB=False,split_parents=False):
        """
        saves the database as pickle. 
        If entire_DB is False, only the separated files are saved (can be used to export the objects when the main database already exists).
        Parameters:
            - path (str): either the path where to store the main AWARE_DB or the subfolder where to store the individual variable dictionaries.
            - If dump_separately is True, consumption, discharge, runoff, EWR and EFR objects are saved separately.
            - if split_parents==True: consumption and discharge content is split into the items of the dataframe and stored separately
            - if entire_DB ==True: self is saved in one DB. But if remove_from_main_DB is True, this just overwrites the file that was just written to disc a few lines above
        """

        if dump_seperately:
            subfolder = self.return_subfolder_path(path)
            self.dumped_paths = {}
            try:
                self.external_consumption_projections
            except AttributeError:
                self.external_consumption_projections = {}
            for separate_data,t in zip([self.consumption,self.discharge,self.runoff,self.EWR,self.EFR, self.external_consumption_projections],
                                       ["cons","dis","runoff","EWR","EFR","external_cons"]):
                
                filepath = subfolder+f"separate_{t}"
                self.dumped_paths.update({t:filepath}) #save the filepaths in the main DB
                print(f"saving...{t}", end=" ")
                if t in ["cons","dis"] and split_parents is True and isinstance(separate_data, str) is False:
                    # split discharge or consumption package into individual variables.
                    # Only for cases where separate_data is not a path string (i.e. when the data was not imported but it existed in a different version of the AWARE_DB)
                    separate_data = self.split_mainvariable_into_types(separate_data,parentpath=filepath) #returns a dictionary of paths for the types
                else:
                    pass
                file = open(filepath, 'wb')
                pickle.dump(self.return_separate_dump_dict(data = separate_data,
                                                           parentpath = subfolder.replace("_parts/","") #if this function was called from strip and save, remove the prefix
                                                           ),
                             file)
                file.close()
            
            if remove_from_main_DB:
                print("removing from main DB")
                # if the AWARE_DB instead of actual data already references path strings with self.consumption etc., these are overwritten by the strings to the dumped objects.
                # the dumped objects as their "data" entry contain the path to the original dump dictionaries with the data.
                if "cons" in self.dumped_paths.keys():
                    self.consumption = self.dumped_paths["cons"]
                if "dis" in self.dumped_paths.keys():
                    self.discharge = self.dumped_paths["dis"]
                if "runoff" in self.dumped_paths.keys():
                    self.runoff = self.dumped_paths["runoff"]
                if "EWR" in self.dumped_paths.keys():
                    self.EWR = self.dumped_paths["EWR"]
                if "EFR" in self.dumped_paths.keys():
                    self.EFR = self.dumped_paths["EFR"]
                if "external_cons" in self.dumped_paths.keys():
                    self.external_consumption_projections = self.dumped_paths["external_cons"]
                self.save(path.replace("_parts/","")) # replacing _parts is only a fallback that is required if the path was given with "_parts" at the end

        if entire_DB:
            file = open(path, 'wb')
            self.Path = path
            print("saving...",path.split("/")[-1])
            pickle.dump(self, file)
            file.close()

        print("done")
        return
    
    def strip_and_save(self,strippedpath,*,save_contents_separated=False,remove_duplicate_cons_columns=True):
        """Create a lighter-weight copy without MAINTABLE data.

        This is useful for reducing memory usage or file size while keeping the core basin-level
        variables and metadata. If requested, the removed data can be exported into a separate
        "_parts" folder.

        Parameters
        ----------
        strippedpath : str
            Destination for the reduced database.
        save_contents_separated : bool, optional
            If True, save the removed groups in separate files under a sibling "_parts" folder.
        remove_duplicate_cons_columns : bool, optional
            Remove duplicate negative-value consumption columns if they are identical to the
            non-negative versions.
        """
        stripped_DB = AWARE_data(descriptor= self.descriptor_short,
                                 GCM = self.GCM,GHM = self.GHM,scenario = self.SCE)
        if isinstance(self.consumption, dict):
            for consdata in self.consumption["content"]:
                if "MAINTABLE" in consdata:
                    pass
                else:
                    stripped_DB.addConsumption(consdata,self.consumption[consdata])
        if remove_duplicate_cons_columns:
            stripped_DB.remove_duplicate_cons_columns()
        if isinstance(self.discharge, dict):
            for disdata in self.discharge["content"]:
                if "MAINTABLE" in disdata:
                    pass
                else:
                    stripped_DB.addDischarge(disdata,self.discharge[disdata])
        for disdata in self.runoff["content"]:
            if "MAINTABLE" in disdata:
                pass
            else:
                stripped_DB.addRunoff(disdata,self.runoff[disdata])
        for disdata in self.EWR["content"]:
            stripped_DB.addEWR(disdata,self.EWR[disdata])
        for disdata in self.EFR["content"]:
            stripped_DB.addEFR(disdata,self.EFR[disdata])
        
        stripped_DB.LongtermAveragePeriods = self.LongtermAveragePeriods
        stripped_DB.RegressionYearPath = self.RegressionYearPath
        stripped_DB.IrrigationAreas = self.IrrigationAreas
        stripped_DB.Area = self.Area
        stripped_DB.AreaDeltaAllocated = self.AreaDeltaAllocated 
        stripped_DB.Delta_basins = self.Delta_basins
        if save_contents_separated:
            subfolder = strippedpath+"_parts/"
            try:
                os.makedirs(subfolder)
            except OSError:
                print (f"Creation of directory {subfolder} failed, maybe exists already. Continue.")
            stripped_DB.save(subfolder,
                             dump_seperately=True,entire_DB=False,remove_from_main_DB =True,split_parents=True) #saves in a folder named after the main database with suffix "parts"
        else:
            stripped_DB.save(strippedpath)
        return None
    
    def remove_duplicate_cons_columns(self):
        """Remove duplicate negative-consumption columns created during basin cleaning.

        Some annual consumption tables include both a version with negative values retained and a
        version with negative values clipped to zero. This method removes the redundant duplicate
        columns when the two are identical.
        """

        cols_w_neg = [f"BasinCons_InclNegat_{month}_m3" for month in self.Mon_List]
        cols_wo_neg = [f"BasinCons_{month}_m3" for month in self.Mon_List]
        #get list of consumption names for which to try to remove duplicate columns
        to_work_on = []
        for c_var in self.consumption["content"]:
            if self.consumption[c_var].TIM=="annual": #only looking for annual files
                data_obj = self.consumption[c_var]
                test_yr_1 = [*data_obj.data.keys()][0]
                test_yr_2 = [*data_obj.data.keys()][-1]
                if isinstance(data_obj.data[test_yr_1], pd.DataFrame):
                    if cols_w_neg[0] in data_obj.data[test_yr_1].columns and cols_w_neg[0] in data_obj.data[test_yr_2].columns:
                        to_work_on.append(c_var)
                else:
                    print(c_var, ": no dataframe")
            else: pass
        
        print("checking for duplicate cons columns in")
        for c_var in to_work_on:
            print(c_var, end="")
            years_where_duplicates = list()
            #check whether for all years the InclNegat columns really are duplicates
            for year in self.consumption[c_var].data.keys():
                compared =  self.consumption[c_var].data[year][cols_w_neg].to_numpy() == self.consumption[c_var].data[year][cols_wo_neg].to_numpy()
                if compared.all(): #only remove the negative consumption rows if they are the same for all months
                    years_where_duplicates.append(year)
            if years_where_duplicates == [*self.consumption[c_var].data.keys()]:
                print("..removing duplicates")
                for year in years_where_duplicates:
                    self.consumption[c_var].data[year].drop(columns=cols_w_neg, inplace=True)
            else:
                print("..not removing consumption column duplicates from any year since for some years the columns do not seem to be duplicates")
        return


    def load_pickled_variables(self,var):
        """Load a previously dumped variable dictionary from disk.

        Parameters
        ----------
        var : str
            Variable group name, such as "cons" or "dis".

        Returns
        -------
        dict
            The deserialized data dictionary for the requested variable group.
        """
        file = open(self.dumped_paths[var], 'rb')
        loaded = pickle.load(file)
        file.close()
        # handle case where individual variables are saved separately
        if "dictionary_type" in [*loaded["data"].keys()] and loaded["longterm_average_periods"]==self.LongtermAveragePeriods:
            # this is for loading childs of the main variable
            if loaded["data"]["dictionary_type"] == "links to separately dumped childs of a main variable":
                # for everey child variable name ("atotuse", "pirruse", etc.), the appropriate pickle is loaded and added to a new dictionary 
                recreated_dictionary = {}
                child_names = [x for x in loaded["data"].keys() if x !="dictionary_type"]
                for child_name in child_names:
                    child_filepath = open(loaded["data"][child_name], 'rb')
                    child_file = pickle.load(child_filepath)
                    child_filepath.close()
                    recreated_dictionary[child_name] = child_file["data"]
                recreated_dictionary["content"] = child_names   
            return recreated_dictionary
        
        else:
            #this is when the loaded pickle is a dictionary that at the "data" key directly contains the dictionary of the original parent variable 
            if loaded["main_path"]!=self.Path:
                raise KeyError("variable and main DB specify different main path")
            elif loaded["longterm_average_periods"]!=self.LongtermAveragePeriods:
                raise KeyError("variable and main DB specify different Longterm Average periods")
            elif 'content' not in loaded["data"].keys():
                if loaded["data"]=={}:
                    print(f"{var} has empty dictionary")
                else:
                    raise ValueError("seems like the loaded file is not a valid dictionary created with the AWARE_data class")
            else:
                return loaded["data"]
    
    def load_externally_saved(self,*,to_load=["cons","dis","runoff","EWR","EFR","external_cons"]):
        """Reload data that was previously saved in external separate files.

        This restores the in-memory dictionaries for the selected groups after a pickled database
        has been reduced or exported in a split form.

        Parameters
        ----------
        to_load : list of str, optional
            Names of groups to reload from disk. Common values are "cons", "dis", "runoff",
            "EWR", and "EFR".
        """
        if all(["cons" in self.dumped_paths.keys() , isinstance(self.consumption,str),"cons" in to_load]):
            print("loading cons ",end="")
            self.consumption =  self.load_pickled_variables("cons")

        if all(["dis" in self.dumped_paths.keys() , isinstance(self.discharge,str),"dis" in to_load]):
            print("loading dis ",end="")
            self.discharge =    self.load_pickled_variables("dis")

        if all(["runoff" in self.dumped_paths.keys() , isinstance(self.runoff,str),"runoff" in to_load]):
            print("loading runoff ",end="")
            self.runoff =       self.load_pickled_variables("runoff")

        if all(["EWR" in self.dumped_paths.keys() , isinstance(self.EWR,str),"EWR" in to_load]):
            print("loading EWR ",end="")
            self.EWR =          self.load_pickled_variables("EWR")

        if all(["EFR" in self.dumped_paths.keys(), isinstance(self.EFR,str),"EFR" in to_load]):
            print("loading EFR ",end="")
            self.EFR =          self.load_pickled_variables("EFR")

        try: # could be that the variable "self.external_consumption_projections" is not defined yet 
            if all(["external_cons" in self.dumped_paths.keys(), isinstance(self.external_consumption_projections,str),"external_cons" in to_load]):
                print("loading external consumption ",end="")
                self.external_consumption_projections = self.load_pickled_variables("external_cons")
        except:
            print("not loading external_cons")
        return

    def addConsumption(self, v_type, object,*, force_update=False):
        """Add a consumption variable to the database.

        Parameters
        ----------
        v_type : str
            Name of the consumption variable, such as "atotuse" or "ptotuse".
        object : AWARE_data_entry
            Data container for that variable.
        force_update : bool, optional
            Allow overwriting an existing variable name when True.
        """
        if v_type not in self.consumption.keys():
            self.consumption.update({v_type:object})
            self.consumption["content"].append(v_type)
            self.searchTable[v_type] = "consumption"
            print("added consumption object", object)
        else:
            self.manage_collision(force_update) # if updates should not be forced, this raises Exception
            self.consumption.update({v_type:object})
            print("replaced consumption object", object)
        return
    
    def addDischarge(self, v_type, object, *,force_update=False):
        """Add a discharge variable to the database.

        Parameters
        ----------
        v_type : str
            Name of the discharge variable.
        object : AWARE_data_entry
            Data entry storing the discharge values.
        force_update : bool, optional
            If True, overwrite an existing variable with the same name.
        """
        if v_type not in self.discharge.keys():
            self.discharge.update({v_type:object})
            self.discharge["content"].append(v_type)
            self.searchTable[v_type] = "discharge"
            print("added discharge object", object)
        
        else:
            self.manage_collision(force_update) # if updates should not be forced, this raises Exception
            self.discharge.update({v_type:object})
            print("replaced discharge object", object)
        return None
    
    def addEWR(self, v_type, object,*, force_update=False):
        """Add an environmental water requirement variable to the database."""
        if v_type not in self.EWR.keys():
            self.EWR.update({v_type:object})
            self.EWR["content"].append(v_type)
            self.searchTable[v_type] = "EWR"
            print("added EWR object", object)
        else:
            self.manage_collision(force_update) # if updates should not be forced, this raises Exception
            self.EWR.update({v_type:object})
            print("replaced EWR object", object)
        return None
    
    def addEFR(self, v_type, object,*, force_update=False):
        """Add an environmental flow requirement variable to the database."""
        if v_type not in self.EFR.keys():
            self.EFR.update({v_type:object})
            self.EFR["content"].append(v_type)
            self.searchTable[v_type] = "EFR"
            print("added EFR object", object)
        else:
            self.manage_collision(force_update) # if updates should not be forced, this raises Exception
            self.EFR.update({v_type:object})
            print("replaced EFR object", object)
        return None
    
    def addRunoff(self, v_type, object,*,force_update=False):
        """Add a runoff variable to the database."""

        if v_type not in self.runoff.keys():
            self.runoff.update({v_type:object})
            self.runoff["content"].append(v_type)
            self.searchTable[v_type] = "runoff"
            print("added runoff object", object)
        else:
            self.manage_collision(force_update) # if updates should not be forced, this raises Exception
            self.runoff.update({v_type:object})
            print("replaced runoff object", object)
        return
    
    def forcing_updates_globally(self):
        if hasattr(self,"ALWAYS_FORCE_UPDATES"): #provides option to set behaviour of force_update globally
            return self.ALWAYS_FORCE_UPDATES
        else:
            return False
    
    def manage_collision(self, force_update):
        if force_update == True:
            pass
        elif self.forcing_updates_globally():
            pass
        else:
            raise Exception("collison: variable type is already in dataframe")
        return None


    def AddUpVariables_consumption(self, rules):
        """Create summed consumption variables from component datasets.

        Parameters
        ----------
        rules : dict
            Mapping from target variable name to a list of source variables. Entries ending in
            "-subtract" are subtracted instead of added.
        """
        if rules ==False or rules ==None:
            return
        
        
        def get_columns(df_cols):
            add_up_cols=self.Mon_List+[x+"_Area_x_Cons_m3" for x in self.Mon_List]+["BasinCons_InclNegat_"+x+"_m3" for x in self.Mon_List]
            # default behaviour: use columns that fit to atotuse
            columns = [x for x in df_cols if x in add_up_cols]
            # if there are no matches, try all columns which contain month names
            if len(columns) ==0:
                columns = [x for x in df_cols if any([month in x for month in self.Mon_List])]
            return columns


        for variable,summands in rules.items():
            #get summands
            datalist =[]
            for summand in summands:
                var_name = summand.split("-subtract")[0] 
                if var_name in self.consumption["content"]:
                    summand_data = self.consumption[var_name].data
                elif var_name in self.discharge["content"]:
                    summand_data = self.discharge[var_name].data
                else:
                    raise ValueError(summand+" is neither discharge or consumption.")
                
                # add dfs to lists for subsequent concatenation, ensure subtraction for -subtract flag
                if "-subtract" in summand:
                    datalist.append({year:df.multiply(-1) for year,df in summand_data.items()})
                else:
                    datalist.append(summand_data)
            all_years_df = {}
            for year in datalist[0].keys():
                # create list of dfs to add up
                concatlist=[]
                oldcols = None
                for summand_var in datalist:
                    # default behaviour: use columns that fit to atotuse
                    columns = get_columns(summand_var[year].columns)
                    # if there are no matches, try all columns which contain month names
                    concatlist.append(summand_var[year][columns])
                    if columns != oldcols and oldcols is not None:
                        raise KeyError("different column names in dfs to sum up")
                    oldcols = columns
                # add up the dfs in the concatlist to get a df of their sum
                concatenated = add_up_dfs_in_concatlist(concatlist)
                #make sure that columns with negative consumption set to zero are provided
                if "BasinCons_Jan_m3" in summand_var[year].columns:
                    for month in self.Mon_List:
                        if "BasinCons_InclNegat_"+month+"_m3" not in concatenated.columns:
                            concatenated["BasinCons_"+month+"_m3"] = concatenated["BasinCons_"+month+"_m3"].mask(concatenated["BasinCons_"+month+"_m3"]<0,0)
                        else:
                            concatenated["BasinCons_"+month+"_m3"] = concatenated["BasinCons_InclNegat_"+month+"_m3"].mask(concatenated["BasinCons_InclNegat_"+month+"_m3"]<0,0)
                if "Basin_ID" in summand_var[year].columns:
                    concatenated["Basin_ID"] = summand_var[year]["Basin_ID"]
                all_years_df[year] = concatenated
            if self.DefaultVariableCategories[variable] =="cons":
                data = AWARE_data_entry(all_years_df, variable = variable, times = "yearspecific", unit="m³/month")
                self.addConsumption(variable, data)
            else:
                raise ValueError("added up variable is not consumption")
        return
                    
    def approximateNaturalDischarge(self):
        """Approximate naturalized discharge from actual discharge and basin consumption.

        This reconstructs a natural discharge proxy by adding basin consumption back to the
        observed outflow discharge. It is mainly used as a fallback or comparison variable and is just a very rough estimation.
        """
        #get actual water consumption and actual discharge on basin level
        act_cons=self.consumption["atotuse"].data
        act_disc=self.discharge["dis"].data
        #do sums for every year
        every_year={}
        for year,cons in act_cons.items():
            nat_disc = pd.DataFrame(index=cons.index,columns=self.Mon_List)
            for month,c_month in zip(self.Mon_List,["BasinCons_InclNegat_"+x+"_m3" for x in self.Mon_List]):
                nat_disc[month] = cons[c_month]+act_disc[year][month]
            every_year[year] = nat_disc
        data = AWARE_data_entry(every_year, variable = "natural_discharge_as_receonstructed_from_atotuse_and_actual_discharge", times = "annual", unit="m³/month")
        self.addDischarge("disnat", data)
        print("created approximated natural discharge from atotuse and discharge")
        return

    def InlandSinkAvailabilities(self):
        """Estimate water availability in inland sink basins from runoff, discharge, and consumption.

        The method reconstructs the inflow and outflow balance around inland sink basins and
        adds adjusted discharge variables needed for downstream EWR and delta calculations.
        """
        #check whether data is available
        self.checkInputsForInlandsinks()
        #get discharge
        sink_infl_separate, sink_infl = self.retrieveInlandSinkInflows(humans="Yes")
        data = AWARE_data_entry(sink_infl, variable = "discharge_inflow_to_InlandSink",
                                times = "annual", unit="m³/month")
        self.addDischarge("dis_sinkinflow", data)
        data = AWARE_data_entry(sink_infl_separate, variable = "discharge_inflow_to_InlandSink_separated_gridcells",
                                times = "annual", unit="m³/month")
        self.addDischarge("dis_sinkinflow_sep", data)

        #get natural discharge (required only for inland sink values that are used in EWR)
        if "disnat" in self.discharge["content"]:
            sink_infl_separate, sink_infl = self.retrieveInlandSinkInflows(humans="No")
            data = AWARE_data_entry(sink_infl, variable = "naturalized_discharge_inflow_to_InlandSink",
                                    times = "annual", unit="m³/month")
            self.addDischarge("disnat_sinkinflow", data)
            data = AWARE_data_entry(sink_infl_separate, variable = "naturalized_discharge_inflow_to_InlandSink_separated_gridcells",
                                    times = "annual", unit="m³/month")
            self.addDischarge("disnat_sinkinflow_sep", data)

        #get columns for MAINTABLE data from runoff and consumption
        cols_Cons = [x+"_Area_x_Cons_m3" for x in self.Mon_List]
        cols_Runoff = ["OutflRunOff_"+x+"_m3" for x in self.Mon_List]
        #get runoff
        if "qtot" in self.runoff["content"]:
            runoff_outflow = self.retrieveInlandSinkRunoff(cols=cols_Runoff, humans="Yes")
            data = AWARE_data_entry(runoff_outflow, variable = "runoff_at_outflow_grid_cells",
                                    times = "annual", unit="m³/month")
            self.addRunoff("qtot_outfl", data)

        #get naturalized runoff
        runoff_outflow_naturalized = self.retrieveInlandSinkRunoff(cols=cols_Runoff, humans="No")
        data = AWARE_data_entry(runoff_outflow_naturalized, variable = "naturalized_runoff_at_outflow_grid_cells",
                                times = "annual", unit="m³/month")
        self.addRunoff("qtotnat_outfl", data)
        #get consumption (for all outflows!)
        cons_outflow = self.retrieveInlandSinkConsumption(cols_Cons)
        data = AWARE_data_entry(cons_outflow, variable = "atotuse_at_outflow_grid_cells", times = "annual", unit="m³/month")
        self.addConsumption("atotuse_outfl", data)

        #calculate workaround
        #calculates the new availability of inland sinks from the provided variables
        SinkAvail_idx=self.IS_basins.loc[self.IS_basins["InlandSink"] == True].index
        InlandSinkAvailability={}
        NaturalizedInlandSinkAvailability={}

        #check whether for naturalized data the same range of years is available as for actual
        DO_FOR_NATURALIZED=False
        if "disnat" in self.discharge["content"]:
            DO_FOR_NATURALIZED = all([max(self.discharge["dis"].data.keys()) == max(self.discharge["disnat"].data.keys()),
                                      min(self.discharge["dis"].data.keys()) == min(self.discharge["disnat"].data.keys())])
        for year in self.discharge["dis"].data.keys():
            IS_Basins = pd.DataFrame(index=SinkAvail_idx)
            ronat = self.runoff["qtotnat_outfl"].data[year]
            con = self.consumption["atotuse_outfl"].data[year]
            for month in self.Mon_List:
                IS_Basins.loc[:,month] = self.discharge["dis_sinkinflow"].data[year].loc[:,month]
                IS_Basins = IS_Basins.fillna(0)
                IS_Basins.loc[:,month]=IS_Basins.loc[:,month]+ronat.loc[:,month]-con.loc[:,month]
            IS_Basins.where(IS_Basins[self.Mon_List]>=0,other=0,inplace=True)
            InlandSinkAvailability[year] = IS_Basins

            if "disnat" in self.discharge["content"]:
                if DO_FOR_NATURALIZED:
                    #same for naturalized discharge
                    IS_Basins_nat = pd.DataFrame(index=SinkAvail_idx)
                    for month in self.Mon_List:
                        IS_Basins_nat.loc[:,month] = self.discharge["disnat_sinkinflow"].data[year].loc[:,month]
                        IS_Basins_nat = IS_Basins_nat.fillna(0)
                        IS_Basins_nat.loc[:,month]=IS_Basins_nat.loc[:,month]+ronat.loc[:,month]
                    IS_Basins_nat.where(IS_Basins_nat[self.Mon_List]>=0,other=0,inplace=True)
                    NaturalizedInlandSinkAvailability[year] = IS_Basins_nat
                else:
                    print("no inland sink approximation for naturalized discharge")

        data = AWARE_data_entry(InlandSinkAvailability, variable = "approximated_available_water_after_human_consumption_in_inlandsinks",
                                times = "annual", unit="m³/month")
        self.addDischarge("dis_in_inland_sink", data)
        if "disnat" in self.discharge["content"]:
        #do the same for naturalized availability
            data = AWARE_data_entry(NaturalizedInlandSinkAvailability, variable = "approximated_naturally_available_water_in_inlandsinks",
                                    times = "annual", unit="m³/month")
            self.addDischarge("disnat_in_inland_sink", data)


        #merge discharge files with inland sink discharge files
        #merge inland sink discharge and discharge in other basins
        for dis_type,dis_type_long in zip(["dis","disnat"],["discharge","naturalized_discharge"]):
            if "disnat" not in self.discharge["content"] and dis_type =="disnat":
                pass #no naturalized data
            elif DO_FOR_NATURALIZED is False and dis_type =="disnat":
                pass #not enough years for naturalized data
            else:
                merged_discharge={}
                for year,DF in self.discharge[dis_type].data.items():
                    inlandsink_DF = self.discharge[dis_type+"_in_inland_sink"].data[year]
                    merged_discharge[year] = mergeDischargeWithInlandSinks(DF,inlandsink_DF,self.Mon_List)
                data = AWARE_data_entry(merged_discharge, variable = dis_type_long+"_at_outflows_including_approximated_inland_sinks",
                                        times = "annual", unit="m³/month")
                self.addDischarge(dis_type+"_with_inland_sinks", data)

        #Add inland sink values to MAINTABLE (required for availability adjustment)
        MAINTABLE_with_Inland_sink_dict={}
        for year,DF in self.discharge["dis_MAINTABLE"].data.items():
            MAINTABLE_with_Inland_sink = DF.copy(deep=True)
            Outflow_dis = self.discharge["dis_with_inland_sinks"].data[year]
            MAINTABLE_with_Inland_sink["Outflow_cell"] = self.discharge["dis_MAINTABLE"].aux["Outflow"]
            MAINTABLE_with_Inland_sink = MAINTABLE_with_Inland_sink.reset_index().set_index(["Basin_ID"])
            MAINTABLE_with_Inland_sink.loc[MAINTABLE_with_Inland_sink["Outflow_cell"]==True,self.Mon_List] = Outflow_dis.loc[:,self.Mon_List].astype("float32")
            MAINTABLE_with_Inland_sink_dict[year] = MAINTABLE_with_Inland_sink.reset_index().set_index(["lat","lon"]).drop(columns=["Outflow_cell"])
        data = AWARE_data_entry(MAINTABLE_with_Inland_sink_dict, variable = "approximated_available_water_after_human_consumption_MAINTABLE",
                                times = "annual", unit="m³/month")
        self.addDischarge("dis_with_inland_sinks_MAINTABLE", data)
        return
    
    def checkInputsForInlandsinks(self):
        assert("dis_MAINTABLE" in self.discharge["content"])
        assert("atotuse_MAINTABLE" in self.consumption["content"])
        assert("qtotnat_MAINTABLE" in self.runoff["content"])
        if "disnat_MAINTABLE" not in self.discharge["content"]:
            print("no naturalized discharge available for inland sink approximations.")
        if "qtot_MAINTABLE" not in self.runoff["content"]:
            print("no qtot available, so no qtot at outflow sink calculated (does not affect inland sink calculations)")
        return
    
    def delete_variable(self, varname):
        if varname in self.consumption["content"]:
            self.consumption.pop(varname)
            self.consumption["content"].remove(varname)
        elif varname in self.discharge["content"]:
            self.discharge.pop(varname)
            self.discharge["content"].remove(varname)
        print("deleted",varname)
        return

    def addAuxiliary(self,*, InlandSinkInflows=None,InlandSinkBasins=None,DeltaBasins=None,Area=None):
        """Store auxiliary maps used throughout the AWARE calculations.

        Parameters
        ----------
        InlandSinkInflows : pandas.DataFrame, optional
            Grid-cell table identifying inland-sink inflow cells. (table with latitude, longitude and bool for whether grid cell is inland sink inflow)
        InlandSinkBasins : pandas.Series, optional
            Basin-level flag indicating which basins are inland sinks. (Series with Basin_ID as index and bool indicating whether the basin is an inland sink)
        DeltaBasins : pandas.DataFrame, optional
            Basin-to-delta allocation metadata used for delta merging. (A DataFrame with Basin_ID	as index, MainBranchBasin_ID indicating which basin this basin belongs to, 2gc_Delta_ID as ID of the Delta, 
                            MainBranchTrue as information whether basin is the main branch of the delta, DissolvedDeltas_MainBasin_ID as main branch basin for every basin)
        Area : pandas.Series, optional
            Basin area data used in area-based adjustments.
        """
        if type(InlandSinkInflows) !=type(None):
            self.IS_inflow_cells = InlandSinkInflows[["InflowToInlandSink","OutflPoints_InlandSink","Basin_ID"]]
        if type(InlandSinkBasins) !=type(None):
            self.IS_basins = InlandSinkBasins
        if type(DeltaBasins) !=type(None):
            self.Delta_basins = DeltaBasins
        if type(Area) !=type(None):
            self.Area = Area
        return 
    
    def retrieveInlandSinkInflows(self,humans="Yes"):
        """Extract discharge inflows for inland-sink grid cells for a given discharge type."""
        if humans == "Yes":
            discharges = self.discharge["dis_MAINTABLE"].data
        elif humans =="No":
            discharges =  self.discharge["disnat_MAINTABLE"].data
        Inflows = dict()
        Inflows_grouped = dict()
        for year, DF in discharges.items():
            temp = pd.concat([DF,self.IS_inflow_cells[["Basin_ID","InflowToInlandSink"]].rename(columns={"Basin_ID":"Into_Basin_ID"})], axis=1)
            Inflows[year] = temp.loc[temp["InflowToInlandSink"]==True,["Basin_ID","Into_Basin_ID"]+self.Mon_List]
            Inflows_grouped[year] = temp.loc[temp["InflowToInlandSink"]==True,["Into_Basin_ID"]+self.Mon_List].groupby("Into_Basin_ID").sum()
            Inflows_grouped[year].index.name = "Basin_ID"
        return Inflows, Inflows_grouped
    
    def retrieveInlandSinkConsumption(self,cols):
        """Extract consumption at terminal grid cells for inland-sink processing."""
        ConsumptionAtOutflow={}
        cols_renamedict = {cols[x]:self.Mon_List[x] for x in range(12)}
        mask = self.consumption["atotuse_MAINTABLE"].aux["Outflow"].reset_index().set_index(["lat","lon"])
        mask = mask.loc[mask["Outflow"]==True].index
        for year, DF in self.consumption["atotuse_MAINTABLE"].data.items():
            #filter to outflows, creating a new file (also non-inland-sinks)
            ConsumptionAtOutflow[year]=DF.loc[mask,cols+["Basin_ID"]].rename(columns=cols_renamedict)
            #set new index
            ConsumptionAtOutflow[year].set_index("Basin_ID", inplace=True)
        
        return ConsumptionAtOutflow
    
    def retrieveInlandSinkRunoff(self, cols, humans="Yes"):
        """
        retrieves inland sink runoff at the outflow cell of a basin. Since runoff is only sampled at the outflow, MAINTABLE is not required
        """
        if humans =="Yes":
            RO = self.runoff["qtot"]
        elif humans =="No":
            RO = self.runoff["qtotnat"]
        RunoffAtOutflow={}
        cols_renamedict = {cols[x]:self.Mon_List[x] for x in range(12)}
        mask = self.IS_basins.loc[self.IS_basins["InlandSink"]==True].index
        for year, DF in RO.data.items():
            #filter to outflows, creating a new file (also non-inland-sinks)
            RunoffAtOutflow[year]=DF.loc[mask,cols].rename(columns=cols_renamedict)
        return RunoffAtOutflow
    
    def calculateEFRs(self,*,from_disnat="disnat_LT_average_inc_inlsinks",suffix=""):
        """Calculate environmental flow requirements from the naturalized long-term discharge.

        Parameters
        ----------
        from_disnat : str, optional
            Name of the discharge dataset to use as input.
        suffix : str, optional
            Suffix appended to the created EFR variable names.
        """
        assert(from_disnat in self.discharge["content"])
        natdis = self.discharge[from_disnat].data["EWR_period"]
        assert(all(natdis.columns==self.Mon_List))
        EFRs, MMFtoMAF = calculateEFRs_generic(natdis)
        data = AWARE_data_entry(EFRs, variable = "EFR_from"+str(self.LongtermAveragePeriods["EWR_period"][0])+"_to_"+str(self.LongtermAveragePeriods["EWR_period"][1])+suffix,
                                    times = "averaged", unit="-")
        self.addEFR("EFR"+suffix, data)
        data = AWARE_data_entry(MMFtoMAF, variable = "Mean_Monthly_Flow_div_by_Mean_Annual_Flow_from"+str(self.LongtermAveragePeriods["EWR_period"][0])+"_to_"+str(self.LongtermAveragePeriods["EWR_period"][1])+suffix,
                                    times = "averaged", unit="-")
        self.addEFR("MMFtoMAF"+suffix, data)
        print("calculated EFRs"+suffix)
        return
    
    def calculateEWRs(self,*,from_disnat="disnat_LT_average_inc_inlsinks",suffix=""):
        """Calculate environmental water requirements from EFRs and naturalized discharge."""
        assert("EFR"+suffix in self.EFR["content"])
        disnat = self.discharge[from_disnat].data["EWR_period"]
        EWRs = disnat.multiply(self.EFR["EFR"+suffix].data)
        data = AWARE_data_entry(EWRs, variable = "Environmental_Water_Requirements_from"+str(self.LongtermAveragePeriods["EWR_period"][0])+"_to_"+str(self.LongtermAveragePeriods["EWR_period"][1])+suffix,
                                    times = "averaged", unit="m³/month")
        self.addEWR("EWR"+suffix, data)
        print("calculated EWR"+suffix)
        return
    
    def DoDeltaMerging(self,*,inlandsinks="approximated"):
        """Merge discharge values in river deltas and recompute EFR/EWR after delta aggregation."""
        if inlandsinks=="approximated":
            suffix = "_LT_average_inc_inlsinks"
        else:
            suffix = "_LT_average"
        # 1. merge discharge values for naturalized and actual discharge
        self.DoDeltaMerging_generic(dis_type = "dis"+suffix)
        if "disnat"+suffix in self.discharge["content"]:
            self.DoDeltaMerging_generic(dis_type = "disnat"+suffix)


        # 2. recalculate EFRs and EWRs from naturalized discharge (if there had been natural discharge to calculate the EFR/EWR)
        if "disnat"+suffix in self.discharge["content"]:
            if "EWR_period" in self.LongtermAveragePeriods:
                self.calculateEFRs(from_disnat="disnat"+suffix+"_w_deltas",suffix="_deltas_merged")
                self.calculateEWRs(from_disnat="disnat"+suffix+"_w_deltas",suffix="_deltas_merged")

        # => Delta consumption does not need to be recalculated since it is only used for weighting 
        print("succesfully merged deltas")
        return


    def LongtermAveraging(self, periods={}, inlandsinks="approximations",*,continuity=True):
        """Compute long-term average discharge for each configured period.

        Parameters
        ----------
        periods : dict, optional
            Mapping from period label to a two-element list or tuple of [start_year, end_year].
        inlandsinks : str, optional
            If "approximations", use inland-sink-adjusted discharge values; otherwise use the
            non-adjusted discharge sequence.
        continuity : bool, optional
            If True, only use periods where both discharge and naturalized discharge are available
            for the same years; otherwise allow partial coverage.
        """
        if len(self.LongtermAveragePeriods) == 0:
            self.LongtermAveragePeriods = periods
        elif self.LongtermAveragePeriods == periods:
            print("LongtermAveragePeriods is already defined, but the same as the provided periods argument.\nWill probably override old longterm means.")
        else:
            raise ValueError("self.LongtermAveragePeriods already exists and differs from the one provided as attribute.\nMaybe this function was already called before?")
        
        if inlandsinks=="approximations":
            strings = [" with ","_with_inland_sinks","_incl_inlandsink_approximation","_inc_inlsinks"]
        else:
            strings = [" WITHOUT ","","",""]

        if not hasattr(self, 'averagetype'): # if AWARE_DB is too old to already have this attribute
            self.averagetype="mean"
            
        print("calculate longterm discharge{s}inland sink approximation".format(s=strings[0]))
        if "disnat"+strings[1] in self.discharge["content"]:
            iterator = zip(["dis","disnat"],["discharge","naturalized_discharge"])
        else:
            iterator = zip(["dis"],["discharge"])

        if continuity:
            for dtype, dtype_long in iterator:
                averaged={}
                for period,years in periods.items():
                    #make list of dataframes to concat
                    DF_list = [self.discharge[dtype+strings[1]].data[x] for x in range(years[0],years[1]+1)]
                    concatenated = pd.concat(DF_list, axis=0)
                    averaged[period] = groupbyIdx_MeanOrMedian(concatenated, self.averagetype)
                    print("concatenated for years",years)
                data = AWARE_data_entry(averaged, variable = dtype_long+"_longterm_average"+strings[2],
                                        times = "longterm", unit="m³/month")
                self.addDischarge(dtype+"_LT_average"+strings[3], data)
        else:
            for dtype, dtype_long in iterator:
                averaged={}
                for period,years in periods.items():
                    #make list of dataframes to concat
                    #check whether data contains all years for this period
                    Data_keys = list(self.discharge[dtype+strings[1]].data.keys())
                    if years[0] in Data_keys and years[1] in Data_keys:
                        DF_list = [self.discharge[dtype+strings[1]].data[x] for x in range(years[0],years[1]+1)]
                        concatenated = pd.concat(DF_list, axis=0)
                        averaged[period] = groupbyIdx_MeanOrMedian(concatenated, self.averagetype)
                        print("averaged for years",years)
                    else:
                        #if period is EWR_period, missing years are filled with the last year
                        if  period == "EWR_period":
                            DF_list = [self.discharge[dtype+strings[1]].data[x] for x in Data_keys if x in range(years[0],years[1]+1)]
                            lastyear = self.discharge[dtype+strings[1]].data[max(Data_keys)]
                            for year in range(years[0],years[1]+1):
                                if year not in Data_keys:
                                    DF_list.append(lastyear)
                            concatenated = pd.concat(DF_list, axis=0)
                            averaged[period] = groupbyIdx_MeanOrMedian(concatenated, self.averagetype)
                            print("averaged for years",years)
                        
                        else: #for all other periods with missing years: do not provide longterm average
                            pass

                data = AWARE_data_entry(averaged, variable = dtype_long+"_longterm_average"+strings[2]+f"_average_mode_is_{self.averagetype.upper()}",
                                        times = "longterm", unit="m³/month")
                self.addDischarge(dtype+"_LT_average"+strings[3], data)
        print("calculated longterm averages")
        return
       
    
    def recalculateLongtermDischargeValues(self,discharge_type="dis_with_inland_sinks", *,dodeltamerging=True):
        """Recompute long-term discharge values after consumption-based adjustments.

        Parameters
        ----------
        discharge_type : str, optional
            Base discharge variable to update, such as "dis_with_inland_sinks".
        dodeltamerging : bool, optional
            If True, also perform delta merging for the recalculated values.
        """
        #get periods for longterm averaging
        self.LongtermAveragePeriods # is a dictionary
        #get the years that were extrapolated and the associated files
        extrapolated = self.discharge["simulated_adjusted_ActAvail_basin"].data 
        
        #get the other years that were not extrapolated from total year range
        #we assume that non-adjusted discharge only exists for older years
        Longterm_Dis = {}
        for period_nr,period in self.LongtermAveragePeriods.items():
            DF_list=[]
            for year in range(period[0],period[1]+1):
                if year in extrapolated.keys():
                    DF_list.append(extrapolated[year])
                else:
                    DF_list.append(self.discharge[discharge_type].data[year])
            
            concatenated = pd.concat(DF_list, axis = 0)
            Longterm_Dis[period_nr] = groupbyIdx_MeanOrMedian(concatenated,self.averagetype)
        data = AWARE_data_entry(Longterm_Dis, variable=discharge_type+f"_LT_average_average_mode_{self.averagetype.upper()}___adjusted_with_consumption_change",
                                times="longterm", unit="m³/month")
        self.addDischarge(discharge_type+"_LT_adj_w_cons_change",data)
        if dodeltamerging:
            self.DoDeltaMerging_generic(dis_type=discharge_type+"_LT_adj_w_cons_change")
        return
    
    def DoDeltaMerging_generic(self, dis_type):
        """
        This function merges water availability in deltas.
        """
        # 1. merge discharge values for naturalized and actual discharge

        delta_discharges={}
        dis_type_long = self.discharge[dis_type].VAR
        if self.discharge[dis_type].TIM == "longterm":
            use_periods = [x for x in self.LongtermAveragePeriods if x in self.discharge[dis_type].data.keys()]
        else:
            use_periods = [x for x in self.discharge[dis_type].data.keys()]
        for period in use_periods:
            #get discharge
            discharge = self.discharge[dis_type].data[period].copy(deep=True)
            #use Delta File as mask to identify the Main Branch 
            discharge["Main"]=self.Delta_basins["DissolvedDeltas_MainBasin_ID"]
            # calculate sum over delta
            Sums=discharge.groupby(by="Main").sum()
            discharge=discharge.reset_index().set_index("Main")
            # apply sum to each basin that has the respective basin as main branch
            discharge.loc[:,self.Mon_List]=Sums.loc[:,self.Mon_List]
            discharge=discharge.set_index("Basin_ID")
            delta_discharges[period] = discharge
        data = AWARE_data_entry(delta_discharges, variable = dis_type_long+"_with_deltas",
                                times = "longterm", unit="m³/month")
        self.addDischarge(dis_type+"_w_deltas", data)

        if type(self.AreaDeltaAllocated) == bool:
            #do allocation of areas in delta (requierd for AMDs because small side branches will otherwise have unreasonably high values)
            self.AreaDeltaAllocated = self.getAreaParams(self.discharge[dis_type+"_w_deltas"].data[period].index)

        # => Delta consumption does not need to be recalculated since it is only used for weighting 
        print("succesfully merged deltas for",dis_type)
        return
    
    def getAreaParams(self,index):
        AreaSeries = self.Area["Rasterstat_CellArea_sum"]
        #check area unit
        if max(AreaSeries) <(50000*50000): #check whether unit is m³ or km³. one grid cell at the equator is ~ 55000*55000 m²
            area= AreaSeries*1000000
            if max(area)>1.6E+12:
                raise ValueError("Unit of areas might not be correct")
        else:
            area = AreaSeries.copy(deep=True)
        #restrict area file to basins used in this run
        area = area.loc[index]
        #sum areas in deltas
        area=self.SumDeltaAreas(area,self.Delta_basins)
        return area

    def SumDeltaAreas(self,Area, allocations):
        Acol=Area.name
        AreaDF=Area.to_frame()
        AreaDF["Main"]=allocations["DissolvedDeltas_MainBasin_ID"]
        SummedArea=AreaDF.groupby(by="Main").sum()
        AreaDF=AreaDF.reset_index()
        AreaDF=AreaDF.set_index("Main")
        #apply sums to individual basins
        AreaDF.loc[:,Acol]=SummedArea.loc[:,Acol]
        print("Test Basin:",47944,AreaDF.loc[47944,["Basin_ID",Acol]])
        #set index
        AreaDF=AreaDF.reset_index()
        AreaDF=AreaDF.set_index("Basin_ID")
        DeltaArea=AreaDF[Acol]
        return DeltaArea
    

    def calculateLongtermActualConsumption(self):
        """
        uses extrapolated atotuse and original atotuse (for years without extrapolation) to calculate longterm extrapolated atotuse for every month.
        Atotuse WITH SUBZERO values is used for that.
        saves with the same column naming as original atotuse (names depend on whether subzero atotuse is set to zero or not).
        """

        #get periods for longterm averaging
        self.LongtermAveragePeriods # is a dictionary
        #get the years that were extrapolated and the associated files
        extrapolated = self.consumption["adjusted_atotuse_basin"].data 

        conscols_wNegative = ["BasinCons_InclNegat_"+x+"_m3" for x in self.Mon_List]        
        Longterm_Cons = {}
        for period_nr,period in self.LongtermAveragePeriods.items():
            DF_list=[]
            for year in range(period[0],period[1]+1):
                if year in extrapolated.keys():
                    DF_list.append(extrapolated[year].rename(columns={self.Mon_List[x]:conscols_wNegative[x] for x in range(12)}))
                else:
                    DF_list.append(self.consumption["atotuse"].data[year][conscols_wNegative])
            
            concatenated = pd.concat(DF_list, axis = 0)
            
            LT_average = concatenated.groupby("Basin_ID").mean()
            for neg_col,zer_col in zip(conscols_wNegative,["BasinCons_"+x+"_m3" for x in self.Mon_List]):
                LT_average[zer_col] = LT_average[neg_col].mask(LT_average[neg_col]<0,0)
            Longterm_Cons[period_nr] = LT_average

        data = AWARE_data_entry(Longterm_Cons, variable="atotuse___adjusted_to_extrapolations_and_availability",
                                times="longterm", unit="m³/month")
        self.addConsumption("atotuse_LT_adjusted_with_consumption_change",data)
        return
        
    def LongtermConsumption(self, variable):
        """
        does longterm averages of a given consumption variable.
        If negative values are in the original values, these are NOT set to zero before averaging.
        """

        averaged={}
        for period,years in self.LongtermAveragePeriods.items():
            #make list of dataframes to concat
            DF_list = [self.consumption[variable].data[x] for x in range(years[0],years[1]+1)]
            concatenated = pd.concat(DF_list, axis=0)
            means = concatenated.groupby(level=0).mean()
            averaged[period] = means[[x for x in means.columns if x not in ["CellCount"]]]
            print("concatenated for years",years)
        data = AWARE_data_entry(averaged, variable = variable+"_longterm_average",
                                times = "longterm", unit="m³/month")
        self.addConsumption(variable+"_LT_average", data)
        return

    def LongtermConsumptionMAINTABLE(self, variable,*,override_lt_periods = False):
        """  
        calculates longterm averages from consumption MAINTABLEs
        - variable: the variable name including the MAINTABLE suffix
        - override_lt_periods: only required if database does not have Longterm periods yet. Is a dictionary of numbering and the start and end years of the periods
        returns nothing
        """
        averaged={}
        if override_lt_periods and self.LongtermAveragePeriods=={}:
            self.LongtermAveragePeriods = override_lt_periods
        elif override_lt_periods and len(self.LongtermAveragePeriods.keys())>0:
            raise ValueError("why specifying override longterm periods if there already are some in the DB")
        elif len(self.LongtermAveragePeriods.keys())==0:
            raise ValueError("there are no longterm averaging periods specified in the DB or in the function inputs")
        else:
            pass
        
        grid_cons_cols = [x+"_Area_x_Cons_m3" for x in self.Mon_List]
        print("concatenated for years", end=": ")
        for period,years in self.LongtermAveragePeriods.items():
            #make list of dataframes to concat
            DF_list = [self.consumption[variable].data[x][grid_cons_cols] for x in range(years[0],years[1]+1)]
            concatenated = pd.concat(DF_list, axis=0)
            averaged[period] = concatenated.groupby(level=[0,1]).mean()
            print(years,end=", ")
        data = AWARE_data_entry(averaged, variable = variable+"_longterm_average",
                                times = "longterm", unit="m³/month")
        self.addConsumption(variable+"_LT_average", data)
        return
      

class AWARE_data_entry:
    """Lightweight container for a single AWARE variable and its time series.

    Each instance stores the actual data dictionary together with metadata describing the
    variable, temporal aggregation type, measurement unit, and any auxiliary table that is
    shared across all years.
    """
    def __init__(self, data, variable = str(), times = str(), unit=str(), *,aux=None):
        """Create a metadata wrapper around a variable's data.

        Parameters
        ----------
        data : dict or pandas.DataFrame
            Time-indexed data for the variable. Typical usage is a dictionary keyed by year or
            long-term period.
        variable : str, optional
            Name of the stored variable.
        times : str, optional
            Temporal convention, e.g. "yearspecific", "longterm", or "averaged".
        unit : str, optional
            Physical unit of the values.
        aux : object, optional
            Auxiliary table attached to the data object, such as grid-cell metadata.
        """
        self.VAR = variable
        self.TIM = times #for example: annual? aggregated?
        self.UNI = unit
        self.data = data
        self.aux = aux
        return
    
    def __repr__(self):
        return ", ".join([self.VAR,self.TIM,self.UNI])

    def plotglobalsums(self,*,save="No",cols=[]):
        try:
            data_list = []
            x_coord = []
            for x,y in self.data.items():
                if len(y.columns)>12 and len(cols)>0:
                    z = y[cols]
                else:
                    z=y
                if type(x) ==int:
                    x_coord.append(x)
                    data_list.append(z.sum().sum())
            plt.plot(x_coord,data_list)
            title_len = len(self.VAR)
            if title_len >80:
                title = self.VAR[:int(title_len//2)]+"-\n"+self.VAR[int(title_len//2):]
            else:
                title = self.VAR
            plt.title(title)
            plt.ylabel(self.UNI)
            plt.ylim(0)
            if save!="No":
                plt.savefig(self.VAR+"global sums.png", dpi=400, layout="tight")
            plt.show()
        except:
            print("could not create figure")

    def plotbasintimeline(self,basin=0,*,save="No",cols =None):
        try:
            data_list = pd.DataFrame()
            x_coord = []
            for x,y in self.data.items():
                if len(y.columns)>12 and len(cols)>0:
                    z = y[cols]
                else:
                    z=y
                if type(x) ==int:
                    x_coord.append(x)
                    if cols  is not None:
                        data_list = pd.concat([data_list,z.loc[basin].loc[cols]], axis=1)
                    else:
                        data_list = pd.concat([data_list,z.loc[basin]], axis=1)
            plt.plot(x_coord,data_list.T, label = data_list.index)
            title_len = len(self.VAR)
            if title_len >80:
                title = self.VAR[:int(title_len//2)]+"-\n"+self.VAR[int(title_len//2):]
            else:
                title = self.VAR
            plt.title(title)
            plt.legend()
            plt.ylabel(self.UNI)
            plt.ylim(0)
            if save!="No":
                plt.savefig(self.VAR+f"{basin} values.png", dpi=400, layout="tight")
            plt.show()
        except:
            print("could not create figure")

def calculateEFRs_generic(DF):
    """Calculate environmental flow requirements from a monthly naturalized discharge table.

    Parameters
    ----------
    DF : pandas.DataFrame
        Basin-level monthly discharge values indexed by basin ID and containing the 12 month
        columns in the order Jan to Dec.

    Returns
    -------
    tuple
        A pair of DataFrames: the calculated EFR values and the monthly-to-annual flow ratio
        used during the calculation.
    """
    assert(all([x==y for x,y in zip(DF.columns,["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])]))
    # calculate Annual Flow in m³/s
    annual = DF.sum(axis=1)
    annual = annual/(365*(24*60*60))
    # Chatham Island is not available in all WaterGAP2.2e ISIMIP runs, a ratio of 0/0 = nan would destroy the EWR and AMD calculations.Therefore make divisor nonzero.
    # => instead waiting for the 0/0 division and then to fillna is not possible due to a bug in pandas (https://github.com/pandas-dev/pandas/issues/39926) 
    annual = annual.replace(0,-1) 
    # calculate monthly flow in m³/s
    monthly = pd.DataFrame(columns=DF.columns)
    day_nr = list((31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31))

    for month, days in zip(DF.columns,day_nr):
        monthly[month] = DF[month]/(days*24*60*60)
    # calculate ratios
    MMFtoMAF=pd.DataFrame(columns=monthly.columns)
    for col in monthly.columns:
        MMFtoMAF[col] = monthly[col]/annual
    # calculate EFRs
    efrcols = ["EFR_"+x for x in DF.columns]
    for month,EFRmonth in zip(DF.columns,efrcols):
        MMFtoMAF.loc[MMFtoMAF[month]<=0.4,EFRmonth] = 0.6
        MMFtoMAF.loc[(MMFtoMAF[month]>0.4) & (MMFtoMAF[month]<=0.8),
                     EFRmonth]                      = 0.3+0.3*(0.8-MMFtoMAF.loc[:,month])/0.4
        MMFtoMAF.loc[MMFtoMAF[month]>0.8,EFRmonth]  = 0.3
    return MMFtoMAF[efrcols].rename(columns={efrcols[x]:DF.columns[x] for x in range(12)}),   MMFtoMAF[DF.columns]

def mergeDischargeWithInlandSinks(original,inlandsink,cols):
    """Replace outflow values in a discharge table with inland-sink-adjusted values.

    Parameters
    ----------
    original : pandas.DataFrame
        Original discharge table.
    inlandsink : pandas.DataFrame
        Alternative discharge values (ONLY!!) for inland-sink basins.
    cols : list-like
        Monthly columns to overwrite in the original table.
    """
    Merged=original.copy(deep=True)
    for column in cols:
        Merged.loc[inlandsink.index,column] = inlandsink.loc[:,column]
    return Merged

def groupbyIdx_MeanOrMedian(DF, mode):
    """Aggregate a DataFrame by its first index level using mean or median.

    Parameters
    ----------
    DF : pandas.DataFrame
        DataFrame indexed by basin or grid-cell identifiers.
    mode : {"mean", "median"}
        Aggregation mode.
    """
    if mode == "mean":
        return DF.groupby(level=0).mean()
    elif mode == "median":
        return DF.groupby(level=0).median()
    else:
        raise ValueError("mode must be either 'mean' or 'median'")

def add_up_dfs_in_concatlist(concatlist):
    """Add a list of DataFrames with matching indices and columns.

    This helper is used when summing multiple component datasets such as irrigation,
    domestic, and industrial consumption.
    """
    concatenated = pd.concat(concatlist, axis=0)
    if concatenated.index.names == ["lat","lon"]:
        return concatenated.groupby(level=[0,1]).sum()
    elif concatenated.index.name == "Basin_ID":
        return concatenated.groupby(level=0).sum()
    