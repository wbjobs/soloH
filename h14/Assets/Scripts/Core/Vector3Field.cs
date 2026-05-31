using UnityEngine;

namespace FlowVisualization.Core
{
    public struct Vector3Field
    {
        public Vector3[,,] Velocity;
        public float[,,] Pressure;
        public float[,,] VorticityMagnitude;
        public Vector3[,,] Vorticity;
        public float[,,] LyapunovExponent;
        public float[,,] FTLE;
        public float[,,] Stretching;
        public float[,,] Compression;
        
        public int DimX, DimY, DimZ;
        public Vector3 MinBounds, MaxBounds;
        public Vector3 CellSize;
        public float TimeStep;
        public float TimeValue;

        public Vector3Field(int dimX, int dimY, int dimZ)
        {
            DimX = dimX;
            DimY = dimY;
            DimZ = dimZ;
            Velocity = new Vector3[dimX, dimY, dimZ];
            Pressure = new float[dimX, dimY, dimZ];
            VorticityMagnitude = new float[dimX, dimY, dimZ];
            Vorticity = new Vector3[dimX, dimY, dimZ];
            LyapunovExponent = new float[dimX, dimY, dimZ];
            FTLE = new float[dimX, dimY, dimZ];
            Stretching = new float[dimX, dimY, dimZ];
            Compression = new float[dimX, dimY, dimZ];
            MinBounds = Vector3.zero;
            MaxBounds = Vector3.one;
            CellSize = Vector3.one;
            TimeStep = 0.01f;
            TimeValue = 0f;
        }

        public Vector3 GetVelocity(Vector3 position)
        {
            Vector3 normalizedPos = Vector3.Scale(
                position - MinBounds,
                new Vector3(1f / CellSize.x, 1f / CellSize.y, 1f / CellSize.z)
            );
            
            int x0 = Mathf.Clamp((int)normalizedPos.x, 0, DimX - 2);
            int y0 = Mathf.Clamp((int)normalizedPos.y, 0, DimY - 2);
            int z0 = Mathf.Clamp((int)normalizedPos.z, 0, DimZ - 2);
            
            float fx = normalizedPos.x - x0;
            float fy = normalizedPos.y - y0;
            float fz = normalizedPos.z - z0;

            Vector3 v000 = Velocity[x0, y0, z0];
            Vector3 v100 = Velocity[x0 + 1, y0, z0];
            Vector3 v010 = Velocity[x0, y0 + 1, z0];
            Vector3 v110 = Velocity[x0 + 1, y0 + 1, z0];
            Vector3 v001 = Velocity[x0, y0, z0 + 1];
            Vector3 v101 = Velocity[x0 + 1, y0, z0 + 1];
            Vector3 v011 = Velocity[x0, y0 + 1, z0 + 1];
            Vector3 v111 = Velocity[x0 + 1, y0 + 1, z0 + 1];

            return Vector3.Lerp(
                Vector3.Lerp(Vector3.Lerp(v000, v100, fx), Vector3.Lerp(v010, v110, fx), fy),
                Vector3.Lerp(Vector3.Lerp(v001, v101, fx), Vector3.Lerp(v011, v111, fx), fy),
                fz
            );
        }

