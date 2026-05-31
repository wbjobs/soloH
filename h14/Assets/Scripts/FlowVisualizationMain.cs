using UnityEngine;
using FlowVisualization.Core;
using FlowVisualization.Data;
using FlowVisualization.Particles;
using FlowVisualization.Rendering;
using FlowVisualization.Interaction;
using FlowVisualization.Compute;
using FlowVisualization.UI;
using FlowVisualization.Analysis;
using FlowVisualization.PIV;

namespace FlowVisualization
{
    [RequireComponent(typeof(ParticleSystemManager))]
    [RequireComponent(typeof(LineRendererManager))]
    [RequireComponent(typeof(ParticleRenderer))]
    [RequireComponent(typeof(ColorMapManager))]
    [RequireComponent(typeof(GPUParticleSystem))]
    public class FlowVisualizationMain : MonoBehaviour
    {
        [Header("Data Settings")]
        public string NetCDFFilePath = "";
        public bool UseSyntheticData = true;
        public int SyntheticResolution = 32;
        public int SyntheticTimeSteps = 128;

        [Header("PIV Settings")]
        public string PIVFilePath = "";
        public bool UsePIVData = false;
        public float PIVDeltaT = 0.01f;
        public float PIVPixelSize = 1e-5f;
        public float PIVMagnification = 1.0f;
        public ReconstructionMethod PIVReconstructionMethod = ReconstructionMethod.InverseDistance;
        public int PIVTargetGridSize = 64;

        [Header("LCS Settings")]
        public bool EnableLCS = true;
        public float LCSIntegrationTime = 2.0f;
        public bool UseGPUForLCS = true;

        [Header("References")]
        public Camera MainCamera;
        public GameObject ControlPanelUI;
        public Material LCSPointMaterial;

        [Header("Performance")]
        public bool UseGPUAcceleration = true;
        public bool UseParallelProcessing = true;
        public int TargetParticlesPerSecond = 100000;

        private ParticleSystemManager _particleSystem;
        private LineRendererManager _lineRenderer;
        private ParticleRenderer _particleRenderer;
        private ColorMapManager _colorMapManager;
        private GPUParticleSystem _gpuParticleSystem;
        private SeedPointPlacer _seedPlacer;
        private FlyCameraController _cameraController;
        private ControlPanel _controlPanel;
        private LyapunovCalculator _lyapunovCalculator;
        private LCSFieldRenderer _lcsRenderer;
        private PIVReader _pivReader;
        private PIVVectorFieldReconstructor _pivReconstructor;

        private bool _dataLoaded;

        private void Awake()
        {
            InitializeComponents();
            SetupCamera();
        }

        private async void Start()
        {
            await LoadData();
            InitializeInteraction();
            InitializeUI();
            InitializeLCS();
            InitializePIV();

            if (_gpuParticleSystem != null && UseGPUAcceleration)
            {
                _particleSystem.OnDataLoaded += () =>
                {
                    _gpuParticleSystem.Initialize(_particleSystem.Field);
                    Debug.Log("GPU Particle System initialized.");

                    if (_lcsRenderer != null && EnableLCS)
                    {
                        _lcsRenderer.RenderGridSize = Mathf.Min(_gpuParticleSystem.FTLEGridSize, 32);
                        _lcsRenderer.LyapunovCalculator = _lyapunovCalculator;
                        _lcsRenderer.GPUParticleSystem = _gpuParticleSystem;
                        _lcsRenderer.ColorMapManager = _colorMapManager;
                        _lcsRenderer.PointMaterial = LCSPointMaterial;
                        _lcsRenderer.UseGPUComputation = UseGPUForLCS;
                        _lcsRenderer.IntegrationTime = LCSIntegrationTime;
                    }
                };
            }
        }

