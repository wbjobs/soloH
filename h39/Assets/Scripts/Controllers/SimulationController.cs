using UnityEngine;
using System;
using System.IO;
using System.Threading.Tasks;
using SoleFrictionSim.Core;
using SoleFrictionSim.Data;
using SoleFrictionSim.Geometry;
using SoleFrictionSim.Compute;
using SoleFrictionSim.UI;

namespace SoleFrictionSim.Controllers
{
    public class SimulationController : MonoBehaviour
    {
        [Header("Scene References")]
        [SerializeField] private ParameterPanel _parameterPanel;
        [SerializeField] private VisualizationPanel _visualizationPanel;
        [SerializeField] private Transform _soleContainer;
        [SerializeField] private Transform _groundPlane;

        [Header("Compute Shaders")]
        [SerializeField] private ComputeShader _bemComputeShader;
        [SerializeField] private ComputeShader _frictionComputeShader;

        [Header("Materials")]
        [SerializeField] private Material _soleMaterial;
        [SerializeField] private Material _heatmapMaterial;
        [SerializeField] private Material _waterFilmMaterial;
        [SerializeField] private Material _wearMaterial;
        [SerializeField] private Material _temperatureMaterial;
        [SerializeField] private Material _wireframeMaterial;

        private Mesh _currentSoleMesh;
        private float[,] _currentHeightField;
        private GameObject _soleObject;
        private MeshFilter _meshFilter;
        private MeshRenderer _meshRenderer;

        private BEMSolver _bemSolver;
        private FrictionCalculator _frictionCalculator;
        private WearCalculator _wearCalculator;
        private ThermalCalculator _thermalCalculator;
        private PatternGenerator _patternGenerator;
        private StlImporter _stlImporter;
        private CadExporter _cadExporter;

        private BEMCompute _bemCompute;
        private FrictionCompute _frictionCompute;

        private ContactResult _currentResult;
        private SimulationState _currentState = SimulationState.Idle;
        private bool _isPaused = false;

        public ContactResult CurrentResult => _currentResult;
        public SimulationState CurrentState => _currentState;

        public event Action<float> OnProgressUpdated;
        public event Action<ContactResult> OnSimulationComplete;
        public event Action<string> OnErrorOccurred;

        private void Awake()
        {
            InitializeSolvers();
            InitializeSoleObject();
            HookEvents();
        }

        private void Start()
        {
            GenerateDefaultPattern();
            _parameterPanel.SetStatus(SimulationState.Idle);
        }

        private void InitializeSolvers()
        {
            _bemSolver = new BEMSolver();
            _frictionCalculator = new FrictionCalculator();
            _wearCalculator = new WearCalculator();
            _thermalCalculator = new ThermalCalculator();
            _patternGenerator = new PatternGenerator();
            _stlImporter = new StlImporter();
            _cadExporter = new CadExporter();

            if (_bemComputeShader != null)
            {
                _bemCompute = new BEMCompute(_bemComputeShader);
            }

            if (_frictionComputeShader != null)
            {
                _frictionCompute = new FrictionCompute(_frictionComputeShader);
            }

            CreateAuxiliaryMaterials();
        }

        private void CreateAuxiliaryMaterials()
        {
            if (_wearMaterial == null)
            {
                _wearMaterial = new Material(Shader.Find("Standard"));
                _wearMaterial.color = new Color(0.8f, 0.2f, 0.1f);
            }

            if (_temperatureMaterial == null)
            {
                _temperatureMaterial = new Material(Shader.Find("Standard"));
                _temperatureMaterial.color = new Color(1f, 0.5f, 0f);
            }
        }

        private void InitializeSoleObject()
        {
            _soleObject = new GameObject("SoleModel");
            _soleObject.transform.SetParent(_soleContainer, false);

            _meshFilter = _soleObject.AddComponent<MeshFilter>();
            _meshRenderer = _soleObject.AddComponent<MeshRenderer>();
            _meshRenderer.material = _soleMaterial;
        }

        private void HookEvents()
        {
            _parameterPanel.GeneratePatternClicked += OnGeneratePattern;
            _parameterPanel.ImportStlClicked += OnImportStl;
            _parameterPanel.StartSimulationClicked += OnStartSimulation;
            _parameterPanel.ResetClicked += OnReset;
            _parameterPanel.ExportDataClicked += OnExportData;
            _parameterPanel.ExportPatternClicked += OnExportPattern;
            _parameterPanel.ExportWornPatternClicked += OnExportWornPattern;

            _visualizationPanel.VisualizationModeChanged += OnVisualizationModeChanged;
            _visualizationPanel.WireframeToggled += OnWireframeToggled;
            _visualizationPanel.IntensityChanged += OnIntensityChanged;
        }

