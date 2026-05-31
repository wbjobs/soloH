using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class TrafficSignGenerator : MonoBehaviour
    {
        public static TrafficSignGenerator Instance { get; private set; }

        public List<TrafficSignData> Signs { get; private set; } = new List<TrafficSignData>();

        [SerializeField] private Material signMaterial;
        [SerializeField] private Material poleMaterial;

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
            if (signMaterial == null)
            {
                signMaterial = new Material(Shader.Find("Standard"));
            }
            if (poleMaterial == null)
            {
                poleMaterial = new Material(Shader.Find("Standard"));
                poleMaterial.color = new Color(0.3f, 0.3f, 0.3f);
            }
        }

        public void Generate(SceneParameters parameters, Transform root, List<RoadSegmentData> roads, System.Random random)
        {
            _random = random;
            Signs.Clear();

            foreach (var road in roads)
            {
                if (road.roadType == RoadType.Intersection)
                {
                    CreateIntersectionSigns(road, parameters, root);
                }
                else if (road.roadType == RoadType.Straight)
                {
                    CreateRoadSigns(road, parameters, root);
                }
            }
        }

        private void CreateIntersectionSigns(RoadSegmentData intersection, SceneParameters parameters, Transform root)
        {
            Vector3 center = intersection.centerPoint.ToVector3();
            float roadWidth = parameters.lanesPerDirection * 2 * parameters.laneWidth;
            float offset = roadWidth / 2f + 3f;

            CreateSign(root, SignType.Stop, center + new Vector3(-offset, 0, -offset), 45f, null);
            CreateSign(root, SignType.Stop, center + new Vector3(offset, 0, -offset), 135f, null);
            CreateSign(root, SignType.Stop, center + new Vector3(offset, 0, offset), 225f, null);
            CreateSign(root, SignType.Stop, center + new Vector3(-offset, 0, offset), 315f, null);
        }

        private void CreateRoadSigns(RoadSegmentData road, SceneParameters parameters, Transform root)
        {
            Vector3 start = road.startPoint.ToVector3();
            Vector3 end = road.endPoint.ToVector3();
            Vector3 dir = (end - start).normalized;
            Vector3 right = Vector3.Cross(Vector3.up, dir).normalized;
            float roadWidth = parameters.lanesPerDirection * 2 * parameters.laneWidth;
            float length = Vector3.Distance(start, end);

            if (length < 60f) return;

            int signCount = Mathf.FloorToInt(length / 80f);
            for (int i = 0; i < signCount; i++)
            {
                float t = (i + 1) / (float)(signCount + 1);
                Vector3 pos = Vector3.Lerp(start, end, t);

                string speedLimit = Mathf.RoundToInt(parameters.maxSpeed * 3.6f).ToString();
                CreateSign(root, SignType.SpeedLimit, pos + right * (roadWidth / 2f + 2f),
                    Quaternion.LookRotation(-right).eulerAngles.y, speedLimit);

                CreateSign(root, SignType.SpeedLimit, pos - right * (roadWidth / 2f + 2f),
                    Quaternion.LookRotation(right).eulerAngles.y, speedLimit);
            }

            if (length > 100f)
            {
                Vector3 midPos = Vector3.Lerp(start, end, 0.5f);
                CreateSign(root, SignType.PedestrianCrossing, midPos + right * (roadWidth / 2f + 2.5f),
                    Quaternion.LookRotation(-right).eulerAngles.y, null);
            }
        }

        private TrafficSignData CreateSign(Transform root, SignType signType, Vector3 position, float rotationY, string value)
        {
            string id = $"Sign_{Signs.Count}";
            var signData = new TrafficSignData
            {
                id = id,
                signType = signType,
                position = new Vector3Data(position),
                rotation = rotationY,
                value = value
            };
            Signs.Add(signData);

            GameObject signObj = new GameObject(id);
            signObj.transform.SetParent(root);
            signObj.transform.position = position;
            signObj.transform.rotation = Quaternion.Euler(0, rotationY, 0);

            GameObject pole = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            pole.transform.SetParent(signObj.transform);
            pole.transform.localPosition = new Vector3(0, 1.5f, 0);
            pole.transform.localScale = new Vector3(0.1f, 1.5f, 0.1f);
            pole.GetComponent<MeshRenderer>().material = poleMaterial;
            Destroy(pole.GetComponent<CapsuleCollider>());

            GameObject signFace = new GameObject("Face");
            signFace.transform.SetParent(signObj.transform);
            signFace.transform.localPosition = new Vector3(0, 2.8f, 0);

            MeshFilter mf = signFace.AddComponent<MeshFilter>();
            MeshRenderer mr = signFace.AddComponent<MeshRenderer>();

            Mesh mesh = new Mesh();
            Vector3[] vertices;
            int[] triangles;

            switch (signType)
            {
                case SignType.Stop:
                    CreateOctagonMesh(out vertices, out triangles);
                    mr.material = new Material(signMaterial);
                    mr.material.color = Color.red;
                    signFace.transform.localScale = new Vector3(0.8f, 0.8f, 0.05f);
                    break;
                case SignType.SpeedLimit:
                    CreateCircleMesh(out vertices, out triangles);
                    mr.material = new Material(signMaterial);
                    mr.material.color = Color.white;
                    signFace.transform.localScale = new Vector3(0.6f, 0.6f, 0.05f);
                    break;
                case SignType.Yield:
                    CreateTriangleMesh(out vertices, out triangles);
                    mr.material = new Material(signMaterial);
                    mr.material.color = new Color(1f, 0.8f, 0f);
                    signFace.transform.localScale = new Vector3(0.9f, 0.9f, 0.05f);
                    break;
                default:
                    CreateSquareMesh(out vertices, out triangles);
                    mr.material = new Material(signMaterial);
                    mr.material.color = Color.blue;
                    signFace.transform.localScale = new Vector3(0.6f, 0.6f, 0.05f);
                    break;
            }

            mesh.vertices = vertices;
            mesh.triangles = triangles;
            mesh.RecalculateNormals();
            mf.mesh = mesh;

            signObj.AddComponent<BoxCollider>().center = new Vector3(0, 2.8f, 0);
            signObj.GetComponent<BoxCollider>().size = new Vector3(1f, 1f, 1f);

            return signData;
        }

        private void CreateOctagonMesh(out Vector3[] vertices, out int[] triangles)
        {
            vertices = new Vector3[8];
            for (int i = 0; i < 8; i++)
            {
                float angle = i * Mathf.PI * 2f / 8f - Mathf.PI / 8f;
                vertices[i] = new Vector3(Mathf.Cos(angle), Mathf.Sin(angle), 0);
            }
            triangles = new int[] { 0, 1, 2, 0, 2, 3, 0, 3, 4, 0, 4, 5, 0, 5, 6, 0, 6, 7 };
        }

        private void CreateCircleMesh(out Vector3[] vertices, out int[] triangles)
        {
            int segments = 32;
            vertices = new Vector3[segments];
            for (int i = 0; i < segments; i++)
            {
                float angle = i * Mathf.PI * 2f / segments;
                vertices[i] = new Vector3(Mathf.Cos(angle), Mathf.Sin(angle), 0);
            }
            triangles = new int[segments * 3];
            for (int i = 0; i < segments; i++)
            {
                triangles[i * 3] = 0;
                triangles[i * 3 + 1] = i;
                triangles[i * 3 + 2] = (i + 1) % segments;
            }
        }

        private void CreateTriangleMesh(out Vector3[] vertices, out int[] triangles)
        {
            vertices = new Vector3[]
            {
                new Vector3(0, 1, 0),
                new Vector3(-0.866f, -0.5f, 0),
                new Vector3(0.866f, -0.5f, 0)
            };
            triangles = new int[] { 0, 1, 2 };
        }

        private void CreateSquareMesh(out Vector3[] vertices, out int[] triangles)
        {
            vertices = new Vector3[]
            {
                new Vector3(-0.5f, 0.5f, 0),
                new Vector3(0.5f, 0.5f, 0),
                new Vector3(0.5f, -0.5f, 0),
                new Vector3(-0.5f, -0.5f, 0)
            };
            triangles = new int[] { 0, 1, 2, 0, 2, 3 };
        }
    }
}