        private void Update()
        {
            HandleKeyboardInput();

            if (_dataLoaded && _gpuParticleSystem != null && _gpuParticleSystem.IsInitialized && UseGPUAcceleration)
            {
                _gpuParticleSystem.UpdateParticles(
                    Time.deltaTime * _particleSystem.SimulationSpeed,
                    _particleSystem.SimulationTime,
                    _particleSystem.Direction,
                    _particleSystem.ColorField
                );
            }
        }

        private void InitializeComponents()
        {
            _particleSystem = GetComponent<ParticleSystemManager>();
            _lineRenderer = GetComponent<LineRendererManager>();
            _particleRenderer = GetComponent<ParticleRenderer>();
            _colorMapManager = GetComponent<ColorMapManager>();
            _gpuParticleSystem = GetComponent<GPUParticleSystem>();

            _particleSystem.NetCDFFilePath = NetCDFFilePath;
            _particleSystem.UseSyntheticData = UseSyntheticData;
            _particleSystem.SyntheticResolution = SyntheticResolution;
            _particleSystem.SyntheticTimeSteps = SyntheticTimeSteps;
            _particleSystem.UseParallelProcessing = UseParallelProcessing;
            _particleSystem.TargetParticlesPerSecond = TargetParticlesPerSecond;

            _gpuParticleSystem.UseGPU = UseGPUAcceleration;

            _pivReader = new PIVReader();
            _pivReconstructor = new PIVVectorFieldReconstructor
            {
                Method = PIVReconstructionMethod,
                TargetGridSizeX = PIVTargetGridSize,
                TargetGridSizeY = PIVTargetGridSize,
                TargetGridSizeZ = 1
            };
        }

        private void InitializeLCS()
        {
            if (!EnableLCS) return;

            GameObject lcsObj = new GameObject("LCSFieldRenderer");
            lcsObj.transform.SetParent(transform);
            _lcsRenderer = lcsObj.AddComponent<LCSFieldRenderer>();

            _lyapunovCalculator = new LyapunovCalculator(
                _particleSystem.Field,
                _particleSystem.Integrator
            );
        }

        private void InitializePIV()
        {
            if (!UsePIVData || string.IsNullOrEmpty(PIVFilePath)) return;

            try
            {
                PIVData pivData = _pivReader.ReadFile(PIVFilePath);
                Vector3Field field = _pivReconstructor.ReconstructField(pivData);
                
                if (_particleSystem.Field != null)
                {
                    for (int z = 0; z < Mathf.Min(field.DimZ, _particleSystem.Field[0].DimZ); z++)
                    {
                        for (int y = 0; y < Mathf.Min(field.DimY, _particleSystem.Field[0].DimY); y++)
                        {
                            for (int x = 0; x < Mathf.Min(field.DimX, _particleSystem.Field[0].DimX); x++)
                            {
                                _particleSystem.Field[0].Velocity[x, y, z] = field.Velocity[x, y, z];
                                _particleSystem.Field[0].Pressure[x, y, z] = field.Pressure[x, y, z];
                                _particleSystem.Field[0].LyapunovExponent[x, y, z] = field.LyapunovExponent[x, y, z];
                                _particleSystem.Field[0].FTLE[x, y, z] = field.FTLE[x, y, z];
                                _particleSystem.Field[0].Stretching[x, y, z] = field.Stretching[x, y, z];
                                _particleSystem.Field[0].Compression[x, y, z] = field.Compression[x, y, z];
                            }
                        }
                    }
                    _particleSystem.Field[0].ComputeDerivedQuantities();
                    Debug.Log($"PIV data loaded and reconstructed: {pivData.Vectors.Count} vectors");
                }
            }
            catch (Exception e)
            {
                Debug.LogError($"Failed to load PIV data: {e.Message}");
            }
        }

        private void SetupCamera()
        {
            if (MainCamera == null)
            {
                MainCamera = Camera.main;
            }

            if (MainCamera != null && MainCamera.GetComponent<FlyCameraController>() == null)
            {
                _cameraController = MainCamera.gameObject.AddComponent<FlyCameraController>();
            }
            else
            {
                _cameraController = MainCamera.GetComponent<FlyCameraController>();
            }

            if (_cameraController != null)
            {
                MainCamera.transform.position = new Vector3(0.5f, 0.5f, 2.0f);
                MainCamera.transform.LookAt(new Vector3(0.5f, 0.5f, 0.5f));
            }
        }

