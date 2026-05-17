import netCDF4 as nc
import numpy as np


class StreamingEventNetCDFWriter:
    def __init__(
        self,
        output_file,
        result_dtype,
        result_fields,
        var_attrs=None,
        global_attrs=None,
        coord_vars=None,
    ):
        self.output_file = output_file
        self.result_dtype = result_dtype
        self.result_fields = result_fields
        self.var_attrs = var_attrs or {}
        self.global_attrs = global_attrs or {}
        self.coord_vars = coord_vars or []
        self.next_index = 0

        self.ds = nc.Dataset(output_file, "w", format="NETCDF4")
        self.ds.createDimension("event", None)

        for coord in self.coord_vars:
            dim_name = coord["dim_name"]
            size = len(coord["data"])
            if dim_name not in self.ds.dimensions:
                self.ds.createDimension(dim_name, size)
            var = self.ds.createVariable(coord["name"], coord.get("dtype", "f4"), coord["dims"])
            var[:] = coord["data"]
            for key, value in coord.get("attrs", {}).items():
                var.setncattr(key, value)

        self.event_vars = {}
        for field in self.result_fields:
            dtype_np = self.result_dtype[field]
            if np.issubdtype(dtype_np, np.floating):
                fill_val = np.nan
            elif dtype_np == np.dtype("i1"):
                fill_val = -127
            elif np.issubdtype(dtype_np, np.integer):
                fill_val = -9999
            else:
                fill_val = None

            if fill_val is None:
                var = self.ds.createVariable(field, dtype_np, ("event",), zlib=True, complevel=4)
            else:
                var = self.ds.createVariable(field, dtype_np, ("event",), fill_value=fill_val, zlib=True, complevel=4)
            for key, value in self.var_attrs.get(field, {}).items():
                var.setncattr(key, value)
            self.event_vars[field] = var

        for key, value in self.global_attrs.items():
            self.ds.setncattr(key, value)

    def append(self, result_arr):
        if result_arr is None or len(result_arr) == 0:
            return
        start = self.next_index
        end = start + len(result_arr)
        for field in self.result_fields:
            self.event_vars[field][start:end] = result_arr[field]
        self.next_index = end

    def close(self):
        if self.ds is not None:
            self.ds.close()
            self.ds = None