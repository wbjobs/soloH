using System;
using System.Collections.Generic;
using UnityEngine;
using GaitSimulation.Core;
using GaitSimulation.Gait;
using GaitSimulation.Exoskeleton;
using GaitSimulation.Battery;
using GaitSimulation.Optimization;
using GaitSimulation.Visualization;
using GaitSimulation.Safety;
using GaitSimulation.Learning;

namespace GaitSimulation.Simulation
{
    public class SimulationManager : MonoBehaviour
    {
        [Header("Simulation Parameters")]
        public float gaitCycleDuration = 1.2f;
        public float bodyMass = 70f;
        public float slopeAngle = 0f;
        public float simulationDuration = 10f;
        public bool useDynamicProgramming = true;
        public int dpTimeSteps = 60;
        public int dpSOCStates = 20;

        [Header("New Features")]
        public bool enableFatigueModel = true;
        public bool enableGaitLearning = true;
        public bool enableFallDetection = true;

        [Header("References")]
        public JointPowerGraph jointPowerGraph;
        public EnergyFlowGraph energyFlowGraph;

        [Header("Runtime State")]
        public bool isSimulating = false;
        public float currentTime = 0f;

        private SimulationConfig _simConfig;
        private ExoskeletonConfig _exoConfig;
        private BatteryState _batteryState;

        private GaitModel _gaitModel;
        private ExoskeletonController _exoskeletonController;
        private BatteryManagementSystem _bms;
        private InputOutputManager _ioManager;
        private DynamicPlanner _dynamicPlanner;

        private FatigueModel _fatigueModel;
        private GaitLearner _gaitLearner;
        private FallDetector _fallDetector;

        public event Action OnSimulationStarted;
        public event Action OnSimulationPaused;
        public event Action OnSimulationResumed;
        public event Action OnSimulationStopped;
        public event Action<SimulationResult> OnSimulationCompleted;

        private void Awake()
        {
            InitializeComponents();
        }

        private void InitializeComponents()
        {
            _simConfig = new SimulationConfig
            {
                gaitCycleDuration = gaitCycleDuration,
                bodyMass = bodyMass,
                slopeAngle = slopeAngle
            };

            _exoConfig = new ExoskeletonConfig();
            _batteryState = new BatteryState();

            _gaitModel = new GaitModel(_simConfig);
            _exoskeletonController = new ExoskeletonController(_exoConfig, _simConfig);
            _bms = new BatteryManagementSystem(_batteryState);
            _ioManager = new InputOutputManager(_simConfig);

            _ioManager.SetInputParameters(gaitCycleDuration, bodyMass, slopeAngle);

            if (useDynamicProgramming)
            {
                _dynamicPlanner = new DynamicPlanner(_simConfig, _exoConfig, _batteryState);
            }

            if (enableFatigueModel)
            {
                _fatigueModel = new FatigueModel(_simConfig);
                _fatigueModel.OnFatigueLevelChanged += HandleFatigueLevelChanged;
                _fatigueModel.OnAssistStrategyChanged += HandleAssistStrategyChanged;
                _fatigueModel.OnFatigueCritical += HandleFatigueCritical;
            }

            if (enableGaitLearning)
            {
                _gaitLearner = new GaitLearner(_simConfig);
                _gaitLearner.OnModelUpdated += HandleModelUpdated;
                _gaitLearner.OnModelConverged += HandleModelConverged;
                _gaitLearner.OnLearningProgress += HandleLearningProgress;
            }

            if (enableFallDetection)
            {
                _fallDetector = new FallDetector(_simConfig, _gaitModel);
                _fallDetector.OnFallRiskChanged += HandleFallRiskChanged;
                _fallDetector.OnBrakingLevelChanged += HandleBrakingLevelChanged;
                _fallDetector.OnFallDetected += HandleFallDetected;
                _fallDetector.OnRecoveryComplete += HandleRecoveryComplete;
            }

            _ioManager.OnDataRecorded += HandleDataRecorded;
            _ioManager.OnSimulationComplete += HandleSimulationComplete;
        }

        private void Start()
        {
            if (useDynamicProgramming && _dynamicPlanner != null)
            {
                Debug.Log("Computing optimal control policy...");
                _dynamicPlanner.ComputeOptimalPolicy(dpTimeSteps, dpSOCStates);
                Debug.Log(_dynamicPlanner.GetPolicySummary());
            }
        }

