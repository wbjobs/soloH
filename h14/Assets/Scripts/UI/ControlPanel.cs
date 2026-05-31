using UnityEngine;
using UnityEngine.UI;
using FlowVisualization.Core;
using FlowVisualization.Particles;
using FlowVisualization.Rendering;
using FlowVisualization.Interaction;
using FlowVisualization.Compute;
using FlowVisualization.Analysis;

namespace FlowVisualization.UI
{
    public class ControlPanel : MonoBehaviour
    {
        [Header("References")]
        public ParticleSystemManager ParticleSystem;
        public SeedPointPlacer SeedPlacer;
        public ColorMapManager ColorMap;
        public FlyCameraController CameraController;
        public GPUParticleSystem GPUParticleSystem;
        public LCSFieldRenderer LCSRenderer;

        [Header("UI Elements")]
        public Text StatusText;
        public Text PerformanceText;
        public Dropdown LineTypeDropdown;
        public Dropdown DirectionDropdown;
        public Dropdown ColorFieldDropdown;
        public Dropdown ColormapDropdown;
        public Slider SpeedSlider;
        public Slider LineWidthSlider;
        public Slider ParticleSizeSlider;
        public Toggle PauseToggle;
        public Toggle ParallelToggle;
        public Toggle GPUToggle;
        public Toggle LCSToggle;
        public Toggle AttractLCSToggle;
        public Toggle RepelLCSToggle;
        public Slider LCSThresholdSlider;
        public Slider LCSIntegrationSlider;
        public Button ResetButton;
        public Button ClearSeedsButton;
        public Button ComputeLCSButton;

        private void Start()
        {
            InitializeUI();
            BindEvents();
        }

        private void InitializeUI()
        {
            if (LineTypeDropdown != null)
            {
                LineTypeDropdown.ClearOptions();
                LineTypeDropdown.AddOptions(new System.Collections.Generic.List<string>
                {
                    "Pathline (路径线)",
                    "Streakline (脉线)",
                    "Stripline (条纹线)"
                });
            }

            if (DirectionDropdown != null)
            {
                DirectionDropdown.ClearOptions();
                DirectionDropdown.AddOptions(new System.Collections.Generic.List<string>
                {
                    "Forward (前向)",
                    "Backward (后向)"
                });
            }

            if (ColorFieldDropdown != null)
            {
                ColorFieldDropdown.ClearOptions();
                ColorFieldDropdown.AddOptions(new System.Collections.Generic.List<string>
                {
                    "Velocity (速度幅值)",
                    "Vorticity (涡量)",
                    "Pressure (压力)",
                    "Lyapunov (李雅普诺夫)",
                    "FTLE",
                    "Stretching (拉伸率)",
                    "Compression (压缩率)"
                });
            }

            if (ColormapDropdown != null)
            {
                ColormapDropdown.ClearOptions();
                ColormapDropdown.AddOptions(new System.Collections.Generic.List<string>
                {
                    "Jet",
                    "Viridis",
                    "Plasma",
                    "Rainbow",
                    "CoolWarm",
                    "Grayscale"
                });
            }

            if (LCSThresholdSlider != null)
            {
                LCSThresholdSlider.minValue = 0f;
                LCSThresholdSlider.maxValue = 1f;
                LCSThresholdSlider.value = 0.3f;
            }

            if (LCSIntegrationSlider != null)
            {
                LCSIntegrationSlider.minValue = 0.1f;
                LCSIntegrationSlider.maxValue = 10f;
                LCSIntegrationSlider.value = 2.0f;
            }
        }

        private void BindEvents()
        {
            if (LineTypeDropdown != null)
            {
                LineTypeDropdown.onValueChanged.AddListener(OnLineTypeChanged);
            }

            if (DirectionDropdown != null)
            {
                DirectionDropdown.onValueChanged.AddListener(OnDirectionChanged);
            }

            if (ColorFieldDropdown != null)
            {
                ColorFieldDropdown.onValueChanged.AddListener(OnColorFieldChanged);
            }

            if (ColormapDropdown != null)
            {
                ColormapDropdown.onValueChanged.AddListener(OnColormapChanged);
            }

            if (SpeedSlider != null)
            {
                SpeedSlider.onValueChanged.AddListener(OnSpeedChanged);
            }

            if (LineWidthSlider != null)
            {
                LineWidthSlider.onValueChanged.AddListener(OnLineWidthChanged);
            }

            if (ParticleSizeSlider != null)
            {
                ParticleSizeSlider.onValueChanged.AddListener(OnParticleSizeChanged);
            }

            if (PauseToggle != null)
            {
                PauseToggle.onValueChanged.AddListener(OnPauseToggled);
            }

            if (ParallelToggle != null)
            {
                ParallelToggle.onValueChanged.AddListener(OnParallelToggled);
            }

            if (GPUToggle != null)
            {
                GPUToggle.onValueChanged.AddListener(OnGPUToggled);
            }

            if (LCSToggle != null)
            {
                LCSToggle.onValueChanged.AddListener(OnLCSToggled);
            }

            if (AttractLCSToggle != null)
            {
                AttractLCSToggle.onValueChanged.AddListener(OnAttractLCSToggled);
            }

            if (RepelLCSToggle != null)
            {
                RepelLCSToggle.onValueChanged.AddListener(OnRepelLCSToggled);
            }

            if (LCSThresholdSlider != null)
            {
                LCSThresholdSlider.onValueChanged.AddListener(OnLCSThresholdChanged);
            }

            if (LCSIntegrationSlider != null)
            {
                LCSIntegrationSlider.onValueChanged.AddListener(OnLCSIntegrationChanged);
            }

            if (ResetButton != null)
            {
                ResetButton.onClick.AddListener(OnResetClicked);
            }

            if (ClearSeedsButton != null)
            {
                ClearSeedsButton.onClick.AddListener(OnClearSeedsClicked);
            }

            if (ComputeLCSButton != null)
            {
                ComputeLCSButton.onClick.AddListener(OnComputeLCSClicked);
            }
        }

