using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;

namespace LanderSim.Terrain
{
    [Serializable]
    public class Crater
    {
        public Vector3 center;
        public float radius;
        public float depth;
        public float rimHeight;
        public float roughness;

        public Crater(Vector3 center, float radius, float depth,
                      float rimHeight = 2f, float roughness = 0.3f)
        {
            this.center = center;
            this.radius = radius;
            this.depth = depth;
            this.rimHeight = rimHeight;
            this.roughness = roughness;
        }

        public float GetHeight(float x, float z)
        {
            float dx = x - center.x;
            float dz = z - center.z;
            float dist = Mathf.Sqrt(dx * dx + dz * dz);

            if (dist > radius * 1.5f) return 0;

            float normalizedDist = dist / radius;
            float height = 0;

            if (normalizedDist < 0.3f)
            {
                float t = normalizedDist / 0.3f;
                height = -depth * (1 - t * t) * Mathf.Exp(-3 * t);
            }
            else if (normalizedDist < 1.0f)
            {
                float t = (normalizedDist - 0.3f) / 0.7f;
                float bowl = -depth * (1 - t * t) * Mathf.Exp(-3 * t);
                float rim = rimHeight * Mathf.Sin(t * Mathf.PI * 0.8f) *
                            Mathf.Exp(-(t - 0.6f) * (t - 0.6f) * 8);
                height = bowl + rim;
            }
            else if (normalizedDist < 1.5f)
            {
                float t = (normalizedDist - 1.0f) / 0.5f;
                height = rimHeight * (1 - t) * (1 - t);
            }

            float noise = (Mathf.PerlinNoise(x * 0.5f, z * 0.5f) - 0.5f) * roughness * depth;
            return height + noise;
        }
    }

    [Serializable]
    public class RockObstacle
    {
        public Vector3 center;
        public Vector3 size;
        public Quaternion rotation;
        public Ellipsoid collisionEllipsoid;

        public RockObstacle(Vector3 center, Vector3 size, Quaternion rotation)
        {
            this.center = center;
            this.size = size;
            this.rotation = rotation;

            Vector3d c = Vector3d.FromVector3(center);
            Vector3d r = Vector3d.FromVector3(size * 0.5f);
            Quaterniond rot = new Quaterniond(rotation.x, rotation.y, rotation.z, rotation.w);
            collisionEllipsoid = new Ellipsoid(c, r, rot);
        }

        public float GetHeight(float x, float z)
        {
            Vector3 localPos = Quaternion.Inverse(rotation) *
                              (new Vector3(x, 0, z) - center);

            float halfX = size.x * 0.5f;
            float halfZ = size.z * 0.5f;

            if (Mathf.Abs(localPos.x) > halfX || Mathf.Abs(localPos.z) > halfZ)
                return 0;

            float nx = localPos.x / halfX;
            float nz = localPos.z / halfZ;
            float dist2 = nx * nx + nz * nz;

            if (dist2 > 1.0f) return 0;

            float heightFactor = Mathf.Sqrt(1 - dist2);
            return center.y + localPos.y + heightFactor * size.y * 0.5f;
        }

        public bool ContainsPoint(Vector3 point)
        {
            Vector3 local = Quaternion.Inverse(rotation) * (point - center);
            Vector3 halfSize = size * 0.5f;
            return Mathf.Abs(local.x) <= halfSize.x &&
                   Mathf.Abs(local.y) <= halfSize.y &&
                   Mathf.Abs(local.z) <= halfSize.z;
        }
    }

    public class TerrainGenerator : MonoBehaviour
    {
        [Header("Terrain Settings")]
        public int resolution = 256;
        public float cellSize = 1.0f;
        public float baseHeight = 50f;
        public float globalScale = 50f;
        public Vector3 terrainOrigin = Vector3.zero;

        [Header("Generation Mode")]
        public bool useRandomGeneration = true;
        public string demFilePath = "";
        public int seed = 42;

