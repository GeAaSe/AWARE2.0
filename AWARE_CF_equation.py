"""Calculate AWARE2.0 characterization factors.

The :class:`AWARECF_equation` class stores the hydrological inputs and
intermediate results used to calculate AWARE characterization factors. The
module also contains the basin-subdivision algorithm used for subdivided
river basins.
"""

import os
import pickle
from collections.abc import Mapping, Sequence
from typing import Any, Hashable
import pandas as pd
import AWARE_data as AD


class AWARE_CF_equation:
    """Store inputs and calculate AWARE characterization factors.

    Hydrological data must be basin-scale data with monthly columns. The
    ``ActAvail`` input may contain several periods; the same periods are used
    for the resulting AMDs and characterization factors.
    """

    def __init__(
        self,
        ActAvail: Any,
        EWR: Any,
        area: pd.Series,
        HWC: pd.DataFrame,
        subbasin_info_path: str,
        AMDwa_period: Hashable,
        *,
        external_AMDwa: float | None = None,
        period_years: Mapping[Hashable, Sequence[int]] | None = None,
        print_messages: bool = True,
    ) -> None:
        """Initialize an AWARE calculation.

        Parameters
        ----------
        ActAvail : AWARE_data_entry or pandas.DataFrame
            Actual availability by basin and period.
        EWR : AWARE_data_entry or pandas.DataFrame
            Environmental water requirements by basin and month.
        area : pandas.Series
            Basin areas in square metres or square kilometres.
        HWC : pandas.DataFrame
            Human water consumption used to calculate the world-average AMD.
            Columns must either follow the ``BasinCons_<month>_m3`` naming
            convention or consist of exactly 12 monthly columns.
        subbasin_info_path : path-like
            Excel file containing the basin connectivity information.
        AMDwa_period : hashable
            Period used to calculate the world-average AMD.
        external_AMDwa : float, optional
            Precomputed world-average AMD.
        period_years : dict, optional
            Mapping of periods to the years represented by each period.
        print_messages : bool, default=True
            Whether progress messages should be printed.
        """

        self.print_messages = print_messages
        self.Actual_Availability = self.check_whether_AWARE_data_entry_object(
            ActAvail, "ActAvail"
        )
        self.EWR = self.check_whether_AWARE_data_entry_object(EWR, "EWR")
        assert isinstance(area, pd.Series)
        if area.max() < (50000 * 50000):
            self.area = area * 1000000
        else:
            self.area = area
        if max(self.area) > 1.5e12:
            raise ValueError("Unit of areas might not be correct")
        assert isinstance(HWC, pd.DataFrame)
        self.HWC = HWC
        self.AMDwa_period = AMDwa_period
        self.subbasin_info = pd.read_excel(subbasin_info_path, index_col="Basin_ID")
        self.periods = [x for x in self.Actual_Availability.data.keys() if x != "EWR_period"]
        self.AMDs: dict[Hashable, Any] = {x: None for x in self.periods}
        self.AMDs_local: dict[Hashable, Any] = {x: None for x in self.periods}
        self.AMDwa: float | None = external_AMDwa
        self.CFs: dict[Hashable, Any] = {x: None for x in self.periods}
        self.CFs_noCO: dict[Hashable, Any] = {x: None for x in self.periods}
        self.period_years = {} if period_years is None else period_years
        if self.print_messages:
            print("created AWARE_equation object")
    
    def check_whether_AWARE_data_entry_object(
        self, data: Any, variable: str
    ) -> Any:
        """Return ``data`` as an :class:`AWARE_data_entry` instance."""
        if isinstance(data, AD.AWARE_data_entry):
            return data
        elif isinstance(data, pd.DataFrame):
            if self.print_messages:
                print("transformed input df to AWARE_data_entry")
            if variable == "EWR":
                return AD.AWARE_data_entry(
                    data=data, variable=variable, times="unknown", unit="unknown"
                )
            return AD.AWARE_data_entry(
                data={0: data}, variable=variable, times="unknown", unit="unknown"
            )
        else:
            raise TypeError("input data is not an accepted type")

    def __repr__(self) -> str:
        amdwa = getattr(self, "AMDwa", None)
        path = getattr(self, "Path", None)
        save_status = (
            f"\nlast saved at (possibly a previous version):\n{path}"
            if path is not None
            else "\nnot saved yet"
        )
        return f"AWARE-equation object containing\nAMDwa: {amdwa}{save_status}"

    def return_subfolder_path(self, path: str) -> str:
        """Return the companion ``_parts`` directory, creating it if needed."""
        if path[-7:] != "_parts/":
            subfolder = path + "_parts/"
        else:
            subfolder = path
        if not os.path.exists(subfolder) and subfolder[-7:] == "_parts/":
            try:
                os.makedirs(subfolder)
            except OSError:
                print(f"Creation of directory {subfolder} failed. Continue.")
        return subfolder

    def save(
        self, path: str, *, dump_separately: bool = False, entire_DB: bool = True
    ) -> None:
        """Serialize the calculation object and optionally its large data fields."""
        if entire_DB:
            self.Path = path
            print("saving...")
            with open(path, "wb") as file:
                pickle.dump(self, file)

        if dump_separately:
            subfolder = self.return_subfolder_path(path)
            self.dumped_paths = {}
            separate_data_items = zip(
                [self.CFs, self.AMDs, self.AMDs_local, self.EWR, self.HWC,
                 self.Actual_Availability],
                ["CFs", "AMDs", "AMDs_local", "EWR", "HWC", "ActAvail"],
            )
            for separate_data, variable in separate_data_items:
                filepath = os.path.join(subfolder, f"separate_{variable}")
                self.dumped_paths[variable] = filepath
                print(f"saving...{variable}", end=" ")
                with open(filepath, "wb") as file:
                    pickle.dump(
                        {
                        "data":separate_data,
                        "longterm_average_periods":self.period_years,
                        "AMDwa":self.AMDwa,
                        "AMDwa_period":self.AMDwa_period,
                        "periods": self.periods,
                        "main_path": subfolder.replace("_parts/","") #if this function was called from strip and save, remove the prefix
                        },
                                 file)

            if entire_DB is False:
                self.Path = path
                print("saving...")
                with open(path, "wb") as file:
                    pickle.dump(self, file)
                self.save(path)

        print("done")
        return
    
    def load_externally_saved(self, *, to_load: Sequence[str] | None = None) -> None:
        """Load selected data fields previously written by :meth:`save`."""
        if to_load is None:
            to_load = ["CFs", "AMDs", "AMDs_local", "EWR", "HWC", "ActAvail"]
        attributes = {
            "CFs": "CFs",
            "AMDs": "AMDs",
            "AMDs_local": "AMDs_local",
            "EWR": "EWR",
            "HWC": "HWC",
            "ActAvail": "Actual_Availability",
        }
        for variable, attribute in attributes.items():
            if (
                variable in to_load
                and variable in self.dumped_paths
                and isinstance(getattr(self, attribute), str)
            ):
                print(f"loading {variable} ", end="")
                setattr(self, attribute, self.load_pickled_variables(variable))

    def load_pickled_variables(self, var: str) -> Any:
        """Load a separately pickled variable and validate its main path."""
        with open(self.dumped_paths[var], "rb") as file:
            loaded = pickle.load(file)
        if loaded["main_path"]!=self.Path:
            raise KeyError("variable and main DB specify different main path")
        else:
            return loaded["data"]

    def calculate_AMD(
        self, *, subbasin_approach: bool = True, prescribed_AMDs_local: Any = None
    ) -> None:
        """Calculate local and, optionally, basin-subdivision AMDs."""
        Basin_Dict = get_basin_dictionary(self.subbasin_info)
        Area_Dict = get_area_dictionary(self.area, Basin_Dict, self.subbasin_info)
        # If prescribed_AMDs_local is given, use it
        if prescribed_AMDs_local is not None:
            self.AMDs_local = prescribed_AMDs_local
        else:
            for p in self.periods:
                # calculate local AMDs
                AMD = self.Actual_Availability.data[p]-self.EWR.data
                AMD = AMD.div(self.area, axis=0)
                AMD.dropna(inplace=True)
                AMD.sort_index(inplace=True)
                self.AMDs_local[p] = AMD.astype('float64')
        
        # Continue with subbasin approach
        for p in self.periods:
            #HANDLE BASIN SUBDIVISION
            if subbasin_approach:
                self.AMDs[p], self.area_from_subbasin_approach, self.actAvail_minus_EWR_from_subbasin_approach = handleSubdivisions(AMD_areas_m2=self.area, ActAvail_m3=self.Actual_Availability.data[p],
                                   EWR_m3=self.EWR.data, local_AMDs_m=self.AMDs_local[p],
                                   subbasin_info=self.subbasin_info,Basin_Dict=Basin_Dict, Area_Dict =Area_Dict,printmessages=self.print_messages)
            else:
                self.AMDs[p] = self.AMDs_local[p].astype('float64')

        return

    def calculate_AMDwa(self, *, AMDwa_period: Hashable = 0) -> None:
        """Calculate the world-average AMD for the selected period."""
        if self.AMDwa is not None:
            return
        else:
            #Compute World Total consumption
            Consum = self.HWC.loc[self.AMDs[AMDwa_period].index]
            Mon_cols = self.AMDs[AMDwa_period].columns # this will be a standard Mon_List
            if "BasinCons_Jan_m3" in Consum.columns: # means these columns are the right ones and the other ones might contain negative consumption values
                Consum = Consum[["BasinCons_"+x+"_m3" for x in Mon_cols]]
                Consum.columns = Mon_cols
                Cons_Sum = Consum[Mon_cols].sum().sum()
                assert("BasinCons_Jan_m3" in self.HWC.columns) # make sure we did not overwrite the original HWC df
            elif len(Consum.columns) ==12:
                Cons_Sum = Consum[Mon_cols].sum().sum()
            else:
                raise KeyError("Don't know which columns to take from HWC for AMDwa calculation")
            # Compute the sum of consumption x AMD products.
            Products = (Consum * self.AMDs[AMDwa_period]).sum().sum()
            #Divide Products by Sum
            self.AMDwa = Products / Cons_Sum
            return

    def calculate_CFs(self, *, print_messages: bool = True) -> None:
        """Calculate AMDs, the world-average AMD, and both CF variants."""
        self.print_messages=print_messages
        self.calculate_AMD()
        self.calculate_AMDwa(AMDwa_period=self.AMDwa_period)
        self.calculateCFs_noCO()
        self.calculate_CFs_withCO()

    def calculateCFs_noCO(self) -> pd.DataFrame:
        """Calculate characterization factors before applying the cutoff."""
        if self.AMDwa is None:
            raise RuntimeError("AMDwa must be calculated before calculating CFs")
        AMDw_a = self.AMDwa
        for period in self.periods:
            cols = self.AMDs[period].columns
            DF=self.AMDs[period].astype('float64')
            DF.where(DF[cols]>0,other=-AMDw_a,inplace=True) #filter out negative AMDis and 0 (if applicable)
            DF[cols] =  AMDw_a/DF[cols]        #calculate AMDwa/AMDi
            DF.sort_index(inplace=True)
            self.CFs_noCO[period] = DF
        return DF
    
    def calculate_CFs_withCO(self) -> None:
        """Apply the AWARE cutoff and calculate annual ranking columns."""
        for period in self.periods:
            cols = self.CFs_noCO[period].columns
            #First: Cut-off at 100, every value bigger will be 100
            DF=self.CFs_noCO[period].copy(deep=True)
            DF.where(DF[cols]<=100,other=100,inplace=True)
            #Second: Cut-off for values smaller or equal 0, they will be 100
            DF.where(DF[cols]>=0,other=100,inplace=True)
            #Third: Cut-off for values smaller than 0.1, they will be 0.1
            DF.where(DF[cols]>=0.1,other=0.1,inplace=True)
            DF["Annual_arithm_average"]=DF[cols].mean(axis=1)
            DF["Rank_based_on_ann_arithm_average"]=DF["Annual_arithm_average"].rank(axis=0)
            DF.sort_index(inplace=True)
            DF = DF.astype('float64')
            self.CFs[period] = DF
            self.CFs_noCO[period] = self.CFs_noCO[period].astype('float64')
        return



    def drop_all_nas(self, df):
        """function is required to safely drop all nas even if they are affected by the na bug of pandas"""
        np_df = df.to_numpy()
        newdf = pd.DataFrame(index=df.index, columns=df.columns, data=np_df)
        newdf = newdf.dropna().astype("float64")
        return newdf

    def get_annual_weighted_CFs(self, CFs, columns, weighting):
        """
        does annual basin aggregation by water consumption.
        If water consumption = 0, CF is arithmetic average
        """
        weightcols = {f"BasinCons_{x}_m3":x for x in columns}
        if list(weightcols.keys())[0] in weighting.columns: #if month names are the atotuse names
            common_index = CFs.index.intersection(weighting.index)
            LT_weights = weighting.loc[common_index, list(weightcols.keys())]
            LT_weights.columns = list(weightcols.values())
        else:
            LT_cons_NAsdropped = self.drop_all_nas(weighting)
            idx = LT_cons_NAsdropped.index.intersection(CFs.index)
            LT_weights = LT_cons_NAsdropped.loc[idx, columns]
        LT_weighted_months = CFs[columns]*LT_weights
        annual_CFs = LT_weighted_months.sum(axis=1, min_count=1).dropna()
        annual_cons = LT_weights.sum(axis=1)
        annual_CFs.loc[annual_cons!=0] = annual_CFs/annual_cons
        annual_CFs.loc[annual_cons==0] = CFs[columns].mean(axis=1)
        annual_CFs.name = "ann"
        return annual_CFs

