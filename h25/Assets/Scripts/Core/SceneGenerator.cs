using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class SceneGenerator : MonoBehaviour
    {
        public static SceneGenerator Instance { get; private set; }

        [SerializeField] private Transform sceneRoot;
        [SerializeField] private Transform roadsRoot;
        [SerializeField] private Transform buildingsRoot;
        [SerializeField] private Transform vehiclesRoot;
        [SerializeField] private Transform pedestriansRoot;
        [SerializeField] private Transform signsRoot;
        [SerializeField] private Transform lightsRoot;

        public List<RoadSegmentData> Roads { get; private set; } = new List<RoadSegmentData>();
        public List<LaneData> Lanes { get; private set; } = new List<LaneData>();
        public List<BuildingData> Buildings { get; private set; } = new List<BuildingData>();
        public List<GameObject> VehicleObjects { get; private set; } = new List<GameObject>();
        public List<GameObject> PedestrianObjects { get; private set; } = new List<GameObject>();
        public List<TrafficSignData> TrafficSigns { get; private set; } = new List<TrafficSignData>();
        public List<TrafficLightData> TrafficLights { get; private set; } = new List<TrafficLightData>();

        public Bounds WorldBounds { get; private set; }

        private System.Random _random;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            EnsureRoots();
        }

        private void EnsureRoots()
        {
            if (sceneRoot == null)
            {
                sceneRoot = new GameObject("Scene").transform;
                sceneRoot.SetParent(transform);
            }
            roadsRoot = CreateChild(sceneRoot, "Roads");
            buildingsRoot = CreateChild(sceneRoot, "Buildings");
            vehiclesRoot = CreateChild(sceneRoot, "Vehicles");
            pedestriansRoot = CreateChild(sceneRoot, "Pedestrians");
            signsRoot = CreateChild(sceneRoot, "Signs");
            lightsRoot = CreateChild(sceneRoot, "TrafficLights");
        }

        private Transform CreateChild(Transform parent, string name)
        {
            var child = new GameObject(name).transform;
            child.SetParent(parent);
            return child;
        }

        public void Generate(SceneParameters parameters)
        {
            _random = new System.Random(DateTime.Now.Millisecond);
            ClearData();

            RoadGenerator.Instance.Generate(parameters, roadsRoot, _random);
            Roads = RoadGenerator.Instance.Roads;
            Lanes = RoadGenerator.Instance.Lanes;

            BuildingGenerator.Instance.Generate(parameters, buildingsRoot, Roads, _random);
            Buildings = BuildingGenerator.Instance.Buildings;

            TrafficSignGenerator.Instance.Generate(parameters, signsRoot, Roads, _random);
            TrafficSigns = TrafficSignGenerator.Instance.Signs;

            TrafficLightGenerator.Instance.Generate(parameters, lightsRoot, Roads, _random);
            TrafficLights = TrafficLightGenerator.Instance.Lights;

            VehicleGenerator.Instance.Generate(parameters, vehiclesRoot, Lanes, _random);
            VehicleObjects = VehicleGenerator.Instance.Vehicles;

            PedestrianGenerator.Instance.Generate(parameters, pedestriansRoot, Roads, _random);
            PedestrianObjects = PedestrianGenerator.Instance.Pedestrians;

            WeatherSystem.Instance.SetWeather(parameters.weather);

            if (CornerCaseGenerator.Instance != null)
            {
                CornerCaseGenerator.Instance.Initialize(_random, sceneRoot);
            }

            CalculateWorldBounds();
        }

        public void Clear()
        {
            for (int i = sceneRoot.childCount - 1; i >= 0; i--)
            {
                DestroyImmediate(sceneRoot.GetChild(i).gameObject);
            }
            ClearData();
            EnsureRoots();
            WeatherSystem.Instance.ResetWeather();

            if (CornerCaseGenerator.Instance != null)
            {
                CornerCaseGenerator.Instance.ResetGenerator();
            }
        }

        private void ClearData()
        {
            Roads.Clear();
            Lanes.Clear();
            Buildings.Clear();
            VehicleObjects.Clear();
            PedestrianObjects.Clear();
            TrafficSigns.Clear();
            TrafficLights.Clear();
        }

        private void CalculateWorldBounds()
        {
            var bounds = new Bounds(Vector3.zero, Vector3.zero);
            bool first = true;

            foreach (var road in Roads)
            {
                if (first)
                {
                    bounds = new Bounds(road.startPoint.ToVector3(), Vector3.zero);
                    first = false;
                }
                bounds.Encapsulate(road.startPoint.ToVector3());
                bounds.Encapsulate(road.endPoint.ToVector3());
            }

            foreach (var building in Buildings)
            {
                bounds.Encapsulate(building.position.ToVector3());
            }

            var expand = 50f;
            bounds.Expand(expand);
            WorldBounds = bounds;
        }

        public int GetRandomInt(int min, int max)
        {
            return _random.Next(min, max);
        }

        public float GetRandomFloat(float min, float max)
        {
            return (float)(_random.NextDouble() * (max - min) + min);
        }

        public System.Random GetRandom()
        {
            return _random;
        }
    }
}