        private async System.Threading.Tasks.Task LoadData()
        {
            try
            {
                _particleSystem.OnDataLoaded += () =>
                {
                    _dataLoaded = true;
                    Debug.Log($"Flow Visualization initialized with {_particleSystem.Field.TimeStepCount} time steps.");
                    Debug.Log($"Resolution: {_particleSystem.Field[0].DimX}x{_particleSystem.Field[0].DimY}x{_particleSystem.Field[0].DimZ}");
                    Debug.Log($"Time range: {_particleSystem.Field.MinTime:F3}s to {_particleSystem.Field.MaxTime:F3}s");
                };

                await System.Threading.Tasks.Task.CompletedTask;
            }
            catch (System.Exception e)
            {
                Debug.LogError($"Failed to initialize flow visualization: {e.Message}");
            }
        }

        private void InitializeInteraction()
        {
            GameObject placerObj = new GameObject("SeedPointPlacer");
            placerObj.transform.SetParent(transform);
            _seedPlacer = placerObj.AddComponent<SeedPointPlacer>();
            _seedPlacer.ParticleSystem = _particleSystem;
            _seedPlacer.MainCamera = MainCamera;
        }

        private void InitializeUI()
        {
            if (ControlPanelUI != null)
            {
                _controlPanel = ControlPanelUI.GetComponent<ControlPanel>();
                if (_controlPanel == null)
                {
                    _controlPanel = ControlPanelUI.AddComponent<ControlPanel>();
                }

                _controlPanel.ParticleSystem = _particleSystem;
                _controlPanel.SeedPlacer = _seedPlacer;
                _controlPanel.ColorMap = _colorMapManager;
                _controlPanel.CameraController = _cameraController;
            }
        }