################################################################
# Code for handling the AMDs in subdivided basins in AWARE2.0
################################################################

        
def handleSubdivisions(
    AMD_areas_m2: pd.Series,
    ActAvail_m3: pd.DataFrame,
    EWR_m3: pd.DataFrame,
    local_AMDs_m: pd.DataFrame,
    subbasin_info: pd.DataFrame,
    Basin_Dict: Mapping[Any, Any],
    Area_Dict: dict[Any, dict[str, Any]],
    printmessages: bool,
) -> tuple[Any, Any, Any]:
    """Calculate AMDs using the iterative basin-subdivision approach.
    - AMD_areas_m2: areas of subbasins
    - ActAvail_m3: The outflow of the subbasins
    - EWR_m3: THe EWR at the outflow of the subbasins
    - local_AMDs_m: the AMDs calculated without respecting subbasin links
    - subbasin_info: the dataframe on next downstream subbasin
    - Basin_Dict: dictionary with subbasins as keys and a list of their downstream subbasins as values
    - Area_Dict: dictionary that for every subbasin shows the associated area sums (of itself and downstream)
    - printmessages: whether to print messages
    """
    if printmessages:print("doing basin subdivision")
    Mon_List = local_AMDs_m.columns.to_list()

    #first run of basin subdivision approach 2
    assert(len(ActAvail_m3.columns) == len(EWR_m3.columns))
    ActDis_minus_EWR = ActAvail_m3-EWR_m3
    AMDs_Iteration_before = getAMDs_with_area_extension_from_lowest(ActDis_minus_EWR,AMD_areas_m2,subbasin_info,Area_Dict) #calculate all AMDs with the area extension method. Everything coming afterwards is for the exception for low local AMDs
    areas_used_for_subbasin_approach = None
    ActDis_minus_EWR_final = None
    AMDs_Iteration_after = None
    #iterations
    for iteration in range(8):
        if printmessages: print("start iteration", iteration)
        # detect which basins have lower local AMD than the area extension AMD
        Area_Dict,toHighcount,pm = checkForTohHighAMDs_efficient(Area_Dict,iteration,local_AMDs_m, AMDs_Iteration_before) # more efficient version of the function checkForTohHighAMDs
        # Area_Dict,toHighcount,pm = checkForTohHighAMDs(Area_Dict,iteration,local_AMDs_m, AMDs_Iteration_before) #check for which ones (basin, month) the area enxtension should not be used...
        if printmessages: print(pm)
        if toHighcount>0:
            shortnd_chains2,mostdownstr2 = newMostDownstreamBasins(Basin_Dict,Area_Dict,iteration,subbasin_info,Mon_List) #...check how upstream basins are affected by that
            if iteration>0:
                shortnd_chains2,mostdownstr2 = merge_previous_basins(Area_Dict,shortnd_chains2,shortened_chains_before,
                                                                     mostdownstr2,mostdownstream_before,iteration,Mon_List) #only further shorten the chains of basins which are now still affected
            Area_Dict = provideAggregatedArea(Area_Dict,AMD_areas_m2,shortnd_chains2,iteration,Mon_List)  # calculate the required upstream area for recalculated area extensions
            
            AMDs_Iteration_after, areas_used_for_subbasin_approach, ActDis_minus_EWR_final = getIteratedAMDs(ActDis_minus_EWR,subbasin_info.index,AMD_areas_m2,Area_Dict,mostdownstr2,iteration,Mon_List) # do the recalculation of area extension using now most downstream basins
            if printmessages: (print(countAffectedBasins(shortnd_chains2,Basin_Dict)[1]))
            AMDs_Iteration_before = AMDs_Iteration_after
            shortened_chains_before, mostdownstream_before = shortnd_chains2,mostdownstr2
        else:
            checkEqualityForNonSubdivisions(local_AMDs_m,AMDs_Iteration_after,Mon_List)

    return AMDs_Iteration_after, areas_used_for_subbasin_approach, ActDis_minus_EWR_final