        private async void OnGeneratePattern()
        {
            try
            {
                var config = _parameterPanel.PatternConfig;
                _parameterPanel.SetInteractable(false);

                await Task.Run(() =>
                {
                    _currentHeightField = _patternGenerator.GetHeightField(config, 128);
                    _currentSoleMesh = _patternGenerator.Generate(config);
                });

                UpdateSoleMesh(_currentSoleMesh);
                _parameterPanel.SetInteractable(true);
            }
            catch (Exception ex)
            {
                _parameterPanel.SetStatus(SimulationState.Error, ex.Message);
                OnErrorOccurred?.Invoke(ex.Message);
            }
        }

        private void OnImportStl()
        {
#if UNITY_EDITOR
            string path = UnityEditor.EditorUtility.OpenFilePanel("Import STL", "", "stl");
#else
            string path = OpenFileDialog("STL Files (*.stl)|*.stl");
#endif

            if (!string.IsNullOrEmpty(path) && File.Exists(path))
            {
                try
                {
                    _parameterPanel.SetInteractable(false);
                    var mesh = _stlImporter.Import(path);

                    if (_stlImporter.ValidateMesh(mesh))
                    {
                        mesh = _stlImporter.NormalizeMesh(mesh);
                        _currentSoleMesh = mesh;
                        _currentHeightField = _stlImporter.ExtractContactHeightField(mesh, 128);
                        UpdateSoleMesh(_currentSoleMesh);
                    }
                    else
                    {
                        _parameterPanel.SetStatus(SimulationState.Error, "Invalid STL mesh");
                    }

                    _parameterPanel.SetInteractable(true);
                }
                catch (Exception ex)
                {
                    _parameterPanel.SetStatus(SimulationState.Error, ex.Message);
                    OnErrorOccurred?.Invoke(ex.Message);
                }
            }
        }

        private async void OnStartSimulation()
        {
            if (_currentState == SimulationState.Running) return;

            try
            {
                _currentState = SimulationState.Running;
                _parameterPanel.SetStatus(SimulationState.Running);
                _parameterPanel.SetInteractable(false);

                var progress = new Progress<float>(p =>
                {
                    _parameterPanel.UpdateProgress(p);
                    OnProgressUpdated?.Invoke(p);
                });

                var material = _parameterPanel.RubberMaterial;
                var ground = _parameterPanel.GroundSurface;
                var simParams = _parameterPanel.SimulationParams;

                _currentResult = await _bemSolver.SolveAsync(_currentSoleMesh, material, ground, simParams, progress);

                if (simParams.useGpuAcceleration && _frictionCompute != null)
                {
                    _frictionCompute.Initialize(simParams.bemResolution, simParams.velocitySamples);
                    _frictionCompute.SetMaterialParams(material);
                    _frictionCompute.SetGroundParams(ground);
                    _frictionCompute.SetSimulationParams(
                        _currentResult.averagePressure,
                        _currentResult.contactAreaRatio,
                        simParams.velocitySamples,
                        simParams.minVelocity,
                        simParams.maxVelocity,
                        simParams);

                    _frictionCompute.SetPressureData(_currentResult.contactPressure);

                    var velocities = _frictionCompute.GetVelocities(
                        simParams.minVelocity,
                        simParams.maxVelocity,
                        simParams.velocitySamples);

                    _currentResult.slipVelocities = velocities;
                    _currentResult.frictionCoefficients = await _frictionCompute.CalculateFrictionCurveAsync();

                    if (simParams.includeHydrodynamics)
                    {
                        _currentResult.waterFilmThickness = await _frictionCompute.CalculateWaterFilmAsync();
                    }

                    _frictionCompute.GenerateHeatmap();
                }
                else
                {
                    _frictionCalculator.UpdateContactResultWithFriction(_currentResult, material, ground, simParams);
                }

                _currentResult.CalculateStatistics();

                if (simParams.enableThermalCoupling)
                {
                    _parameterPanel.UpdateProgress(0.75f, "计算温度场...");
                    await Task.Run(() =>
                    {
                        _thermalCalculator.CalculateTemperatureField(
                            _currentResult, material, ground, simParams, 1f);
                    });
                }

                if (simParams.enableWearSimulation)
                {
                    _parameterPanel.UpdateProgress(0.9f, "计算磨损分布...");
                    await Task.Run(() =>
                    {
                        _wearCalculator.CalculateWear(_currentResult, material, ground, simParams);
                    });
                }

                _currentResult.CalculateStatistics();
                _visualizationPanel.UpdateContactResult(_currentResult);

                _currentState = SimulationState.Completed;
                _parameterPanel.SetStatus(SimulationState.Completed);
                _parameterPanel.SetInteractable(true);

                OnSimulationComplete?.Invoke(_currentResult);
            }
            catch (Exception ex)
            {
                _currentState = SimulationState.Error;
                _parameterPanel.SetStatus(SimulationState.Error, ex.Message);
                _parameterPanel.SetInteractable(true);
                OnErrorOccurred?.Invoke(ex.Message);
            }
        }

