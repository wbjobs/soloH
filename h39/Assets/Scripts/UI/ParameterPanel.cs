using UnityEngine;
using UnityEngine.UI;
using System.Collections.Generic;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.UI
{
    public class ParameterPanel : MonoBehaviour
    {
        [Header("Pattern Parameters")]
        [SerializeField] private Dropdown _patternTypeDropdown;
        [SerializeField] private Slider _patternDepthSlider;
        [SerializeField] private Text _patternDepthValue;
        [SerializeField] private Slider _patternSpacingSlider;
        [SerializeField] private Text _patternSpacingValue;
        [SerializeField] private Slider _patternAngleSlider;
        [SerializeField] private Text _patternAngleValue;

        [Header("Sole Dimensions")]
        [SerializeField] private Slider _soleWidthSlider;
        [SerializeField] private Text _soleWidthValue;
        [SerializeField] private Slider _soleLengthSlider;
        [SerializeField] private Text _soleLengthValue;

        [Header("Rubber Material")]
        [SerializeField] private Slider _shoreHardnessSlider;
        [SerializeField] private Text _shoreHardnessValue;
        [SerializeField] private Slider _elasticModulusSlider;
        [SerializeField] private Text _elasticModulusValue;
        [SerializeField] private Slider _lossFactorSlider;
        [SerializeField] private Text _lossFactorValue;

        [Header("Surface Roughness")]
        [SerializeField] private Slider _hurstExponentSlider;
        [SerializeField] private Text _hurstExponentValue;
        [SerializeField] private Slider _rmsRoughnessSlider;
        [SerializeField] private Text _rmsRoughnessValue;

        [Header("Ground Surface")]
        [SerializeField] private Dropdown _groundTypeDropdown;
        [SerializeField] private Slider _waterFilmSlider;
        [SerializeField] private Text _waterFilmValue;

        [Header("Simulation Parameters")]
        [SerializeField] private Slider _normalLoadSlider;
        [SerializeField] private Text _normalLoadValue;
        [SerializeField] private Slider _bemResolutionSlider;
        [SerializeField] private Text _bemResolutionValue;
        [SerializeField] private Toggle _hydrodynamicsToggle;
        [SerializeField] private Toggle _gpuAccelerationToggle;

        [Header("Velocity Range")]
        [SerializeField] private Slider _minVelocitySlider;
        [SerializeField] private Text _minVelocityValue;
        [SerializeField] private Slider _maxVelocitySlider;
        [SerializeField] private Text _maxVelocityValue;
        [SerializeField] private Slider _velocitySamplesSlider;
        [SerializeField] private Text _velocitySamplesValue;

        [Header("Stick-Slip Model")]
        [SerializeField] private Toggle _stickSlipToggle;
        [SerializeField] private Slider _staticFrictionMultiplierSlider;
        [SerializeField] private Text _staticFrictionMultiplierValue;
        [SerializeField] private Slider _transitionVelocitySlider;
        [SerializeField] private Text _transitionVelocityValue;
        [SerializeField] private Slider _transitionSharpnessSlider;
        [SerializeField] private Text _transitionSharpnessValue;

        [Header("Edge Stress Correction")]
        [SerializeField] private Toggle _edgeSmoothingToggle;
        [SerializeField] private Slider _edgeSmoothingRadiusSlider;
        [SerializeField] private Text _edgeSmoothingRadiusValue;
        [SerializeField] private Slider _edgeStressReductionSlider;
        [SerializeField] private Text _edgeStressReductionValue;

        [Header("Wear Simulation")]
        [SerializeField] private Toggle _wearSimulationToggle;
        [SerializeField] private Slider _wearCoefficientSlider;
        [SerializeField] private Text _wearCoefficientValue;
        [SerializeField] private Slider _slidingDistanceSlider;
        [SerializeField] private Text _slidingDistanceValue;

        [Header("Thermal Coupling")]
        [SerializeField] private Toggle _thermalCouplingToggle;
        [SerializeField] private Slider _ambientTempSlider;
        [SerializeField] private Text _ambientTempValue;
        [SerializeField] private Slider _heatPartitionSlider;
        [SerializeField] private Text _heatPartitionValue;

        [Header("Control Buttons")]
        [SerializeField] private Button _generatePatternButton;
        [SerializeField] private Button _importStlButton;
        [SerializeField] private Button _startSimulationButton;
        [SerializeField] private Button _resetButton;
        [SerializeField] private Button _exportDataButton;
        [SerializeField] private Button _exportStlButton;
        [SerializeField] private Button _exportWornButton;

        [Header("Progress")]
        [SerializeField] private Slider _progressBar;
        [SerializeField] private Text _progressText;
        [SerializeField] private Text _statusText;

        private PatternConfig _patternConfig = new PatternConfig();
        private SimulationParams _simulationParams = new SimulationParams();
        private RubberMaterial _rubberMaterial;
        private GroundSurface _groundSurface;

        public PatternConfig PatternConfig => _patternConfig;
        public SimulationParams SimulationParams => _simulationParams;
        public RubberMaterial RubberMaterial => _rubberMaterial;
        public GroundSurface GroundSurface => _groundSurface;

        private void Awake()
        {
            InitializeUI();
            HookEvents();
            LoadPresets();
        }

        private void InitializeUI()
        {
            _patternTypeDropdown.options = new List<Dropdown.OptionData>
            {
                new Dropdown.OptionData("Herringbone"),
                new Dropdown.OptionData("Wave"),
                new Dropdown.OptionData("Block")
            };

            _groundTypeDropdown.options = new List<Dropdown.OptionData>
            {
                new Dropdown.OptionData("Dry Asphalt"),
                new Dropdown.OptionData("Wet Asphalt"),
                new Dropdown.OptionData("Dry Tile"),
                new Dropdown.OptionData("Wet Tile"),
                new Dropdown.OptionData("Ice")
            };
        }

        private void HookEvents()
        {
            _patternTypeDropdown.onValueChanged.AddListener(OnPatternTypeChanged);
            _patternDepthSlider.onValueChanged.AddListener(OnPatternDepthChanged);
            _patternSpacingSlider.onValueChanged.AddListener(OnPatternSpacingChanged);
            _patternAngleSlider.onValueChanged.AddListener(OnPatternAngleChanged);
            _soleWidthSlider.onValueChanged.AddListener(OnSoleWidthChanged);
            _soleLengthSlider.onValueChanged.AddListener(OnSoleLengthChanged);
            _shoreHardnessSlider.onValueChanged.AddListener(OnShoreHardnessChanged);
            _elasticModulusSlider.onValueChanged.AddListener(OnElasticModulusChanged);
            _lossFactorSlider.onValueChanged.AddListener(OnLossFactorChanged);
            _hurstExponentSlider.onValueChanged.AddListener(OnHurstExponentChanged);
            _rmsRoughnessSlider.onValueChanged.AddListener(OnRmsRoughnessChanged);
            _groundTypeDropdown.onValueChanged.AddListener(OnGroundTypeChanged);
            _waterFilmSlider.onValueChanged.AddListener(OnWaterFilmChanged);
            _normalLoadSlider.onValueChanged.AddListener(OnNormalLoadChanged);
            _bemResolutionSlider.onValueChanged.AddListener(OnBemResolutionChanged);
            _hydrodynamicsToggle.onValueChanged.AddListener(OnHydrodynamicsToggled);
            _gpuAccelerationToggle.onValueChanged.AddListener(OnGpuAccelerationToggled);

            if (_minVelocitySlider != null) _minVelocitySlider.onValueChanged.AddListener(OnMinVelocityChanged);
            if (_maxVelocitySlider != null) _maxVelocitySlider.onValueChanged.AddListener(OnMaxVelocityChanged);
            if (_velocitySamplesSlider != null) _velocitySamplesSlider.onValueChanged.AddListener(OnVelocitySamplesChanged);
            if (_stickSlipToggle != null) _stickSlipToggle.onValueChanged.AddListener(OnStickSlipToggled);
            if (_staticFrictionMultiplierSlider != null) _staticFrictionMultiplierSlider.onValueChanged.AddListener(OnStaticFrictionMultiplierChanged);
            if (_transitionVelocitySlider != null) _transitionVelocitySlider.onValueChanged.AddListener(OnTransitionVelocityChanged);
            if (_transitionSharpnessSlider != null) _transitionSharpnessSlider.onValueChanged.AddListener(OnTransitionSharpnessChanged);
            if (_edgeSmoothingToggle != null) _edgeSmoothingToggle.onValueChanged.AddListener(OnEdgeSmoothingToggled);
            if (_edgeSmoothingRadiusSlider != null) _edgeSmoothingRadiusSlider.onValueChanged.AddListener(OnEdgeSmoothingRadiusChanged);
            if (_edgeStressReductionSlider != null) _edgeStressReductionSlider.onValueChanged.AddListener(OnEdgeStressReductionChanged);

            if (_wearSimulationToggle != null) _wearSimulationToggle.onValueChanged.AddListener(OnWearSimulationToggled);
            if (_wearCoefficientSlider != null) _wearCoefficientSlider.onValueChanged.AddListener(OnWearCoefficientChanged);
            if (_slidingDistanceSlider != null) _slidingDistanceSlider.onValueChanged.AddListener(OnSlidingDistanceChanged);
            if (_thermalCouplingToggle != null) _thermalCouplingToggle.onValueChanged.AddListener(OnThermalCouplingToggled);
            if (_ambientTempSlider != null) _ambientTempSlider.onValueChanged.AddListener(OnAmbientTempChanged);
            if (_heatPartitionSlider != null) _heatPartitionSlider.onValueChanged.AddListener(OnHeatPartitionChanged);

            _generatePatternButton.onClick.AddListener(() => GeneratePatternClicked?.Invoke());
            _importStlButton.onClick.AddListener(() => ImportStlClicked?.Invoke());
            _startSimulationButton.onClick.AddListener(() => StartSimulationClicked?.Invoke());
            _resetButton.onClick.AddListener(() => ResetClicked?.Invoke());
            _exportDataButton.onClick.AddListener(() => ExportDataClicked?.Invoke());
            if (_exportStlButton != null) _exportStlButton.onClick.AddListener(() => ExportPatternClicked?.Invoke());
            if (_exportWornButton != null) _exportWornButton.onClick.AddListener(() => ExportWornPatternClicked?.Invoke());
        }

        private void LoadPresets()
        {
            _rubberMaterial = PresetDataFactory.CreateMediumRubber();
            _groundSurface = PresetDataFactory.CreateDryAsphalt();

            _shoreHardnessSlider.value = _rubberMaterial.shoreHardness;
            _elasticModulusSlider.value = _rubberMaterial.elasticModulus;
            _lossFactorSlider.value = _rubberMaterial.lossFactor;
            _hurstExponentSlider.value = _rubberMaterial.hurstExponent;
            _rmsRoughnessSlider.value = _rubberMaterial.rmsRoughness;

            _groundTypeDropdown.value = (int)_groundSurface.groundType;
            _waterFilmSlider.value = _groundSurface.waterFilmThickness;

            if (_minVelocitySlider != null) _minVelocitySlider.value = _simulationParams.minVelocity;
            if (_maxVelocitySlider != null) _maxVelocitySlider.value = _simulationParams.maxVelocity;
            if (_velocitySamplesSlider != null) _velocitySamplesSlider.value = _simulationParams.velocitySamples;
            if (_stickSlipToggle != null) _stickSlipToggle.isOn = _simulationParams.enableStickSlip;
            if (_staticFrictionMultiplierSlider != null) _staticFrictionMultiplierSlider.value = _simulationParams.staticFrictionMultiplier;
            if (_transitionVelocitySlider != null) _transitionVelocitySlider.value = _simulationParams.transitionVelocity;
            if (_transitionSharpnessSlider != null) _transitionSharpnessSlider.value = _simulationParams.transitionSharpness;
            if (_edgeSmoothingToggle != null) _edgeSmoothingToggle.isOn = _simulationParams.enableEdgeSmoothing;
            if (_edgeSmoothingRadiusSlider != null) _edgeSmoothingRadiusSlider.value = _simulationParams.edgeSmoothingRadius;
            if (_edgeStressReductionSlider != null) _edgeStressReductionSlider.value = _simulationParams.edgeStressReduction;

            if (_wearSimulationToggle != null) _wearSimulationToggle.isOn = _simulationParams.enableWearSimulation;
            if (_wearCoefficientSlider != null) _wearCoefficientSlider.value = _simulationParams.wearCoefficient;
            if (_slidingDistanceSlider != null) _slidingDistanceSlider.value = _simulationParams.slidingDistance;
            if (_thermalCouplingToggle != null) _thermalCouplingToggle.isOn = _simulationParams.enableThermalCoupling;
            if (_ambientTempSlider != null) _ambientTempSlider.value = _simulationParams.ambientTemperature;
            if (_heatPartitionSlider != null) _heatPartitionSlider.value = _simulationParams.heatPartitionCoeff;

            UpdateUIValues();
        }

        private void OnPatternTypeChanged(int value)
        {
            _patternConfig.patternType = (PatternType)value;
            PatternConfigChanged?.Invoke(_patternConfig);
        }

        private void OnPatternDepthChanged(float value)
        {
            _patternConfig.patternDepth = value;
            _patternDepthValue.text = $"{value:0.0} mm";
            PatternConfigChanged?.Invoke(_patternConfig);
        }

        private void OnPatternSpacingChanged(float value)
        {
            _patternConfig.patternSpacing = value;
            _patternSpacingValue.text = $"{value:0.0} mm";
            PatternConfigChanged?.Invoke(_patternConfig);
        }

        private void OnPatternAngleChanged(float value)
        {
            _patternConfig.patternAngle = value;
            _patternAngleValue.text = $"{value:0}°";
            PatternConfigChanged?.Invoke(_patternConfig);
        }

        private void OnSoleWidthChanged(float value)
        {
            _patternConfig.soleWidth = value;
            _soleWidthValue.text = $"{value:0.0} cm";
            PatternConfigChanged?.Invoke(_patternConfig);
        }

        private void OnSoleLengthChanged(float value)
        {
            _patternConfig.soleLength = value;
            _soleLengthValue.text = $"{value:0.0} cm";
            PatternConfigChanged?.Invoke(_patternConfig);
        }

        private void OnShoreHardnessChanged(float value)
        {
            _rubberMaterial.shoreHardness = value;
            _shoreHardnessValue.text = $"Shore A {value:0}";
            RubberMaterialChanged?.Invoke(_rubberMaterial);
        }

        private void OnElasticModulusChanged(float value)
        {
            _rubberMaterial.elasticModulus = value;
            _elasticModulusValue.text = $"{value:0.0} MPa";
            RubberMaterialChanged?.Invoke(_rubberMaterial);
        }

        private void OnLossFactorChanged(float value)
        {
            _rubberMaterial.lossFactor = value;
            _lossFactorValue.text = $"{value:0.00}";
            RubberMaterialChanged?.Invoke(_rubberMaterial);
        }

        private void OnHurstExponentChanged(float value)
        {
            _rubberMaterial.hurstExponent = value;
            _hurstExponentValue.text = $"{value:0.00}";
            RubberMaterialChanged?.Invoke(_rubberMaterial);
        }

        private void OnRmsRoughnessChanged(float value)
        {
            _rubberMaterial.rmsRoughness = value;
            _rmsRoughnessValue.text = $"{value:0} μm";
            RubberMaterialChanged?.Invoke(_rubberMaterial);
        }

        private void OnGroundTypeChanged(int value)
        {
            _groundSurface = value switch
            {
                0 => PresetDataFactory.CreateDryAsphalt(),
                1 => PresetDataFactory.CreateWetAsphalt(),
                2 => PresetDataFactory.CreateDryTile(),
                3 => PresetDataFactory.CreateWetTile(),
                4 => PresetDataFactory.CreateIce(),
                _ => PresetDataFactory.CreateDryAsphalt()
            };

            _waterFilmSlider.value = _groundSurface.waterFilmThickness;
            GroundSurfaceChanged?.Invoke(_groundSurface);
        }

        private void OnWaterFilmChanged(float value)
        {
            _groundSurface.waterFilmThickness = value;
            _waterFilmValue.text = $"{value:0.0} μm";
            GroundSurfaceChanged?.Invoke(_groundSurface);
        }

        private void OnNormalLoadChanged(float value)
        {
            _simulationParams.normalLoad = value;
            _normalLoadValue.text = $"{value:0} N";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnBemResolutionChanged(float value)
        {
            _simulationParams.bemResolution = Mathf.RoundToInt(value);
            _bemResolutionValue.text = $"{Mathf.RoundToInt(value)}x{Mathf.RoundToInt(value)}";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnHydrodynamicsToggled(bool enabled)
        {
            _simulationParams.includeHydrodynamics = enabled;
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnGpuAccelerationToggled(bool enabled)
        {
            _simulationParams.useGpuAcceleration = enabled;
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnMinVelocityChanged(float value)
        {
            _simulationParams.minVelocity = value;
            if (_minVelocityValue != null) _minVelocityValue.text = $"{value:0.000000} m/s";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnMaxVelocityChanged(float value)
        {
            _simulationParams.maxVelocity = value;
            if (_maxVelocityValue != null) _maxVelocityValue.text = $"{value:0.0} m/s";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnVelocitySamplesChanged(float value)
        {
            _simulationParams.velocitySamples = Mathf.RoundToInt(value);
            if (_velocitySamplesValue != null) _velocitySamplesValue.text = $"{Mathf.RoundToInt(value)} points";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnStickSlipToggled(bool enabled)
        {
            _simulationParams.enableStickSlip = enabled;
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnStaticFrictionMultiplierChanged(float value)
        {
            _simulationParams.staticFrictionMultiplier = value;
            if (_staticFrictionMultiplierValue != null) _staticFrictionMultiplierValue.text = $"{value:0.00}x";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnTransitionVelocityChanged(float value)
        {
            _simulationParams.transitionVelocity = value;
            if (_transitionVelocityValue != null) _transitionVelocityValue.text = $"{value:0.0000} m/s";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnTransitionSharpnessChanged(float value)
        {
            _simulationParams.transitionSharpness = value;
            if (_transitionSharpnessValue != null) _transitionSharpnessValue.text = $"{value:0.00}";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnEdgeSmoothingToggled(bool enabled)
        {
            _simulationParams.enableEdgeSmoothing = enabled;
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnEdgeSmoothingRadiusChanged(float value)
        {
            _simulationParams.edgeSmoothingRadius = value;
            if (_edgeSmoothingRadiusValue != null) _edgeSmoothingRadiusValue.text = $"{value:0.0} cells";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnEdgeStressReductionChanged(float value)
        {
            _simulationParams.edgeStressReduction = value;
            if (_edgeStressReductionValue != null) _edgeStressReductionValue.text = $"{value * 100:0}%";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnWearSimulationToggled(bool enabled)
        {
            _simulationParams.enableWearSimulation = enabled;
            WearSimulationToggled?.Invoke(enabled);
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnWearCoefficientChanged(float value)
        {
            _simulationParams.wearCoefficient = value;
            if (_wearCoefficientValue != null) _wearCoefficientValue.text = $"{value:0.00e0}";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnSlidingDistanceChanged(float value)
        {
            _simulationParams.slidingDistance = value;
            if (_slidingDistanceValue != null) _slidingDistanceValue.text = $"{value:0} m";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnThermalCouplingToggled(bool enabled)
        {
            _simulationParams.enableThermalCoupling = enabled;
            ThermalCouplingToggled?.Invoke(enabled);
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnAmbientTempChanged(float value)
        {
            _simulationParams.ambientTemperature = value;
            if (_ambientTempValue != null) _ambientTempValue.text = $"{value:0.0} °C";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void OnHeatPartitionChanged(float value)
        {
            _simulationParams.heatPartitionCoeff = value;
            if (_heatPartitionValue != null) _heatPartitionValue.text = $"{value:0.00}";
            SimulationParamsChanged?.Invoke(_simulationParams);
        }

        private void UpdateUIValues()
        {
            _patternDepthValue.text = $"{_patternConfig.patternDepth:0.0} mm";
            _patternSpacingValue.text = $"{_patternConfig.patternSpacing:0.0} mm";
            _patternAngleValue.text = $"{_patternConfig.patternAngle:0}°";
            _soleWidthValue.text = $"{_patternConfig.soleWidth:0.0} cm";
            _soleLengthValue.text = $"{_patternConfig.soleLength:0.0} cm";
            _shoreHardnessValue.text = $"Shore A {_rubberMaterial.shoreHardness:0}";
            _elasticModulusValue.text = $"{_rubberMaterial.elasticModulus:0.0} MPa";
            _lossFactorValue.text = $"{_rubberMaterial.lossFactor:0.00}";
            _hurstExponentValue.text = $"{_rubberMaterial.hurstExponent:0.00}";
            _rmsRoughnessValue.text = $"{_rubberMaterial.rmsRoughness:0} μm";
            _waterFilmValue.text = $"{_groundSurface.waterFilmThickness:0.0} μm";
            _normalLoadValue.text = $"{_simulationParams.normalLoad:0} N";
            _bemResolutionValue.text = $"{_simulationParams.bemResolution}x{_simulationParams.bemResolution}";

            if (_minVelocityValue != null) _minVelocityValue.text = $"{_simulationParams.minVelocity:0.000000} m/s";
            if (_maxVelocityValue != null) _maxVelocityValue.text = $"{_simulationParams.maxVelocity:0.0} m/s";
            if (_velocitySamplesValue != null) _velocitySamplesValue.text = $"{_simulationParams.velocitySamples} points";
            if (_staticFrictionMultiplierValue != null) _staticFrictionMultiplierValue.text = $"{_simulationParams.staticFrictionMultiplier:0.00}x";
            if (_transitionVelocityValue != null) _transitionVelocityValue.text = $"{_simulationParams.transitionVelocity:0.0000} m/s";
            if (_transitionSharpnessValue != null) _transitionSharpnessValue.text = $"{_simulationParams.transitionSharpness:0.00}";
            if (_edgeSmoothingRadiusValue != null) _edgeSmoothingRadiusValue.text = $"{_simulationParams.edgeSmoothingRadius:0.0} cells";
            if (_edgeStressReductionValue != null) _edgeStressReductionValue.text = $"{_simulationParams.edgeStressReduction * 100:0}%";

            if (_wearCoefficientValue != null) _wearCoefficientValue.text = $"{_simulationParams.wearCoefficient:0.00e0}";
            if (_slidingDistanceValue != null) _slidingDistanceValue.text = $"{_simulationParams.slidingDistance:0} m";
            if (_ambientTempValue != null) _ambientTempValue.text = $"{_simulationParams.ambientTemperature:0.0} °C";
            if (_heatPartitionValue != null) _heatPartitionValue.text = $"{_simulationParams.heatPartitionCoeff:0.00}";
        }

        public void UpdateProgress(float progress, string status = null)
        {
            _progressBar.value = progress;
            _progressText.text = $"{progress * 100:0}%";
            if (!string.IsNullOrEmpty(status))
            {
                _statusText.text = status;
            }
        }

        public void SetStatus(SimulationState state, string message = null)
        {
            string stateText = state switch
            {
                SimulationState.Idle => "Ready",
                SimulationState.Running => "Computing...",
                SimulationState.Paused => "Paused",
                SimulationState.Completed => "Completed",
                SimulationState.Error => "Error",
                _ => "Unknown"
            };

            _statusText.text = string.IsNullOrEmpty(message) ? stateText : $"{stateText}: {message}";

            _startSimulationButton.interactable = state == SimulationState.Idle || state == SimulationState.Completed || state == SimulationState.Error;
        }

        public void SetInteractable(bool interactable)
        {
            _generatePatternButton.interactable = interactable;
            _importStlButton.interactable = interactable;
            _exportDataButton.interactable = interactable;
        }

        public event System.Action GeneratePatternClicked;
        public event System.Action ImportStlClicked;
        public event System.Action StartSimulationClicked;
        public event System.Action ResetClicked;
        public event System.Action ExportDataClicked;
        public event System.Action ExportPatternClicked;
        public event System.Action ExportWornPatternClicked;

        public event System.Action<PatternConfig> PatternConfigChanged;
        public event System.Action<RubberMaterial> RubberMaterialChanged;
        public event System.Action<GroundSurface> GroundSurfaceChanged;
        public event System.Action<SimulationParams> SimulationParamsChanged;
        public event System.Action<bool> WearSimulationToggled;
        public event System.Action<bool> ThermalCouplingToggled;
    }
}