def get_basin_dictionary(sub_bas_inf: pd.DataFrame) -> dict[Any, list[Any]]:
    """Return each subbasin and its downstream basin chain."""
    basin_dictionary = {}
    for basin in sub_bas_inf.index:
        basin_dictionary[basin] = [basin]
        downstream = basin
        while sub_bas_inf.at[downstream, "Flows_to"] != -11:
            downstream = sub_bas_inf.at[downstream, "Flows_to"]
            basin_dictionary[basin].append(downstream)
    return basin_dictionary

def get_area_dictionary(
    area_m2: pd.Series,
    bas_dict: Mapping[Any, Sequence[Any]],
    bas_info: pd.DataFrame,
) -> dict[Any, dict[str, Any]]:
    """
    Return area totals for each subbasin and its downstream chain.
    provides a dictionary that for every subbasin shows the associated area sums (of itself and downstream) à la
    55118: {'AreaList': [425558.622802734 (own area),393197.448730469 (next downstream area),147622.799316406,101538.041503906],
            'AreaSum': 1067916.912353515 (all areas together),
            'AreaOutflowBasin': 101538.041503906}
    takes as input:
    - area_m2: the area of basins
    - bas_dict: a dictionary with subbasins as keys and a list of their downstream subbasins as values
    - bas_info: the dataframe on basin interconnections
    """
    AreaDictionary=dict()
    for basin in bas_dict.keys():
        AreaList=[area_m2.loc[x] for x in bas_dict[basin]]
        area_affected=sum(AreaList)
        AreaOutflow=area_m2.loc[bas_info.loc[basin,"BASIN0_ID"]]
        AreaDictionary[basin]={"AreaList":AreaList,
                            "AreaSum":area_affected,
                            "AreaOutflowBasin":AreaOutflow
                            }
    return AreaDictionary