        private void Update()
        {
            if (isSimulating)
            {
                float deltaTime = Time.deltaTime;
                AdvanceSimulation(deltaTime);
            }
        }

        public void StartSimulation()
        {
            if (isSimulating) return;

            ResetSimulation();

            if (useDynamicProgramming && _dynamicPlanner != null && !_dynamicPlanner.PolicyComputed)
            {
                _dynamicPlanner.ComputeOptimalPolicy(dpTimeSteps, dpSOCStates);
            }

            isSimulating = true;
            currentTime = 0f;
            OnSimulationStarted?.Invoke();
            Debug.Log($"Simulation started. Duration: {simulationDuration}s");
        }

        public void PauseSimulation()
        {
            if (!isSimulating) return;

            isSimulating = false;
            OnSimulationPaused?.Invoke();
            Debug.Log("Simulation paused.");
        }

        public void ResumeSimulation()
        {
            if (isSimulating) return;

            isSimulating = true;
            OnSimulationResumed?.Invoke();
            Debug.Log("Simulation resumed.");
        }

        public void StopSimulation()
        {
            isSimulating = false;
            _ioManager.FinalizeSimulation();
            OnSimulationStopped?.Invoke();
            Debug.Log("Simulation stopped.");
        }

        public void ResetSimulation()
        {
            currentTime = 0f;
            _gaitModel.Reset();
            _exoskeletonController.Reset();
            _bms.Reset();
            _ioManager.Reset();

            if (_dynamicPlanner != null)
            {
                _dynamicPlanner.Reset();
            }

            if (_fatigueModel != null)
            {
                _fatigueModel.Reset();
            }

            if (_gaitLearner != null)
            {
                _gaitLearner.Reset();
            }

            if (_fallDetector != null)
            {
                _fallDetector.Reset();
            }

            Debug.Log("Simulation reset.");
        }

        private void AdvanceSimulation(float deltaTime)
        {
            if (currentTime >= simulationDuration)
            {
                StopSimulation();
                return;
            }

            currentTime += deltaTime;

            _gaitModel.Update(currentTime, deltaTime);

            float gaitPhaseLeft = _gaitModel.GetNormalizedPhase(currentTime, Side.Left);
            float gaitPhaseRight = _gaitModel.GetNormalizedPhase(currentTime, Side.Right);

            if (_fatigueModel != null && enableFatigueModel)
            {
                _fatigueModel.Update(deltaTime, _gaitModel.JointStates, 1.0f);
            }

            if (_gaitLearner != null && enableGaitLearning)
            {
                _gaitLearner.Update(currentTime, _gaitModel.JointStates, gaitPhaseLeft, gaitPhaseRight);
            }

            if (_fallDetector != null && enableFallDetection)
            {
                _fallDetector.Update(currentTime, deltaTime, _gaitModel.JointStates, gaitPhaseLeft, gaitPhaseRight);
            }

            UpdateAdaptiveControlRatios(gaitPhaseLeft, gaitPhaseRight);

            Dictionary<(Side, JointType), ExoskeletonMode> modeOverrides = null;
            if (useDynamicProgramming && _dynamicPlanner != null && _dynamicPlanner.PolicyComputed)
            {
                modeOverrides = _dynamicPlanner.GetFullModeOverride(currentTime, _batteryState.currentSOC);
            }

            _exoskeletonController.Update(currentTime, deltaTime, _gaitModel.JointStates, modeOverrides);

            var (motorPower, generatorPower) = _exoskeletonController.GetTotalPowers(_gaitModel.JointStates);
            float netPower = motorPower - generatorPower;

            _bms.Update(netPower, deltaTime);

            _ioManager.Update(currentTime, deltaTime, _gaitModel, _exoskeletonController, _bms);
        }

