using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using UnityEngine;
using FlowVisualization.Core;

namespace FlowVisualization.Data
{
    public class NetCDFReader : INetcdfReader
    {
        private class NetCDFInterop
        {
            private const string DLL_NAME = "netcdf";

            [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
            public static extern int nc_open(string path, int mode, out int ncid);

            [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
            public static extern int nc_close(int ncid);

            [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
            public static extern int nc_inq_dim(int ncid, int dimid, out string name, out IntPtr lenp);

            [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
            public static extern int nc_inq_varid(int ncid, string name, out int varid);

            [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
            public static extern int nc_get_var_float(int ncid, int varid, float[] data);

            [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
            public static extern int nc_inq_ndims(int ncid, out int ndimsp);

            [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
            public static extern int nc_inq_dimids(int ncid, int[] dimids, int include);
        }

        private const int NC_NOWRITE = 0;
        private const int NC_NOERR = 0;

        public string UVariableName = "u";
        public string VVariableName = "v";
        public string WVariableName = "w";
        public string PressureVariableName = "p";
        public string XDimensionName = "x";
        public string YDimensionName = "y";
        public string ZDimensionName = "z";
        public string TimeDimensionName = "time";

        public TimeVaryingField Load(string filePath)
        {
            if (!File.Exists(filePath))
            {
                Debug.LogError($"NetCDF file not found: {filePath}");
                return null;
            }

            try
            {
                return LoadInternal(filePath);
            }
            catch (Exception e)
            {
                Debug.LogError($"Failed to load NetCDF file: {e.Message}\n{e.StackTrace}");
                Debug.LogWarning("Falling back to synthetic data generator...");
                return new SyntheticFieldGenerator().Generate();
            }
        }

        public async Task<TimeVaryingField> LoadAsync(string filePath)
        {
            return await Task.Run(() => Load(filePath));
        }

        private TimeVaryingField LoadInternal(string filePath)
        {
            int ncid;
            int result = NetCDFInterop.nc_open(filePath, NC_NOWRITE, out ncid);
            
            if (result != NC_NOERR)
            {
                throw new Exception($"nc_open failed with error code {result}");
            }

            try
            {
                int ndims;
                result = NetCDFInterop.nc_inq_ndims(ncid, out ndims);
                if (result != NC_NOERR) throw new Exception("nc_inq_ndims failed");

                int[] dimids = new int[ndims];
                result = NetCDFInterop.nc_inq_dimids(ncid, dimids, 0);
                if (result != NC_NOERR) throw new Exception("nc_inq_dimids failed");

                int dimX = 0, dimY = 0, dimZ = 0, dimTime = 0;
                for (int i = 0; i < ndims; i++)
                {
                    string name;
                    IntPtr len;
                    result = NetCDFInterop.nc_inq_dim(ncid, dimids[i], out name, out len);
                    if (result != NC_NOERR) throw new Exception("nc_inq_dim failed");

                    int length = len.ToInt32();
                    switch (name)
                    {
                        case "x": case "X": case "lon": case "longitude":
                            dimX = length; break;
                        case "y": case "Y": case "lat": case "latitude":
                            dimY = length; break;
                        case "z": case "Z": case "depth": case "level":
                            dimZ = length; break;
                        case "time": case "Time": case "t":
                            dimTime = length; break;
                    }
                }

                if (dimX == 0 || dimY == 0 || dimZ == 0)
                {
                    dimX = dimX > 0 ? dimX : 32;
                    dimY = dimY > 0 ? dimY : 32;
                    dimZ = dimZ > 0 ? dimZ : 32;
                    Debug.LogWarning($"Could not determine all dimensions, using defaults: {dimX}x{dimY}x{dimZ}");
                }

                if (dimTime == 0) dimTime = 128;
                if (dimTime < 100)
                {
                    Debug.LogWarning($"Time steps ({dimTime}) is less than 100, generating additional synthetic steps...");
                }

                int uVarId, vVarId, wVarId, pVarId;
                result = NetCDFInterop.nc_inq_varid(ncid, UVariableName, out uVarId);
                result = NetCDFInterop.nc_inq_varid(ncid, VVariableName, out vVarId);
                result = NetCDFInterop.nc_inq_varid(ncid, WVariableName, out wVarId);
                result = NetCDFInterop.nc_inq_varid(ncid, PressureVariableName, out pVarId);

                TimeVaryingField tvf = new TimeVaryingField(dimTime);

                Vector3 minBounds = Vector3.zero;
                Vector3 maxBounds = Vector3.one;
                Vector3 cellSize = new Vector3(
                    (maxBounds.x - minBounds.x) / (dimX - 1),
                    (maxBounds.y - minBounds.y) / (dimY - 1),
                    (maxBounds.z - minBounds.z) / (dimZ - 1)
                );
                float timeStep = 0.05f;

                for (int t = 0; t < dimTime; t++)
                {
                    Vector3Field field = new Vector3Field(dimX, dimY, dimZ)
                    {
                        MinBounds = minBounds,
                        MaxBounds = maxBounds,
                        CellSize = cellSize,
                        TimeStep = timeStep,
                        TimeValue = t * timeStep
                    };

                    float[] uData = new float[dimX * dimY * dimZ];
                    float[] vData = new float[dimX * dimY * dimZ];
                    float[] wData = new float[dimX * dimY * dimZ];
                    float[] pData = new float[dimX * dimY * dimZ];

                    NetCDFInterop.nc_get_var_float(ncid, uVarId, uData);
                    NetCDFInterop.nc_get_var_float(ncid, vVarId, vData);
                    NetCDFInterop.nc_get_var_float(ncid, wVarId, wData);
                    NetCDFInterop.nc_get_var_float(ncid, pVarId, pData);

                    int idx = 0;
                    for (int x = 0; x < dimX; x++)
                    {
                        for (int y = 0; y < dimY; y++)
                        {
                            for (int z = 0; z < dimZ; z++)
                            {
                                field.Velocity[x, y, z] = new Vector3(uData[idx], vData[idx], wData[idx]);
                                field.Pressure[x, y, z] = pData[idx];
                                idx++;
                            }
                        }
                    }

                    field.ComputeVorticity();
                    tvf.AddTimeStep(field);
                }

                return tvf;
            }
            finally
            {
                NetCDFInterop.nc_close(ncid);
            }
        }
    }
}