def getAMDs_with_area_extension_from_lowest(
    ActDis_minus_EWR: pd.DataFrame,
    areas_m2: pd.Series,
    bas_info: pd.DataFrame,
    area_dict: dict[Any, dict[str, Any]],
) -> pd.DataFrame:
    """Calculate area-extended AMDs for all subbasins."""
    availab_remain=pd.DataFrame()
    # List of area values for all basins.
    AllBasArea=areas_m2.copy(deep=True)
    #replace local area values by sums of affected areas (own and downstream area)
    for basin in bas_info.index:
        AllBasArea.loc[basin]=area_dict[basin]["AreaSum"]
    #change EWR and Availability so it is always the final outflow basin's one
    ActDis_minus_EWR_final = ActDis_minus_EWR.copy(deep=True)
    for basin in bas_info.index:
        outflow_basin = bas_info.at[basin,"BASIN0_ID"]
        for month in ActDis_minus_EWR.columns:
            ActDis_minus_EWR_final.loc[basin,month] = ActDis_minus_EWR.loc[outflow_basin,month]
    #calculate AMDs for all basins
    for month in ActDis_minus_EWR.columns:
        availab_remain[month] = ActDis_minus_EWR_final[month]/AllBasArea
    availab_remain=availab_remain.dropna()
    return availab_remain

