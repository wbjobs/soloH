using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    [Serializable]
    public enum CornerCaseType
    {
        None,
        FallingObject,
        PedestrianSuddenCrossing,
        SuddenBraking,
        TrafficLightFailure,
        WrongWayVehicle,
        AnimalCrossing,
        DebrisOnRoad,
        ConstructionZone,
        EmergencyVehicle,
        DoorOpening,
        CyclistSwerving,
        BrokenTrafficLight,
        PedestrianChasingBall,
        CarJackknifing
    }

    [Serializable]
    public class CornerCaseEvent
    {
        public string id;
        public CornerCaseType caseType;
        public float triggerTime;
        public Vector3Data position;
        public Vector3Data rotation;
        public float duration;
        public bool isActive;
        public string description;
        public Dictionary<string, string> parameters;
    }

    [Serializable]
    public class CornerCaseConfig
    {
        [Range(0f, 1f)] public float eventProbability = 0.3f;
        [Range(5f, 120f)] public float minInterval = 15f;
        [Range(10f, 300f)] public float maxInterval = 60f;
        public List<CornerCaseType> enabledCases = new List<CornerCaseType>();
        public int maxConcurrentEvents = 2;
    }

    public class CornerCaseGenerator : MonoBehaviour
    {
        public static CornerCaseGenerator Instance { get; private set; }

        [SerializeField] private CornerCaseConfig config = new CornerCaseConfig();

        private List<CornerCaseEvent> _activeEvents = new List<CornerCaseEvent>();
        private List<CornerCaseEvent> _eventHistory = new List<CornerCaseEvent>();
        private System.Random _random;
        private float _nextEventTime;
        private Transform _eventsRoot;
        private bool _isInitialized;

        private GameObject _currentFallingObject;
        private PedestrianAIController _suddenPedestrian;
        private VehicleAIController _wrongWayVehicle;
        private GameObject _roadDebris;
        private GameObject _emergencyVehicle;
        private Dictionary<CornerCaseType, Func<CornerCaseEvent, bool>> _eventHandlers;

        public event Action<CornerCaseEvent> OnEventTriggered;
        public event Action<CornerCaseEvent> OnEventEnded;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            InitializeHandlers();
            InitializeDefaultConfig();
        }

        private void InitializeDefaultConfig()
        {
            if (config.enabledCases.Count == 0)
            {
                config.enabledCases.AddRange(new[]
                {
                    CornerCaseType.FallingObject,
                    CornerCaseType.PedestrianSuddenCrossing,
                    CornerCaseType.SuddenBraking,
                    CornerCaseType.DebrisOnRoad,
                    CornerCaseType.DoorOpening,
                    CornerCaseType.PedestrianChasingBall
                });
            }
        }

        private void InitializeHandlers()
        {
            _eventHandlers = new Dictionary<CornerCaseType, Func<CornerCaseEvent, bool>>
            {
                { CornerCaseType.FallingObject, HandleFallingObject },
                { CornerCaseType.PedestrianSuddenCrossing, HandlePedestrianCrossing },
                { CornerCaseType.SuddenBraking, HandleSuddenBraking },
                { CornerCaseType.TrafficLightFailure, HandleTrafficLightFailure },
                { CornerCaseType.WrongWayVehicle, HandleWrongWayVehicle },
                { CornerCaseType.AnimalCrossing, HandleAnimalCrossing },
                { CornerCaseType.DebrisOnRoad, HandleDebrisOnRoad },
                { CornerCaseType.ConstructionZone, HandleConstructionZone },
                { CornerCaseType.EmergencyVehicle, HandleEmergencyVehicle },
                { CornerCaseType.DoorOpening, HandleDoorOpening },
                { CornerCaseType.CyclistSwerving, HandleCyclistSwerving },
                { CornerCaseType.BrokenTrafficLight, HandleBrokenTrafficLight },
                { CornerCaseType.PedestrianChasingBall, HandlePedestrianChasingBall },
                { CornerCaseType.CarJackknifing, HandleCarJackknifing }
            };
        }

        public void Initialize(System.Random random, Transform root)
        {
            _random = random;
            _eventsRoot = new GameObject("CornerCases").transform;
            _eventsRoot.SetParent(root);
            _nextEventTime = Time.time + config.minInterval;
            _isInitialized = true;
        }

        private void Update()
        {
            if (!_isInitialized || SimulationManager.Instance == null) return;
            if (SimulationManager.Instance.State != SimulationState.Playing) return;

            if (_random == null) return;

            UpdateActiveEvents();

            if (Time.time >= _nextEventTime && _activeEvents.Count < config.maxConcurrentEvents)
            {
                if ((float)_random.NextDouble() < config.eventProbability)
                {
                    TriggerRandomEvent();
                }
                _nextEventTime = Time.time + Mathf.Lerp(config.minInterval, config.maxInterval, (float)_random.NextDouble());
            }
        }

        private void UpdateActiveEvents()
        {
            for (int i = _activeEvents.Count - 1; i >= 0; i--)
            {
                var ev = _activeEvents[i];
                if (Time.time >= ev.triggerTime + ev.duration)
                {
                    EndEvent(ev);
                    _activeEvents.RemoveAt(i);
                }
            }
        }

        public void TriggerRandomEvent()
        {
            if (config.enabledCases.Count == 0) return;

            int idx = _random.Next(config.enabledCases.Count);
            var caseType = config.enabledCases[idx];
            TriggerEvent(caseType);
        }

        public CornerCaseEvent TriggerEvent(CornerCaseType caseType)
        {
            if (!_isInitialized)
            {
                Debug.LogWarning("CornerCaseGenerator not initialized!");
                return null;
            }

            var eventData = CreateEventData(caseType);

            if (_eventHandlers.TryGetValue(caseType, out var handler))
            {
                bool success = handler(eventData);
                if (!success)
                {
                    Debug.LogWarning($"Failed to trigger corner case: {caseType}");
                    return null;
                }
            }

            eventData.isActive = true;
            _activeEvents.Add(eventData);
            _eventHistory.Add(eventData);

            OnEventTriggered?.Invoke(eventData);
            SimulationManager.Instance?.Log($"Corner Case Triggered: {caseType} - {eventData.description}");

            return eventData;
        }

        private CornerCaseEvent CreateEventData(CornerCaseType type)
        {
            var position = GetRandomEventPosition();
            string id = $"CornerCase_{_eventHistory.Count}_{type}";

            return new CornerCaseEvent
            {
                id = id,
                caseType = type,
                triggerTime = Time.time,
                position = new Vector3Data(position),
                rotation = new Vector3Data(Vector3.zero),
                duration = GetDurationForCase(type),
                isActive = false,
                description = GetDescriptionForCase(type),
                parameters = new Dictionary<string, string>()
            };
        }

        private Vector3 GetRandomEventPosition()
        {
            var vehicles = FindObjectsOfType<VehicleAIController>();
            if (vehicles.Length > 0)
            {
                var vehicle = vehicles[_random.Next(vehicles.Length)];
                return vehicle.transform.position + vehicle.transform.forward * (_random.Next(20, 80));
            }
            return Vector3.zero;
        }

        private float GetDurationForCase(CornerCaseType type)
        {
            switch (type)
            {
                case CornerCaseType.FallingObject: return 8f;
                case CornerCaseType.PedestrianSuddenCrossing: return 10f;
                case CornerCaseType.SuddenBraking: return 5f;
                case CornerCaseType.DebrisOnRoad: return 30f;
                case CornerCaseType.EmergencyVehicle: return 15f;
                case CornerCaseType.PedestrianChasingBall: return 12f;
                default: return 10f;
            }
        }

        private string GetDescriptionForCase(CornerCaseType type)
        {
            switch (type)
            {
                case CornerCaseType.FallingObject: return "Objects falling from overpass ahead";
                case CornerCaseType.PedestrianSuddenCrossing: return "Pedestrian suddenly crossing road";
                case CornerCaseType.SuddenBraking: return "Vehicle ahead brakes suddenly";
                case CornerCaseType.DebrisOnRoad: return "Debris detected on road ahead";
                case CornerCaseType.DoorOpening: return "Parked car door opening";
                case CornerCaseType.PedestrianChasingBall: return "Child chasing ball into street";
                default: return type.ToString();
            }
        }

        private bool HandleFallingObject(CornerCaseEvent ev)
        {
            _currentFallingObject = GameObject.CreatePrimitive(PrimitiveType.Cube);
            _currentFallingObject.name = "FallingCrate";
            _currentFallingObject.transform.position = ev.position.ToVector3() + Vector3.up * 15f;
            _currentFallingObject.transform.localScale = new Vector3(1.5f, 1.5f, 1.5f);
            _currentFallingObject.transform.SetParent(_eventsRoot);

            var rb = _currentFallingObject.AddComponent<Rigidbody>();
            rb.mass = 50f;
            rb.velocity = Vector3.down * 5f;

            var renderer = _currentFallingObject.GetComponent<MeshRenderer>();
            var mat = new Material(Shader.Find("Standard"));
            mat.color = new Color(0.6f, 0.4f, 0.2f);
            renderer.material = mat;

            ev.parameters["objectType"] = "Crate";
            ev.parameters["mass"] = "50kg";
            return true;
        }

        private bool HandlePedestrianCrossing(CornerCaseEvent ev)
        {
            Vector3 spawnPos = ev.position.ToVector3() + Vector3.right * 10f;
            Vector3 targetPos = ev.position.ToVector3() + Vector3.left * 10f;

            var pedestrianObj = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            pedestrianObj.name = "SuddenPedestrian";
            pedestrianObj.transform.position = spawnPos;
            pedestrianObj.transform.localScale = new Vector3(0.5f, 1f, 0.5f);
            pedestrianObj.transform.SetParent(_eventsRoot);

            var ai = pedestrianObj.AddComponent<PedestrianAIController>();
            var path = new List<Vector3Data>
            {
                new Vector3Data(spawnPos),
                new Vector3Data(targetPos)
            };
            ai.Initialize(path, 4f);

            _suddenPedestrian = ai;

            var collider = pedestrianObj.GetComponent<CapsuleCollider>();
            collider.isTrigger = false;

            ev.parameters["pedestrianSpeed"] = "4m/s";
            ev.parameters["crossingTime"] = "5s";
            return true;
        }

        private bool HandleSuddenBraking(CornerCaseEvent ev)
        {
            var vehicles = FindObjectsOfType<VehicleAIController>();
            if (vehicles.Length < 2) return false;

            VehicleAIController targetVehicle = null;
            float maxSpeed = 0f;

            foreach (var v in vehicles)
            {
                if (v.CurrentSpeed > maxSpeed && v.CurrentSpeed > 5f)
                {
                    maxSpeed = v.CurrentSpeed;
                    targetVehicle = v;
                }
            }

            if (targetVehicle == null) return false;

            var brakeForceMethod = targetVehicle.GetType().GetMethod("ApplyEmergencyBrake",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);

            if (brakeForceMethod != null)
            {
                brakeForceMethod.Invoke(targetVehicle, new object[] { 3f });
            }
            else
            {
                var speedField = targetVehicle.GetType().GetField("_currentSpeed",
                    System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                speedField?.SetValue(targetVehicle, 0f);
            }

            ev.position = new Vector3Data(targetVehicle.transform.position);
            ev.parameters["targetVehicle"] = targetVehicle.name;
            ev.parameters["deceleration"] = "8m/s²";
            return true;
        }

        private bool HandleDebrisOnRoad(CornerCaseEvent ev)
        {
            _roadDebris = new GameObject("RoadDebris");
            _roadDebris.transform.position = ev.position.ToVector3();
            _roadDebris.transform.SetParent(_eventsRoot);

            int debrisCount = _random.Next(3, 8);
            for (int i = 0; i < debrisCount; i++)
            {
                var piece = GameObject.CreatePrimitive(PrimitiveType.Cube);
                piece.transform.SetParent(_roadDebris.transform);
                piece.transform.localPosition = new Vector3(
                    (float)(_random.NextDouble() - 0.5) * 4f,
                    0.1f,
                    (float)(_random.NextDouble() - 0.5) * 6f);
                piece.transform.localScale = new Vector3(
                    0.3f + (float)_random.NextDouble() * 0.5f,
                    0.2f,
                    0.3f + (float)_random.NextDouble() * 0.5f);
                piece.transform.rotation = Quaternion.Euler(0, (float)_random.NextDouble() * 360f, 0);

                var renderer = piece.GetComponent<MeshRenderer>();
                var mat = new Material(Shader.Find("Standard"));
                mat.color = new Color(0.3f, 0.3f, 0.35f);
                renderer.material = mat;

                var rb = piece.AddComponent<Rigidbody>();
                rb.mass = 5f;
            }

            ev.parameters["debrisCount"] = debrisCount.ToString();
            ev.parameters["obstacleLength"] = "6m";
            return true;
        }

        private bool HandleDoorOpening(CornerCaseEvent ev)
        {
            var doorObj = GameObject.CreatePrimitive(PrimitiveType.Cube);
            doorObj.name = "OpenDoor";
            doorObj.transform.position = ev.position.ToVector3() + transform.right * 2f;
            doorObj.transform.localScale = new Vector3(0.1f, 1.2f, 1f);
            doorObj.transform.rotation = Quaternion.Euler(0, 45f, 0);
            doorObj.transform.SetParent(_eventsRoot);

            var renderer = doorObj.GetComponent<MeshRenderer>();
            var mat = new Material(Shader.Find("Standard"));
            mat.color = Color.red;
            renderer.material = mat;

            ev.parameters["side"] = "Right";
            ev.parameters["openingAngle"] = "45°";
            return true;
        }

        private bool HandlePedestrianChasingBall(CornerCaseEvent ev)
        {
            Vector3 spawnPos = ev.position.ToVector3() + Vector3.right * 15f;

            var ball = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            ball.name = "Ball";
            ball.transform.position = spawnPos;
            ball.transform.localScale = new Vector3(0.3f, 0.3f, 0.3f);
            ball.transform.SetParent(_eventsRoot);
            var ballRb = ball.AddComponent<Rigidbody>();
            ballRb.velocity = -transform.right * 6f + Vector3.up * 2f;

            var childObj = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            childObj.name = "Child";
            childObj.transform.position = spawnPos + Vector3.right * 3f;
            childObj.transform.localScale = new Vector3(0.4f, 0.8f, 0.4f);
            childObj.transform.SetParent(_eventsRoot);

            var childAI = childObj.AddComponent<PedestrianAIController>();
            var path = new List<Vector3Data>
            {
                new Vector3Data(spawnPos + Vector3.right * 3f),
                new Vector3Data(ev.position.ToVector3() + Vector3.left * 5f)
            };
            childAI.Initialize(path, 5f);

            ev.parameters["childAge"] = "7";
            ev.parameters["ballSpeed"] = "6m/s";
            return true;
        }

        private bool HandleTrafficLightFailure(CornerCaseEvent ev)
        {
            ev.parameters["intersection"] = "N/A";
            return true;
        }

        private bool HandleWrongWayVehicle(CornerCaseEvent ev)
        {
            ev.parameters["speed"] = "40km/h";
            return true;
        }

        private bool HandleAnimalCrossing(CornerCaseEvent ev)
        {
            ev.parameters["animalType"] = "Deer";
            return true;
        }

        private bool HandleConstructionZone(CornerCaseEvent ev)
        {
            ev.parameters["zoneLength"] = "50m";
            return true;
        }

        private bool HandleEmergencyVehicle(CornerCaseEvent ev)
        {
            ev.parameters["type"] = "Ambulance";
            return true;
        }

        private bool HandleCyclistSwerving(CornerCaseEvent ev)
        {
            ev.parameters["swerveDistance"] = "1.5m";
            return true;
        }

        private bool HandleBrokenTrafficLight(CornerCaseEvent ev)
        {
            ev.parameters["state"] = "FlashingRed";
            return true;
        }

        private bool HandleCarJackknifing(CornerCaseEvent ev)
        {
            ev.parameters["vehicleType"] = "Truck";
            return true;
        }

        private void EndEvent(CornerCaseEvent ev)
        {
            ev.isActive = false;

            switch (ev.caseType)
            {
                case CornerCaseType.FallingObject:
                    if (_currentFallingObject != null)
                        Destroy(_currentFallingObject, 2f);
                    break;
                case CornerCaseType.PedestrianSuddenCrossing:
                case CornerCaseType.PedestrianChasingBall:
                    if (_suddenPedestrian != null)
                        Destroy(_suddenPedestrian.gameObject, 2f);
                    break;
                case CornerCaseType.DebrisOnRoad:
                    if (_roadDebris != null)
                        Destroy(_roadDebris, 5f);
                    break;
                case CornerCaseType.DoorOpening:
                    var doors = _eventsRoot.Find("OpenDoor");
                    if (doors != null) Destroy(doors.gameObject);
                    break;
            }

            OnEventEnded?.Invoke(ev);
            SimulationManager.Instance?.Log($"Corner Case Ended: {ev.caseType}");
        }

        public void ClearAllEvents()
        {
            foreach (var ev in _activeEvents)
            {
                EndEvent(ev);
            }
            _activeEvents.Clear();

            if (_eventsRoot != null)
            {
                for (int i = _eventsRoot.childCount - 1; i >= 0; i--)
                {
                    Destroy(_eventsRoot.GetChild(i).gameObject);
                }
            }
        }

        public void ResetGenerator()
        {
            ClearAllEvents();
            _eventHistory.Clear();
            _nextEventTime = Time.time + config.minInterval;
        }

        public List<CornerCaseEvent> GetActiveEvents()
        {
            return new List<CornerCaseEvent>(_activeEvents);
        }

        public List<CornerCaseEvent> GetEventHistory()
        {
            return new List<CornerCaseEvent>(_eventHistory);
        }

        public CornerCaseConfig GetConfig()
        {
            return config;
        }

        public void SetConfig(CornerCaseConfig newConfig)
        {
            config = newConfig;
        }

        public float GetTimeUntilNextEvent()
        {
            return Mathf.Max(0, _nextEventTime - Time.time);
        }
    }
}
