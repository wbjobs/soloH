using System;
using System.Collections.Generic;
using UnityEngine;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.Geometry
{
    public class PatternGenerator
    {
        private readonly System.Random _random = new System.Random(42);

        public Mesh Generate(PatternConfig config)
        {
            return config.patternType switch
            {
                PatternType.Herringbone => GenerateHerringbone(config),
                PatternType.Wave => GenerateWave(config),
                PatternType.Block => GenerateBlock(config),
                _ => GenerateHerringbone(config)
            };
        }

        public float[,] GetHeightField(PatternConfig config, int resolution)
        {
            float[,] heightField = new float[resolution, resolution];
            float width = config.soleWidth * 0.01f;
            float length = config.soleLength * 0.01f;
            float depth = config.patternDepth * 0.001f;
            float spacing = config.patternSpacing * 0.001f;
            float angleRad = config.patternAngle * Mathf.Deg2Rad;

            Func<float, float, float> heightFunc = config.patternType switch
            {
                PatternType.Herringbone => (x, z) => HerringboneHeight(x, z, depth, spacing, angleRad),
                PatternType.Wave => (x, z) => WaveHeight(x, z, depth, spacing, angleRad),
                PatternType.Block => (x, z) => BlockHeight(x, z, depth, spacing),
                _ => (x, z) => HerringboneHeight(x, z, depth, spacing, angleRad)
            };

            float soleAspect = width / length;

            for (int i = 0; i < resolution; i++)
            {
                for (int j = 0; j < resolution; j++)
                {
                    float u = (float)i / (resolution - 1);
                    float v = (float)j / (resolution - 1);

                    float x = (u - 0.5f) * width;
                    float z = (v - 0.5f) * length;

                    float mask = SoleMask(u, v, soleAspect);
                    float h = heightFunc(x, z) * mask;

                    heightField[i, j] = Mathf.Max(0, h);
                }
            }

            return heightField;
        }

        private Mesh GenerateHerringbone(PatternConfig config)
        {
            int res = config.meshResolution;
            var vertices = new List<Vector3>(res * res);
            var triangles = new List<int>((res - 1) * (res - 1) * 6);
            var normals = new List<Vector3>(res * res);
            var uvs = new List<Vector2>(res * res);

            float width = config.soleWidth * 0.01f;
            float length = config.soleLength * 0.01f;
            float depth = config.patternDepth * 0.001f;
            float spacing = config.patternSpacing * 0.001f;
            float angleRad = config.patternAngle * Mathf.Deg2Rad;
            float soleAspect = width / length;

            for (int i = 0; i < res; i++)
            {
                for (int j = 0; j < res; j++)
                {
                    float u = (float)i / (res - 1);
                    float v = (float)j / (res - 1);

                    float x = (u - 0.5f) * width;
                    float z = (v - 0.5f) * length;

                    float mask = SoleMask(u, v, soleAspect);
                    float h = HerringboneHeight(x, z, depth, spacing, angleRad) * mask;
                    h = Mathf.Max(0, h);

                    vertices.Add(new Vector3(x, h, z));
                    uvs.Add(new Vector2(u, v));
                    normals.Add(Vector3.up);
                }
            }

            for (int i = 0; i < res - 1; i++)
            {
                for (int j = 0; j < res - 1; j++)
                {
                    int idx = i * res + j;
                    triangles.Add(idx);
                    triangles.Add(idx + res);
                    triangles.Add(idx + 1);
                    triangles.Add(idx + 1);
                    triangles.Add(idx + res);
                    triangles.Add(idx + res + 1);
                }
            }

            var mesh = new Mesh
            {
                indexFormat = res * res > 65535 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16,
                vertices = vertices.ToArray(),
                triangles = triangles.ToArray(),
                uv = uvs.ToArray()
            };

            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            mesh.RecalculateTangents();

            return mesh;
        }

        private Mesh GenerateWave(PatternConfig config)
        {
            int res = config.meshResolution;
            var vertices = new List<Vector3>(res * res);
            var triangles = new List<int>((res - 1) * (res - 1) * 6);
            var normals = new List<Vector3>(res * res);
            var uvs = new List<Vector2>(res * res);

            float width = config.soleWidth * 0.01f;
            float length = config.soleLength * 0.01f;
            float depth = config.patternDepth * 0.001f;
            float spacing = config.patternSpacing * 0.001f;
            float angleRad = config.patternAngle * Mathf.Deg2Rad;
            float soleAspect = width / length;

            for (int i = 0; i < res; i++)
            {
                for (int j = 0; j < res; j++)
                {
                    float u = (float)i / (res - 1);
                    float v = (float)j / (res - 1);

                    float x = (u - 0.5f) * width;
                    float z = (v - 0.5f) * length;

                    float mask = SoleMask(u, v, soleAspect);
                    float h = WaveHeight(x, z, depth, spacing, angleRad) * mask;
                    h = Mathf.Max(0, h);

                    vertices.Add(new Vector3(x, h, z));
                    uvs.Add(new Vector2(u, v));
                    normals.Add(Vector3.up);
                }
            }

            for (int i = 0; i < res - 1; i++)
            {
                for (int j = 0; j < res - 1; j++)
                {
                    int idx = i * res + j;
                    triangles.Add(idx);
                    triangles.Add(idx + res);
                    triangles.Add(idx + 1);
                    triangles.Add(idx + 1);
                    triangles.Add(idx + res);
                    triangles.Add(idx + res + 1);
                }
            }

            var mesh = new Mesh
            {
                indexFormat = res * res > 65535 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16,
                vertices = vertices.ToArray(),
                triangles = triangles.ToArray(),
                uv = uvs.ToArray()
            };

            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            mesh.RecalculateTangents();

            return mesh;
        }

        private Mesh GenerateBlock(PatternConfig config)
        {
            int res = config.meshResolution;
            var vertices = new List<Vector3>(res * res);
            var triangles = new List<int>((res - 1) * (res - 1) * 6);
            var normals = new List<Vector3>(res * res);
            var uvs = new List<Vector2>(res * res);

            float width = config.soleWidth * 0.01f;
            float length = config.soleLength * 0.01f;
            float depth = config.patternDepth * 0.001f;
            float spacing = config.patternSpacing * 0.001f;
            float soleAspect = width / length;

            for (int i = 0; i < res; i++)
            {
                for (int j = 0; j < res; j++)
                {
                    float u = (float)i / (res - 1);
                    float v = (float)j / (res - 1);

                    float x = (u - 0.5f) * width;
                    float z = (v - 0.5f) * length;

                    float mask = SoleMask(u, v, soleAspect);
                    float h = BlockHeight(x, z, depth, spacing) * mask;
                    h = Mathf.Max(0, h);

                    vertices.Add(new Vector3(x, h, z));
                    uvs.Add(new Vector2(u, v));
                    normals.Add(Vector3.up);
                }
            }

            for (int i = 0; i < res - 1; i++)
            {
                for (int j = 0; j < res - 1; j++)
                {
                    int idx = i * res + j;
                    triangles.Add(idx);
                    triangles.Add(idx + res);
                    triangles.Add(idx + 1);
                    triangles.Add(idx + 1);
                    triangles.Add(idx + res);
                    triangles.Add(idx + res + 1);
                }
            }

            var mesh = new Mesh
            {
                indexFormat = res * res > 65535 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16,
                vertices = vertices.ToArray(),
                triangles = triangles.ToArray(),
                uv = uvs.ToArray()
            };

            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            mesh.RecalculateTangents();

            return mesh;
        }

        private float HerringboneHeight(float x, float z, float depth, float spacing, float angle)
        {
            float cosA = Mathf.Cos(angle);
            float sinA = Mathf.Sin(angle);

            float proj1 = x * cosA + z * sinA;
            float proj2 = x * cosA - z * sinA;

            float stripe1 = Mathf.Abs(Mathf.Repeat(proj1, spacing) - spacing * 0.5f);
            float stripe2 = Mathf.Abs(Mathf.Repeat(proj2, spacing) - spacing * 0.5f);

            float grooveWidth = spacing * 0.3f;
            float groove1 = stripe1 < grooveWidth * 0.5f ? 1f : 0f;
            float groove2 = stripe2 < grooveWidth * 0.5f ? 1f : 0f;

            float groove = Mathf.Max(groove1, groove2);
            return depth * (1f - groove);
        }

        private float WaveHeight(float x, float z, float depth, float spacing, float angle)
        {
            float cosA = Mathf.Cos(angle);
            float sinA = Mathf.Sin(angle);

            float proj = x * cosA + z * sinA;
            float wave = Mathf.Sin(2f * Mathf.PI * proj / spacing);

            float grooveWidth = spacing * 0.3f;
            float groove = wave > Mathf.Cos(Mathf.PI * grooveWidth / spacing) ? 1f : 0f;

            return depth * (1f - groove);
        }

        private float BlockHeight(float x, float z, float depth, float spacing)
        {
            float grooveWidth = spacing * 0.25f;

            float gx = Mathf.Abs(Mathf.Repeat(x, spacing) - spacing * 0.5f);
            float gz = Mathf.Abs(Mathf.Repeat(z, spacing) - spacing * 0.5f);

            float grooveX = gx < grooveWidth * 0.5f ? 1f : 0f;
            float grooveZ = gz < grooveWidth * 0.5f ? 1f : 0f;

            float groove = Mathf.Max(grooveX, grooveZ);
            return depth * (1f - groove);
        }

        private float SoleMask(float u, float v, float aspect)
        {
            u = (u - 0.5f) * 2f;
            v = (v - 0.5f) * 2f;

            float x = u;
            float y = v * aspect;

            float r = Mathf.Sqrt(x * x + y * y);

            float toeAngle = Mathf.Atan2(y, x);
            float heelAngle = Mathf.Atan2(y, -x);

            float toeWidth = 0.9f * Mathf.Cos(toeAngle * 0.5f);
            float heelWidth = 0.85f * Mathf.Cos(heelAngle * 0.5f);

            float maxR = x > 0 ? toeWidth : heelWidth;

            float edgeWidth = 0.05f;
            if (r < maxR - edgeWidth) return 1f;
            if (r < maxR) return 1f - (r - (maxR - edgeWidth)) / edgeWidth;
            return 0f;
        }

        public Mesh AddRoughness(Mesh mesh, RubberMaterial material, float amplitude = 0.0001f)
        {
            var vertices = mesh.vertices;
            var normals = mesh.normals;

            for (int i = 0; i < vertices.Length; i++)
            {
                float noise = (float)(_random.NextDouble() * 2.0 - 1.0);
                vertices[i] += normals[i] * noise * amplitude;
            }

            mesh.vertices = vertices;
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();

            return mesh;
        }
    }
}
