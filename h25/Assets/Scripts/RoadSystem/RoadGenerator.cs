using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class RoadGenerator : MonoBehaviour
    {
        public static RoadGenerator Instance { get; private set; }

        public List<RoadSegmentData> Roads { get; private set; } = new List<RoadSegmentData>();
        public List<LaneData> Lanes { get; private set; } = new List<LaneData>();

        [SerializeField] private Material roadMaterial;
        [SerializeField] private Material laneMarkingMaterial;
        [SerializeField] private Material sidewalkMaterial;

        private System.Random _random;

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
            if (roadMaterial == null)
            {
                roadMaterial = new Material(Shader.Find("Standard"));
                roadMaterial.color = new Color(0.2f, 0.2f, 0.2f);
            }
            if (laneMarkingMaterial == null)
            {
                laneMarkingMaterial = new Material(Shader.Find("Standard"));
                laneMarkingMaterial.color = Color.white;
                laneMarkingMaterial.SetFloat("_Glossiness", 0f);
            }
            if (sidewalkMaterial == null)
            {
                sidewalkMaterial = new Material(Shader.Find("Standard"));
                sidewalkMaterial.color = new Color(0.6f, 0.6f, 0.6f);
            }
        }

        public void Generate(SceneParameters parameters, Transform root, System.Random random)
        {
            _random = random;
            Roads.Clear();
            Lanes.Clear();

            GenerateGridRoads(parameters, root);
            GenerateLanes(parameters);
            GenerateIntersections(parameters, root);
        }

        private void GenerateGridRoads(SceneParameters parameters, Transform root)
        {
            int gridSize = Mathf.Clamp(Mathf.RoundToInt(parameters.roadLength / 50f), 2, 6);
            float spacing = parameters.roadLength / gridSize;
            float halfSize = (gridSize * spacing) / 2f;

            for (int i = 0; i <= gridSize; i++)
            {
                float zPos = -halfSize + i * spacing;
                CreateRoadSegment(
                    new Vector3(-halfSize, 0, zPos),
                    new Vector3(halfSize, 0, zPos),
                    parameters,
                    RoadType.Straight,
                    root,
                    $"Road_H_{i}"
                );
            }

            for (int i = 0; i <= gridSize; i++)
            {
                float xPos = -halfSize + i * spacing;
                CreateRoadSegment(
                    new Vector3(xPos, 0, -halfSize),
                    new Vector3(xPos, 0, halfSize),
                    parameters,
                    RoadType.Straight,
                    root,
                    $"Road_V_{i}"
                );
            }

            if (parameters.curvature > 0.1f)
            {
                AddCurvedRoads(parameters, root, halfSize, spacing);
            }
        }

        private void CreateRoadSegment(Vector3 start, Vector3 end, SceneParameters parameters,
            RoadType roadType, Transform root, string id)
        {
            var roadData = new RoadSegmentData
            {
                id = id,
                startPoint = new Vector3Data(start),
                endPoint = new Vector3Data(end),
                centerPoint = new Vector3Data((start + end) / 2f),
                lanesPerDirection = parameters.lanesPerDirection,
                laneWidth = parameters.laneWidth,
                roadType = roadType,
                curvature = parameters.curvature,
                centerLinePoints = GenerateCenterLinePoints(start, end, parameters.curvature)
            };
            Roads.Add(roadData);
            CreateRoadMesh(roadData, parameters, root);
            CreateSidewalks(roadData, parameters, root);
        }

        private List<Vector3Data> GenerateCenterLinePoints(Vector3 start, Vector3 end, float curvature)
        {
            var points = new List<Vector3Data>();
            int segments = Mathf.CeilToInt(Vector3.Distance(start, end) / 2f);
            Vector3 dir = (end - start).normalized;
            Vector3 perp = Vector3.Cross(Vector3.up, dir).normalized;

            for (int i = 0; i <= segments; i++)
            {
                float t = (float)i / segments;
                Vector3 pos = Vector3.Lerp(start, end, t);
                if (curvature > 0.01f)
                {
                    float curveAmount = Mathf.Sin(t * Mathf.PI) * curvature * 10f;
                    pos += perp * curveAmount;
                }
                points.Add(new Vector3Data(pos));
            }
            return points;
        }

        private void CreateRoadMesh(RoadSegmentData road, SceneParameters parameters, Transform root)
        {
            GameObject roadObj = new GameObject(road.id);
            roadObj.transform.SetParent(root);

            float totalWidth = parameters.lanesPerDirection * 2 * parameters.laneWidth;

            var meshFilter = roadObj.AddComponent<MeshFilter>();
            var meshRenderer = roadObj.AddComponent<MeshRenderer>();
            meshRenderer.material = roadMaterial;

            var mesh = new Mesh();
            var vertices = new List<Vector3>();
            var triangles = new List<int>();
            var uvs = new List<Vector2>();

            var points = road.centerLinePoints;
            Vector3 forward = Vector3.forward;

            for (int i = 0; i < points.Count; i++)
            {
                Vector3 p = points[i].ToVector3();
                if (i < points.Count - 1)
                {
                    forward = (points[i + 1].ToVector3() - p).normalized;
                }
                Vector3 right = Vector3.Cross(Vector3.up, forward).normalized;

                vertices.Add(p - right * totalWidth / 2f);
                vertices.Add(p + right * totalWidth / 2f);

                uvs.Add(new Vector2((float)i / points.Count, 0));
                uvs.Add(new Vector2((float)i / points.Count, 1));
            }

            for (int i = 0; i < points.Count - 1; i++)
            {
                int baseIndex = i * 2;
                triangles.Add(baseIndex);
                triangles.Add(baseIndex + 2);
                triangles.Add(baseIndex + 1);
                triangles.Add(baseIndex + 1);
                triangles.Add(baseIndex + 2);
                triangles.Add(baseIndex + 3);
            }

            mesh.vertices = vertices.ToArray();
            mesh.triangles = triangles.ToArray();
            mesh.uv = uvs.ToArray();
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();

            meshFilter.mesh = mesh;

            roadObj.AddComponent<MeshCollider>().sharedMesh = mesh;
            CreateLaneMarkings(road, parameters, root);
        }

        private void CreateLaneMarkings(RoadSegmentData road, SceneParameters parameters, Transform root)
        {
            int totalLanes = parameters.lanesPerDirection * 2;
            float totalWidth = totalLanes * parameters.laneWidth;

            var points = road.centerLinePoints;

            for (int lane = 1; lane < totalLanes; lane++)
            {
                GameObject markingObj = new GameObject($"{road.id}_LaneMarking_{lane}");
                markingObj.transform.SetParent(root);
                markingObj.transform.position = new Vector3(0, 0.02f, 0);

                var meshFilter = markingObj.AddComponent<MeshFilter>();
                var meshRenderer = markingObj.AddComponent<MeshRenderer>();
                meshRenderer.material = laneMarkingMaterial;

                var mesh = new Mesh();
                var vertices = new List<Vector3>();
                var triangles = new List<int>();

                float laneOffset = -totalWidth / 2f + lane * parameters.laneWidth;
                bool isDashed = lane != parameters.lanesPerDirection;
                Vector3 forward = Vector3.forward;

                for (int i = 0; i < points.Count; i++)
                {
                    Vector3 p = points[i].ToVector3();
                    if (i < points.Count - 1)
                    {
                        forward = (points[i + 1].ToVector3() - p).normalized;
                    }
                    Vector3 right = Vector3.Cross(Vector3.up, forward).normalized;
                    Vector3 lanePos = p + right * laneOffset;

                    if (isDashed)
                    {
                        float segLength = 2f;
                        float gapLength = 2f;
                        float distFromStart = i * 2f;
                        float cyclePos = distFromStart % (segLength + gapLength);
                        if (cyclePos < segLength)
                        {
                            vertices.Add(lanePos - right * 0.05f + Vector3.up * 0.02f);
                            vertices.Add(lanePos + right * 0.05f + Vector3.up * 0.02f);
                        }
                    }
                    else
                    {
                        vertices.Add(lanePos - right * 0.05f + Vector3.up * 0.02f);
                        vertices.Add(lanePos + right * 0.05f + Vector3.up * 0.02f);
                    }
                }

                for (int i = 0; i < vertices.Count - 2; i += 2)
                {
                    triangles.Add(i);
                    triangles.Add(i + 2);
                    triangles.Add(i + 1);
                    triangles.Add(i + 1);
                    triangles.Add(i + 2);
                    triangles.Add(i + 3);
                }

                mesh.vertices = vertices.ToArray();
                mesh.triangles = triangles.ToArray();
                mesh.RecalculateNormals();
                meshFilter.mesh = mesh;
            }
        }

        private void CreateSidewalks(RoadSegmentData road, SceneParameters parameters, Transform root)
        {
            float totalWidth = parameters.lanesPerDirection * 2 * parameters.laneWidth;
            float sidewalkWidth = 2f;
            var points = road.centerLinePoints;

            CreateSidewalkSide(road, parameters, root, points, totalWidth / 2f, sidewalkWidth, "Left");
            CreateSidewalkSide(road, parameters, root, points, -totalWidth / 2f, -sidewalkWidth, "Right");
        }

        private void CreateSidewalkSide(RoadSegmentData road, SceneParameters parameters, Transform root,
            List<Vector3Data> points, float startOffset, float endOffset, string side)
        {
            GameObject sidewalkObj = new GameObject($"{road.id}_Sidewalk_{side}");
            sidewalkObj.transform.SetParent(root);

            var meshFilter = sidewalkObj.AddComponent<MeshFilter>();
            var meshRenderer = sidewalkObj.AddComponent<MeshRenderer>();
            meshRenderer.material = sidewalkMaterial;

            var mesh = new Mesh();
            var vertices = new List<Vector3>();
            var triangles = new List<int>();

            Vector3 forward = Vector3.forward;

            for (int i = 0; i < points.Count; i++)
            {
                Vector3 p = points[i].ToVector3();
                if (i < points.Count - 1)
                {
                    forward = (points[i + 1].ToVector3() - p).normalized;
                }
                Vector3 right = Vector3.Cross(Vector3.up, forward).normalized;

                vertices.Add(p + right * startOffset + Vector3.up * 0.05f);
                vertices.Add(p + right * (startOffset + endOffset) + Vector3.up * 0.05f);
            }

            for (int i = 0; i < points.Count - 1; i++)
            {
                int baseIndex = i * 2;
                triangles.Add(baseIndex);
                triangles.Add(baseIndex + 2);
                triangles.Add(baseIndex + 1);
                triangles.Add(baseIndex + 1);
                triangles.Add(baseIndex + 2);
                triangles.Add(baseIndex + 3);
            }

            mesh.vertices = vertices.ToArray();
            mesh.triangles = triangles.ToArray();
            mesh.RecalculateNormals();
            meshFilter.mesh = mesh;
        }

        private void GenerateLanes(SceneParameters parameters)
        {
            Lanes.Clear();

            foreach (var road in Roads)
            {
                int totalLanes = parameters.lanesPerDirection * 2;
                float totalWidth = totalLanes * parameters.laneWidth;
                var centerPoints = road.centerLinePoints;

                for (int laneIndex = 0; laneIndex < totalLanes; laneIndex++)
                {
                    var lane = new LaneData
                    {
                        id = $"{road.id}_Lane_{laneIndex}",
                        roadId = road.id,
                        laneIndex = laneIndex,
                        direction = laneIndex < parameters.lanesPerDirection ? LaneDirection.Backward : LaneDirection.Forward,
                        waypoints = new List<Vector3Data>()
                    };

                    float laneOffset = -totalWidth / 2f + (laneIndex + 0.5f) * parameters.laneWidth;
                    Vector3 forward = Vector3.forward;

                    for (int i = 0; i < centerPoints.Count; i++)
                    {
                        Vector3 p = centerPoints[i].ToVector3();
                        if (i < centerPoints.Count - 1)
                        {
                            forward = (centerPoints[i + 1].ToVector3() - p).normalized;
                        }
                        Vector3 right = Vector3.Cross(Vector3.up, forward).normalized;
                        var wp = lane.direction == LaneDirection.Forward ? i : centerPoints.Count - 1 - i;
                        Vector3 lanePos = centerPoints[wp].ToVector3() + right * laneOffset;
                        lane.waypoints.Add(new Vector3Data(lanePos));
                    }
                    Lanes.Add(lane);
                }
            }
        }

        private void GenerateIntersections(SceneParameters parameters, Transform root)
        {
            float halfSize = (Mathf.CeilToInt(parameters.roadLength / 50f) * (parameters.roadLength / Mathf.CeilToInt(parameters.roadLength / 50f))) / 2f;
            float spacing = parameters.roadLength / Mathf.CeilToInt(parameters.roadLength / 50f);
            int gridSize = Mathf.CeilToInt(parameters.roadLength / 50f);

            for (int x = 1; x < gridSize; x++)
            {
                for (int z = 1; z < gridSize; z++)
                {
                    float xPos = -halfSize + x * spacing;
                    float zPos = -halfSize + z * spacing;

                    var road = new RoadSegmentData
                    {
                        id = $"Intersection_{x}_{z}",
                        startPoint = new Vector3Data(new Vector3(xPos, 0, zPos)),
                        endPoint = new Vector3Data(new Vector3(xPos, 0, zPos)),
                        centerPoint = new Vector3Data(new Vector3(xPos, 0, zPos)),
                        lanesPerDirection = parameters.lanesPerDirection,
                        laneWidth = parameters.laneWidth,
                        roadType = RoadType.Intersection,
                        centerLinePoints = new List<Vector3Data> { new Vector3Data(new Vector3(xPos, 0, zPos)) }
                    };
                    Roads.Add(road);

                    CreateIntersectionMesh(new Vector3(xPos, 0, zPos), parameters, root, road.id);
                }
            }
        }

        private void CreateIntersectionMesh(Vector3 center, SceneParameters parameters, Transform root, string id)
        {
            GameObject intersectionObj = new GameObject(id);
            intersectionObj.transform.SetParent(root);
            intersectionObj.transform.position = center;

            float roadWidth = parameters.lanesPerDirection * 2 * parameters.laneWidth;
            float size = roadWidth + 4f;

            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cube.transform.SetParent(intersectionObj.transform);
            cube.transform.localPosition = new Vector3(0, -0.05f, 0);
            cube.transform.localScale = new Vector3(size, 0.1f, size);
            cube.GetComponent<MeshRenderer>().material = roadMaterial;
            Destroy(cube.GetComponent<BoxCollider>());

            intersectionObj.AddComponent<BoxCollider>().center = new Vector3(0, -0.05f, 0);
            intersectionObj.GetComponent<BoxCollider>().size = new Vector3(size, 0.1f, size);
        }

        private void AddCurvedRoads(SceneParameters parameters, Transform root, float halfSize, float spacing)
        {
            int curvedCount = Mathf.RoundToInt(parameters.curvature * 3);
            for (int i = 0; i < curvedCount; i++)
            {
                float startX = -halfSize + (i + 0.5f) * spacing;
                float startZ = -halfSize;
                float endX = halfSize - (i + 0.5f) * spacing;
                float endZ = halfSize;

                CreateRoadSegment(
                    new Vector3(startX, 0, startZ),
                    new Vector3(endX, 0, endZ),
                    parameters,
                    RoadType.Curved,
                    root,
                    $"Road_Curved_{i}"
                );
            }
        }

        public LaneData GetRandomLane(LaneDirection direction)
        {
            var matchingLanes = Lanes.FindAll(l => l.direction == direction && l.waypoints.Count > 2);
            if (matchingLanes.Count == 0) return null;
            return matchingLanes[_random.Next(matchingLanes.Count)];
        }

        public LaneData GetLaneById(string id)
        {
            return Lanes.Find(l => l.id == id);
        }
    }
}