        private void UpdateAdaptiveControlRatios(float gaitPhaseLeft, float gaitPhaseRight)
        {
            float baseAssistRatio = _exoConfig.assistRatio;
            float baseRegenRatio = _exoConfig.regenerationRatio;

            foreach (Side side in Enum.GetValues(typeof(Side)))
            {
                foreach (JointType joint in new[] { JointType.Knee, JointType.Ankle })
                {
                    float gaitPhase = side == Side.Left ? gaitPhaseLeft : gaitPhaseRight;

                    float assistRatio = baseAssistRatio;
                    float regenRatio = baseRegenRatio;

                    if (_fatigueModel != null && enableFatigueModel)
                    {
                        assistRatio = _fatigueModel.GetAdjustedAssistRatio(assistRatio, joint);
                        regenRatio = _fatigueModel.GetAdjustedRegenerationRatio(regenRatio, joint);
                    }

                    if (_gaitLearner != null && enableGaitLearning)
                    {
                        regenRatio = _gaitLearner.GetAdjustedRegenerationRatio(regenRatio, joint, gaitPhase);
                        assistRatio = _gaitLearner.GetPersonalizedAssistRatio(assistRatio, joint);
                    }

                    if (_fallDetector != null && enableFallDetection)
                    {
                        assistRatio = _fallDetector.GetModifiedAssistRatio(assistRatio, joint);
                        regenRatio = _fallDetector.GetModifiedRegenerationRatio(regenRatio, joint);
                    }

                    _exoskeletonController.SetAdaptiveAssistRatio(side, joint, assistRatio);
                    _exoskeletonController.SetAdaptiveRegenerationRatio(side, joint, regenRatio);
                }
            }
        }

        private void HandleDataRecorded(TimePointData data)
        {
            if (jointPowerGraph != null)
            {
                jointPowerGraph.AddData(data);
            }

            if (energyFlowGraph != null)
            {
                energyFlowGraph.AddData(data);
            }
        }

        private void HandleSimulationComplete(SimulationResult result)
        {
            OnSimulationCompleted?.Invoke(result);
            Debug.Log(result.GetSummaryText());
            Debug.Log(_bms.GetStatusText());

            if (_dynamicPlanner != null && _dynamicPlanner.PolicyComputed)
            {
                Debug.Log(_dynamicPlanner.GetPolicySummary());
            }

            if (_fatigueModel != null && enableFatigueModel)
            {
                Debug.Log(_fatigueModel.GetStatusText());
            }

            if (_gaitLearner != null && enableGaitLearning)
            {
                Debug.Log(_gaitLearner.GetLearningStatus());
            }

            if (_fallDetector != null && enableFallDetection)
            {
                Debug.Log(_fallDetector.GetStatusText());
            }
        }

        private void HandleFatigueLevelChanged(float fatigueLevel)
        {
        }

        private void HandleAssistStrategyChanged(float assistBoost)
        {
            Debug.Log($"Assist strategy updated: +{assistBoost * 100:F1}% boost");
        }

        private void HandleFatigueCritical()
        {
            Debug.LogWarning("⚠️ CRITICAL FATIGUE DETECTED! Consider resting.");
        }

        private void HandleModelUpdated(PersonalizedGaitModel model)
        {
        }

        private void HandleModelConverged()
        {
            Debug.Log("✓ Gait learning model converged! Personalized control active.");
        }

        private void HandleLearningProgress(float progress)
        {
        }

        private void HandleFallRiskChanged(FallRiskLevel riskLevel)
        {
            if (riskLevel >= FallRiskLevel.High)
            {
                Debug.LogWarning($"⚠️ Fall risk increased: {riskLevel}");
            }
        }

        private void HandleBrakingLevelChanged(BrakingLevel brakingLevel)
        {
            if (brakingLevel >= BrakingLevel.PartialBrake)
            {
                Debug.LogWarning($"⚠️ Braking activated: {brakingLevel}");
            }
        }

        private void HandleFallDetected()
        {
            Debug.LogError("🚨 FALL DETECTED! Emergency safety measures engaged.");
        }

        private void HandleRecoveryComplete()
        {
            Debug.Log("✓ Recovery complete. Normal operation resumed.");
        }

        public void UpdateInputParameters(float gaitCycle, float mass, float slope)
        {
            gaitCycleDuration = gaitCycle;
            bodyMass = mass;
            slopeAngle = slope;

            _ioManager.SetInputParameters(gaitCycle, mass, slope);

            if (useDynamicProgramming && _dynamicPlanner != null)
            {
                _dynamicPlanner.Reset();
                _dynamicPlanner.ComputeOptimalPolicy(dpTimeSteps, dpSOCStates);
            }

            Debug.Log($"Input parameters updated: Cycle={gaitCycle:F2}s, Mass={mass:F1}kg, Slope={slope:F1}°");
        }

