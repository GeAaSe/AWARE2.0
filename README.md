# AWARE 2.0 - Water Characterization Factor Calculator

This repository contains the implementation of **AWARE 2.0** characterization factors on basin-month-resolution, as documented in https://doi.org/10.1111/jiec.70023. CFs for use in LCA are provided at https://doi.org/10.5281/zenodo.8215863.

> Note: This code allows to recalculate AWARE2.0. However, due to time constraints at the moment of publishing, it is not optimized for efficiency and could very well be implemented much easier without the AWARE_data and AWARE_CF_equation classes. The reason for the rather overcomplicated logic is that the code was extracted from a larger project that required this logic.


## Overview

AWARE 2.0 provides spatially explicit characterization factors (CFs) that estimate water deprivation potential at the basin level. The methodology combines:
- Actual water availability estimations [from Global Hydrological Model (GHM) WaterGAP2.2e]
- Environmental water requirements (EWR)
- Human water consumption

## Project Structure

### Core Modules

- **`AWARE_data.py`** - Main data class (`AWARE_data`) that stores and manages all hydrological data obtained from netCDF files, including water consumption, discharge, and environmental water requirements.

- **`AWARE_CF_equation.py`** - Core calculation engine (`AWARE_CF_equation`) that computes AWARE characterization factors from hydrological inputs. Includes basin-subdivision algorithms for subdivided river basins.

- **`AWARE_data_import.py`** - Data import and processing functions for converting raw hydrological data (from WaterGAP2.2e) into basin-scale aggregated values. Also works with some other GHMs providing output on ISIMIP.

- **`AWARE_aggregation.py`** - Aggregation tools (`countryAggregator` class) for aggregating basin-scale characterization factors to country level using spatial weighting.

- **`AWARE_help.py`** - Helper functions for common operations including file handling, unit conversions, and data validation.

### Data

#### Input Data (`Input/`)
- WaterGAP 2.2e model outputs for various hydrological variables:
  - `atotuse_*`: Total anthropogenic water use
  - `dis_*`: Water discharge
  - `pXXXuse_*`: Sectoral water use (domestic, industrial, irrigation, livestock, manufacturing, electricity)
  - `qtot_*`: Total runoff
  
- Mapping and basin information:
  - `mapping/BasinGrid.csv` - Grid-to-basin mapping
  - `mapping/Area.csv` - Basin areas
  - `mapping/Deltas.csv` - Delta basin information
  - `mapping/InlandSinkBasins.csv` - Inland sink basins
  - `mapping/InlandSinkInflowCells.csv` - Inland sink inflow cells

#### Output Data (`Output/`)
- Calculated characterization factors and intermediate results
- Separate components for consumption and discharge

#### Post-processing (`Input/postprocessing/`)
- Prescribed differences between original and postprocessed WaterGAP2.2e data for 2009-2019

### Jupyter Notebooks
- **`AWARE2.0_reproduced.ipynb`** - Main notebook demonstrating the complete AWARE 2.0 calculation workflow


## Installation & Requirements

### Dependencies
- Python 3.11
- pandas
- xarray
- numpy
- openpyxl (for Excel file handling)
- certifi
- netcdf4

### Setup
1. Clone or download the repository
2. Create a Python environment with required Python packages (see requirements.txt for the package versions this code was tested with)
3. Download the Input data (see Jupyter Notebook for more information)
4. Run Jupyter Notebook


## Usage

### Basic Workflow

1. **Data Import**: Use functions in `AWARE_data_import.py` to process raw GHM/GCM output data
2. **Create Data Object**: Initialize an `AWARE_data` object with your model combination metadata
3. **Calculate Characterization Factors**: Use `AWARECF_equation` to compute CFs from hydrological inputs

### Example Usage

See the Jupyter notebooks for complete, working examples.

## Citation

If you use this code in your research, please cite 
- Seitfudem, G., Berger, M., Schmied, H. M., & Boulay, A.-M. (2025). The updated and improved method for water scarcity impact assessment in LCA, AWARE2.0. Journal of Industrial Ecology, 29(3), 891–907. https://doi.org/10.1111/jiec.70023
Further relevant citations:
- Boulay, A.-M., Bare, J., Benini, L., Berger, M., Lathuillière, M. J., Manzardo, A., Margni, M., Motoshita, M., Núñez, M., Pastor, A. V., Ridoutt, B., Oki, T., Worbe, S., & Pfister, S. (2018). The WULCA consensus characterization model for water scarcity footprints: Assessing impacts of water consumption based on available water remaining (AWARE). International Journal of Life Cycle Assessment, 23(2), 368–378. https://doi.org/10.1007/s11367-017-1333-8


## Author

Georg Seitfudem, georg.seitfudem@polymtl.ca

## License

CC BY 4.0

