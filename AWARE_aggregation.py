"""
this module is tested in 032_Country aggregation code.ipynb
"""

import numpy as np
from ensemble_analysis_helper import *
import pandas as pd
from tqdm import tqdm


class countryAggregator:
    """
    use aggregate_to_countries(CFs,weighting) for aggregation
    use add_full_country_mapping(countryCFs) for adding mapping between GLAM and ecoinvent    
    """
    
    def __init__(self, country_definition):
        """
        takes one of two country definition names:
        - 'ecoinvent310'
        - 'ecoinvent310_with_replacement_from_GLAM': This is based on the ecoinvent, but better resolution geometries from GLAM replace some of the ecoinvent geometries 
        - 'GLAM (territories combined with mainland)'

        
        use aggregate_to_countries(CFs,weighting) for aggregation
        use add_full_country_mapping(countryCFs) for adding mapping between GLAM and ecoinvent
        """
        self.country_definition = country_definition
        #get country-grid cell intersection
        gridcell_landareashare_countries_attrs = {
            "ecoinvent310":{"path":r"I:\PhD_10_AWARE_Fut\Data\Input\_Masks and Mapping\country_aggregation\gridcell_landareashare_countries_ecoinvent310.csv",
                            "country_ID_name":"shortname",
                            "path_to_countrylist": r"i:\PhD_10_AWARE_Fut\Data\Input\_Masks and Mapping\country_aggregation\ecoinvent310_all_wo_major_lakes.csv"},
            "ecoinvent310_with_replacement_from_GLAM":{"path":r"I:\PhD_10_AWARE_Fut\Data\Input\_Masks and Mapping\country_aggregation\gridcell_landareashare_countries_ecoinvent310_with_GLAM_replacement.csv",
                            "country_ID_name":"shortname",
                            "path_to_countrylist": r"i:\PhD_10_AWARE_Fut\Data\Input\_Masks and Mapping\country_aggregation\ecoinvent310_all_wo_major_lakes.csv"},
            "GLAM (territories combined with mainland)": {"path":r"I:\PhD_10_AWARE_Fut\Data\Input\_Masks and Mapping\country_aggregation\gridcell_landareashare_countries_GLAMTerrComb.csv",
                                                          "country_ID_name":"ROMNAM",
                                                          "path_to_countrylist":r"I:\PhD_10_AWARE_Fut\Data\Input\_Masks and Mapping\country_aggregation\country_entire_areas_GLAMTerrComb.csv"}
                                                          }
        
        local_country_def = gridcell_landareashare_countries_attrs[country_definition]
        self.gridcell_landareashare_countries_raw = pd.read_csv(local_country_def["path"], keep_default_na=False, index_col=[0,1])
        self.gridcell_landareashare_countries_raw["Basin_ID"]  = self.gridcell_landareashare_countries_raw["Basin_ID"].replace("",np.nan).astype("float")
        self.gridcell_landareashare_countries =  self.gridcell_landareashare_countries_raw.dropna(subset = ['Basin_ID'])
        self.gridcell_landareashare_countries = self.gridcell_landareashare_countries.reset_index().set_index(["lat","lon"])
        
        self.country_ID_name =  "Countries_" + local_country_def["country_ID_name"]
        self.all_countries_in_definition = pd.read_csv(local_country_def["path_to_countrylist"], keep_default_na=False)[local_country_def["country_ID_name"]].to_list()
        self.all_countries_df = pd.DataFrame(index=self.all_countries_in_definition)
        self.all_countries_df.index.name = self.country_ID_name
        self.Mon_List = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        self.initialize_definition_mapping()
        
        return

    def __repr__(self) -> str:
        string = "country aggregator object using the country definition of "+self.country_definition
        return string
    
    def initialize_definition_mapping(self):
        self.definition_mapping = pd.read_excel(r"I:\PhD_10_AWARE_Fut\Data\Input\_Masks and Mapping\country_aggregation\GLAM_ecoinvent310_fullmapping.xlsx",
                                                keep_default_na=False) #discard default na because of potential problem with Namibia (NA)
        if self.country_definition =="ecoinvent310":
            self.definition_mapping = self.definition_mapping.set_index("ecoinvent_shortname")
        elif self.country_definition =="GLAM (territories combined with mainland)":
            self.definition_mapping = self.definition_mapping.set_index("GLAM_country_name")
        elif self.country_definition =="ecoinvent310_with_replacement_from_GLAM":
            self.definition_mapping = self.definition_mapping.set_index("ecoinvent_shortname")
        return
        

    def aggregate_to_countries(self,CFs,weighting,*,print_add_countries=True,store_country_cons_per_basin=False):
        """
        checks the time dimension of the input data and based on that calls the aggregation routine either once or for all items of the CF dictionary.
        There are three possible options:
        - snapshot: CFs and weighting are both a dataframe for one year
        - timeline_oneWeight: CFs is a dictionary of DFs, weighting is one DF
        - timelines: CFs and weighting are both dictionaries of DFs
        Parameters:
        - CFs: either a DF with CFs or a dict of such DFs. The DF indices have to be Basin_IDs
        - weighting: either a DF with weighting values such as water consumption, or a dict of DFs. If both CFs and weighting are dictionaries, their keys have to be identical.
                        the indices have to be lat lon
        """
        self.printaddedcountries = print_add_countries
        #set/reset the stored weighted main_df that can be used to quicker calculate the timeline with one single weight df
        self.stored_weighted_main_df = False
        self.stored_weighting_input = pd.DataFrame()
        self.store_country_cons_per_basin = store_country_cons_per_basin
        self.country_cons_per_basin = pd.DataFrame(columns=list(CFs.keys()))
        #check what type of input (CF and consumption is either one dataframe or a dictionary of DFs)
        dimensions = self.check_dimensions(CFs,weighting)
        #call aggregation
        if dimensions == "snapshot":
            print("calculating aggregations for a CF 'snapshot'")
            aggregated = self.aggregate(CFs,weighting)

        elif dimensions == 'timeline_oneWeight':
            aggregated = dict()
            for year,df in tqdm(CFs.items()):
                aggregated[year] = self.aggregate(df,weighting,keep_weighting = True)

        elif dimensions =="timelines":
            aggregated = dict()
            for year in tqdm(CFs.keys()):
                aggregated[year] = self.aggregate(CFs[year],weighting[year], iteration_nr=year)
    
        print("aggregation completed")
        return aggregated
    
    def check_dimensions(self, CFs, weighting):
        if isinstance(CFs,pd.DataFrame) and isinstance(weighting,pd.DataFrame):
            assert(all([x==y for x,y in zip(CFs.columns, self.Mon_List)]))
            assert(all([x==y for x,y in zip(weighting.columns, self.Mon_List)]))
            assert(list(weighting.index.names) == ["lat","lon"])
            return "snapshot"
        
        elif isinstance(CFs,dict) and isinstance(weighting,pd.DataFrame):
            for x,df in CFs.items():
                assert(isinstance(df,pd.DataFrame))
                assert(all([x==y for x,y in zip(df.columns, self.Mon_List)]))

            assert(weighting.columns == self.Mon_List)
            assert(list(weighting.index.names) == ["lat","lon"])
            return "timeline_oneWeight"
        
        elif isinstance(CFs,dict) and isinstance(weighting,dict):
            for x,df in CFs.items():
                assert(isinstance(df,pd.DataFrame))
                assert(all([x==y for x,y in zip(df.columns, self.Mon_List)]))
            for x,df in weighting.items():
                assert(isinstance(df,pd.DataFrame))
                assert(all([x==y for x,y in zip(df.columns, self.Mon_List)]))
                assert(list(df.index.names) == ["lat","lon"])
            assert(list(weighting.keys()).sort() == list(CFs.keys()).sort())
            return "timelines"

        else:
            raise TypeError("CFs or weighting do not adhere to required format")

               
    def aggregate(self,cf,weights,*, keep_weighting=False,iteration_nr=0):
        """
        prepares a large dataframe with one row for every country-gridcell intersection
        then calls a function that transforms everything into country-aggregated CFs on annual and monthly level
        expects a CF dataframe with month columns (Basin_ID indexed) and a weighting dataframe with month columns (lat lon indexed)
        returns the final aggregated CFs (and more)
        keep_weighting decides whether the main_df after calculating the grid cell country water consumption should be stored and reused 
        """

        
        if keep_weighting == True and isinstance(self.stored_weighted_main_df,pd.DataFrame):
            if self.stored_weighting_input.equals(weights):
                main_df = self.stored_weighted_main_df.copy(deep=True)
            else:
                raise ValueError("Tried to use previous main_df and weights, but apparently the weights are not equal to the new input")

        elif self.stored_weighted_main_df == False and any([keep_weighting==True,keep_weighting==False]):
            #create fresh Dataframe of the landareashares, only with gridcells that are covered by basins
            main_df = self.gridcell_landareashare_countries.copy(deep=True)

            #link consumption and gridcells
            main_df = main_df.join(weights[self.Mon_List])
            # older and MUCH slower: main_df.loc[main_df.index.intersection(weights.index),self.Mon_List] = weights[self.Mon_List]

            #calculate country consumption of grid cell, SET NEGATIVE VALUES TO ZERO
            gridcell_cons_of_countries_cols = [f"CountryGridCons_{month}" for month in self.Mon_List]
            main_df[gridcell_cons_of_countries_cols] = main_df[self.Mon_List].multiply(main_df["CountryAreaShare"], axis=0).clip(lower=0)
            
            # calculate consumption per basin and country
            if self.store_country_cons_per_basin:
                self.country_cons_per_basin[iteration_nr] = self.return_basin_cons_for_saving(main_df,gridcell_cons_of_countries_cols)

            if keep_weighting ==True:
                self.stored_weighted_main_df = main_df.copy(deep=True)
                self.stored_weighting_input = weights
        else:
            raise TypeError("Problem with code, should not arrive at this line")

        # link CFs to gridcells
        main_df = main_df.reset_index().set_index("Basin_ID")
        gridcell_cfs_cols = [f"CF_{month}" for month in self.Mon_List]
        main_df[gridcell_cfs_cols] = cf[self.Mon_List]

        #do country aggregation
        aggregated_CFs = self.return_aggregated_country_cfs(main_df, self.country_ID_name, gridcell_cons_of_countries_cols,gridcell_cfs_cols)

        return aggregated_CFs

    def return_basin_cons_for_saving(self, main_df,gridcell_cons_of_countries_cols):
        country_cons_per_basin = main_df.groupby([self.country_ID_name,"Basin_ID"]).sum()[gridcell_cons_of_countries_cols]
        country_cons_per_basin.columns = self.Mon_List
        country_cons_per_basin["annual"] = country_cons_per_basin.sum(axis=1)
        return country_cons_per_basin.stack()

    def return_aggregated_country_cfs(self, main_df, country_codes, country_gridcons_cols, gridcell_cfs_cols):
        '''
        expects
        - df with country shares etc.
        - country_codes: the column name of the country IDs
        - country_gridcons_cols: the column names of the gridcell-specific consumption per country and month, something like ["CountryGridCons_Jan",..]
        - gridcell_cfs_cols: the column names of the gridcell-specific CF values something like ["CF_Jan",..]
        '''
        #***monthly aggregations***
        #**************************
        #calculate full monthly consumption per country
        main_df.reset_index(inplace=True)
        country_cons_months = ["Country_Cons_"+month for month in self.Mon_List]
        country_res = pd.DataFrame(columns = country_cons_months) #country_res is for "country resolution df"

        for month,month_cons in zip(country_cons_months,country_gridcons_cols):
            country_res[month] = main_df.loc[main_df['CF_Jan'].notna(),[country_codes,month_cons]].groupby(by=country_codes)[month_cons].sum()
        removed_but_weird = main_df.loc[(main_df['CF_Jan'].isna())&(main_df[gridcell_cfs_cols].sum(axis=1)>0),"Basin_ID"].astype(int).unique()
        print(">>>>>>>>>> removed weird basins where JanuaryCF is nan but others not", removed_but_weird)
        #calculate country-share-consumption*CF for every grid cell
        gridcell_cons_x_CF_cols = ["Cons_x_CF_"+month for month in self.Mon_List]
        main_df[gridcell_cons_x_CF_cols] = main_df[country_gridcons_cols].multiply(main_df[gridcell_cfs_cols].to_numpy(),
                                                                                   axis=0) # conversion to numpy is OK bc indices are the same (same main dataframe)

        #group country sum of weighted CFs
        countr_consXcf_cols = [f"Country_Cons_x_CF_{m}" for m in self.Mon_List]
        country_res[countr_consXcf_cols] = main_df.groupby(by=country_codes)[gridcell_cons_x_CF_cols].sum(min_count=1) #min_count makes sure results are NA if no CFxcons value available

        #divide weighted CF sum by consumption total => voila!! aggregated CF!
        country_aggr_CF_cols = ["countryCF_"+month for month in self.Mon_List]
        country_res[country_aggr_CF_cols] = country_res[countr_consXcf_cols].div(country_res[country_cons_months].to_numpy(),
                                                                                 axis=0) # conversion to numpy is OK bc indices are the same (same main dataframe)
        #country_res[country_aggr_CF_cols] = country_res[country_aggr_CF_cols].mask(country_res[countr_consXcf_cols]==0, main_df.groupby(by=country_codes))
        
        #***annual aggregations***
        #**************************
        country_res["Country_Cons_x_CF_annual"] = country_res[countr_consXcf_cols].sum(axis=1)
        country_res["Country_Cons_annual"] = country_res[country_cons_months].sum(axis=1)
        country_res["countryCF_annual"] = country_res["Country_Cons_x_CF_annual"]/country_res["Country_Cons_annual"]
        
        #clean countries with zero consumption or nodata to NaN
        country_res.replace([np.inf, -np.inf],np.nan, inplace=True)

        #if there were countries without any underlying basin, they are not in the country_res df. To ensure intercompatibility, these are added now
        country_res = self.add_missing_countries(country_res)
        return country_res
    

    def add_missing_countries(self, country_CFs):
        missing_countries = [x for x in self.all_countries_in_definition if x not in country_CFs.index]
        # Create a DataFrame with all countries in the definition
        country_CFs = country_CFs.reindex(self.all_countries_df.index) # self.all_countries_df is an empty df with self.all_countries_in_definition as index values

        if self.printaddedcountries:
            print("added missing countries",missing_countries)
        return country_CFs
    
    def add_full_country_mapping(self,country_cfs):
        assert(isinstance(country_cfs,pd.DataFrame))
        #get country ID column of CFs
        assert(self.country_ID_name == country_cfs.index.name)
        print("******\nnote that the mapping is based on for which countries political boundary differences made a difference in CFs in AWARE2.0.\n \
              some countries might have the same boundaries in the different methods but are not separated in this mapping method.\n \
              The issue of Namibia shortname NA has been corrected")
        return_df = self.definition_mapping.copy(deep=True)
        return_df.loc[country_cfs.index.intersection(return_df.index), country_cfs.columns] = country_cfs
        return return_df
    
    def return_timelines_as_wide_df(self, aggregated):
        """
        transforms the dictionary (keys are the years, values are the dataframes with the aggregations)
        into a large dataframe that has the countries and variables (months, annual values, consumption, CFs,...) as index and the years as columns
        """
        all_aggregated_keys = [x for x in aggregated.keys()]
        all_country_runs = pd.concat([aggregated[x].stack() for x in all_aggregated_keys], axis = 1)
        all_country_runs.index.names = ["Countries_shortname","variable"]
        return all_country_runs
    
    def return_country_name(self,shortnames):
        if self.country_definition == "ecoinvent310":
            return [self.definition_mapping.loc[x,"ecoinvent_country_name"] for x in shortnames]
        elif self.country_definition =="GLAM (territories combined with mainland)":
            return [self.definition_mapping.loc[x,"GLAM_country_name"] for x in shortnames]
        
    def return_covered_basins_for_country(self, Country):
        country_gridcells = self.gridcell_landareashare_countries.loc[self.gridcell_landareashare_countries["Countries_shortname"]==Country]
        return country_gridcells["Basin_ID"].unique().astype(int)
    
    def get_basinxgeometry_annual_CFs(self, CFs, consumption_weights, *,iteration_for_weights = 0):
        """ Calculates seasonally weighted annual CFs for each intersection between geometry and basins.
        
        PROBABLY A DEAD FUNCTION
        """
        if consumption_weights == "own":
            weights = self.country_cons_per_basin[iteration_for_weights]
            print("using weights from list position",iteration_for_weights)
        elif isinstance(consumption_weights, pd.DataFrame):
            assert consumption_weights.index.names == [self.country_ID_name,"Basin_ID"]
            weights = consumption_weights
        else:
            raise ValueError("consumption weight does not have the correct format (dataframe or string 'own')")
        
        