        [Header("Crater Settings")]
        public int minCraters = 5;
        public int maxCraters = 15;
        public float minCraterRadius = 10f;
        public float maxCraterRadius = 50f;
        public float minCraterDepth = 3f;
        public float maxCraterDepth = 15f;

        [Header("Rock Settings")]
        public int minRocks = 20;
        public int maxRocks = 50;
        public float minRockSize = 1f;
        public float maxRockSize = 8f;

        [Header("Noise Settings")]
        public float noiseScale = 0.01f;
        public float noiseAmplitude = 10f;
        public int noiseOctaves = 4;
        public float noisePersistence = 0.5f;
        public float noiseLacunarity = 2.0f;

        public TerrainData TerrainData { get; private set; }
        public List<Crater> Craters { get; private set; }
        public List<RockObstacle> Rocks { get; private set; }

        private System.Random random;

        public void GenerateTerrain()
        {
            random = new System.Random(seed);
            TerrainData = new TerrainData(resolution, resolution, cellSize, terrainOrigin);
            Craters = new List<Crater>();
            Rocks = new List<RockObstacle>();

            if (useRandomGeneration)
            {
                GenerateRandomTerrain();
            }
            else
            {
                LoadDEMTerrain();
            }

            TerrainData.UpdateHeightBounds();
        }

        private void GenerateRandomTerrain()
        {
            float[,] noiseHeights = GeneratePerlinNoise();

            for (int x = 0; x < resolution; x++)
            {
                for (int z = 0; z < resolution; z++)
                {
                    float worldX = terrainOrigin.x + x * cellSize;
                    float worldZ = terrainOrigin.z + z * cellSize;

                    float height = baseHeight + noiseHeights[x, z] * noiseAmplitude;

                    foreach (var crater in Craters)
                    {
                        height += crater.GetHeight(worldX, worldZ);
                    }

                    foreach (var rock in Rocks)
                    {
                        float rockHeight = rock.GetHeight(worldX, worldZ);
                        if (rockHeight > height)
                            height = rockHeight;
                    }

                    TerrainData.heights[x, z] = height;
                }
            }

            GenerateCraters();
            GenerateRocks();
        }

        private float[,] GeneratePerlinNoise()
        {
            float[,] heights = new float[resolution, resolution];
            float maxValue = 0;

            for (int x = 0; x < resolution; x++)
            {
                for (int z = 0; z < resolution; z++)
                {
                    float amplitude = 1;
                    float frequency = 1;
                    float noiseHeight = 0;

                    float worldX = terrainOrigin.x + x * cellSize;
                    float worldZ = terrainOrigin.z + z * cellSize;

                    for (int i = 0; i < noiseOctaves; i++)
                    {
                        float sampleX = worldX * noiseScale * frequency;
                        float sampleZ = worldZ * noiseScale * frequency;

                        float perlin = Mathf.PerlinNoise(sampleX, sampleZ) * 2 - 1;
                        noiseHeight += perlin * amplitude;

                        amplitude *= noisePersistence;
                        frequency *= noiseLacunarity;
                    }

                    heights[x, z] = noiseHeight;
                    maxValue = Mathf.Max(maxValue, Mathf.Abs(noiseHeight));
                }
            }

            if (maxValue > 0)
            {
                for (int x = 0; x < resolution; x++)
                {
                    for (int z = 0; z < resolution; z++)
                    {
                        heights[x, z] /= maxValue;
                    }
                }
            }

            return heights;
        }

