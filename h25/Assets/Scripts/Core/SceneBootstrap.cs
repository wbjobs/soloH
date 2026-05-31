using UnityEngine;

namespace CitySimulator
{
    public class SceneBootstrap : MonoBehaviour
    {
        [SerializeField] private bool autoGenerateOnStart = true;
        [SerializeField] private bool createGroundPlane = true;

        private SimulationManager _simulationManager;
        private SceneGenerator _sceneGenerator;
        private RoadGenerator _roadGenerator;
        private BuildingGenerator _buildingGenerator;
        private TrafficSignGenerator _trafficSignGenerator;
        private TrafficLightGenerator _trafficLightGenerator;
        private VehicleGenerator _vehicleGenerator;
        private PedestrianGenerator _pedestrianGenerator;
        private WeatherSystem _weatherSystem;
        private TrajectoryRecorder _trajectoryRecorder;
        private ReplaySystem _replaySystem;
        private SceneExporter _sceneExporter;
        private CameraSystem _cameraSystem;
        private UIController _uiController;
        private ILDriverModel _ilDriverModel;
        private CollaborativeLaneChangeManager _laneChangeManager;
        private CornerCaseGenerator _cornerCaseGenerator;

        private void Awake()
        {
            CreateManagers();
            InitializeEnvironment();
        }

        private void Start()
        {
            if (autoGenerateOnStart)
            {
                SimulationManager.Instance.GenerateScene();
            }
        }

        private void CreateManagers()
        {
            GameObject managersRoot = new GameObject("Managers");
            DontDestroyOnLoad(managersRoot);

            _simulationManager = CreateManager<SimulationManager>(managersRoot.transform, "SimulationManager");
            _sceneGenerator = CreateManager<SceneGenerator>(managersRoot.transform, "SceneGenerator");
            _roadGenerator = CreateManager<RoadGenerator>(managersRoot.transform, "RoadGenerator");
            _buildingGenerator = CreateManager<BuildingGenerator>(managersRoot.transform, "BuildingGenerator");
            _trafficSignGenerator = CreateManager<TrafficSignGenerator>(managersRoot.transform, "TrafficSignGenerator");
            _trafficLightGenerator = CreateManager<TrafficLightGenerator>(managersRoot.transform, "TrafficLightGenerator");
            _vehicleGenerator = CreateManager<VehicleGenerator>(managersRoot.transform, "VehicleGenerator");
            _pedestrianGenerator = CreateManager<PedestrianGenerator>(managersRoot.transform, "PedestrianGenerator");
            _weatherSystem = CreateManager<WeatherSystem>(managersRoot.transform, "WeatherSystem");
            _trajectoryRecorder = CreateManager<TrajectoryRecorder>(managersRoot.transform, "TrajectoryRecorder");
            _replaySystem = CreateManager<ReplaySystem>(managersRoot.transform, "ReplaySystem");
            _sceneExporter = CreateManager<SceneExporter>(managersRoot.transform, "SceneExporter");
            _cameraSystem = CreateManager<CameraSystem>(managersRoot.transform, "CameraSystem");
            _uiController = CreateManager<UIController>(managersRoot.transform, "UIController");
            _ilDriverModel = CreateManager<ILDriverModel>(managersRoot.transform, "ILDriverModel");
            _laneChangeManager = CreateManager<CollaborativeLaneChangeManager>(managersRoot.transform, "LaneChangeManager");
            _cornerCaseGenerator = CreateManager<CornerCaseGenerator>(managersRoot.transform, "CornerCaseGenerator");
        }

        private T CreateManager<T>(Transform parent, string name) where T : MonoBehaviour
        {
            GameObject obj = new GameObject(name);
            obj.transform.SetParent(parent);
            return obj.AddComponent<T>();
        }

        private void InitializeEnvironment()
        {
            if (createGroundPlane)
            {
                CreateGroundPlane();
            }

            CreateCamera();
        }

        private void CreateGroundPlane()
        {
            GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            ground.transform.position = new Vector3(0, -0.1f, 0);
            ground.transform.localScale = new Vector3(100, 1, 100);
            Renderer groundRenderer = ground.GetComponent<Renderer>();
            Material groundMat = new Material(Shader.Find("Standard"));
            groundMat.color = new Color(0.3f, 0.4f, 0.3f);
            groundRenderer.material = groundMat;
            Destroy(ground.GetComponent<MeshCollider>());
            ground.AddComponent<MeshCollider>();
        }

        private void CreateCamera()
        {
            if (Camera.main == null)
            {
                GameObject cameraObj = new GameObject("Main Camera");
                cameraObj.tag = "MainCamera";
                Camera cam = cameraObj.AddComponent<Camera>();
                cam.clearFlags = CameraClearFlags.Skybox;
                cam.fieldOfView = 60f;
                cam.nearClipPlane = 0.1f;
                cam.farClipPlane = 1000f;
                cameraObj.AddComponent<AudioListener>();

                if (CameraSystem.Instance != null)
                {
                    var camSystem = CameraSystem.Instance;
                    camSystem.GetType().GetField("mainCamera",
                        System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                        ?.SetValue(camSystem, cam);
                }
            }
        }

        public void SetAutoGenerate(bool autoGenerate)
        {
            autoGenerateOnStart = autoGenerate;
        }
    }
}
