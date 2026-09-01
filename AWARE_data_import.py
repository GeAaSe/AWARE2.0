import xarray as xr
import pandas as pd
from typing import Optional, Tuple, List, Dict, Any

Mon_List = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def CellCountCheck(Data: pd.DataFrame, Counts: pd.DataFrame) -> None:
    # check whether the cell number corresponds to the cells column calculated in QGIS
    Counts["Consumption_Cell_count"] = Data["CellCount"]
    Counts["SameCount"] = False
    Counts.loc[Counts["Consumption_Cell_count"] == Counts["Rasterstat_Cell_count"], "SameCount"] = True
    TrueCells = Counts["SameCount"].value_counts()[True]
    if TrueCells == len(Data):
        pass
    elif len(Data) - TrueCells == 1 and Counts.loc[67311, "SameCount"] == False:
        # CellCounts are right except for Chatham Island (that's fine, results from WaterGAP version)
        pass
    elif len(Data) - TrueCells == 1 and Counts.loc[26769, "SameCount"] == False:
        print("Issue for watershed 26729 in matsiro, where the cell the furthest back is nan. proceeding as normal.")
    elif any([TrueCells == x for x in [9015, 9011, 9005, 10547, 10543, 10537]]):
        print("assuming that this is data from PCR-GLOBWB, which misses differing numbers of basins (depending on GCM or year),\nmostly islands and coastal cells. continuing script")
    else:
        raise Exception(f"The number of cells per basin ({TrueCells}) is not the same as in the AreaStatistics file")