        private void GenerateCraters()
        {
            int numCraters = random.Next(minCraters, maxCraters + 1);
            float terrainSize = resolution * cellSize;

            for (int i = 0; i < numCraters; i++)
            {
                float x = terrainOrigin.x + (float)random.NextDouble() * terrainSize;
                float z = terrainOrigin.z + (float)random.NextDouble() * terrainSize;
                float radius = minCraterRadius + (float)random.NextDouble() *
                              (maxCraterRadius - minCraterRadius);
                float depth = minCraterDepth + (float)random.NextDouble() *
                             (maxCraterDepth - minCraterDepth);
                float rimHeight = depth * 0.2f;
                float roughness = 0.2f + (float)random.NextDouble() * 0.3f;

                Vector3 center = new Vector3(x, 0, z);
                Craters.Add(new Crater(center, radius, depth, rimHeight, roughness));
            }
        }

        private void GenerateRocks()
        {
            int numRocks = random.Next(minRocks, maxRocks + 1);
            float terrainSize = resolution * cellSize;

            for (int i = 0; i < numRocks; i++)
            {
                float x = terrainOrigin.x + (float)random.NextDouble() * terrainSize;
                float z = terrainOrigin.z + (float)random.NextDouble() * terrainSize;

                float sizeX = minRockSize + (float)random.NextDouble() *
                             (maxRockSize - minRockSize);
                float sizeY = minRockSize + (float)random.NextDouble() *
                             (maxRockSize - minRockSize);
                float sizeZ = minRockSize + (float)random.NextDouble() *
                             (maxRockSize - minRockSize);

                float height = TerrainData.GetHeight(x, z);
                Vector3 center = new Vector3(x, height + sizeY * 0.3f, z);
                Vector3 size = new Vector3(sizeX, sizeY, sizeZ);
                Quaternion rotation = Quaternion.Euler(
                    (float)random.NextDouble() * 360f,
                    (float)random.NextDouble() * 360f,
                    (float)random.NextDouble() * 360f
                );

                Rocks.Add(new RockObstacle(center, size, rotation));
            }
        }

        private void LoadDEMTerrain()
        {
            if (string.IsNullOrEmpty(demFilePath) || !System.IO.File.Exists(demFilePath))
            {
                Debug.LogWarning("DEM file not found, using random generation.");
                GenerateRandomTerrain();
                return;
            }

            try
            {
                byte[] rawData = System.IO.File.ReadAllBytes(demFilePath);
                int headerSize = 256;

                if (rawData.Length >= headerSize)
                {
                    int width = BitConverter.ToInt32(rawData, 0);
                    int height = BitConverter.ToInt32(rawData, 4);
                    float cellSizeDEM = BitConverter.ToSingle(rawData, 8);

                    int offset = headerSize;

                    for (int x = 0; x < resolution && x < width; x++)
                    {
                        for (int z = 0; z < resolution && z < height; z++)
                        {
                            int idx = offset + (z * width + x) * 4;
                            if (idx + 4 <= rawData.Length)
                            {
                                TerrainData.heights[x, z] = BitConverter.ToSingle(rawData, idx);
                            }
                        }
                    }
                }
            }
            catch (Exception e)
            {
                Debug.LogError($"Failed to load DEM: {e.Message}");
                GenerateRandomTerrain();
            }
        }

        public bool CheckCollision(Ellipsoid ellipsoid, double safetyMargin = 1.0)
        {
            foreach (var rock in Rocks)
            {
                if (ellipsoid.Intersects(rock.collisionEllipsoid, safetyMargin))
                {
                    return true;
                }
            }
            return false;
        }

        public bool CheckCollision(Vector3d point, double radius)
        {
            foreach (var rock in Rocks)
            {
                if (rock.collisionEllipsoid.Distance(point) < radius)
                {
                    return true;
                }
            }
            return false;
        }

        public List<RockObstacle> GetObstaclesInBounds(Bounds bounds)
        {
            List<RockObstacle> result = new List<RockObstacle>();
            foreach (var rock in Rocks)
            {
                Bounds rockBounds = new Bounds(rock.center, rock.size);
                if (bounds.Intersects(rockBounds))
                {
                    result.Add(rock);
                }
            }
            return result;
        }
    }
}