        public SimulationConfig GetConfig() => _simConfig;
        public GaitModel GetGaitModel() => _gaitModel;
        public ExoskeletonController GetExoskeletonController() => _exoskeletonController;
        public BatteryManagementSystem GetBMS() => _bms;
        public InputOutputManager GetIOManager() => _ioManager;
        public DynamicPlanner GetDynamicPlanner() => _dynamicPlanner;
        public FatigueModel GetFatigueModel() => _fatigueModel;
        public GaitLearner GetGaitLearner() => _gaitLearner;
        public FallDetector GetFallDetector() => _fallDetector;
        public SimulationResult GetResult() => _ioManager?.Result;

        public Dictionary<string, float> GetCurrentMetrics()
        {
            return _ioManager?.GetCurrentMetrics() ?? new Dictionary<string, float>();
        }

        private void OnDestroy()
        {
            if (_ioManager != null)
            {
                _ioManager.OnDataRecorded -= HandleDataRecorded;
                _ioManager.OnSimulationComplete -= HandleSimulationComplete;
            }

            if (_fatigueModel != null)
            {
                _fatigueModel.OnFatigueLevelChanged -= HandleFatigueLevelChanged;
                _fatigueModel.OnAssistStrategyChanged -= HandleAssistStrategyChanged;
                _fatigueModel.OnFatigueCritical -= HandleFatigueCritical;
            }

            if (_gaitLearner != null)
            {
                _gaitLearner.OnModelUpdated -= HandleModelUpdated;
                _gaitLearner.OnModelConverged -= HandleModelConverged;
                _gaitLearner.OnLearningProgress -= HandleLearningProgress;
            }

            if (_fallDetector != null)
            {
                _fallDetector.OnFallRiskChanged -= HandleFallRiskChanged;
                _fallDetector.OnBrakingLevelChanged -= HandleBrakingLevelChanged;
                _fallDetector.OnFallDetected -= HandleFallDetected;
                _fallDetector.OnRecoveryComplete -= HandleRecoveryComplete;
            }
        }

        private void OnGUI()
        {
            DrawControlPanel();
            DrawMetricsDisplay();
            DrawFatigueDisplay();
            DrawLearningDisplay();
            DrawSafetyDisplay();
        }

        private void DrawControlPanel()
        {
            float panelX = 20f;
            float panelY = Screen.height - 140f;
            float panelW = 400f;
            float panelH = 120f;

            GUI.Box(new Rect(panelX, panelY, panelW, panelH), "Simulation Control");

            GUIStyle buttonStyle = new GUIStyle(GUI.skin.button)
            {
                fontSize = 12,
                fontStyle = FontStyle.Bold
            };

            if (GUI.Button(new Rect(panelX + 10f, panelY + 25f, 80f, 30f), isSimulating ? "Pause" : "Start", buttonStyle))
            {
                if (isSimulating) PauseSimulation();
                else StartSimulation();
            }

            if (GUI.Button(new Rect(panelX + 100f, panelY + 25f, 80f, 30f), "Stop", buttonStyle))
            {
                StopSimulation();
            }

            if (GUI.Button(new Rect(panelX + 190f, panelY + 25f, 80f, 30f), "Reset", buttonStyle))
            {
                ResetSimulation();
            }

            GUI.Label(new Rect(panelX + 10f, panelY + 65f, 100f, 20f), "Gait Cycle (s):");
            gaitCycleDuration = GUI.HorizontalSlider(new Rect(panelX + 110f, panelY + 70f, 120f, 20f), gaitCycleDuration, 0.5f, 3.0f);
            GUI.Label(new Rect(panelX + 235f, panelY + 65f, 50f, 20f), gaitCycleDuration.ToString("F2"));

            GUI.Label(new Rect(panelX + 10f, panelY + 90f, 100f, 20f), "Body Mass (kg):");
            bodyMass = GUI.HorizontalSlider(new Rect(panelX + 110f, panelY + 95f, 120f, 20f), bodyMass, 30f, 150f);
            GUI.Label(new Rect(panelX + 235f, panelY + 90f, 50f, 20f), bodyMass.ToString("F0"));

            GUI.Label(new Rect(panelX + 290f, panelY + 65f, 80f, 20f), "Slope (°):");
            slopeAngle = GUI.HorizontalSlider(new Rect(panelX + 290f, panelY + 90f, 100f, 20f), slopeAngle, -15f, 15f);
            GUI.Label(new Rect(panelX + 300f, panelY + 100f, 80f, 20f), slopeAngle.ToString("F1"));

            if (GUI.Button(new Rect(panelX + 300f, panelY + 25f, 90f, 30f), "Apply Params", buttonStyle))
            {
                UpdateInputParameters(gaitCycleDuration, bodyMass, slopeAngle);
            }
        }