        private void OnReset()
        {
            _currentResult = null;
            _currentState = SimulationState.Idle;
            _isPaused = false;

            _parameterPanel.SetStatus(SimulationState.Idle);
            _parameterPanel.UpdateProgress(0f);
            _parameterPanel.SetInteractable(true);

            _meshRenderer.material = _soleMaterial;
            _meshRenderer.enabled = true;
        }

        private async void OnExportData()
        {
            await ShowExportMenu(false);
        }

        private async void OnExportPattern()
        {
            await ShowExportMenu(false);
        }

        private async void OnExportWornPattern()
        {
            await ShowExportMenu(true);
        }

        private async Task ShowExportMenu(bool exportWorn)
        {
            string[] options = { "STL (Binary)", "STL (ASCII)", "OBJ", "DXF 2D Contour", "CSV Data" };
            string[] extensions = { "stl", "stl", "obj", "dxf", "csv" };

#if UNITY_EDITOR
            int choice = UnityEditor.EditorUtility.DisplayDialogComplex(
                "Export Pattern",
                "Select export format:",
                options[0],
                "Cancel",
                options[1] + "\n" + options[2] + "\n" + options[3] + "\n" + options[4]);

            if (choice == 1) return;

            ExportFormat format = choice == 0 ? ExportFormat.STL_Binary :
                                choice == 2 ? ExportFormat.STL_ASCII :
                                choice == 3 ? ExportFormat.OBJ :
                                choice == 4 ? ExportFormat.DXF_2D :
                                ExportFormat.CSV_Data;

            string ext = extensions[choice == 0 ? 0 : choice == 2 ? 1 : choice == 3 ? 2 : choice == 4 ? 3 : 4];
            string path = UnityEditor.EditorUtility.SaveFilePanel($"Export {format}", "", $"sole_pattern.{ext}", ext);
#else
            string path = SaveFileDialog("All Files (*.*)|*.*");
            ExportFormat format = ExportFormat.STL_Binary;
#endif

            if (!string.IsNullOrEmpty(path))
            {
                if (exportWorn)
                    await ExportWornPattern(path, format);
                else
                    await ExportData(path, format);
            }
        }

        public async Task<bool> ExportData(string filePath, ExportFormat format)
        {
            try
            {
                bool result = false;
                _parameterPanel.SetStatus(SimulationState.Running, $"Exporting {format}...");

                await Task.Run(() =>
                {
                    result = format switch
                    {
                        ExportFormat.STL_Binary => _cadExporter.ExportSTL(_currentSoleMesh, filePath, true),
                        ExportFormat.STL_ASCII => _cadExporter.ExportSTL(_currentSoleMesh, filePath, false),
                        ExportFormat.OBJ => _cadExporter.ExportOBJ(_currentSoleMesh, filePath),
                        ExportFormat.DXF_2D => _cadExporter.ExportDXF2D(_currentHeightField, filePath),
                        ExportFormat.CSV_Data => _cadExporter.ExportContactDataCSV(_currentResult, filePath),
                        _ => false
                    };
                });

                if (result)
                {
                    _parameterPanel.SetStatus(SimulationState.Completed, $"Exported to {Path.GetFileName(filePath)}");
                }
                else
                {
                    _parameterPanel.SetStatus(SimulationState.Error, "Export failed");
                }

                return result;
            }
            catch (Exception ex)
            {
                _parameterPanel.SetStatus(SimulationState.Error, ex.Message);
                return false;
            }
        }

