using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class PedestrianGenerator : MonoBehaviour
    {
        public static PedestrianGenerator Instance { get; private set; }

        public List<GameObject> Pedestrians { get; private set; } = new List<GameObject>();
        public List<PedestrianData> PedestrianDataList { get; private set; } = new List<PedestrianData>();

        [SerializeField] private Material[] clothingMaterials;

        private System.Random _random;
        private readonly Color[] _skinColors = new Color[]
        {
            new Color(0.95f, 0.82f, 0.68f),
            new Color(0.85f, 0.65f, 0.5f),
            new Color(0.6f, 0.45f, 0.35f),
            new Color(0.9f, 0.75f, 0.6f),
            new Color(0.5f, 0.35f, 0.25f)
        };

        private readonly Color[] _clothingColors = new Color[]
        {
            Color.red, Color.blue, Color.green, Color.gray, Color.black,
            Color.yellow, Color.cyan, Color.magenta, Color.white, new Color(0.6f, 0.3f, 0.1f)
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
            if (clothingMaterials == null || clothingMaterials.Length == 0)
            {
                clothingMaterials = new Material[_clothingColors.Length];
                for (int i = 0; i < _clothingColors.Length; i++)
                {
                    clothingMaterials[i] = new Material(Shader.Find("Standard"));
                    clothingMaterials[i].color = _clothingColors[i];
                }
            }
        }

        public void Generate(SceneParameters parameters, Transform root, List<RoadSegmentData> roads, System.Random random)
        {
            _random = random;
            Pedestrians.Clear();
            PedestrianDataList.Clear();

            for (int i = 0; i < parameters.pedestrianCount; i++)
            {
                CreatePedestrian(root, roads, parameters);
            }
        }

        private void CreatePedestrian(Transform root, List<RoadSegmentData> roads, SceneParameters parameters)
        {
            string id = $"Pedestrian_{Pedestrians.Count}";

            var sidewalkPoints = FindSidewalkPosition(roads);
            if (sidewalkPoints.Count < 2) return;

            Vector3 startPos = sidewalkPoints[0];
            Vector3 endPos = sidewalkPoints[sidewalkPoints.Count - 1];

            var path = GenerateRandomPath(sidewalkPoints);

            float walkingSpeed = _random.Next(80, 150) / 100f;

            Color skinColor = _skinColors[_random.Next(_skinColors.Length)];
            Color clothingColor = _clothingColors[_random.Next(_clothingColors.Length)];

            GameObject pedObj = new GameObject(id);
            pedObj.transform.SetParent(root);
            pedObj.transform.position = startPos;
            pedObj.transform.rotation = Quaternion.LookRotation((path[1] - path[0]).normalized);

            CreatePedestrianMesh(pedObj.transform, skinColor, clothingColor);

            CapsuleCollider col = pedObj.AddComponent<CapsuleCollider>();
            col.height = 1.8f;
            col.center = new Vector3(0, 0.9f, 0);
            col.radius = 0.25f;

            Rigidbody rb = pedObj.AddComponent<Rigidbody>();
            rb.mass = 70f;
            rb.freezeRotation = true;
            rb.drag = 2f;

            var ai = pedObj.AddComponent<PedestrianAIController>();
            ai.Initialize(path, walkingSpeed, skinColor, clothingColor);

            Pedestrians.Add(pedObj);

            var pedData = new PedestrianData
            {
                id = id,
                position = new Vector3Data(startPos),
                rotation = new Vector3Data(pedObj.transform.rotation.eulerAngles),
                walkingSpeed = walkingSpeed,
                path = ConvertToVector3DataList(path)
            };
            PedestrianDataList.Add(pedData);
        }

        private List<Vector3> FindSidewalkPosition(List<RoadSegmentData> roads)
        {
            var points = new List<Vector3>();
            var validRoads = roads.FindAll(r => r.roadType == RoadType.Straight && r.centerLinePoints.Count > 3);
            if (validRoads.Count == 0) return points;

            var road = validRoads[_random.Next(validRoads.Count)];
            var centerPoints = road.centerLinePoints;
            Vector3 forward = (centerPoints[1].ToVector3() - centerPoints[0].ToVector3()).normalized;
            Vector3 right = Vector3.Cross(Vector3.up, forward).normalized;

            float totalWidth = road.lanesPerDirection * 2 * road.laneWidth;
            float sidewalkOffset = totalWidth / 2f + 1f;
            float side = _random.Next(0, 2) == 0 ? 1 : -1;

            int startIdx = _random.Next(0, Mathf.Max(1, centerPoints.Count - 5));
            int endIdx = Mathf.Min(startIdx + _random.Next(5, 10), centerPoints.Count - 1);

            for (int i = startIdx; i <= endIdx; i++)
            {
                Vector3 p = centerPoints[i].ToVector3() + right * sidewalkOffset * side;
                p.y = 0.1f;
                points.Add(p);
            }
            return points;
        }

        private List<Vector3> GenerateRandomPath(List<Vector3> basePoints)
        {
            if (basePoints.Count < 2) return basePoints;

            var path = new List<Vector3>(basePoints);
            float wanderAmount = 0.5f;

            for (int i = 0; i < path.Count; i++)
            {
                Vector3 pos = path[i];
                Vector3 dir = Vector3.zero;
                if (i > 0) dir = (path[i] - path[i - 1]).normalized;
                Vector3 perp = Vector3.Cross(Vector3.up, dir).normalized;

                float offset = (float)(_random.NextDouble() - 0.5) * wanderAmount;
                path[i] = pos + perp * offset;
            }

            return path;
        }

        private void CreatePedestrianMesh(Transform parent, Color skinColor, Color clothingColor)
        {
            GameObject body = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            body.name = "Body";
            body.transform.SetParent(parent);
            body.transform.localPosition = new Vector3(0, 0.9f, 0);
            body.transform.localScale = new Vector3(0.4f, 0.8f, 0.4f);
            var bodyMat = new Material(Shader.Find("Standard"));
            bodyMat.color = clothingColor;
            body.GetComponent<MeshRenderer>().material = bodyMat;
            Destroy(body.GetComponent<CapsuleCollider>());

            GameObject head = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            head.name = "Head";
            head.transform.SetParent(parent);
            head.transform.localPosition = new Vector3(0, 1.7f, 0);
            head.transform.localScale = new Vector3(0.25f, 0.25f, 0.25f);
            var headMat = new Material(Shader.Find("Standard"));
            headMat.color = skinColor;
            head.GetComponent<MeshRenderer>().material = headMat;
            Destroy(head.GetComponent<SphereCollider>());

            GameObject armL = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            armL.name = "ArmL";
            armL.transform.SetParent(parent);
            armL.transform.localPosition = new Vector3(-0.3f, 1.1f, 0);
            armL.transform.localScale = new Vector3(0.12f, 0.5f, 0.12f);
            armL.transform.rotation = Quaternion.Euler(0, 0, 30);
            armL.GetComponent<MeshRenderer>().material = bodyMat;
            Destroy(armL.GetComponent<CapsuleCollider>());

            GameObject armR = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            armR.name = "ArmR";
            armR.transform.SetParent(parent);
            armR.transform.localPosition = new Vector3(0.3f, 1.1f, 0);
            armR.transform.localScale = new Vector3(0.12f, 0.5f, 0.12f);
            armR.transform.rotation = Quaternion.Euler(0, 0, -30);
            armR.GetComponent<MeshRenderer>().material = bodyMat;
            Destroy(armR.GetComponent<CapsuleCollider>());
        }

        private List<Vector3Data> ConvertToVector3DataList(List<Vector3> vectors)
        {
            var result = new List<Vector3Data>();
            foreach (var v in vectors)
            {
                result.Add(new Vector3Data(v));
            }
            return result;
        }
    }
}