        private void DrawMetricsDisplay()
        {
            float panelX = Screen.width - 220f;
            float panelY = 20f;
            float panelW = 200f;
            float panelH = 200f;

            GUI.Box(new Rect(panelX, panelY, panelW, panelH), "Real-time Metrics");

            var metrics = GetCurrentMetrics();
            GUIStyle labelStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 11,
                normal = { textColor = Color.white }
            };

            int i = 0;
            foreach (var kvp in metrics)
            {
                GUI.Label(new Rect(panelX + 10f, panelY + 25f + i * 22f, 180f, 20f),
                    $"{kvp.Key}: {kvp.Value:F2}", labelStyle);
                i++;
            }

            GUI.Label(new Rect(panelX + 10f, panelY + 25f + i * 22f, 180f, 20f),
                $"DP Enabled: {useDynamicProgramming}", labelStyle);
        }

        private void DrawFatigueDisplay()
        {
            if (_fatigueModel == null || !enableFatigueModel) return;

            float panelX = 20f;
            float panelY = 20f;
            float panelW = 220f;
            float panelH = 180f;

            GUI.Box(new Rect(panelX, panelY, panelW, panelH), "Muscle Fatigue");

            GUIStyle labelStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 11,
                normal = { textColor = Color.white }
            };

            GUIStyle titleStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 11,
                fontStyle = FontStyle.Bold,
                normal = { textColor = Color.yellow }
            };

            FatigueLevel level = _fatigueModel.GetFatigueLevel();
            Color levelColor = level == FatigueLevel.Critical ? Color.red :
                              level == FatigueLevel.High ? Color.yellow :
                              level == FatigueLevel.Moderate ? new Color(1f, 0.5f, 0f) :
                              level == FatigueLevel.Low ? Color.green : Color.white;

            GUI.Label(new Rect(panelX + 10f, panelY + 25f, 200f, 20f),
                $"Level: {level} ({_fatigueModel.overallFatigueLevel * 100:F0}%)",
                new GUIStyle(labelStyle) { normal = { textColor = levelColor } });

            GUI.Label(new Rect(panelX + 10f, panelY + 45f, 200f, 20f),
                $"Glycogen: {_fatigueModel.muscleGlycogen * 100:F0}%", labelStyle);
            GUI.Label(new Rect(panelX + 10f, panelY + 65f, 200f, 20f),
                $"Lactic Acid: {_fatigueModel.lacticAcid * 100:F0}%", labelStyle);
            GUI.Label(new Rect(panelX + 10f, panelY + 85f, 200f, 20f),
                $"Assist Boost: +{_fatigueModel.currentAssistBoost * 100:F0}%", labelStyle);

            GUI.Label(new Rect(panelX + 10f, panelY + 110f, 200f, 20f), "Muscle Groups:", titleStyle);
            GUI.Label(new Rect(panelX + 10f, panelY + 130f, 200f, 18f),
                $"  Quad: {_fatigueModel.quadriceps.fatigueLevel * 100:F0}%", labelStyle);
            GUI.Label(new Rect(panelX + 10f, panelY + 148f, 200f, 18f),
                $"  Gastroc: {_fatigueModel.gastrocnemius.fatigueLevel * 100:F0}%", labelStyle);
        }

        private void DrawLearningDisplay()
        {
            if (_gaitLearner == null || !enableGaitLearning) return;

            float panelX = 250f;
            float panelY = 20f;
            float panelW = 220f;
            float panelH = 150f;

            GUI.Box(new Rect(panelX, panelY, panelW, panelH), "Gait Learning");

            GUIStyle labelStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 11,
                normal = { textColor = Color.white }
            };

            var model = _gaitLearner.PersonalizedModel;
            float confidence = model.learningConfidence * 100f;

            GUI.Label(new Rect(panelX + 10f, panelY + 25f, 200f, 20f),
                $"Training: {model.trainingCycles} cycles", labelStyle);

            float barWidth = 180f;
            float barHeight = 15f;
            GUI.Box(new Rect(panelX + 10f, panelY + 50f, barWidth, barHeight), "");
            GUI.DrawTexture(new Rect(panelX + 12f, panelY + 52f, (barWidth - 4f) * confidence / 100f, barHeight - 4f),
                Texture2D.whiteTexture);
            GUI.Label(new Rect(panelX + 10f, panelY + 48f, 200f, 20f),
                $"Confidence: {confidence:F0}%", new GUIStyle(labelStyle) { normal = { textColor = Color.black } });

            GUI.Label(new Rect(panelX + 10f, panelY + 72f, 200f, 20f),
                $"Converged: {_gaitLearner.PersonalizedModel.trainingCycles >= 20}", labelStyle);
            GUI.Label(new Rect(panelX + 10f, panelY + 92f, 200f, 20f),
                $"Strength: {model.userStrengthLevel * 100:F0}%", labelStyle);
            GUI.Label(new Rect(panelX + 10f, panelY + 112f, 200f, 20f),
                $"Cadence: {model.preferredCadence:F0} spm", labelStyle);
            GUI.Label(new Rect(panelX + 10f, panelY + 130f, 200f, 18f),
                $"Opt Knee Phase: {model.optimalRegenerationPointKnee * 100:F0}%", labelStyle);
        }

        private void DrawSafetyDisplay()
        {
            if (_fallDetector == null || !enableFallDetection) return;

            float panelX = Screen.width - 220f;
            float panelY = 230f;
            float panelW = 200f;
            float panelH = 160f;

            GUI.Box(new Rect(panelX, panelY, panelW, panelH), "Fall Detection");

            GUIStyle labelStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 11,
                normal = { textColor = Color.white }
            };

            var risk = _fallDetector.CurrentRiskLevel;
            var braking = _fallDetector.CurrentBrakingLevel;
            var stability = _fallDetector.StabilityMetrics;

            Color riskColor = risk >= FallRiskLevel.Critical ? Color.red :
                             risk >= FallRiskLevel.High ? Color.yellow :
                             risk >= FallRiskLevel.Moderate ? new Color(1f, 0.5f, 0f) :
                             Color.green;

            GUI.Label(new Rect(panelX + 10f, panelY + 25f, 180f, 20f),
                $"Risk: {risk}", new GUIStyle(labelStyle) { normal = { textColor = riskColor } });

            Color brakeColor = braking >= BrakingLevel.FullBrake ? Color.red :
                              braking >= BrakingLevel.PartialBrake ? Color.yellow :
                              Color.green;

            GUI.Label(new Rect(panelX + 10f, panelY + 45f, 180f, 20f),
                $"Braking: {braking}", new GUIStyle(labelStyle) { normal = { textColor = brakeColor } });

            GUI.Label(new Rect(panelX + 10f, panelY + 68f, 180f, 18f),
                $"Stability: {stability.overallStabilityScore * 100:F0}%", labelStyle);
            GUI.Label(new Rect(panelX + 10f, panelY + 86f, 180f, 18f),
                $"Trunk Sway: {stability.trunkSwayAngle:F1}°", labelStyle);
            GUI.Label(new Rect(panelX + 10f, panelY + 104f, 180f, 18f),
                $"Margin of Safety: {stability.marginOfStability * 100:F0}%", labelStyle);
            GUI.Label(new Rect(panelX + 10f, panelY + 122f, 180f, 18f),
                $"DGI: {stability.dynamicGaitIndex * 100:F0}%", labelStyle);

            if (GUI.Button(new Rect(panelX + 10f, panelY + panelH - 35f, panelW - 20f, 25f),
                "Emergency Brake"))
            {
                _fallDetector.TriggerEmergencyBrake();
            }
        }
    }
}
