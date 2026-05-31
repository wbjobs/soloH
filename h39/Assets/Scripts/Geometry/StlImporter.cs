using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

namespace SoleFrictionSim.Geometry
{
    public class StlImporter
    {
        private struct Facet
        {
            public Vector3 normal;
            public Vector3 v1;
            public Vector3 v2;
            public Vector3 v3;
        }

        public Mesh Import(string filePath)
        {
            if (!File.Exists(filePath))
            {
                throw new FileNotFoundException($"STL file not found: {filePath}");
            }

            byte[] header = new byte[80];
            using (var fs = new FileStream(filePath, FileMode.Open, FileAccess.Read))
            using (var br = new BinaryReader(fs))
            {
                br.Read(header, 0, 80);
                string headerStr = Encoding.ASCII.GetString(header).Trim();

                if (headerStr.StartsWith("solid") && IsBinaryFormat(header, fs))
                {
                    return ImportBinary(br);
                }
                else if (headerStr.StartsWith("solid"))
                {
                    fs.Position = 0;
                    using (var sr = new StreamReader(fs))
                    {
                        return ImportAscii(sr);
                    }
                }
                else
                {
                    return ImportBinary(br);
                }
            }
        }

        private bool IsBinaryFormat(byte[] header, FileStream fs)
        {
            if (fs.Length < 84) return true;

            long pos = fs.Position;
            fs.Position = 80;
            byte[] countBytes = new byte[4];
            fs.Read(countBytes, 0, 4);
            uint facetCount = BitConverter.ToUInt32(countBytes, 0);
            long expectedSize = 84 + facetCount * 50;
            fs.Position = pos;

            return Math.Abs(fs.Length - expectedSize) < 100;
        }

        private Mesh ImportBinary(BinaryReader br)
        {
            uint facetCount = br.ReadUInt32();
            var facets = new List<Facet>((int)facetCount);

            for (int i = 0; i < facetCount; i++)
            {
                var facet = new Facet
                {
                    normal = new Vector3(br.ReadSingle(), br.ReadSingle(), br.ReadSingle()),
                    v1 = new Vector3(br.ReadSingle(), br.ReadSingle(), br.ReadSingle()),
                    v2 = new Vector3(br.ReadSingle(), br.ReadSingle(), br.ReadSingle()),
                    v3 = new Vector3(br.ReadSingle(), br.ReadSingle(), br.ReadSingle())
                };
                br.ReadUInt16();
                facets.Add(facet);
            }

            return BuildMesh(facets);
        }

        private Mesh ImportAscii(StreamReader sr)
        {
            var facets = new List<Facet>();
            string line;
            Facet currentFacet = new Facet();
            int vertexIndex = 0;

            while ((line = sr.ReadLine()) != null)
            {
                line = line.Trim();
                if (line.StartsWith("facet normal"))
                {
                    string[] parts = line.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                    currentFacet.normal = new Vector3(
                        float.Parse(parts[2]),
                        float.Parse(parts[3]),
                        float.Parse(parts[4]));
                    vertexIndex = 0;
                }
                else if (line.StartsWith("vertex"))
                {
                    string[] parts = line.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                    var v = new Vector3(
                        float.Parse(parts[1]),
                        float.Parse(parts[2]),
                        float.Parse(parts[3]));

                    if (vertexIndex == 0) currentFacet.v1 = v;
                    else if (vertexIndex == 1) currentFacet.v2 = v;
                    else currentFacet.v3 = v;
                    vertexIndex++;
                }
                else if (line.StartsWith("endfacet"))
                {
                    facets.Add(currentFacet);
                }
            }

            return BuildMesh(facets);
        }

        private Mesh BuildMesh(List<Facet> facets)
        {
            var vertices = new List<Vector3>(facets.Count * 3);
            var normals = new List<Vector3>(facets.Count * 3);
            var triangles = new List<int>(facets.Count * 3);

            for (int i = 0; i < facets.Count; i++)
            {
                int idx = i * 3;
                vertices.Add(facets[i].v1);
                vertices.Add(facets[i].v2);
                vertices.Add(facets[i].v3);

                normals.Add(facets[i].normal);
                normals.Add(facets[i].normal);
                normals.Add(facets[i].normal);

                triangles.Add(idx);
                triangles.Add(idx + 1);
                triangles.Add(idx + 2);
            }

            var mesh = new Mesh
            {
                indexFormat = vertices.Count > 65535 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16,
                vertices = vertices.ToArray(),
                normals = normals.ToArray(),
                triangles = triangles.ToArray()
            };

            mesh.RecalculateBounds();
            mesh.RecalculateTangents();

            return mesh;
        }