def checkForTohHighAMDs_efficient(
    Area_Dict: dict[Any, dict[str, Any]],
    iter_number: int,
    loc_avail: pd.DataFrame,
    iterated_avail: pd.DataFrame,
) -> tuple[dict[Any, dict[str, Any]], int, str]:
    """Find basin-months where local AMD is below the iterated AMD."""

    counter=0
    iter_key = f"{iter_number}_IterationLocalAMDIsSmallerThanAppr2"
    months = loc_avail.columns
    for basin, basin_data in Area_Dict.items():
        basin_data[iter_key]=set()
        loc_basin = loc_avail.loc[basin]
        iter_basin = iterated_avail.loc[basin]
        for month in months:
            if ten_sig_figs_efficient(loc_basin[month]) < ten_sig_figs_efficient(iter_basin[month]):
                basin_data[iter_key].add(month)
                counter+=1
        #now we know for which month there is an underestimation of CFs
    if iter_number == 7 and counter > 0:
        raise RecursionError("7th iteration should not be needed") 
    return Area_Dict,counter,f"{counter} instances of AMD too high compared to local availability"

def ten_sig_figs_efficient(number: float) -> float:
    """Round a number to ten significant figures for stable comparisons."""
    return float(f"{number:.10g}")

def newMostDownstreamBasins(
    basin_dict: dict[Any, list[Any]],
    area_dict: dict[Any, dict[str, Any]],
    iter_number: int,
    bas_info: pd.DataFrame,
    Mon_List: Sequence[Hashable],
) -> tuple[dict[Any, Any], dict[Any, Any]]:
    """Find the most downstream controlling basin for each month."""
    ShortenedChainsDict={} #collects all complete chains of downstream subbasins, then the chains are update to only lead up to the most downstream basin where AMD needs to be local
    MostDownstreamBasin={} # first only has all most outflows to sea as values, then is updated with the most downstream basin where AMD needs to be local
    for basinID, chain in basin_dict.items():
        #gets the chains of basins and prepares a new column in the area dictionary which shows all downstream basins and the respective month where the AMD needs to be adjusted 
        area_dict[basinID]["downstreamHighLocalAMDs"+str(iter_number)]=MonthBasinTouples(chain, area_dict, str(iter_number))
        #now for every basin we have a list of tuples that indicates in which month which downstream basin is affected
        monthly_chain_long=[tuple([mon,chain]) for mon in Mon_List]
        ShortenedChainsDict.update([(basinID,dict(monthly_chain_long))]) #the shortenedChainsDict step per step has all complete basin chains in it now, a copy for every month
        OutflowToSea=[tuple([mon,bas_info.loc[basinID,"BASIN0_ID"]]) for mon in Mon_List] #this list contains the outflow to sea for the current basin for every month
        MostDownstreamBasin.update([(basinID, dict(OutflowToSea))]) #the MostDownstreamBasin step per step has all outflows to sea in it for every basin
        monthly_final_basins=getMonthlyAffectedDownstreamList(area_dict,basinID,str(iter_number),Mon_List)
        #now we have a list for every month for that usptream basin, which shows which downstream basins are affected
        entire_chain=list(enumerate(chain))
        for month, monthlylist in monthly_final_basins.items():
            if len(monthlylist)>1:
                idx = getHighestIndexedBasin(monthlylist,entire_chain)
                mostdownstream = chain[idx]
            elif len(monthlylist)==1: mostdownstream=monthlylist[0]
            elif len(monthlylist)==0: mostdownstream=bas_info.at[basinID,"BASIN0_ID"]
            #now we know that mostdownstream is the basin which is the furthest downstream and has the low local water availability
            #so we cut the entire chain after mostdownstream
            short_chain=splitChainAfterBasin(chain,mostdownstream)
            ShortenedChainsDict[basinID].update([(month, short_chain)])
            MostDownstreamBasin[basinID].update([(month, mostdownstream)])
    return ShortenedChainsDict,MostDownstreamBasin