        public async Task<bool> ExportWornPattern(string filePath, ExportFormat format)
        {
            if (_currentHeightField == null || _currentResult?.wearDepth == null) return false;

            try
            {
                _parameterPanel.SetStatus(SimulationState.Running, "Exporting worn pattern...");

                bool result = false;
                var config = _parameterPanel.PatternConfig;
                float width = config.soleWidth * 0.01f;
                float length = config.soleLength * 0.01f;
                float baseHeight = 0.005f;

                await Task.Run(() =>
                {
                    if (format == ExportFormat.STL_Binary || format == ExportFormat.STL_ASCII)
                    {
                        result = _cadExporter.ExportWornPatternSTL(
                            _currentHeightField, _currentResult.wearDepth, filePath,
                            width, length, baseHeight, format == ExportFormat.STL_Binary);
                    }
                    else
                    {
                        float[,] wornHeight = new float[_currentHeightField.GetLength(0), _currentHeightField.GetLength(1)];
                        for (int i = 0; i < wornHeight.GetLength(0); i++)
                            for (int j = 0; j < wornHeight.GetLength(1); j++)
                                wornHeight[i, j] = Mathf.Max(0f, _currentHeightField[i, j] - _currentResult.wearDepth[i, j]);

                        if (format == ExportFormat.DXF_2D)
                        {
                            result = _cadExporter.ExportDXF2D(wornHeight, filePath);
                        }
                        else if (format == ExportFormat.OBJ)
                        {
                            Mesh mesh = _patternGenerator.Generate(config);
                            result = _cadExporter.ExportOBJ(mesh, filePath);
                        }
                    }
                });

                if (result)
                {
                    _parameterPanel.SetStatus(SimulationState.Completed, $"Exported to {Path.GetFileName(filePath)}");
                }
                else
                {
                    _parameterPanel.SetStatus(SimulationState.Error, "Export failed");
                }

                return result;
            }
            catch (Exception ex)
            {
                _parameterPanel.SetStatus(SimulationState.Error, ex.Message);
                return false;
            }
        }

        private void OnVisualizationModeChanged(VisualizationMode mode)
        {
            switch (mode)
            {
                case VisualizationMode.Solid:
                    _meshRenderer.material = _soleMaterial;
                    break;
                case VisualizationMode.ContactPressure:
                    if (_currentResult != null)
                    {
                        UpdateHeatmapMaterial();
                        _meshRenderer.material = _heatmapMaterial;
                    }
                    break;
                case VisualizationMode.WaterFilm:
                    if (_currentResult != null && _currentResult.waterFilmThickness != null)
                    {
                        UpdateWaterFilmMaterial();
                        _meshRenderer.material = _waterFilmMaterial;
                    }
                    break;
                case VisualizationMode.WearDepth:
                    if (_currentResult != null && _currentResult.wearDepth != null)
                    {
                        UpdateWearMaterial();
                        _meshRenderer.material = _wearMaterial;
                    }
                    break;
                case VisualizationMode.Temperature:
                    if (_currentResult != null && _currentResult.temperatureField != null)
                    {
                        UpdateTemperatureMaterial();
                        _meshRenderer.material = _temperatureMaterial;
                    }
                    break;
                case VisualizationMode.Wireframe:
                    _meshRenderer.material = _wireframeMaterial;
                    break;
            }
        }

        private void OnWireframeToggled(bool show)
        {
            if (_meshRenderer != null)
            {
                _meshRenderer.material.SetFloat("_OutlineWidth", show ? 0.005f : 0f);
            }
        }

        private void OnIntensityChanged(float intensity)
        {
            if (_heatmapMaterial != null)
            {
                _heatmapMaterial.SetFloat("_Intensity", intensity);
            }
            if (_wearMaterial != null)
            {
                _wearMaterial.SetFloat("_Intensity", intensity);
            }
            if (_temperatureMaterial != null)
            {
                _temperatureMaterial.SetFloat("_Intensity", intensity);
            }
        }

        private void GenerateDefaultPattern()
        {
            var config = _parameterPanel.PatternConfig;
            _currentSoleMesh = _patternGenerator.Generate(config);
            UpdateSoleMesh(_currentSoleMesh);
        }

        private void UpdateSoleMesh(Mesh mesh)
        {
            if (_meshFilter != null)
            {
                _meshFilter.mesh = mesh;
            }
        }

        private void UpdateHeatmapMaterial()
        {
            if (_currentResult == null) return;

            int n = _currentResult.Resolution;
            Texture2D pressureTex = new Texture2D(n, n, TextureFormat.RFloat, false);

            float[] flatData = new float[n * n];
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    flatData[i * n + j] = _currentResult.GetPressureAt(i, j);
                }
            }

            pressureTex.SetPixelData(flatData, 0);
            pressureTex.Apply();