        private void Update()
        {
            UpdateStatusText();
            UpdatePerformanceText();
        }

        private void UpdateStatusText()
        {
            if (StatusText == null || ParticleSystem == null) return;

            string status = ParticleSystem.IsPaused ? "PAUSED" : "RUNNING";
            string direction = ParticleSystem.Direction == IntegrationDirection.Forward ? "→" : "←";
            string dataSource = ParticleSystem.UseSyntheticData ? "Synthetic" : "NetCDF";
            string lcsStatus = LCSRenderer != null && LCSRenderer.ShowLCS ? "ON" : "OFF";
            string gpuStatus = GPUParticleSystem != null && GPUParticleSystem.UseGPU && GPUParticleSystem.IsInitialized ? "ON" : "OFF";
            
            StatusText.text = $"Status: {status} | " +
                              $"Time: {ParticleSystem.SimulationTime:F3}s | " +
                              $"Dir: {direction} | " +
                              $"Source: {dataSource} | " +
                              $"GPU: {gpuStatus} | " +
                              $"LCS: {lcsStatus} | " +
                              $"Seeds: {ParticleSystem.SeedPoints.Count}";
        }

        private void UpdatePerformanceText()
        {
            if (PerformanceText == null || ParticleSystem == null) return;

            string perfText = $"Particles: {ParticleSystem.TotalActiveParticles} | " +
                              $"Rate: {ParticleSystem.ParticlesProcessedPerSecond}/s | " +
                              $"FPS: {(int)(1f / Time.deltaTime)} | " +
                              $"Parallel: {ParticleSystem.UseParallelProcessing}";

            if (GPUParticleSystem != null && GPUParticleSystem.IsInitialized && GPUParticleSystem.UseGPU)
            {
                perfText += $" | GPU FPS: {GPUParticleSystem.AverageFramesPerSecond:F1} | " +
                            $"GPU Rate: {GPUParticleSystem.AverageParticlesPerSecond:F0}/s";
            }

            PerformanceText.text = perfText;
        }

        private void OnLineTypeChanged(int index)
        {
            if (SeedPlacer != null)
            {
                SeedPlacer.SetLineType((LineType)index);
            }
        }

        private void OnDirectionChanged(int index)
        {
            if (ParticleSystem != null)
            {
                ParticleSystem.SetIntegrationDirection((IntegrationDirection)index);
            }
        }

        private void OnColorFieldChanged(int index)
        {
            ScalarFieldType type = (ScalarFieldType)index;
            if (ParticleSystem != null)
            {
                ParticleSystem.UpdateColorField(type);
            }
            if (ColorMap != null)
            {
                ColorMap.SetFieldType(type);
            }
        }

        private void OnColormapChanged(int index)
        {
            if (ColorMap != null)
            {
                ColorMap.SetColormap((ColorMapManager.ColormapType)index);
            }
        }

        private void OnSpeedChanged(float value)
        {
            if (ParticleSystem != null)
            {
                ParticleSystem.SimulationSpeed = value;
            }
        }

        private void OnLineWidthChanged(float value)
        {
            LineRendererManager lrm = GetComponent<LineRendererManager>();
            if (lrm != null)
            {
                lrm.SetLineWidth(value);
            }
        }

        private void OnParticleSizeChanged(float value)
        {
            ParticleRenderer pr = GetComponent<ParticleRenderer>();
            if (pr != null)
            {
                pr.SetParticleSize(value);
            }
        }

        private void OnPauseToggled(bool isPaused)
        {
            if (ParticleSystem != null)
            {
                ParticleSystem.IsPaused = isPaused;
            }
        }

        private void OnParallelToggled(bool useParallel)
        {
            if (ParticleSystem != null)
            {
                ParticleSystem.UseParallelProcessing = useParallel;
            }
        }

        private void OnResetClicked()
        {
            if (ParticleSystem != null)
            {
                ParticleSystem.ResetSimulation();
            }
        }

        private void OnClearSeedsClicked()
        {
            if (SeedPlacer != null)
            {
                SeedPlacer.ClearAllSeeds();
            }
        }

        private void OnGPUToggled(bool useGPU)
        {
            if (GPUParticleSystem != null)
            {
                GPUParticleSystem.UseGPU = useGPU;
            }
        }

        private void OnLCSToggled(bool showLCS)
        {
            if (LCSRenderer != null)
            {
                LCSRenderer.ToggleLCS(showLCS);
            }
        }

        private void OnAttractLCSToggled(bool show)
        {
            if (LCSRenderer != null)
            {
                LCSRenderer.ToggleAttracting(show);
            }
        }

        private void OnRepelLCSToggled(bool show)
        {
            if (LCSRenderer != null)
            {
                LCSRenderer.ToggleRepelling(show);
            }
        }

        private void OnLCSThresholdChanged(float threshold)
        {
            if (LCSRenderer != null)
            {
                LCSRenderer.SetThreshold(threshold);
            }
        }

        private void OnLCSIntegrationChanged(float integrationTime)
        {
            if (LCSRenderer != null)
            {
                LCSRenderer.SetIntegrationTime(integrationTime);
            }
        }

        private void OnComputeLCSClicked()
        {
            if (LCSRenderer != null && ParticleSystem != null)
            {
                LCSRenderer.UpdateLCSData(ParticleSystem.SimulationTime);
            }
        }
    }
}
