using System;
using UnityEngine;
using LanderSim.Core;

namespace LanderSim.Terrain
{
    [Serializable]
    public class TerrainData
    {
        public int resolutionX;
        public int resolutionZ;
        public float cellSize;
        public float[,] heights;
        public Vector3 origin;

        public float minHeight;
        public float maxHeight;

        public TerrainData(int resX, int resZ, float cellSize, Vector3 origin)
        {
            resolutionX = resX;
            resolutionZ = resZ;
            this.cellSize = cellSize;
            this.origin = origin;
            heights = new float[resX, resZ];
            minHeight = float.MaxValue;
            maxHeight = float.MinValue;
        }

        public float GetHeight(int x, int z)
        {
            x = Mathf.Clamp(x, 0, resolutionX - 1);
            z = Mathf.Clamp(z, 0, resolutionZ - 1);
            return heights[x, z];
        }

        public float GetHeight(float worldX, float worldZ)
        {
            float localX = (worldX - origin.x) / cellSize;
            float localZ = (worldZ - origin.z) / cellSize;

            int x0 = Mathf.FloorToInt(localX);
            int z0 = Mathf.FloorToInt(localZ);
            int x1 = x0 + 1;
            int z1 = z0 + 1;

            float fx = localX - x0;
            float fz = localZ - z0;

            float h00 = GetHeight(x0, z0);
            float h10 = GetHeight(x1, z0);
            float h01 = GetHeight(x0, z1);
            float h11 = GetHeight(x1, z1);

            float h0 = Mathf.Lerp(h00, h10, fx);
            float h1 = Mathf.Lerp(h01, h11, fx);
            return Mathf.Lerp(h0, h1, fz);
        }

        public Vector3d GetWorldPosition(int x, int z)
        {
            return new Vector3d(
                origin.x + x * cellSize,
                heights[x, z],
                origin.z + z * cellSize
            );
        }

        public Vector3d GetNormal(int x, int z)
        {
            float hL = GetHeight(x - 1, z);
            float hR = GetHeight(x + 1, z);
            float hD = GetHeight(x, z - 1);
            float hU = GetHeight(x, z + 1);

            Vector3d tangentX = new Vector3d(2 * cellSize, hR - hL, 0);
            Vector3d tangentZ = new Vector3d(0, hU - hD, 2 * cellSize);

            return Vector3d.Cross(tangentZ, tangentX).normalized;
        }

        public float GetSlope(int x, int z)
        {
            Vector3d normal = GetNormal(x, z);
            return (float)(Math.Acos(Vector3d.Dot(normal, Vector3d.up)) * 180.0 / Math.PI);
        }

        public float GetRoughness(int x, int z, int kernelSize = 3)
        {
            float sum = 0;
            int count = 0;
            float center = GetHeight(x, z);
            int half = kernelSize / 2;

            for (int dx = -half; dx <= half; dx++)
            {
                for (int dz = -half; dz <= half; dz++)
                {
                    if (dx == 0 && dz == 0) continue;
                    int xi = x + dx;
                    int zi = z + dz;
                    if (xi >= 0 && xi < resolutionX && zi >= 0 && zi < resolutionZ)
                    {
                        sum += Mathf.Abs(GetHeight(xi, zi) - center);
                        count++;
                    }
                }
            }

            return count > 0 ? sum / count : 0;
        }

        public void UpdateHeightBounds()
        {
            minHeight = float.MaxValue;
            maxHeight = float.MinValue;

            for (int x = 0; x < resolutionX; x++)
            {
                for (int z = 0; z < resolutionZ; z++)
                {
                    minHeight = Mathf.Min(minHeight, heights[x, z]);
                    maxHeight = Mathf.Max(maxHeight, heights[x, z]);
                }
            }
        }

        public bool IsInBounds(int x, int z)
        {
            return x >= 0 && x < resolutionX && z >= 0 && z < resolutionZ;
        }

        public bool IsInBounds(float worldX, float worldZ)
        {
            float localX = (worldX - origin.x) / cellSize;
            float localZ = (worldZ - origin.z) / cellSize;
            return localX >= 0 && localX < resolutionX - 1 &&
                   localZ >= 0 && localZ < resolutionZ - 1;
        }
    }
}