        public float GetScalarValue(Vector3 position, ScalarFieldType type)
        {
            Vector3 normalizedPos = Vector3.Scale(
                position - MinBounds,
                new Vector3(1f / CellSize.x, 1f / CellSize.y, 1f / CellSize.z)
            );
            
            int x0 = Mathf.Clamp((int)normalizedPos.x, 0, DimX - 2);
            int y0 = Mathf.Clamp((int)normalizedPos.y, 0, DimY - 2);
            int z0 = Mathf.Clamp((int)normalizedPos.z, 0, DimZ - 2);
            
            float fx = normalizedPos.x - x0;
            float fy = normalizedPos.y - y0;
            float fz = normalizedPos.z - z0;

            if (type == ScalarFieldType.VelocityMagnitude)
            {
                return Mathf.Lerp(
                    Mathf.Lerp(Mathf.Lerp(Velocity[x0, y0, z0].magnitude, Velocity[x0 + 1, y0, z0].magnitude, fx),
                        Mathf.Lerp(Velocity[x0, y0 + 1, z0].magnitude, Velocity[x0 + 1, y0 + 1, z0].magnitude, fx), fy),
                    Mathf.Lerp(Mathf.Lerp(Velocity[x0, y0, z0 + 1].magnitude, Velocity[x0 + 1, y0, z0 + 1].magnitude, fx),
                        Mathf.Lerp(Velocity[x0, y0 + 1, z0 + 1].magnitude, Velocity[x0 + 1, y0 + 1, z0 + 1].magnitude, fx), fy),
                    fz
                );
            }

            float[,,] field = type switch
            {
                ScalarFieldType.Pressure => Pressure,
                ScalarFieldType.Vorticity => VorticityMagnitude,
                ScalarFieldType.LyapunovExponent => LyapunovExponent,
                ScalarFieldType.FTLE => FTLE,
                ScalarFieldType.Stretching => Stretching,
                ScalarFieldType.Compression => Compression,
                _ => Pressure
            };

            return Mathf.Lerp(
                Mathf.Lerp(Mathf.Lerp(field[x0, y0, z0], field[x0 + 1, y0, z0], fx),
                    Mathf.Lerp(field[x0, y0 + 1, z0], field[x0 + 1, y0 + 1, z0], fx), fy),
                Mathf.Lerp(Mathf.Lerp(field[x0, y0, z0 + 1], field[x0 + 1, y0, z0 + 1], fx),
                    Mathf.Lerp(field[x0, y0 + 1, z0 + 1], field[x0 + 1, y0 + 1, z0 + 1], fx), fy),
                fz
            );
        }

        public void ComputeVorticity()
        {
            float inv2dx = 1f / (2f * CellSize.x);
            float inv2dy = 1f / (2f * CellSize.y);
            float inv2dz = 1f / (2f * CellSize.z);

            for (int x = 1; x < DimX - 1; x++)
            {
                for (int y = 1; y < DimY - 1; y++)
                {
                    for (int z = 1; z < DimZ - 1; z++)
                    {
                        Vector3 vxp = Velocity[x + 1, y, z];
                        Vector3 vxm = Velocity[x - 1, y, z];
                        Vector3 vyp = Velocity[x, y + 1, z];
                        Vector3 vym = Velocity[x, y - 1, z];
                        Vector3 vzp = Velocity[x, y, z + 1];
                        Vector3 vzm = Velocity[x, y, z - 1];

                        float dvzdy = (vzp.y - vzm.y) * inv2dy;
                        float dvydz = (vyp.z - vym.z) * inv2dz;
                        float dvxdz = (vzp.x - vzm.x) * inv2dz;
                        float dvzdx = (vxp.z - vxm.z) * inv2dx;
                        float dvydx = (vxp.y - vxm.y) * inv2dx;
                        float dvxdy = (vyp.x - vym.x) * inv2dy;

                        Vorticity[x, y, z] = new Vector3(
                            dvzdy - dvydz,
                            dvxdz - dvzdx,
                            dvydx - dvxdy
                        );
                        VorticityMagnitude[x, y, z] = Vorticity[x, y, z].magnitude;
                    }
                }
            }
        }

        public bool IsInsideBounds(Vector3 position)
        {
            return position.x >= MinBounds.x && position.x <= MaxBounds.x &&
                   position.y >= MinBounds.y && position.y <= MaxBounds.y &&
                   position.z >= MinBounds.z && position.z <= MaxBounds.z;
        }
    }

    public enum ScalarFieldType
    {
        VelocityMagnitude,
        Vorticity,
        Pressure,
        LyapunovExponent,
        FTLE,
        Stretching,
        Compression
    }

    public enum IntegrationDirection
    {
        Forward,
        Backward
    }
}
