using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;

namespace LanderSim.Terrain
{
    public class TerrainVisualizer : MonoBehaviour
    {
        public TerrainGenerator terrainGenerator;
        public Material terrainMaterial;

        public bool showCraters = true;
        public bool showRocks = true;
        public bool showTerrainMesh = true;

        private GameObject terrainMeshObject;
        private Mesh terrainMesh;
        private List<GameObject> rockObjects;

        public void Initialize(TerrainGenerator generator, Material material = null)
        {
            terrainGenerator = generator;
            terrainMaterial = material;
            rockObjects = new List<GameObject>();
        }

        public void Visualize()
        {
            if (terrainGenerator == null || terrainGenerator.TerrainData == null) return;

            ClearVisualization();

            if (showTerrainMesh)
            {
                CreateTerrainMesh();
            }

            if (showRocks && terrainGenerator.Rocks != null)
            {
                CreateRockMeshes();
            }

            if (showCraters && terrainGenerator.Craters != null)
            {
                UpdateTerrainWithCraters();
            }
        }

        private void CreateTerrainMesh()
        {
            TerrainData data = terrainGenerator.TerrainData;

            terrainMeshObject = new GameObject("TerrainMesh");
            terrainMeshObject.transform.parent = transform;
            terrainMeshObject.transform.position = data.origin;

            MeshFilter meshFilter = terrainMeshObject.AddComponent<MeshFilter>();
            MeshRenderer meshRenderer = terrainMeshObject.AddComponent<MeshRenderer>();
            MeshCollider meshCollider = terrainMeshObject.AddComponent<MeshCollider>();

            terrainMesh = new Mesh();
            terrainMesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;

            int vertexCount = data.resolutionX * data.resolutionZ;
            Vector3[] vertices = new Vector3[vertexCount];
            Vector3[] normals = new Vector3[vertexCount];
            Vector2[] uvs = new Vector2[vertexCount];
            int[] triangles = new int[(data.resolutionX - 1) * (data.resolutionZ - 1) * 6];

            for (int x = 0; x < data.resolutionX; x++)
            {
                for (int z = 0; z < data.resolutionZ; z++)
                {
                    int idx = z * data.resolutionX + x;
                    float height = data.heights[x, z];

                    vertices[idx] = new Vector3(
                        x * data.cellSize,
                        height - data.origin.y,
                        z * data.cellSize
                    );

                    Vector3d normal = data.GetNormal(x, z);
                    normals[idx] = normal.ToVector3();

                    uvs[idx] = new Vector2(
                        (float)x / data.resolutionX,
                        (float)z / data.resolutionZ
                    );
                }
            }

            int triIndex = 0;
            for (int x = 0; x < data.resolutionX - 1; x++)
            {
                for (int z = 0; z < data.resolutionZ - 1; z++)
                {
                    int idx = z * data.resolutionX + x;
                    int idxRight = idx + 1;
                    int idxUp = idx + data.resolutionX;
                    int idxUpRight = idxUp + 1;

                    triangles[triIndex++] = idx;
                    triangles[triIndex++] = idxUp;
                    triangles[triIndex++] = idxRight;

                    triangles[triIndex++] = idxRight;
                    triangles[triIndex++] = idxUp;
                    triangles[triIndex++] = idxUpRight;
                }
            }

            terrainMesh.vertices = vertices;
            terrainMesh.normals = normals;
            terrainMesh.uv = uvs;
            terrainMesh.triangles = triangles;
            terrainMesh.RecalculateBounds();

            meshFilter.mesh = terrainMesh;
            meshCollider.sharedMesh = terrainMesh;

            if (terrainMaterial != null)
            {
                meshRenderer.material = terrainMaterial;
            }
            else
            {
                Material defaultMat = new Material(Shader.Find("Standard"));
                defaultMat.color = new Color(0.7f, 0.65f, 0.55f);
                meshRenderer.material = defaultMat;
            }
        }

        private void CreateRockMeshes()
        {
            Material rockMaterial = new Material(Shader.Find("Standard"));
            rockMaterial.color = new Color(0.4f, 0.35f, 0.3f);

            foreach (var rock in terrainGenerator.Rocks)
            {
                GameObject rockObj = GameObject.CreatePrimitive(PrimitiveType.Cube);
                rockObj.name = "Rock";
                rockObj.transform.parent = transform;
                rockObj.transform.position = rock.center;
                rockObj.transform.rotation = rock.rotation;
                rockObj.transform.localScale = rock.size;

                Renderer renderer = rockObj.GetComponent<Renderer>();
                renderer.material = rockMaterial;

                rockObjects.Add(rockObj);
            }
        }

        private void UpdateTerrainWithCraters()
        {
            if (terrainMesh == null) return;

            Vector3[] vertices = terrainMesh.vertices;
            TerrainData data = terrainGenerator.TerrainData;

            for (int x = 0; x < data.resolutionX; x++)
            {
                for (int z = 0; z < data.resolutionZ; z++)
                {
                    int idx = z * data.resolutionX + x;
                    Vector3 worldPos = new Vector3(
                        data.origin.x + x * data.cellSize,
                        0,
                        data.origin.z + z * data.cellSize
                    );

                    float craterOffset = 0;
                    foreach (var crater in terrainGenerator.Craters)
                    {
                        craterOffset += crater.GetHeight(worldPos.x, worldPos.z);
                    }

                    vertices[idx].y = data.heights[x, z] - data.origin.y + craterOffset;
                }
            }

            terrainMesh.vertices = vertices;
            terrainMesh.RecalculateNormals();
            terrainMesh.RecalculateBounds();
        }

        public void SetTerrainMaterial(Material material)
        {
            terrainMaterial = material;
            if (terrainMeshObject != null)
            {
                MeshRenderer renderer = terrainMeshObject.GetComponent<MeshRenderer>();
                if (renderer != null)
                {
                    renderer.material = material;
                }
            }
        }

        public void ToggleTerrainMesh(bool show)
        {
            showTerrainMesh = show;
            if (terrainMeshObject != null)
            {
                terrainMeshObject.SetActive(show);
            }
        }

        public void ToggleRocks(bool show)
        {
            showRocks = show;
            foreach (var rock in rockObjects)
            {
                if (rock != null)
                {
                    rock.SetActive(show);
                }
            }
        }

        public void ClearVisualization()
        {
            if (terrainMeshObject != null)
            {
                Destroy(terrainMeshObject);
            }

            foreach (var rock in rockObjects)
            {
                if (rock != null)
                {
                    Destroy(rock);
                }
            }

            rockObjects.Clear();

            if (terrainMesh != null)
            {
                Destroy(terrainMesh);
            }
        }

        public void Cleanup()
        {
            ClearVisualization();
        }

        void OnDestroy()
        {
            Cleanup();
        }
    }
}
