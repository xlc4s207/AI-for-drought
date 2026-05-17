import numpy as np
import scipy.io as scio
import cc3d
import h5py
import os
from mpi4py import MPI
from sys import stdout
from netCDF4 import Dataset
import itertools

# Determine the parameters for code parallelism
# "rank"" represents the first core in a parallel environment (for example, in a 16-core CPU, rank=0 represents the first core).
# "size"" represents the total number of cores in the parallel environment (16-core CPU, size is 16)
comm = MPI.COMM_WORLD
rank = comm.rank
size = comm.size

# Clustering process, here we use ERA5-Land's 1981 northern hemisphere warm season as an example.
year=1981
day=np.arange(121, 125) #05-01 ~ 05.04

# "path" need to set this path as your path.
# "inpath" contains Netcdf4 files in 0/1 Boolean format, where 1 represents drought conditions and 0 represents non-drought conditions. 
# Each Netcdf4 file is a 360*150 (lon*lat) matrix (excluding areas with latitude less than -60 degrees, i.e., Antarctica).
# "outpath" is the storage path for the results of three-dimensional spatial (lon, lat, depth) drought.
#path="Your path/data"
path="/data/users/guan/CV/data"
inpath=path+"/sm_bool" 
outpath=path+"/cluster1"
os.makedirs(str(outpath), exist_ok=True)

task_len=len(day)

def depthcluster(chunk):
  chunk_length = len(chunk)
  for i in range(0, chunk_length):
    # Read matrixs of Boolean values (longitude, latitude) across three soil layers
    f1 = Dataset(inpath+'/swvl1_'+str(day[int(chunk[int(i)])])+'.nc')
    mask_day1 = f1.variables["SMI"][:]
    f2 = Dataset(inpath+'/swvl2_'+str(day[int(chunk[int(i)])])+'.nc')
    mask_day2 = f2.variables["SMI"][:]
    f3 = Dataset(inpath+'/swvl3_'+str(day[int(chunk[int(i)])])+'.nc')
    mask_day3 = f3.variables["SMI"][:]
    # Transpose the array dimensions from (lon, lat, time) to (time, lat, lon) for easier merging later.
    mask_day1 = mask_day1.transpose(2,1,0)
    mask_day2 = mask_day2.transpose(2,1,0)
    mask_day3 = mask_day3.transpose(2,1,0)
    # Concatenate three matrices into a three-dimensional array (longitude, latitude, depth)
    tempdata = np.concatenate((mask_day1,mask_day2,mask_day3), axis=2)
    # Use the 26 connectivity criteria to identify three-dimensional (longitude, latitude, depth) contiguous droughts
    cluster1, N = cc3d.connected_components(tempdata, connectivity=26, return_N=True)  
    # Count the number of drought cubic grid boxes within each connected region (drought).
    a = []
    for x in range(1, N+1):
      count = np.sum(cluster1 == x)
      a.append(count)
    # Save the 3D cluster, the number of clusters N, and the number of drought cubic grid boxes of each cluster to a .mat file.
    scio.savemat(outpath+'/test_'+str(day[int(chunk[int(i)])])+'.mat',{'cluster':cluster1,'N':N,'L':a})

# Set the starting offset for parallel processes (used to skip the first offset processes)
offset = 0
# Get the total length of the task list for day (i.e., the total number of tasks)
nlen = len(day)
# Calculate the approximate number of tasks that should be allocated to each process (rounded up), and allocate them only to size-offset processes.
h = np.ceil(nlen / np.float32(size - offset))
# For processes other than the last one, allocate tasks from the start index to start + h.
if rank >= offset and rank < size - 1:
  chunk = np.arange((rank - offset) * h, (rank - offset) * h + h)
# For the last process, allocate all remaining tasks to avoid losing tasks.
elif rank == size - 1:
  chunk = np.arange((rank - offset) * h, nlen)
  
depthcluster(chunk)