def MonthBasinTouples(chain, area_dict, Pref):
    """
    for all basins in a given basin chain it is checked whether these basins have a month where their local AMD is smaller than the AMD calculated before
    the month and the basin are added to a list of touples
    """
    ToupleList=[]
    iter_key = Pref+"_IterationLocalAMDIsSmallerThanAppr2"
    for listel in chain:
        for affected_month in area_dict[listel][iter_key]:
            ToupleList.append((affected_month,listel))
    return ToupleList

def getMonthlyAffectedDownstreamList(
    AD: dict[Any, dict[str, Any]],
    bas: Any,
    num: str,
    Mon_List: Sequence[Hashable],
) -> dict[Hashable, list[Any]]:
    """Return downstream basins affecting each month for one basin."""
    Diction={}
    for month in Mon_List:
        Diction[month]=[]
        for pair in AD[bas]["downstreamHighLocalAMDs"+num]:
            if month in pair: Diction[month].append(pair[1])
    return Diction

def getHighestIndexedBasin(
    monthlylist: Sequence[Any], entire_chain: Sequence[tuple[int, Any]]
) -> int:
    index=0
    for downbas in monthlylist:
        for item in entire_chain:
            if item[1]==downbas and item[0]>index: #item is a tuple of (index, basinID)
                index=item[0]
    return index

