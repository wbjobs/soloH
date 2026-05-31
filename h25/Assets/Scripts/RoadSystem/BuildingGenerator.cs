using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class BuildingGenerator : MonoBehaviour
    {
        public static BuildingGenerator Instance { get; private set; }

        public List<BuildingData> Buildings { get; private set; } = new List<BuildingData>();

        [SerializeField] private Material[] buildingMaterials;
        [SerializeField] private Material windowMaterial;

        private System.Random _random;
        private readonly Color[] _buildingColors = new Color[]
        {
            new Color(0.7f, 0.65f, 0.6f),
            new Color(0.6f, 0.58f, 0.55f),
            new Color(0.5f, 0.45f, 0.42f),
            new Color(0.3f, 0.35f, 0.4f),
            new Color(0.8f, 0.75f, 0.7f),
            new Color(0.55f, 0.52f, 0.48f)
        };

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            EnsureMaterials();
        }

        private void EnsureMaterials()
        {
            if (buildingMaterials == null || buildingMaterials.Length == 0)
            {
                buildingMaterials = new Material[6];
                for (int i = 0; i < 6; i++)
                {
                    buildingMaterials[i] = new Material(Shader.Find("Standard"));
                    buildingMaterials[i].color = _buildingColors[i];
                }
            }
            if (windowMaterial == null)
            {
                windowMaterial = new Material(Shader.Find("Standard"));
                windowMaterial.color = new Color(0.2f, 0.3f, 0.5f);
                windowMaterial.SetFloat("_Glossiness", 0.8f);
            }
        }

        public void Generate(SceneParameters parameters, Transform root, List<RoadSegmentData> roads, System.Random random)
        {
            _random = random;
            Buildings.Clear();

            float halfSize = parameters.roadLength / 2f;
            float cellSize = 25f;
            int cellsPerSide = Mathf.FloorToInt(halfSize * 2f / cellSize);

            for (int x = 0; x < cellsPerSide; x++)
            {
                for (int z = 0; z < cellsPerSide; z++)
                {
                    float worldX = -halfSize + x * cellSize + cellSize / 2f;
                    float worldZ = -halfSize + z * cellSize + cellSize / 2f;

                    if (IsOnRoad(new Vector3(worldX, 0, worldZ), roads, parameters))
                        continue;

                    if (_random.Next(0, 100) > parameters.buildingDensity)
                        continue;

                    CreateBuilding(root, worldX, worldZ, cellSize * 0.8f);
                }
            }
        }

        private bool IsOnRoad(Vector3 position, List<RoadSegmentData> roads, SceneParameters parameters)
        {
            float roadWidth = parameters.lanesPerDirection * 2 * parameters.laneWidth + 2f;
            foreach (var road in roads)
            {
                if (road.roadType == RoadType.Intersection)
                {
                    float size = roadWidth + 6f;
                    if (Mathf.Abs(position.x - road.centerPoint.x) < size &&
                        Mathf.Abs(position.z - road.centerPoint.z) < size)
                        return true;
                }
                else
                {
                    Vector3 start = road.startPoint.ToVector3();
                    Vector3 end = road.endPoint.ToVector3();
                    float dist = DistanceToLineSegment(position, start, end);
                    if (dist < roadWidth)
                        return true;
                }
            }
            return false;
        }

        private float DistanceToLineSegment(Vector3 point, Vector3 lineStart, Vector3 lineEnd)
        {
            Vector3 line = lineEnd - lineStart;
            float lineLength = line.magnitude;
            if (lineLength < 0.001f) return Vector3.Distance(point, lineStart);

            Vector3 dir = line.normalized;
            float t = Mathf.Clamp(Vector3.Dot(point - lineStart, dir), 0, lineLength);
            Vector3 closest = lineStart + dir * t;
            return Vector3.Distance(point, closest);
        }

        private void CreateBuilding(Transform root, float x, float z, float maxSize)
        {
            string id = $"Building_{Buildings.Count}";

            float width = _random.Next(8, (int)(maxSize));
            float depth = _random.Next(8, (int)(maxSize));
            int floors = _random.Next(2, 15);
            float height = floors * 3f;
            float rotation = _random.Next(0, 4) * 90f;

            var buildingData = new BuildingData
            {
                id = id,
                position = new Vector3Data(new Vector3(x, height / 2f, z)),
                scale = new Vector3Data(new Vector3(width, height, depth)),
                rotation = rotation,
                floors = floors
            };
            Buildings.Add(buildingData);

            GameObject buildingObj = new GameObject(id);
            buildingObj.transform.SetParent(root);
            buildingObj.transform.position = buildingData.position.ToVector3();
            buildingObj.transform.rotation = Quaternion.Euler(0, rotation, 0);

            GameObject mainBody = GameObject.CreatePrimitive(PrimitiveType.Cube);
            mainBody.name = "Body";
            mainBody.transform.SetParent(buildingObj.transform);
            mainBody.transform.localPosition = Vector3.zero;
            mainBody.transform.localScale = buildingData.scale.ToVector3();
            mainBody.GetComponent<MeshRenderer>().material = buildingMaterials[_random.Next(buildingMaterials.Length)];
            Destroy(mainBody.GetComponent<BoxCollider>());

            buildingObj.AddComponent<BoxCollider>().center = Vector3.zero;
            buildingObj.GetComponent<BoxCollider>().size = buildingData.scale.ToVector3();

            AddWindows(mainBody, buildingData.scale.ToVector3(), floors);
            AddRoof(buildingObj, width, depth, height);
        }

        private void AddWindows(GameObject body, Vector3 scale, int floors)
        {
            float windowSize = 1.5f;
            float windowSpacing = 2f;
            int windowsPerFloorX = Mathf.Max(1, Mathf.FloorToInt(scale.x / windowSpacing) - 1);
            int windowsPerFloorZ = Mathf.Max(1, Mathf.FloorToInt(scale.z / windowSpacing) - 1);

            for (int floor = 0; floor < floors; floor++)
            {
                float yPos = -scale.y / 2f + 1.5f + floor * 3f;

                for (int wx = 0; wx < windowsPerFloorX; wx++)
                {
                    float xPos = -scale.x / 2f + windowSpacing + wx * windowSpacing;
                    CreateWindow(body, new Vector3(xPos, yPos, scale.z / 2f + 0.01f), new Vector3(windowSize, 1.8f, 0.1f));
                    CreateWindow(body, new Vector3(xPos, yPos, -scale.z / 2f - 0.01f), new Vector3(windowSize, 1.8f, 0.1f));
                }

                for (int wz = 0; wz < windowsPerFloorZ; wz++)
                {
                    float zPos = -scale.z / 2f + windowSpacing + wz * windowSpacing;
                    CreateWindow(body, new Vector3(scale.x / 2f + 0.01f, yPos, zPos), new Vector3(0.1f, 1.8f, windowSize));
                    CreateWindow(body, new Vector3(-scale.x / 2f - 0.01f, yPos, zPos), new Vector3(0.1f, 1.8f, windowSize));
                }
            }
        }

        private void CreateWindow(GameObject parent, Vector3 localPos, Vector3 size)
        {
            GameObject window = GameObject.CreatePrimitive(PrimitiveType.Cube);
            window.transform.SetParent(parent.transform);
            window.transform.localPosition = localPos;
            window.transform.localScale = size;
            window.GetComponent<MeshRenderer>().material = windowMaterial;
            Destroy(window.GetComponent<BoxCollider>());
        }

        private void AddRoof(GameObject building, float width, float depth, float height)
        {
            GameObject roof = GameObject.CreatePrimitive(PrimitiveType.Cube);
            roof.name = "Roof";
            roof.transform.SetParent(building.transform);
            roof.transform.localPosition = new Vector3(0, height / 2f + 0.25f, 0);
            roof.transform.localScale = new Vector3(width + 0.5f, 0.3f, depth + 0.5f);
            roof.GetComponent<MeshRenderer>().material.color = new Color(0.2f, 0.2f, 0.2f);
            Destroy(roof.GetComponent<BoxCollider>());
        }
    }
}