            _heatmapMaterial.SetTexture("_PressureData", pressureTex);
            _heatmapMaterial.SetFloat("_MinPressure", 0f);
            _heatmapMaterial.SetFloat("_MaxPressure", _currentResult.maxContactPressure);
        }

        private void UpdateWaterFilmMaterial()
        {
            if (_currentResult?.waterFilmThickness == null) return;

            int n = _currentResult.waterFilmThickness.GetLength(0);
            Texture2D waterTex = new Texture2D(n, n, TextureFormat.RFloat, false);

            float[] flatData = new float[n * n];
            float maxH = 0f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float h = _currentResult.waterFilmThickness[i, j];
                    flatData[i * n + j] = h;
                    if (h > maxH) maxH = h;
                }
            }

            waterTex.SetPixelData(flatData, 0);
            waterTex.Apply();

            _waterFilmMaterial.SetTexture("_WaterFilmData", waterTex);
            _waterFilmMaterial.SetFloat("_MinThickness", 0f);
            _waterFilmMaterial.SetFloat("_MaxThickness", maxH);
        }

        private void UpdateWearMaterial()
        {
            if (_currentResult?.wearDepth == null) return;

            int n = _currentResult.wearDepth.GetLength(0);
            Texture2D wearTex = new Texture2D(n, n, TextureFormat.RFloat, false);

            float[] flatData = new float[n * n];
            float maxWear = _currentResult.maxWearDepth > 0 ? _currentResult.maxWearDepth : 1e-6f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    flatData[i * n + j] = _currentResult.GetWearDepthAt(i, j);
                }
            }

            wearTex.SetPixelData(flatData, 0);
            wearTex.Apply();

            _wearMaterial.SetTexture("_WearData", wearTex);
            _wearMaterial.SetFloat("_MinWear", 0f);
            _wearMaterial.SetFloat("_MaxWear", maxWear);
        }

        private void UpdateTemperatureMaterial()
        {
            if (_currentResult?.temperatureField == null) return;

            int n = _currentResult.temperatureField.GetLength(0);
            Texture2D tempTex = new Texture2D(n, n, TextureFormat.RFloat, false);

            float[] flatData = new float[n * n];
            float maxTemp = Mathf.Max(_currentResult.maxTemperature, _currentResult.averageTemperature + 1f);
            float minTemp = _currentResult.averageTemperature - 5f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float t = _currentResult.GetTemperatureAt(i, j);
                    flatData[i * n + j] = Mathf.InverseLerp(minTemp, maxTemp, t);
                }
            }

            tempTex.SetPixelData(flatData, 0);
            tempTex.Apply();

            _temperatureMaterial.SetTexture("_TempData", tempTex);
            _temperatureMaterial.SetFloat("_MinTemp", minTemp);
            _temperatureMaterial.SetFloat("_MaxTemp", maxTemp);
        }

        private void ExportCsv(ContactResult result, string path)
        {
            using (var writer = new StreamWriter(path))
            {
                writer.WriteLine("# Sole Friction Simulation Results");
                writer.WriteLine($"# Compute Time: {result.computeTime:0.00}s");
                writer.WriteLine($"# Iterations: {result.iterations}");
                writer.WriteLine($"# Max Pressure: {result.maxContactPressure:0.0e0} Pa");
                writer.WriteLine($"# Average Pressure: {result.averagePressure:0.0e0} Pa");
                writer.WriteLine($"# Contact Area Ratio: {result.contactAreaRatio * 100:0.0}%");
                writer.WriteLine();

                writer.WriteLine("Slip Velocity (m/s),Friction Coefficient");
                if (result.slipVelocities != null && result.frictionCoefficients != null)
                {
                    for (int i = 0; i < result.slipVelocities.Length; i++)
                    {
                        writer.WriteLine($"{result.slipVelocities[i]:0.0e0},{result.frictionCoefficients[i]:0.000}");
                    }
                }

                writer.WriteLine();
                writer.WriteLine("Contact Pressure Distribution (Pa)");
                int n = result.Resolution;
                for (int i = 0; i < n; i++)
                {
                    for (int j = 0; j < n; j++)
                    {
                        if (j > 0) writer.Write(",");
                        writer.Write($"{result.GetPressureAt(i, j):0.0e0}");
                    }
                    writer.WriteLine();
                }

                if (result.waterFilmThickness != null)
                {
                    writer.WriteLine();
                    writer.WriteLine("Water Film Thickness (m)");
                    for (int i = 0; i < n; i++)
                    {
                        for (int j = 0; j < n; j++)
                        {
                            if (j > 0) writer.Write(",");
                            writer.Write($"{result.waterFilmThickness[i, j]:0.0e0}");
                        }
                        writer.WriteLine();
                    }
                }
            }
        }

        private string OpenFileDialog(string filter)
        {
            return "";
        }

        private string SaveFileDialog(string filter)
        {
            return "";
        }

        private void OnDestroy()
        {
            _bemCompute?.Dispose();
            _frictionCompute?.Dispose();
        }
    }
}