        private void HandleKeyboardInput()
        {
            if (Input.GetKeyDown(KeyCode.Space))
            {
                _particleSystem.TogglePause();
            }

            if (Input.GetKeyDown(KeyCode.R))
            {
                _particleSystem.ResetSimulation();
                _gpuParticleSystem?.ResetParticles();
            }

            if (Input.GetKeyDown(KeyCode.F))
            {
                _particleSystem.SetIntegrationDirection(IntegrationDirection.Forward);
            }

            if (Input.GetKeyDown(KeyCode.B))
            {
                _particleSystem.SetIntegrationDirection(IntegrationDirection.Backward);
            }

            if (Input.GetKeyDown(KeyCode.G))
            {
                UseGPUAcceleration = !UseGPUAcceleration;
                if (_gpuParticleSystem != null)
                {
                    _gpuParticleSystem.UseGPU = UseGPUAcceleration;
                }
                Debug.Log($"GPU Acceleration: {UseGPUAcceleration}");
            }

            if (Input.GetKeyDown(KeyCode.Alpha1))
            {
                _particleSystem.UpdateColorField(ScalarFieldType.VelocityMagnitude);
                Debug.Log("Color field: Velocity Magnitude");
            }

            if (Input.GetKeyDown(KeyCode.Alpha2))
            {
                _particleSystem.UpdateColorField(ScalarFieldType.Vorticity);
                Debug.Log("Color field: Vorticity");
            }

            if (Input.GetKeyDown(KeyCode.Alpha3))
            {
                _particleSystem.UpdateColorField(ScalarFieldType.Pressure);
                Debug.Log("Color field: Pressure");
            }

            if (Input.GetKeyDown(KeyCode.Alpha4))
            {
                _particleSystem.UpdateColorField(ScalarFieldType.LyapunovExponent);
                Debug.Log("Color field: Lyapunov Exponent");
            }

            if (Input.GetKeyDown(KeyCode.Alpha5))
            {
                _particleSystem.UpdateColorField(ScalarFieldType.FTLE);
                Debug.Log("Color field: FTLE");
            }

            if (Input.GetKeyDown(KeyCode.Alpha6))
            {
                _particleSystem.UpdateColorField(ScalarFieldType.Stretching);
                Debug.Log("Color field: Stretching");
            }

            if (Input.GetKeyDown(KeyCode.Alpha7))
            {
                _particleSystem.UpdateColorField(ScalarFieldType.Compression);
                Debug.Log("Color field: Compression");
            }

            if (Input.GetKeyDown(KeyCode.L))
            {
                if (_lcsRenderer != null)
                {
                    _lcsRenderer.ToggleLCS(!_lcsRenderer.ShowLCS);
                    Debug.Log($"LCS Visualization: {(_lcsRenderer.ShowLCS ? "ON" : "OFF")}");
                }
            }

            if (Input.GetKeyDown(KeyCode.Y))
            {
                if (_lcsRenderer != null)
                {
                    _lcsRenderer.ToggleAttracting(!_lcsRenderer.ShowAttracting);
                    Debug.Log($"Attracting LCS: {(_lcsRenderer.ShowAttracting ? "ON" : "OFF")}");
                }
            }

            if (Input.GetKeyDown(KeyCode.U))
            {
                if (_lcsRenderer != null)
                {
                    _lcsRenderer.ToggleRepelling(!_lcsRenderer.ShowRepelling);
                    Debug.Log($"Repelling LCS: {(_lcsRenderer.ShowRepelling ? "ON" : "OFF")}");
                }
            }

            if (Input.GetKeyDown(KeyCode.Plus) || Input.GetKeyDown(KeyCode.Equals))
            {
                if (_lcsRenderer != null)
                {
                    _lcsRenderer.SetThreshold(Mathf.Min(1.0f, _lcsRenderer.Threshold + 0.05f));
                    Debug.Log($"LCS Threshold: {_lcsRenderer.Threshold:F2}");
                }
            }

            if (Input.GetKeyDown(KeyCode.Minus))
            {
                if (_lcsRenderer != null)
                {
                    _lcsRenderer.SetThreshold(Mathf.Max(0.0f, _lcsRenderer.Threshold - 0.05f));
                    Debug.Log($"LCS Threshold: {_lcsRenderer.Threshold:F2}");
                }
            }

            if (Input.GetKeyDown(KeyCode.C))
            {
                _seedPlacer.ClearAllSeeds();
                Debug.Log("All seeds cleared.");
            }

            if (Input.GetKeyDown(KeyCode.T))
            {
                RunValidationTests();
            }

            if (Input.GetKeyDown(KeyCode.Escape))
            {
                Application.Quit();
            }
        }

        private void RunValidationTests()
        {
            FlowVisualization.Tests.BugFixValidation bugValidator = GetComponent<FlowVisualization.Tests.BugFixValidation>();
            if (bugValidator == null)
            {
                bugValidator = gameObject.AddComponent<FlowVisualization.Tests.BugFixValidation>();
                bugValidator.RunTestsOnStart = false;
            }
            bugValidator.StressTestIterations = 200;
            bugValidator.ParticlesPerIteration = 50;
            bugValidator.RunAllTests();

            FlowVisualization.Tests.NewFeatureValidation newFeatureValidator = GetComponent<FlowVisualization.Tests.NewFeatureValidation>();
            if (newFeatureValidator == null)
            {
                newFeatureValidator = gameObject.AddComponent<FlowVisualization.Tests.NewFeatureValidation>();
                newFeatureValidator.RunTestsOnStart = false;
            }
            newFeatureValidator.TestGridSize = 16;
            newFeatureValidator.TestParticleCount = 1000;
            newFeatureValidator.PIVVectorCount = 1000;
            newFeatureValidator.RunAllTests();
        }

