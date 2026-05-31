using System.Collections.Generic;
using UnityEngine;

namespace SoleFrictionSim.Geometry
{
    public static class MeshProcessor
    {
        public static Mesh WeldVertices(Mesh mesh, float tolerance = 1e-6f)
        {
            var vertices = mesh.vertices;
            var triangles = mesh.triangles;
            var normals = mesh.normals;
            var uvs = mesh.uv;

            var uniqueVertices = new List<Vector3>();
            var uniqueNormals = new List<Vector3>();
            var uniqueUVs = new List<Vector2>();
            var vertexMap = new Dictionary<int, int>();

            for (int i = 0; i < vertices.Length; i++)
            {
                int foundIndex = -1;
                for (int j = 0; j < uniqueVertices.Count; j++)
                {
                    if (Vector3.Distance(vertices[i], uniqueVertices[j]) < tolerance)
                    {
                        foundIndex = j;
                        break;
                    }
                }

                if (foundIndex >= 0)
                {
                    vertexMap[i] = foundIndex;
                }
                else
                {
                    vertexMap[i] = uniqueVertices.Count;
                    uniqueVertices.Add(vertices[i]);
                    uniqueNormals.Add(normals[i]);
                    if (uvs.Length > i) uniqueUVs.Add(uvs[i]);
                }
            }

            var newTriangles = new int[triangles.Length];
            for (int i = 0; i < triangles.Length; i++)
            {
                newTriangles[i] = vertexMap[triangles[i]];
            }

            var result = new Mesh
            {
                indexFormat = uniqueVertices.Count > 65535 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16,
                vertices = uniqueVertices.ToArray(),
                normals = uniqueNormals.ToArray(),
                triangles = newTriangles
            };

            if (uniqueUVs.Count == uniqueVertices.Count)
            {
                result.uv = uniqueUVs.ToArray();
            }

            result.RecalculateBounds();
            result.RecalculateTangents();

            return result;
        }

        public static Mesh SimplifyMesh(Mesh mesh, int targetTriangles)
        {
            var vertices = mesh.vertices;
            var triangles = mesh.triangles;
            var normals = mesh.normals;

            int currentTriCount = triangles.Length / 3;
            if (currentTriCount <= targetTriangles) return mesh;

            int removeCount = currentTriCount - targetTriangles;
            var triangleToRemove = new HashSet<int>();
            var edgeCosts = new Dictionary<long, float>();
            var edgeTriangles = new Dictionary<long, List<int>>();

            for (int i = 0; i < triangles.Length; i += 3)
            {
                for (int j = 0; j < 3; j++)
                {
                    int v1 = triangles[i + j];
                    int v2 = triangles[i + (j + 1) % 3];
                    if (v1 > v2) (v1, v2) = (v2, v1);

                    long key = ((long)v1 << 32) | (uint)v2;
                    if (!edgeCosts.ContainsKey(key))
                    {
                        float cost = Vector3.Distance(vertices[v1], vertices[v2]);
                        edgeCosts[key] = cost;
                        edgeTriangles[key] = new List<int>();
                    }
                    edgeTriangles[key].Add(i / 3);
                }
            }

            var sortedEdges = new List<long>(edgeCosts.Keys);
            sortedEdges.Sort((a, b) => edgeCosts[a].CompareTo(edgeCosts[b]));

            int removed = 0;
            foreach (var edge in sortedEdges)
            {
                if (removed >= removeCount) break;

                var tris = edgeTriangles[edge];
                if (tris.Count != 2) continue;

                bool canRemove = true;
                foreach (var tri in tris)
                {
                    if (triangleToRemove.Contains(tri))
                    {
                        canRemove = false;
                        break;
                    }
                }

                if (canRemove)
                {
                    foreach (var tri in tris)
                    {
                        triangleToRemove.Add(tri);
                        removed++;
                    }
                }
            }

            var newTriangles = new List<int>();
            for (int i = 0; i < triangles.Length; i += 3)
            {
                int triIndex = i / 3;
                if (!triangleToRemove.Contains(triIndex))
                {
                    newTriangles.Add(triangles[i]);
                    newTriangles.Add(triangles[i + 1]);
                    newTriangles.Add(triangles[i + 2]);
                }
            }

            var result = new Mesh
            {
                indexFormat = vertices.Length > 65535 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16,
                vertices = vertices,
                normals = normals,
                triangles = newTriangles.ToArray()
            };

            if (mesh.uv.Length == vertices.Length)
            {
                result.uv = mesh.uv;
            }

            result.RecalculateBounds();
            result.RecalculateNormals();
            result.RecalculateTangents();

            return result;
        }

        public static Mesh FlipNormals(Mesh mesh)
        {
            var normals = mesh.normals;
            for (int i = 0; i < normals.Length; i++)
            {
                normals[i] = -normals[i];
            }

            var triangles = mesh.triangles;
            for (int i = 0; i < triangles.Length; i += 3)
            {
                (triangles[i], triangles[i + 2]) = (triangles[i + 2], triangles[i]);
            }

            mesh.normals = normals;
            mesh.triangles = triangles;
            mesh.RecalculateNormals();

            return mesh;
        }

        public static Mesh SmoothNormals(Mesh mesh, float angleThreshold = 60f)
        {
            var vertices = mesh.vertices;
            var normals = new Vector3[vertices.Length];
            var triangles = mesh.triangles;

            var vertexNormals = new Dictionary<int, List<Vector3>>();

            for (int i = 0; i < vertices.Length; i++)
            {
                vertexNormals[i] = new List<Vector3>();
            }

            for (int i = 0; i < triangles.Length; i += 3)
            {
                int i1 = triangles[i];
                int i2 = triangles[i + 1];
                int i3 = triangles[i + 2];

                Vector3 v1 = vertices[i1];
                Vector3 v2 = vertices[i2];
                Vector3 v3 = vertices[i3];

                Vector3 edge1 = v2 - v1;
                Vector3 edge2 = v3 - v1;
                Vector3 normal = Vector3.Cross(edge1, edge2).normalized;

                vertexNormals[i1].Add(normal);
                vertexNormals[i2].Add(normal);
                vertexNormals[i3].Add(normal);
            }

            float dotThreshold = Mathf.Cos(angleThreshold * Mathf.Deg2Rad);

            for (int i = 0; i < vertices.Length; i++)
            {
                var faceNormals = vertexNormals[i];
                if (faceNormals.Count == 0)
                {
                    normals[i] = Vector3.up;
                    continue;
                }

                Vector3 baseNormal = faceNormals[0];
                Vector3 sum = Vector3.zero;
                int count = 0;

                foreach (var n in faceNormals)
                {
                    if (Vector3.Dot(baseNormal, n) > dotThreshold)
                    {
                        sum += n;
                        count++;
                    }
                }

                normals[i] = count > 0 ? sum.normalized : baseNormal;
            }

            mesh.normals = normals;
            return mesh;
        }

        public static Vector2 CalculateMeshSize(Mesh mesh)
        {
            var bounds = mesh.bounds;
            return new Vector2(bounds.size.x, bounds.size.z);
        }

        public static float CalculateMeshArea(Mesh mesh)
        {
            var vertices = mesh.vertices;
            var triangles = mesh.triangles;

            float area = 0f;
            for (int i = 0; i < triangles.Length; i += 3)
            {
                Vector3 v1 = vertices[triangles[i]];
                Vector3 v2 = vertices[triangles[i + 1]];
                Vector3 v3 = vertices[triangles[i + 2]];

                area += Vector3.Cross(v2 - v1, v3 - v1).magnitude * 0.5f;
            }

            return area;
        }
    }
}