        public bool ValidateMesh(Mesh mesh)
        {
            if (mesh == null) return false;
            if (mesh.vertexCount == 0) return false;
            if (mesh.triangles.Length == 0) return false;

            var bounds = mesh.bounds;
            if (bounds.size.x < 0.001f || bounds.size.y < 0.001f || bounds.size.z < 0.001f)
                return false;

            return true;
        }

        public Mesh NormalizeMesh(Mesh mesh, float targetSize = 0.3f)
        {
            var vertices = mesh.vertices;
            var bounds = mesh.bounds;
            var center = bounds.center;
            float maxDim = Mathf.Max(bounds.size.x, bounds.size.y, bounds.size.z);
            float scale = targetSize / maxDim;

            for (int i = 0; i < vertices.Length; i++)
            {
                vertices[i] = (vertices[i] - center) * scale;
                (vertices[i].x, vertices[i].z) = (vertices[i].z, -vertices[i].x);
            }

            mesh.vertices = vertices;
            mesh.RecalculateBounds();
            mesh.RecalculateNormals();

            return mesh;
        }

        public float[,] ExtractContactHeightField(Mesh mesh, int resolution)
        {
            var vertices = mesh.vertices;
            var bounds = mesh.bounds;

            float[,] heightField = new float[resolution, resolution];
            int[,] sampleCount = new int[resolution, resolution];

            float minX = bounds.min.x;
            float minZ = bounds.min.z;
            float rangeX = bounds.size.x;
            float rangeZ = bounds.size.z;

            for (int i = 0; i < vertices.Length; i++)
            {
                float u = (vertices[i].x - minX) / rangeX;
                float v = (vertices[i].z - minZ) / rangeZ;

                int x = Mathf.Clamp((int)(u * (resolution - 1)), 0, resolution - 1);
                int z = Mathf.Clamp((int)(v * (resolution - 1)), 0, resolution - 1);

                heightField[x, z] += vertices[i].y;
                sampleCount[x, z]++;
            }

            for (int x = 0; x < resolution; x++)
            {
                for (int z = 0; z < resolution; z++)
                {
                    if (sampleCount[x, z] > 0)
                    {
                        heightField[x, z] /= sampleCount[x, z];
                    }
                    else
                    {
                        heightField[x, z] = float.NaN;
                    }
                }
            }

            FillMissingValues(heightField);

            float minY = float.MaxValue;
            for (int x = 0; x < resolution; x++)
                for (int z = 0; z < resolution; z++)
                    if (heightField[x, z] < minY) minY = heightField[x, z];

            for (int x = 0; x < resolution; x++)
                for (int z = 0; z < resolution; z++)
                    heightField[x, z] -= minY;

            return heightField;
        }

        private void FillMissingValues(float[,] data)
        {
            int n = data.GetLength(0);
            int m = data.GetLength(1);

            for (int x = 0; x < n; x++)
            {
                for (int z = 0; z < m; z++)
                {
                    if (float.IsNaN(data[x, z]))
                    {
                        float sum = 0;
                        int count = 0;

                        for (int dx = -1; dx <= 1; dx++)
                        {
                            for (int dz = -1; dz <= 1; dz++)
                            {
                                int nx = x + dx;
                                int nz = z + dz;
                                if (nx >= 0 && nx < n && nz >= 0 && nz < m && !float.IsNaN(data[nx, nz]))
                                {
                                    sum += data[nx, nz];
                                    count++;
                                }
                            }
                        }

                        if (count > 0)
                        {
                            data[x, z] = sum / count;
                        }
                        else
                        {
                            data[x, z] = 0;
                        }
                    }
                }
            }
        }
    }
}
