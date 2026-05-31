using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class VehicleGenerator : MonoBehaviour
    {
        public static VehicleGenerator Instance { get; private set; }

        public List<GameObject> Vehicles { get; private set; } = new List<GameObject>();
        public List<VehicleData> VehicleDataList { get; private set; } = new List<VehicleData>();
        public GameObject PlayerVehicle { get; private set; }

        [SerializeField] private Material[] vehicleMaterials;
        [SerializeField] private Material wheelMaterial;

        private System.Random _random;
        private readonly Color[] _vehicleColors = new Color[]
        {
            Color.red, Color.blue, Color.white, Color.black, Color.gray,
            Color.green, Color.yellow, new Color(0.8f, 0.4f, 0.1f), Color.cyan, Color.magenta
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
            if (vehicleMaterials == null || vehicleMaterials.Length == 0)
            {
                vehicleMaterials = new Material[_vehicleColors.Length];
                for (int i = 0; i < _vehicleColors.Length; i++)
                {
                    vehicleMaterials[i] = new Material(Shader.Find("Standard"));
                    vehicleMaterials[i].color = _vehicleColors[i];
                }
            }
            if (wheelMaterial == null)
            {
                wheelMaterial = new Material(Shader.Find("Standard"));
                wheelMaterial.color = Color.black;
            }
        }

        public void Generate(SceneParameters parameters, Transform root, List<LaneData> lanes, System.Random random)
        {
            _random = random;
            Vehicles.Clear();
            VehicleDataList.Clear();
            PlayerVehicle = null;

            float roadLength = parameters.roadLength;
            float densityFactor = parameters.vehicleDensity;
            int totalLanes = lanes.Count;
            int vehicleCount = Mathf.FloorToInt(totalLanes * roadLength / 50f * densityFactor);

            bool playerCreated = false;

            for (int i = 0; i < vehicleCount; i++)
            {
                var lane = lanes[_random.Next(lanes.Count)];
                if (lane.waypoints.Count < 2) continue;

                int wpIndex = _random.Next(0, Mathf.Max(1, lane.waypoints.Count - 5));
                Vector3 pos = lane.waypoints[wpIndex].ToVector3() + Vector3.up * 0.5f;
                Vector3 nextPos = lane.waypoints[Mathf.Min(wpIndex + 1, lane.waypoints.Count - 1)].ToVector3();
                Quaternion rot = Quaternion.LookRotation((nextPos - pos).normalized);

                VehicleType type = (VehicleType)_random.Next(0, 4);
                Color color = _vehicleColors[_random.Next(_vehicleColors.Length)];

                bool isPlayer = !playerCreated;
                if (isPlayer) playerCreated = true;

                var vehicle = CreateVehicle(root, pos, rot, type, color, parameters, lane.id, isPlayer, wpIndex);
                Vehicles.Add(vehicle);

                var vehicleData = new VehicleData
                {
                    id = vehicle.name,
                    vehicleType = type,
                    position = new Vector3Data(pos),
                    rotation = new Vector3Data(rot.eulerAngles),
                    scale = new Vector3Data(GetVehicleScale(type)),
                    maxSpeed = parameters.maxSpeed * GetSpeedMultiplier(type),
                    currentSpeed = 0,
                    currentLaneId = lane.id,
                    color = new ColorData(color)
                };
                VehicleDataList.Add(vehicleData);

                if (isPlayer)
                {
                    PlayerVehicle = vehicle;
                }
            }

            if (PlayerVehicle == null && Vehicles.Count > 0)
            {
                PlayerVehicle = Vehicles[0];
            }
        }

        private GameObject CreateVehicle(Transform root, Vector3 position, Quaternion rotation,
            VehicleType type, Color color, SceneParameters parameters, string laneId, bool isPlayer, int wpIndex)
        {
            string id = isPlayer ? "Vehicle_Player" : $"Vehicle_{Vehicles.Count}";
            GameObject vehicleObj = new GameObject(id);
            vehicleObj.transform.SetParent(root);
            vehicleObj.transform.position = position;
            vehicleObj.transform.rotation = rotation;

            Vector3 scale = GetVehicleScale(type);

            GameObject body = GameObject.CreatePrimitive(PrimitiveType.Cube);
            body.name = "Body";
            body.transform.SetParent(vehicleObj.transform);
            body.transform.localPosition = new Vector3(0, 0.3f, 0);
            body.transform.localScale = new Vector3(scale.x, 0.6f, scale.z);
            var bodyMat = new Material(vehicleMaterials[0].shader);
            bodyMat.color = color;
            body.GetComponent<MeshRenderer>().material = bodyMat;
            Destroy(body.GetComponent<BoxCollider>());

            GameObject cabin = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cabin.name = "Cabin";
            cabin.transform.SetParent(vehicleObj.transform);
            cabin.transform.localPosition = new Vector3(0, 0.75f, type == VehicleType.Car ? -0.2f : 0);
            cabin.transform.localScale = new Vector3(scale.x * 0.9f, 0.5f, scale.z * (type == VehicleType.Car ? 0.5f : 0.7f));
            var cabinMat = new Material(Shader.Find("Standard"));
            cabinMat.color = new Color(0.3f, 0.6f, 0.8f, 0.7f);
            cabin.GetComponent<MeshRenderer>().material = cabinMat;
            Destroy(cabin.GetComponent<BoxCollider>());

            CreateWheel(vehicleObj.transform, new Vector3(scale.x / 2f - 0.15f, 0.25f, scale.z / 2f - 0.25f));
            CreateWheel(vehicleObj.transform, new Vector3(-scale.x / 2f + 0.15f, 0.25f, scale.z / 2f - 0.25f));
            CreateWheel(vehicleObj.transform, new Vector3(scale.x / 2f - 0.15f, 0.25f, -scale.z / 2f + 0.25f));
            CreateWheel(vehicleObj.transform, new Vector3(-scale.x / 2f + 0.15f, 0.25f, -scale.z / 2f + 0.25f));

            if (type == VehicleType.Truck)
            {
                GameObject cargo = GameObject.CreatePrimitive(PrimitiveType.Cube);
                cargo.name = "Cargo";
                cargo.transform.SetParent(vehicleObj.transform);
                cargo.transform.localPosition = new Vector3(0, 0.6f, -0.8f);
                cargo.transform.localScale = new Vector3(scale.x * 0.9f, 0.8f, scale.z * 0.6f);
                var cargoMat = new Material(Shader.Find("Standard"));
                cargoMat.color = new Color(0.9f, 0.8f, 0.6f);
                cargo.GetComponent<MeshRenderer>().material = cargoMat;
                Destroy(cargo.GetComponent<BoxCollider>());
            }

            Rigidbody rb = vehicleObj.AddComponent<Rigidbody>();
            rb.mass = GetVehicleMass(type);
            rb.drag = 0.5f;
            rb.angularDrag = 2f;
            rb.centerOfMass = new Vector3(0, -0.3f, 0);

            BoxCollider col = vehicleObj.AddComponent<BoxCollider>();
            col.center = new Vector3(0, 0.5f, 0);
            col.size = new Vector3(scale.x, 1.2f, scale.z);

            var ai = vehicleObj.AddComponent<VehicleAIController>();
            ai.Initialize(laneId, wpIndex, parameters, isPlayer);

            if (isPlayer)
            {
                var playerControl = vehicleObj.AddComponent<PlayerVehicleController>();
                playerControl.enabled = false;
            }

            var collisionDetector = vehicleObj.AddComponent<CollisionDetector>();
            collisionDetector.VehicleId = id;

            return vehicleObj;
        }

        private void CreateWheel(Transform parent, Vector3 localPos)
        {
            GameObject wheel = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            wheel.transform.SetParent(parent);
            wheel.transform.localPosition = localPos;
            wheel.transform.localRotation = Quaternion.Euler(0, 0, 90);
            wheel.transform.localScale = new Vector3(0.25f, 0.15f, 0.25f);
            wheel.GetComponent<MeshRenderer>().material = wheelMaterial;
            Destroy(wheel.GetComponent<CapsuleCollider>());
        }

        private Vector3 GetVehicleScale(VehicleType type)
        {
            switch (type)
            {
                case VehicleType.Car: return new Vector3(1.8f, 1.2f, 4.5f);
                case VehicleType.Truck: return new Vector3(2.5f, 1.5f, 8f);
                case VehicleType.Bus: return new Vector3(2.5f, 3f, 12f);
                case VehicleType.Motorcycle: return new Vector3(0.8f, 1.2f, 2.5f);
                default: return new Vector3(1.8f, 1.2f, 4.5f);
            }
        }

        private float GetVehicleMass(VehicleType type)
        {
            switch (type)
            {
                case VehicleType.Car: return 1500f;
                case VehicleType.Truck: return 5000f;
                case VehicleType.Bus: return 8000f;
                case VehicleType.Motorcycle: return 200f;
                default: return 1500f;
            }
        }

        private float GetSpeedMultiplier(VehicleType type)
        {
            switch (type)
            {
                case VehicleType.Car: return 1.0f;
                case VehicleType.Truck: return 0.7f;
                case VehicleType.Bus: return 0.6f;
                case VehicleType.Motorcycle: return 1.2f;
                default: return 1.0f;
            }
        }

        public void TogglePlayerControl(bool enable)
        {
            if (PlayerVehicle == null) return;

            var playerControl = PlayerVehicle.GetComponent<PlayerVehicleController>();
            var aiControl = PlayerVehicle.GetComponent<VehicleAIController>();

            if (playerControl != null)
                playerControl.enabled = enable;
            if (aiControl != null)
                aiControl.enabled = !enable;

            var rb = PlayerVehicle.GetComponent<Rigidbody>();
            if (rb != null)
            {
                if (enable)
                {
                    rb.ResetInertiaTensor();
                }
            }

            SimulationManager.Instance.Log(enable ? "Player control engaged" : "Player control disengaged");
        }
    }
}