def DisFileCreation(MAINTABLE: pd.DataFrame,
        Mon_List: List[str],
        BasinGrid: pd.DataFrame,
        *,
        InldSink: bool = False,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    if "dis" in MAINTABLE.columns: MAINTABLE=MAINTABLE.droplevel(0, axis=1)
    MAINTABLE["Annual_Average"]=MAINTABLE[Mon_List].mean(axis=1)
    
    #link coordinates to Basin_ID
    MAINTABLE = ApplyBasin_IDs(BasinGrid, MAINTABLE)
    
    #MAINTABLE is now a table with the discharge value for each lat/lon pair, 
    #and the corresponding information for this point from BasinGridFile
    OutflowCol = getOutflowFilterColumn(InldSink) #returns either TRUE for (up to eight) inflow cells to inland sinks or the individual outflow cells
    OutflowFiltered=MAINTABLE[MAINTABLE[OutflowCol]== True]  #Filter MAINTABLE to outflow cells
    Filtered=pd.DataFrame()
    for month in Mon_List:
        Filtered[month]=OutflowFiltered[month].groupby(level=2).sum(min_count=1) #perform aggregation based on Basin_ID. 
        #For regular basins, this does not change anything about the values, as after Outflow filtering there is just one value per Basin_ID,
        # it just serves to get rid of the lat/lon while at the same time makes Basin_ID the index. But 
        # for the inland sinks, it sums up all cells considered as delivering Outflows INTO the sink.
    Filtered.dropna(axis=0, how="all", inplace=True)
    Filtered = Filtered.astype("Float32")
    MAINTABLE[Mon_List] = MAINTABLE[Mon_List].astype("float32")
    MAINTABLE = MAINTABLE.reset_index().set_index(["lat","lon"])
    MAINTABLE_cols = Mon_List+["Annual_Average","Basin_ID"]
    auxiliary = MAINTABLE[[x for x in MAINTABLE.columns if x not in MAINTABLE_cols]]
    MAINTABLE = MAINTABLE[MAINTABLE_cols]
    return Filtered, MAINTABLE, auxiliary

def RunoffCalculation(
    MAINTABLE: pd.DataFrame,
    Mon_List: List[str],
    AreaCounts: pd.DataFrame,
    BasinGrid: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "qtot" in MAINTABLE.columns: MAINTABLE=MAINTABLE.droplevel(0, axis=1)
    MAINTABLE["Annual_Average_negConsneg"]=MAINTABLE[Mon_List].mean(axis=1)
    
    #link coordinates to Basin_ID
    MAINTABLE = ApplyBasin_IDs(BasinGrid, MAINTABLE)

    #MAINTABLE is now a table with the consumption value for each lat/lon pair, 
    #and the corresponding information for this point from BasinGridFile
    km2Tom2=1000*1000
    kg_m3=1000
    BasinValue=pd.DataFrame()
    
    #calculate area*runoff and get value at outflow cell
    for month in Mon_List:
        MAINT_Col_Runoff_m3=month+"_Area_x_RunOff_m3"
        #Multiply every monthly data point by its respective area, convert from km2 to m2 and from kg to m3
        MAINTABLE[MAINT_Col_Runoff_m3]=MAINTABLE.loc[:,month]*MAINTABLE.loc[:,"CellA_continental_km2"]*km2Tom2/kg_m3
        #Filter to just the Outflow Cell value
        BasinValue["OutflRunOff_"+month+"_m3"]=MAINTABLE.loc[MAINTABLE["Outflow"]==True, MAINT_Col_Runoff_m3]  
    BasinValue.reset_index(inplace=True)
    BasinValue.set_index("Basin_ID",inplace=True)
    BasinValue.drop(columns=["lat","lon"],inplace=True)

    BasinValue = BasinValue.astype("Float32")
    MT_columns = [month+"_Area_x_RunOff_m3" for month in Mon_List]+Mon_List
    auxiliary = MAINTABLE[[x for x in MAINTABLE.columns if x not in MT_columns]]
    MAINTABLE = MAINTABLE[[month+"_Area_x_RunOff_m3" for month in Mon_List]+Mon_List].astype("float32")
    MAINTABLE = MAINTABLE.reset_index().set_index(["lat","lon"])
    BasinValue["CellCount"]=MAINTABLE[["Jul_Area_x_RunOff_m3","Basin_ID"]].groupby("Basin_ID").count()
    CellCountCheck(BasinValue,AreaCounts)

    BasinValue.dropna(axis=0, how="all", inplace=True)
    return BasinValue,MAINTABLE,auxiliary

def ConsumptionCalculation(
    MAINTABLE: pd.DataFrame,
    Mon_List: List[str],
    AreaCounts: pd.DataFrame,
    BasinGrid: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "atotuse" in MAINTABLE.columns: MAINTABLE=MAINTABLE.droplevel(0, axis=1)
    if "ptotuse" in MAINTABLE.columns: MAINTABLE=MAINTABLE.droplevel(0, axis=1)
    MAINTABLE["Annual_Average_negConsneg"]=MAINTABLE[Mon_List].mean(axis=1)
    
    #link coordinates to Basin_ID
    MAINTABLE = ApplyBasin_IDs(BasinGrid, MAINTABLE)
    
    #MAINTABLE is now a table with the consumption value for each lat/lon pair, 
    #and the corresponding information for this point from BasinGridFile
    km2Tom2=1000*1000
    kg_m3=1000
    BasinValue=pd.DataFrame()
    #calculate area*consumption, sum up over basin and in case set negative basin consumption to zero
    for month in Mon_List:
        #Multiply every monthly data point by its respective area, convert from km2 to m2 and from kg to m3
        MAINTABLE[month+"_Area_x_Cons_m3"]=MAINTABLE.loc[:,month]*MAINTABLE.loc[:,"CellA_continental_km2"]*km2Tom2/kg_m3
        #sum up all cells of one basin
        negatCol="BasinCons_InclNegat_"+month+"_m3"
        BasinValue[negatCol]=MAINTABLE[month+"_Area_x_Cons_m3"].groupby(level=2).sum()
        BasinValue["BasinCons_"+month+"_m3"]=BasinValue[negatCol]
        BasinValue.loc[BasinValue[negatCol]<0,"BasinCons_"+month+"_m3"]=0

    #decrease Filesize
    MT_columns = [month+"_Area_x_Cons_m3" for month in Mon_List]+Mon_List
    auxiliary = MAINTABLE[[x for x in MAINTABLE.columns if x not in MT_columns]]
    MAINTABLE = MAINTABLE.reset_index().set_index(["lat","lon"])
    BasinValue = BasinValue.astype("Float32")
    #check numbers of grid cells covered
    BasinValue["CellCount"]=MAINTABLE[["Jul_Area_x_Cons_m3","Basin_ID"]].groupby("Basin_ID").count().astype('int32') #int16 would be fine as well but might be problematic if higher grid resolution is used
    CellCountCheck(BasinValue, AreaCounts)

    BasinValue.dropna(axis=0, how="all", inplace=True)
    return BasinValue, MAINTABLE, auxiliary


def get_years_from_filename(fname):
    file_details = fname.split(".")[0].split("_")

    try:
        years = (int(file_details[-2]), int(file_details[-1]))
    except (IndexError, ValueError) as exc:
        raise ValueError("Filename must end with two integer years after 1850") from exc

    if any(year <= 1850 for year in years):
        raise ValueError("Filename years must both be after 1850")

    return years

def return_dataframes_given_cons_path(
    path: str,
    varname: str,
    BasinArea: pd.DataFrame,
    BasinGrid: pd.DataFrame,
    vartype: str,
    startyear: int
    ) -> dict:

    # get data
    file_years = get_years_from_filename(path)
    startyear_offset = startyear - file_years[0]
    filename_yearscovered = file_years[1]-file_years[0]+1
    filename_nr_of_monthscovered = filename_yearscovered*12

    DataFRAME, unit = get_dataframe_from_xarray(path, slice(startyear_offset*12, filename_nr_of_monthscovered), varname)
    print(unit)
    DataFRAME.columns = [x for x in range(startyear_offset*12, filename_nr_of_monthscovered)]

    monthseconds = ReturnMonthSeconds()
    if unit == "kg m-2 s-1":
        m_per_day_conv = 1
    elif unit == "m d-1":
        #conversion of m/day to kg/m2s
        m_per_day_conv = 1/86.4
    else:
        raise ValueError("unit of netcdf data seems to differ from expected units")
    All_Years_run: Dict[str, Any] = {"MAINTABLE":{},"Basin":{}}
    for year in range(filename_yearscovered):
        if year>= startyear_offset:
            start=year*12
            end=start+11
            SLICE = DataFRAME.loc[:,start:end].copy()
            SLICE.columns = Mon_List
            for month,factor in zip(Mon_List,monthseconds):
                SLICE.loc[:,month] = factor * SLICE.loc[:,month]*m_per_day_conv
            if vartype =="cons":
                BasinTotal,MAINTABLE,auxiliary = ConsumptionCalculation(SLICE, Mon_List, BasinArea, BasinGrid = BasinGrid)
            elif vartype =="runoff":
                BasinTotal,MAINTABLE,auxiliary = RunoffCalculation(SLICE, Mon_List, BasinArea, BasinGrid = BasinGrid)
            All_Years_run["MAINTABLE"][year+file_years[0]] = MAINTABLE
            All_Years_run["Basin"][year+file_years[0]] = BasinTotal
    All_Years_run["gridcells_auxiliary"] = auxiliary
    return All_Years_run

def return_dataframes_given_dis_path(
    dis: str,
    BasinGrid: pd.DataFrame,
    startyear: int
    ) -> dict:

    file_years = get_years_from_filename(dis)
    startyear_offset = startyear - file_years[0]
    filename_yearscovered = file_years[1]-file_years[0]+1
    filename_monthscovered = filename_yearscovered*12
    # get discharge data

    DataFRAME, unit = get_dataframe_from_xarray(dis, slice(startyear_offset*12, filename_monthscovered), "dis")
    DataFRAME.columns = [x for x in range(startyear_offset*12, filename_monthscovered)]

    if any([unit=="m3 s-1",unit=="m3s-1",unit=="m^3/s",unit=="m3/s"]):
        monthSeconds = ReturnMonthSeconds()
        unit_factor = monthSeconds
    elif any([unit=="kg s-1",unit=="kgs-1"]):
        monthSeconds = ReturnMonthSeconds()
        unit_factor = [x/1000 for x in monthSeconds] #to get to m³
    else:
        print(unit)    

    All_Years_dis: Dict[str, Any] = {"MAINTABLE": {}, "Basin": {}}
    for year in range(filename_yearscovered):
        if year>= startyear_offset:
            start=year*12
            end=start+11
            SLICE = DataFRAME.loc[:,start:end].copy()
            SLICE.columns = Mon_List
            for month,factor in zip(Mon_List,unit_factor):
                SLICE.loc[:,month] = factor * SLICE.loc[:,month]
            BasinTotal, MAINTABLE, auxiliary = DisFileCreation(SLICE,Mon_List,BasinGrid = BasinGrid, InldSink=False)
            All_Years_dis["MAINTABLE"][year+file_years[0]] = MAINTABLE
            All_Years_dis["Basin"][year+file_years[0]] = BasinTotal
    All_Years_dis["gridcells_auxiliary"] = auxiliary
    return All_Years_dis

def get_dataframe_from_xarray(path, month_slice, var):
    # we don't trust time indices, but we trust that the data is monthly and starts with January
    ds = xr.open_dataset(path, decode_times=False).dropna(dim="lat", how="all")
    ds = ds.assign_coords(time=range(len(ds.time)))
    DataFRAME = ds[var].sel(time=month_slice).to_dataframe(dim_order=["time","lat","lon"]).unstack("time")
    DataFRAME.dropna(axis=0, how="all", inplace=True)
    DataFRAME = DataFRAME.droplevel(0, axis=1)
    unit = ds[var].attrs["units"]
    ds.close()
    return DataFRAME, unit



def ReturnMonthSeconds():
    """
    returns the number of seconds per month
    """
    secPerDay=60*60*24
    Yr_sec = list((31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31))
    for elem in range(12):
        Yr_sec[elem] = Yr_sec[elem]*secPerDay
    return Yr_sec

def getOutflowFilterColumn(InldSink):
    """
    Selects which type of filter should be used to determine the relevant grid cells for discharge
    """

    if InldSink == True:
        return "InflowToInlandSink"
    elif InldSink == False:
        return "Outflow"
    

def ApplyBasin_IDs(BasinFile,Table):
    """
    open and append basin grid file, which indicates the relation between basin index and coordinates of every grid cell
    """
    Table=pd.concat([BasinFile,Table], axis=1)
    Table["Basin_ID"]=Table["Basin_ID"].convert_dtypes(convert_integer=True, convert_floating=False)
    Table.set_index("Basin_ID", append=True, inplace=True)
    return Table
