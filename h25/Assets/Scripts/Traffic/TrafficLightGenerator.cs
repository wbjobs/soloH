using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class TrafficLightGenerator : MonoBehaviour
    {
        public static TrafficLightGenerator Instance { get; private set; }

        public List<TrafficLightData> Lights { get; private set; } = new List<TrafficLightData>();
        public List<TrafficLightController> Controllers { get; private set; } = new List<TrafficLightController>();

        [SerializeField] private Material poleMaterial;
        [SerializeField] private Material housingMaterial;
        [SerializeField] private Material redLightOn;
        [SerializeField] private Material yellowLightOn;
        [SerializeField] private Material greenLightOn;
        [SerializeField] private Material lightOff;

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
            if (poleMaterial == null)
            {
                poleMaterial = new Material(Shader.Find("Standard"));
                poleMaterial.color = new Color(0.2f, 0.2f, 0.2f);
            }
            if (housingMaterial == null)
            {
                housingMaterial = new Material(Shader.Find("Standard"));
                housingMaterial.color = Color.black;
            }
            if (redLightOn == null)
            {
                redLightOn = new Material(Shader.Find("Standard"));
                redLightOn.color = Color.red;
                redLightOn.SetColor("_EmissionColor", Color.red * 0.5f);
            }
            if (yellowLightOn == null)
            {
                yellowLightOn = new Material(Shader.Find("Standard"));
                yellowLightOn.color = Color.yellow;
                yellowLightOn.SetColor("_EmissionColor", Color.yellow * 0.5f);
            }
            if (greenLightOn == null)
            {
                greenLightOn = new Material(Shader.Find("Standard"));
                greenLightOn.color = Color.green;
                greenLightOn.SetColor("_EmissionColor", Color.green * 0.5f);
            }
            if (lightOff == null)
            {
                lightOff = new Material(Shader.Find("Standard"));
                lightOff.color = new Color(0.1f, 0.1f, 0.1f);
            }
        }

        public void Generate(SceneParameters parameters, Transform root, List<RoadSegmentData> roads, System.Random random)
        {
            _random = random;
            Lights.Clear();
            Controllers.Clear();

            foreach (var road in roads)
            {
                if (road.roadType == RoadType.Intersection)
                {
                    CreateIntersectionLights(road, parameters, root);
                }
            }
        }

        private void CreateIntersectionLights(RoadSegmentData intersection, SceneParameters parameters, Transform root)
        {
            Vector3 center = intersection.centerPoint.ToVector3();
            float roadWidth = parameters.lanesPerDirection * 2 * parameters.laneWidth;
            float offset = roadWidth / 2f + 2f;

            var positions = new (Vector3 pos, Vector3 rot)[]
            {
                (new Vector3(-offset, 0, -offset), new Vector3(0, 45, 0)),
                (new Vector3(offset, 0, -offset), new Vector3(0, 135, 0)),
                (new Vector3(offset, 0, offset), new Vector3(0, 225, 0)),
                (new Vector3(-offset, 0, offset), new Vector3(0, 315, 0))
            };

            var intersectionControllers = new List<TrafficLightController>();

            foreach (var (pos, rot) in positions)
            {
                string id = $"TrafficLight_{Lights.Count}";
                var lightData = new TrafficLightData
                {
                    id = id,
                    position = new Vector3Data(pos),
                    rotation = new Vector3Data(rot),
                    controlledRoadId = intersection.id,
                    redDuration = parameters.trafficLightPeriod * 0.5f,
                    yellowDuration = 3f,
                    greenDuration = parameters.trafficLightPeriod * 0.4f
                };
                Lights.Add(lightData);

                var controller = CreateTrafficLight(root, lightData, pos, rot);
                Controllers.Add(controller);
                intersectionControllers.Add(controller);
            }

            for (int i = 0; i < intersectionControllers.Count; i++)
            {
                int orthogonalIndex = (i + 2) % 4;
                intersectionControllers[i].Initialize(lightData, intersectionControllers[orthogonalIndex],
                    redLightOn, yellowLightOn, greenLightOn, lightOff);
            }

            if (intersectionControllers.Count >= 2)
            {
                intersectionControllers[0].SetInitialState(TrafficLightState.Green);
                intersectionControllers[1].SetInitialState(TrafficLightState.Red);
                intersectionControllers[2].SetInitialState(TrafficLightState.Green);
                intersectionControllers[3].SetInitialState(TrafficLightState.Red);
            }
        }

        private TrafficLightController CreateTrafficLight(Transform root, TrafficLightData data, Vector3 position, Vector3 rotation)
        {
            GameObject lightObj = new GameObject(data.id);
            lightObj.transform.SetParent(root);
            lightObj.transform.position = position;
            lightObj.transform.rotation = Quaternion.Euler(rotation);

            GameObject pole = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            pole.transform.SetParent(lightObj.transform);
            pole.transform.localPosition = new Vector3(0, 2f, 0);
            pole.transform.localScale = new Vector3(0.15f, 2f, 0.15f);
            pole.GetComponent<MeshRenderer>().material = poleMaterial;
            Destroy(pole.GetComponent<CapsuleCollider>());

            GameObject arm = GameObject.CreatePrimitive(PrimitiveType.Cube);
            arm.transform.SetParent(lightObj.transform);
            arm.transform.localPosition = new Vector3(0, 3.8f, -1f);
            arm.transform.localScale = new Vector3(0.1f, 0.1f, 2f);
            arm.GetComponent<MeshRenderer>().material = poleMaterial;
            Destroy(arm.GetComponent<BoxCollider>());

            GameObject housing = new GameObject("Housing");
            housing.transform.SetParent(lightObj.transform);
            housing.transform.localPosition = new Vector3(0, 3.8f, -2.2f);
            housing.transform.localScale = Vector3.one;

            GameObject housingBody = GameObject.CreatePrimitive(PrimitiveType.Cube);
            housingBody.transform.SetParent(housing.transform);
            housingBody.transform.localPosition = Vector3.zero;
            housingBody.transform.localScale = new Vector3(0.5f, 1.2f, 0.3f);
            housingBody.GetComponent<MeshRenderer>().material = housingMaterial;
            Destroy(housingBody.GetComponent<BoxCollider>());

            GameObject redLight = CreateLight(housing.transform, new Vector3(0, 0.35f, 0.16f), lightOff);
            GameObject yellowLight = CreateLight(housing.transform, new Vector3(0, 0f, 0.16f), lightOff);
            GameObject greenLight = CreateLight(housing.transform, new Vector3(0, -0.35f, 0.16f), lightOff);

            lightObj.AddComponent<BoxCollider>().center = new Vector3(0, 2.5f, 0);
            lightObj.GetComponent<BoxCollider>().size = new Vector3(0.5f, 5f, 3f);

            var controller = lightObj.AddComponent<TrafficLightController>();
            controller.SetLightReferences(redLight, yellowLight, greenLight);

            return controller;
        }

        private GameObject CreateLight(Transform parent, Vector3 localPos, Material material)
        {
            GameObject light = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            light.transform.SetParent(parent);
            light.transform.localPosition = localPos;
            light.transform.localScale = new Vector3(0.2f, 0.2f, 0.1f);
            light.GetComponent<MeshRenderer>().material = material;
            Destroy(light.GetComponent<SphereCollider>());
            return light;
        }
    }

    public class TrafficLightController : MonoBehaviour
    {
        public TrafficLightState CurrentState { get; private set; }
        public TrafficLightData Data { get; private set; }
        public float TimeRemainingInState { get; private set; }
        public float CurrentStateDuration { get; private set; }

        public event Action<TrafficLightState> OnStateChanged;

        private GameObject _redLight;
        private GameObject _yellowLight;
        private GameObject _greenLight;
        private TrafficLightController _orthogonalLight;
        private Material _redOn;
        private Material _yellowOn;
        private Material _greenOn;
        private Material _lightOff;
        private float _timer;
        private bool _initialized;
        private bool _isAllRed;

        private const float ALL_RED_DURATION = 1.5f;

        public void Initialize(TrafficLightData data, TrafficLightController orthogonal,
            Material redOn, Material yellowOn, Material greenOn, Material lightOff)
        {
            Data = data;
            _orthogonalLight = orthogonal;
            _redOn = redOn;
            _yellowOn = yellowOn;
            _greenOn = greenOn;
            _lightOff = lightOff;
            _initialized = true;
        }

        public void SetLightReferences(GameObject red, GameObject yellow, GameObject green)
        {
            _redLight = red;
            _yellowLight = yellow;
            _greenLight = green;
        }

        public void SetInitialState(TrafficLightState state)
        {
            CurrentState = state;
            UpdateLights();
            _timer = 0f;
            CurrentStateDuration = GetCurrentDuration();
            TimeRemainingInState = CurrentStateDuration;
            _isAllRed = false;
        }

        private void Update()
        {
            if (!_initialized || SimulationManager.Instance == null) return;
            if (SimulationManager.Instance.State != SimulationState.Playing) return;

            _timer += Time.deltaTime;
            TimeRemainingInState = CurrentStateDuration - _timer;

            float duration = _isAllRed ? ALL_RED_DURATION : GetCurrentDuration();
            if (_timer >= duration)
            {
                ChangeState();
            }
        }

        private float GetCurrentDuration()
        {
            switch (CurrentState)
            {
                case TrafficLightState.Red: return Data.redDuration;
                case TrafficLightState.Yellow: return Data.yellowDuration;
                case TrafficLightState.Green: return Data.greenDuration;
                default: return 10f;
            }
        }

        private void ChangeState()
        {
            if (_isAllRed)
            {
                _isAllRed = false;
                SetState(TrafficLightState.Red);
                if (_orthogonalLight != null)
                {
                    _orthogonalLight.RequestGreen();
                }
                _timer = 0f;
                CurrentStateDuration = GetCurrentDuration();
                return;
            }

            switch (CurrentState)
            {
                case TrafficLightState.Green:
                    SetState(TrafficLightState.Yellow);
                    _timer = 0f;
                    CurrentStateDuration = GetCurrentDuration();
                    break;
                case TrafficLightState.Yellow:
                    _isAllRed = true;
                    SetState(TrafficLightState.Red);
                    _timer = 0f;
                    CurrentStateDuration = ALL_RED_DURATION;
                    break;
                case TrafficLightState.Red:
                    break;
            }
        }

        private void RequestGreen()
        {
            if (CurrentState == TrafficLightState.Red && !_isAllRed)
            {
                SetState(TrafficLightState.Green);
                _timer = 0f;
                CurrentStateDuration = GetCurrentDuration();
            }
        }

        private void SetState(TrafficLightState newState)
        {
            if (CurrentState != newState)
            {
                CurrentState = newState;
                UpdateLights();
                OnStateChanged?.Invoke(CurrentState);
            }
        }

        private void UpdateLights()
        {
            _redLight.GetComponent<MeshRenderer>().material = CurrentState == TrafficLightState.Red ? _redOn : _lightOff;
            _yellowLight.GetComponent<MeshRenderer>().material = CurrentState == TrafficLightState.Yellow ? _yellowOn : _lightOff;
            _greenLight.GetComponent<MeshRenderer>().material = CurrentState == TrafficLightState.Green ? _greenOn : _lightOff;
        }

        public bool CanPass()
        {
            return CurrentState == TrafficLightState.Green || CurrentState == TrafficLightState.Yellow;
        }

        public bool CanPass(float vehicleSpeed, float distanceToStopLine)
        {
            if (_isAllRed) return false;

            if (CurrentState == TrafficLightState.Green)
            {
                if (TimeRemainingInState < 1.0f)
                {
                    float stoppingDistance = CalculateStoppingDistance(vehicleSpeed);
                    if (distanceToStopLine < stoppingDistance)
                    {
                        return true;
                    }
                    return false;
                }
                return true;
            }

            if (CurrentState == TrafficLightState.Yellow)
            {
                float stoppingDistance = CalculateStoppingDistance(vehicleSpeed);
                float timeToCross = distanceToStopLine / Mathf.Max(vehicleSpeed, 0.1f);

                if (distanceToStopLine < stoppingDistance)
                {
                    return true;
                }

                if (timeToCross < TimeRemainingInState)
                {
                    return true;
                }

                return false;
            }

            return false;
        }

        private float CalculateStoppingDistance(float speed)
        {
            float deceleration = 8f;
            float reactionTime = 0.5f;
            float reactionDistance = speed * reactionTime;
            float brakingDistance = (speed * speed) / (2f * deceleration);
            return reactionDistance + brakingDistance + 1f;
        }

        public bool IsApproachingRedLight(float vehicleSpeed, float distanceToStopLine)
        {
            if (_isAllRed) return true;

            if (CurrentState == TrafficLightState.Red)
            {
                return distanceToStopLine < 30f;
            }

            if (CurrentState == TrafficLightState.Yellow ||
                (CurrentState == TrafficLightState.Green && TimeRemainingInState < 2.0f))
            {
                float stoppingDistance = CalculateStoppingDistance(vehicleSpeed);
                return distanceToStopLine < stoppingDistance + 10f;
            }

            return false;
        }
    }
}