        private void OnGUI()
        {
            if (!_dataLoaded)
            {
                GUI.Box(new Rect(10, 10, 300, 50), "Loading flow data... Please wait.");
                return;
            }

            int yOffset = 10;
            GUI.Box(new Rect(10, yOffset, 380, 280), "Flow Visualization Controls");

            yOffset += 30;
            GUI.Label(new Rect(20, yOffset, 360, 20), 
                $"Status: {(_particleSystem.IsPaused ? "PAUSED" : "RUNNING")} | " +
                $"Time: {_particleSystem.SimulationTime:F3}s");

            yOffset += 25;
            GUI.Label(new Rect(20, yOffset, 360, 20),
                $"Direction: {_particleSystem.Direction} | " +
                $"Speed: {_particleSystem.SimulationSpeed:F1}x");

            yOffset += 25;
            GUI.Label(new Rect(20, yOffset, 360, 20),
                $"Particles: {_particleSystem.TotalActiveParticles} | " +
                $"Rate: {_particleSystem.ParticlesProcessedPerSecond}/s");

            yOffset += 25;
            GUI.Label(new Rect(20, yOffset, 360, 20),
                $"Color Field: {_particleSystem.ColorField} | " +
                $"Seeds: {_particleSystem.SeedPoints.Count}");

            yOffset += 25;
            string gpuStatus = UseGPUAcceleration && _gpuParticleSystem.IsInitialized ? "ON" : "OFF";
            string lcsStatus = EnableLCS && _lcsRenderer != null && _lcsRenderer.ShowLCS ? "ON" : "OFF";
            GUI.Label(new Rect(20, yOffset, 360, 20),
                $"GPU: {gpuStatus} | LCS: {lcsStatus} | " +
                $"Parallel: {_particleSystem.UseParallelProcessing}");

            if (UseGPUAcceleration && _gpuParticleSystem.IsInitialized)
            {
                yOffset += 25;
                GUI.Label(new Rect(20, yOffset, 360, 20),
                    $"GPU FPS: {_gpuParticleSystem.AverageFramesPerSecond:F1} | " +
                    $"GPU Rate: {_gpuParticleSystem.AverageParticlesPerSecond:F0}/s");
            }

            if (EnableLCS && _lcsRenderer != null && _lcsRenderer.ShowLCS)
            {
                yOffset += 25;
                GUI.Label(new Rect(20, yOffset, 360, 20),
                    $"LCS: Attr={(char)916}{(_lcsRenderer.ShowAttracting ? "ON" : "OFF")} " +
                    $"Rep={(_lcsRenderer.ShowRepelling ? "ON" : "OFF")} | " +
                    $"Thresh: {_lcsRenderer.Threshold:F2}");
            }

            yOffset += 25;
            GUI.Label(new Rect(20, yOffset, 360, 20), "Shortcuts:");
            yOffset += 20;
            GUI.Label(new Rect(30, yOffset, 350, 18), "Space=Pause/Play | R=Reset | F=Forward | B=Backward");
            yOffset += 18;
            GUI.Label(new Rect(30, yOffset, 350, 18), "1-7=Color Field (Vel/Vort/Press/Lyap/FTLE/Str/Comp)");
            yOffset += 18;
            GUI.Label(new Rect(30, yOffset, 350, 18), "L=Toggle LCS | Y=Attr LCS | U=Rep LCS | +/- =Threshold");
            yOffset += 18;
            GUI.Label(new Rect(30, yOffset, 350, 18), "G=Toggle GPU | RightMouse+Drag=Rotate | WASD=Move");
            yOffset += 18;
            GUI.Label(new Rect(30, yOffset, 350, 18), "Q/E=Up/Down | 1/2/3=Line Type | LeftClick=Place");
            yOffset += 18;
            GUI.Label(new Rect(30, yOffset, 350, 18), "Ctrl+Click=Delete | C=Clear Seeds | T=Run Tests");
        }

        private void OnDestroy()
        {
            _particleSystem?.ClearAllSeedPoints();
        }
    }
}
