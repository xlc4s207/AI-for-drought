# Introduction for these codes

This code repository supports the analysis presented in the study: "Anthropogenic Exacerbation of Soil Moisture Droughts Hidden Below the Surface", Yansong Guan ([DRmaster\@cug.edu.cn](mailto:DRmaster@cug.edu.cn){.email}), Xihui Gu ([guxh\@cug.edu.cn](mailto:guxh@cug.edu.cn){.email}).

The core methodology relies on a Lagrangian four-dimensional tracking framework to identify and characterize deep drought events. The codebase implements the three main components described in the Methods section of the paper: 1. Spatial Identification (cluster1.py); 2. Temporal Identification (cluster2.py); 3. Drought Characteristic Analysis (characteristic.R).

## cluster1.py

This script identifies drought grid boxes within individual soil layers and merges them into three-dimensional spatial drought events (longitude, latitude, depth). At each timestep, vertically and horizontally adjacent grid boxes across layers are connected using 26-connectivity to form fully three-dimensional drought object (longitude × latitude × depth).

26-connectivity considers all neighbors:

-   9 grid cells in the layer above

-   8 in the current layer (excluding the center)

-   9 in the layer below

This connectivity ensures both vertical and horizontal continuity in detected events.

The core function utilizes the Python package cc3d (connected-components-3d) (Silversmith, 2021). Due to the computational intensity of this step, the script is designed for MPI-based parallel computing. Before running the script, install the following Python dependencies:

``` bash
pip install numpy scipy cc3d h5py mpi4py netCDF4
```

You also need to ensure an MPI runtime environment is available (e.g., OpenMPI). Run the script with:

``` bash
mpiexec -n 4 python cluster.py
```

## cluster2.py

This script is used to identify the temporal evolution of a tridimensional drought object. Any spatially contiguous three-dimensional drought objects that share overlap ratios greater than given ratio over consecutive timesteps were consolidated into a single four-dimensional (space-depth-time) contiguous cluster. This step is following Sun et al., 2023. This original python code is available in <https://github.com/cindyisok/Subsurface_MHW/blob/main/mhw_overlap_tracks_4d_125.py>. We referenced and improved the original code from Sun et al., 2023 to adapt to parallel environments and improve computational efficiency. The sample code here (cluster2.py) does not couple parallel modules (see cluster1.py) and can be run directly from the command line.

## characteristic.R

This script is used to calculate the drought characteristics (duration and intensity, etc) for drought events. Before running this script, you need to install the following R packages:

``` r
install.packages("data.table")
install.packages("ncdf4")
install.packages("parallel")
install.packages("magrittr")
```

Parallel processing is supported using R’s parLapply.

## Supporting Data

### drought_threshold/\*

This folder stores the drought thresholds for each of the three soil layers. Each file, when read using R, is formatted as a two-column matrix: the first column represents the 90th percentile (we used), and the second column represents the 80th percentile, with each row corresponding to a land grid cell. For example, the file "threshold1.RData" represents the soil moisture drought threshold for the first layer based on ERA5-Land. Although .RData is not a universal data storage format, it is a highly efficient and compatible format within R-based workflows.

### sm/\*

This folder stores the daily soil water values for each soil layer from May 1 to May 4, 1981. For example, the file "swvl1_121.nc" represents the soil mositure of the first layer on the 121st day (i.e., May 1) of 1981. Since all years' data exceed 50 GB, we have selected only a few days in 1981 as examples.

### sm_bool/\*

This folder stores the daily binary drought masks for each soil layer from May 1 to May 4, 1981. For example, the file "swvl1_121.nc" represents the drought mask of the first soil layer on the 121st day (i.e., May 1) of 1981, where grid cells with a value of "1" indicate drought conditions (daily soil moisture below the 90th threshold) and "0" indicate non-drought conditions.

### map_mask_filter.txt

The file 'map_mask_filter.txt' contains a binary land–sea mask for the spatial domain used in the analysis. It is structured as a 2D matrix with dimensions corresponding to longitude (360 grid points from −179.5° to 179.5°) and latitude (150 grid points from −59.5° to 89.5°). Each grid cell is assigned a value of 1 for land and 0 for ocean or excluded regions. This mask is used to filter out non-land areas when calculating drought events and related metrics.

### Reference

1.  Guan, Y. *et al.* Increase in ocean-onto-land droughts and their drivers under anthropogenic climate change. *npj Climate and Atmospheric Science* **6**, 195 (2023).
2.  Kong, D. *et al*. Contribution of Anthropogenic Activities to the Intensification of Heat Index‐Based Spatiotemporally Contiguous Heatwave Events in China. *JGR Atmospheres* **129**, e2023JD040004 (2024).
3.  Silversmith, W. cc3d: Connected components on multilabel 3D & 2D images. Zenodo <https://doi.org/10.5281/ZENODO.5535250> (2021).
4.  Sun, D., Li, F., Jing, Z., Hu, S. & Zhang, B. Frequent marine heatwaves hidden below the surface of the global ocean. *Nat. Geosci.* **16**, 1099–1104 (2023).