def splitChainAfterBasin(test_list: Sequence[Any], lastbas: Any) -> list[Any]:
    size=len(test_list)
    idx_list = [idx + 1 for idx, val in enumerate(test_list) if val == lastbas] # a list showing the indexes before which to cut
    res = [test_list[i: j] for i, j in
        zip([0] + idx_list, idx_list + 
        ([size] if idx_list[-1] != size else []))]
    return list(res[0])

def provideAggregatedArea(AD,area,chain_dict,iter_number, months):
    """
    provides for each basin the areas of itself and downstream up to the most downstream basin where AMD needs to be local
    """
    colname=f"Iteration_{iter_number}"
    for basinID,entry in AD.items():
        entry[colname]={}
        downstream_basins = chain_dict[basinID]
        for month in months:
            AreaList=[area.loc[x] for x in downstream_basins[month]] #every month has its own chain dict!
            area_affected=sum(AreaList)
            entry[colname].update([(month,{"AreaList":AreaList,"AreaSum":area_affected})])
    return AD

def getIteratedAMDs(
    ActDis_minus_EWR: pd.DataFrame,
    bas_info: Any,
    areas_m2: pd.Series,
    area_dict: dict[Any, dict[str, Any]],
    mostdownstream: dict[Any, dict[Hashable, Any]],
    iter_number: int,
    dis_columns: Sequence[Hashable],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calculate AMDs using iteration-specific downstream areas."""
    #DF of area values for all basins and months
    VariableBasinAreas = replaceAreaValuesForAMDCalc(areas_m2,bas_info,
                                                            area_dict,f"Iteration_{iter_number}",dis_columns)
    #change EWR and Availability so it is the newly specified lowest basin
    ActDis_minus_EWR_final = ActDis_minus_EWR.copy(deep=True)
    for basin in bas_info:
        mostdownstream_basin = mostdownstream[basin]
        for month in dis_columns:
            ActDis_minus_EWR_final.at[basin,month] = ActDis_minus_EWR.at[mostdownstream_basin[month],month]

    #calculate AMDs for all basins
    availab_remain = ActDis_minus_EWR_final/VariableBasinAreas
    return availab_remain.dropna(), VariableBasinAreas, ActDis_minus_EWR_final

def replaceAreaValuesForAMDCalc(
    areas: pd.Series,
    subbas_idx: Sequence[Any],
    AD: dict[Any, dict[str, Any]],
    iteration: str,
    months: Sequence[Hashable],
) -> pd.DataFrame:
    """Return monthly basin areas, retaining original areas where unchanged. (retains the areas for non-subdivided basins!)"""
    base = pd.concat([areas] * len(months), axis=1)
    base.columns = months
    for basin in subbas_idx:  # replace area values of subbasins
        area_dict_of_basin = AD[basin][iteration]
        for month in months:
            base.at[basin,month] = area_dict_of_basin[month]["AreaSum"]
    return base

def countAffectedBasins(
    ChainDict: Mapping[Any, Mapping[Hashable, Any]],
    RootDict: Mapping[Any, Any],
) -> tuple[int, str]:
    countAffected= 0
    for basin,MonListe in ChainDict.items():
        Affected=0
        for Month in MonListe.values():
            if Month != RootDict[basin]: Affected=1
        if Affected == 1: countAffected +=1       
    return countAffected, f"Basins affected out of {len(ChainDict.values())} : {countAffected}"

def checkEqualityForNonSubdivisions(
    local: pd.DataFrame, new: pd.DataFrame, cols: Sequence[Hashable]
) -> None:
    for month in cols:
        if ten_sig_figs_efficient(local.at[27939,month]) != ten_sig_figs_efficient(new.at[27939,month]):
            raise ValueError("Somehow the AMD of non-subdivided basins might have been changed by the code")
        if ten_sig_figs_efficient(local.at[33683,month]) != ten_sig_figs_efficient(new.at[33683,month]):
            raise ValueError("Somehow the AMD of non-subdivided basins might have been changed by the code")
    return

def merge_previous_basins(
    area_dict: dict[Any, dict[str, Any]],
    newChains: dict[Any, dict[Hashable, Sequence[Any]]],
    oldChains: dict[Any, dict[Hashable, Sequence[Any]]],
    newEnd: dict[Any, dict[Hashable, Any]],
    oldEnd: dict[Any, dict[Hashable, Any]],
    Iteration: int,
    Mon_List: Sequence[Hashable],
) -> tuple[dict[Any, Any], dict[Any, Any]]:
    """Update previously shortened chains still affected by this iteration.
    Basically uses the old shortened chains and replaces chains where in the new iteration there still is local AMD smaller than area extension AMD."""
    iteration_marker = f"{Iteration}_IterationLocalAMDIsSmallerThanAppr2"
    for basin,newchain in newChains.items():
        area_dict_of_basin = area_dict[basin][iteration_marker]
        for Month in Mon_List:
            if Month in area_dict_of_basin:
                oldChains[basin][Month]=newchain[Month] #only for months which in the new iteration are affected, values are replaced
                oldEnd[basin][Month]=newEnd[basin][Month]
                #print("for this basin the shortened chain was inserted in the old shortened chain:",basin)
    return oldChains, oldEnd
