using System;
using System.Text;
using UnityEngine;
using UnityEngine.UI;
using LanderSim.Main;
using LanderSim.Core;
using LanderSim.Simulation;

namespace LanderSim.UI
{
    public class UIManager : MonoBehaviour
    {
        public LanderSimulator simulator;

        [Header("Panels")]
        public GameObject mainPanel;
        public GameObject infoPanel;
        public GameObject controlsPanel;
        public GameObject monteCarloPanel;

        [Header("Buttons")]
        public Button generateTerrainBtn;
        public Button generateGridBtn;
        public Button generateRiskMapBtn;
        public Button planPathBtn;
        public Button simulateBtn;
        public Button monteCarloBtn;
        public Button resetBtn;

        [Header("Dropdowns")]
        public Dropdown algorithmDropdown;

        [Header("Sliders")]
        public Slider timeScaleSlider;
        public Slider monteCarloCountSlider;

        [Header("Toggles")]
        public Toggle showHeatmapToggle;
        public Toggle showTrajectoryToggle;
        public Toggle showVelocityVectorsToggle;
        public Toggle showThrustVectorsToggle;
        public Toggle showDeviationVectorsToggle;

        [Header("Text Fields")]
        public Text infoText;
        public Text statusText;
        public Text monteCarloProgressText;
        public Text monteCarloResultsText;
        public Text selectedSiteText;

        [Header("Input Fields")]
        public InputField seedInputField;

        private bool isInitialized = false;

        void Start()
        {
            InitializeUI();
            ConnectEvents();

            if (simulator != null)
            {
                simulator.OnTerrainGenerated += UpdateTerrainInfo;
                simulator.OnRiskMapGenerated += UpdateRiskMapInfo;
                simulator.OnPathPlanned += UpdatePathInfo;
                simulator.OnSimulationStarted += OnSimulationStart;
                simulator.OnSimulationCompleted += OnSimulationEnd;
                simulator.OnMonteCarloProgress += UpdateMonteCarloProgress;
                simulator.OnMonteCarloComplete += UpdateMonteCarloResults;

                if (simulator.SiteSelector != null)
                {
                    simulator.SiteSelector.OnSiteSelected += OnSiteSelected;
                    simulator.SiteSelector.OnCandidatesUpdated += OnCandidatesUpdated;
                }
            }

            isInitialized = true;
        }

        private void InitializeUI()
        {
            if (algorithmDropdown != null)
            {
                algorithmDropdown.options.Clear();
                algorithmDropdown.options.Add(new Dropdown.OptionData("A*"));
                algorithmDropdown.options.Add(new Dropdown.OptionData("RRT"));
                algorithmDropdown.options.Add(new Dropdown.OptionData("RRT*"));
                algorithmDropdown.value = 0;
            }

            if (timeScaleSlider != null)
            {
                timeScaleSlider.minValue = 0.1f;
                timeScaleSlider.maxValue = 5.0f;
                timeScaleSlider.value = 1.0f;
            }

            if (monteCarloCountSlider != null)
            {
                monteCarloCountSlider.minValue = 10;
                monteCarloCountSlider.maxValue = 500;
                monteCarloCountSlider.value = 100;
            }

            UpdateStatus("Ready");
        }

        private void ConnectEvents()
        {
            if (generateTerrainBtn != null)
                generateTerrainBtn.onClick.AddListener(OnGenerateTerrain);
            if (generateGridBtn != null)
                generateGridBtn.onClick.AddListener(OnGenerateGrid);
            if (generateRiskMapBtn != null)
                generateRiskMapBtn.onClick.AddListener(OnGenerateRiskMap);
            if (planPathBtn != null)
                planPathBtn.onClick.AddListener(OnPlanPath);
            if (simulateBtn != null)
                simulateBtn.onClick.AddListener(OnSimulate);
            if (monteCarloBtn != null)
                monteCarloBtn.onClick.AddListener(OnRunMonteCarlo);
            if (resetBtn != null)
                resetBtn.onClick.AddListener(OnReset);

            if (algorithmDropdown != null)
                algorithmDropdown.onValueChanged.AddListener(OnAlgorithmChanged);
            if (timeScaleSlider != null)
                timeScaleSlider.onValueChanged.AddListener(OnTimeScaleChanged);

            if (showHeatmapToggle != null)
                showHeatmapToggle.onValueChanged.AddListener(OnToggleHeatmap);
            if (showTrajectoryToggle != null)
                showTrajectoryToggle.onValueChanged.AddListener(OnToggleTrajectory);
            if (showVelocityVectorsToggle != null)
                showVelocityVectorsToggle.onValueChanged.AddListener(OnToggleVelocityVectors);
            if (showThrustVectorsToggle != null)
                showThrustVectorsToggle.onValueChanged.AddListener(OnToggleThrustVectors);
            if (showDeviationVectorsToggle != null)
                showDeviationVectorsToggle.onValueChanged.AddListener(OnToggleDeviationVectors);

            if (seedInputField != null)
                seedInputField.onEndEdit.AddListener(OnSeedChanged);
        }

        private void OnGenerateTerrain()
        {
            if (simulator == null) return;

            UpdateStatus("Generating terrain...");
            simulator.GenerateTerrain();
        }

        private void OnGenerateGrid()
        {
            if (simulator == null) return;

            UpdateStatus("Generating grid...");
            simulator.GenerateGrid();
        }

        private void OnGenerateRiskMap()
        {
            if (simulator == null) return;

            UpdateStatus("Generating risk map...");
            simulator.GenerateRiskMap();
            simulator.GenerateCandidates();
        }

        private void OnPlanPath()
        {
            if (simulator == null || !simulator.SiteSelector.SelectedSite.HasValue)
            {
                UpdateStatus("Select a landing site first!");
                return;
            }

            UpdateStatus("Planning path...");
            simulator.PlanPathToSite(simulator.SiteSelector.SelectedSite.Value);
        }

        private void OnSimulate()
        {
            if (simulator == null) return;

            UpdateStatus("Simulating trajectory...");
            simulator.SimulateTrajectory();
            simulator.StartPlayback();
        }

        private async void OnRunMonteCarlo()
        {
            if (simulator == null) return;

            int count = (int)(monteCarloCountSlider != null ?
                monteCarloCountSlider.value : 100);

            UpdateStatus($"Running Monte Carlo ({count} simulations)...");
            simulator.RunMonteCarloSimulation(count);
        }

        private void OnReset()
        {
            if (simulator == null) return;

            simulator.ResetSimulation();
            UpdateStatus("Reset");
        }

        private void OnAlgorithmChanged(int index)
        {
            if (simulator == null) return;

            switch (index)
            {
                case 0:
                    simulator.pathAlgorithm = PathAlgorithm.AStar;
                    break;
                case 1:
                    simulator.pathAlgorithm = PathAlgorithm.RRT;
                    break;
                case 2:
                    simulator.pathAlgorithm = PathAlgorithm.RRTStar;
                    break;
            }
        }

        private void OnTimeScaleChanged(float value)
        {
            if (simulator != null)
            {
                simulator.timeScale = value;
                Time.timeScale = value;
            }
        }

        private void OnToggleHeatmap(bool show)
        {
            if (simulator != null && simulator.Heatmap != null)
            {
                simulator.Heatmap.ToggleHeatmap(show);
            }
        }

        private void OnToggleTrajectory(bool show)
        {
            if (simulator != null && simulator.TrajectoryViz != null)
            {
                if (simulator.TrajectoryViz.trajectoryLine != null)
                {
                    simulator.TrajectoryViz.trajectoryLine.gameObject.SetActive(show);
                }
            }
        }

        private void OnToggleVelocityVectors(bool show)
        {
            if (simulator != null && simulator.TrajectoryViz != null)
            {
                simulator.TrajectoryViz.ToggleVelocityVectors(show);
            }
        }

        private void OnToggleThrustVectors(bool show)
        {
            if (simulator != null && simulator.TrajectoryViz != null)
            {
                simulator.TrajectoryViz.ToggleThrustVectors(show);
            }
        }

        private void OnToggleDeviationVectors(bool show)
        {
            if (simulator != null && simulator.ErrorEllipse != null)
            {
                simulator.ErrorEllipse.ToggleDeviationVectors(show);
            }
        }

        private void OnSeedChanged(string seedText)
        {
            int seed;
            if (int.TryParse(seedText, out seed) && simulator != null)
            {
                simulator.randomSeed = seed;
            }
        }

        private void UpdateTerrainInfo()
        {
            if (simulator == null || simulator.TerrainData == null) return;

            var data = simulator.TerrainData;
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("=== TERRAIN INFO ===");
            sb.AppendLine($"Resolution: {data.resolutionX}x{data.resolutionZ}");
            sb.AppendLine($"Cell Size: {data.cellSize:F1}m");
            sb.AppendLine($"Height Range: {data.minHeight:F1} - {data.maxHeight:F1}m");
            sb.AppendLine($"Craters: {simulator.TerrainGenerator.Craters?.Count ?? 0}");
            sb.AppendLine($"Rocks: {simulator.TerrainGenerator.Rocks?.Count ?? 0}");

            UpdateInfoText(sb.ToString());
            UpdateStatus("Terrain generated");
        }

        private void UpdateRiskMapInfo()
        {
            if (simulator == null || simulator.RiskMap == null) return;

            StringBuilder sb = new StringBuilder();
            sb.AppendLine("=== RISK MAP ===");
            sb.AppendLine("Green: Low Risk");
            sb.AppendLine("Yellow: Moderate Risk");
            sb.AppendLine("Red: High Risk");
            sb.AppendLine("Magenta: Critical Risk");
            sb.AppendLine();
            sb.AppendLine("Click on terrain or press 1-0 to select landing site");

            UpdateInfoText(sb.ToString());
            UpdateStatus("Risk map generated");
        }

        private void UpdatePathInfo()
        {
            if (simulator == null || simulator.PlannedPath == null) return;

            StringBuilder sb = new StringBuilder();
            sb.AppendLine("=== PATH INFO ===");
            sb.AppendLine($"Waypoints: {simulator.PlannedPath.Count}");
            sb.AppendLine($"Algorithm: {simulator.pathAlgorithm}");

            if (simulator.PlannedPath.Count > 1)
            {
                double totalDist = 0;
                for (int i = 1; i < simulator.PlannedPath.Count; i++)
                {
                    totalDist += Vector3d.Distance(
                        simulator.PlannedPath[i - 1],
                        simulator.PlannedPath[i]
                    );
                }
                sb.AppendLine($"Total Distance: {totalDist:F1}m");
            }

            UpdateInfoText(sb.ToString());
            UpdateStatus("Path planned");
        }

        private void OnSimulationStart()
        {
            UpdateStatus("Simulating...");
        }

        private void OnSimulationEnd()
        {
            if (simulator == null || simulator.SimulatedTrajectory == null) return;

            var traj = simulator.SimulatedTrajectory;
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("=== SIMULATION RESULTS ===");
            sb.AppendLine($"Flight Time: {traj[traj.Count - 1].time:F1}s");
            sb.AppendLine($"Fuel Used: {simulator.initialFuel - " +
                         "traj[traj.Count - 1].fuel:F1}kg");
            sb.AppendLine($"Final Altitude: {traj[traj.Count - 1].position.y:F1}m");

            var lastPoint = traj[traj.Count - 1];
            if (lastPoint.position.y < 1.0 && lastPoint.velocity.magnitude < 3.0)
            {
                sb.AppendLine("Status: LANDED SUCCESSFULLY");
            }
            else if (lastPoint.position.y < 1.0)
            {
                sb.AppendLine("Status: CRASHED");
            }
            else
            {
                sb.AppendLine("Status: IN FLIGHT");
            }

            UpdateInfoText(sb.ToString());
            UpdateStatus("Simulation complete");
        }

        private void UpdateMonteCarloProgress(int completed, int total)
        {
            float percent = (float)completed / total * 100;
            string text = $"Progress: {completed}/{total} ({percent:F1}%)";

            if (monteCarloProgressText != null)
            {
                monteCarloProgressText.text = text;
            }

            UpdateStatus($"Monte Carlo: {percent:F1}%");
        }

        private void UpdateMonteCarloResults(MonteCarloStatistics stats)
        {
            if (stats == null) return;

            StringBuilder sb = new StringBuilder();
            sb.AppendLine("=== MONTE CARLO RESULTS ===");
            sb.AppendLine($"Total Simulations: {stats.totalSimulations}");
            sb.AppendLine($"Successful Landings: {stats.successfulLandings}");
            sb.AppendLine($"Success Rate: {stats.successRate:P2}");
            sb.AppendLine($"Crash Rate: {stats.crashRate:P2}");
            sb.AppendLine($"95% Confidence: ±{stats.confidence95:P2}");
            sb.AppendLine();
            sb.AppendLine($"Mean Flight Time: {stats.meanFlightTime:F1}s");
            sb.AppendLine($"Mean Fuel Used: {stats.meanFuelUsed:F1}kg");
            sb.AppendLine($"Mean Landing Error: {stats.meanLandingError:F2}m");
            sb.AppendLine();
            sb.AppendLine($"Mean Position: {stats.meanLandingPosition}");
            sb.AppendLine($"Std Deviation: ({Math.Sqrt(stats.stdDevLandingPosition.x):F2}, " +
                         $"{Math.Sqrt(stats.stdDevLandingPosition.y):F2}, " +
                         $"{Math.Sqrt(stats.stdDevLandingPosition.z):F2})");

            if (monteCarloResultsText != null)
            {
                monteCarloResultsText.text = sb.ToString();
            }

            UpdateStatus("Monte Carlo complete");
        }

        private void OnSiteSelected(LandingSite site)
        {
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("=== SELECTED LANDING SITE ===");
            sb.AppendLine($"Position: {site.position}");
            sb.AppendLine($"Slope: {site.slope:F1}°");
            sb.AppendLine($"Roughness: {site.roughness:F3}");
            sb.AppendLine($"Shadow Factor: {site.shadowFactor:F2}");
            sb.AppendLine($"Total Risk: {site.totalRisk:F3}");

            if (selectedSiteText != null)
            {
                selectedSiteText.text = sb.ToString();
            }
        }

        private void OnCandidatesUpdated(System.Collections.Generic.List<LandingSite> sites)
        {
            if (sites == null || sites.Count == 0) return;

            StringBuilder sb = new StringBuilder();
            sb.AppendLine("=== CANDIDATE LANDING SITES ===");
            for (int i = 0; i < Math.Min(10, sites.Count); i++)
            {
                sb.AppendLine($"{i + 1}. Risk: {sites[i].totalRisk:F3} | " +
                             $"Slope: {sites[i].slope:F1}° | " +
                             $"Rough: {sites[i].roughness:F3}");
            }

            UpdateInfoText(sb.ToString());
        }

        private void UpdateInfoText(string text)
        {
            if (infoText != null)
            {
                infoText.text = text;
            }
        }

        private void UpdateStatus(string status)
        {
            if (statusText != null)
            {
                statusText.text = $"Status: {status}";
            }
        }

        void Update()
        {
            if (simulator != null && simulator.LanderState != null)
            {
                StringBuilder sb = new StringBuilder();
                sb.AppendLine("=== LANDER STATE ===");
                sb.AppendLine($"Position: {simulator.LanderState.position}");
                sb.AppendLine($"Velocity: {simulator.LanderState.velocity}");
                sb.AppendLine($"Fuel: {simulator.LanderState.fuelMass:F1}kg");
                sb.AppendLine($"Throttle: {simulator.LanderState.throttle:F2}");
                sb.AppendLine($"Attitude: {simulator.LanderState.attitude}");

                if (infoText != null && infoText.text.StartsWith("=== LANDER"))
                {
                    infoText.text = sb.ToString();
                }
            }
        }

        void OnDestroy()
        {
            if (simulator != null)
            {
                simulator.OnTerrainGenerated -= UpdateTerrainInfo;
                simulator.OnRiskMapGenerated -= UpdateRiskMapInfo;
                simulator.OnPathPlanned -= UpdatePathInfo;
                simulator.OnSimulationStarted -= OnSimulationStart;
                simulator.OnSimulationCompleted -= OnSimulationEnd;
                simulator.OnMonteCarloProgress -= UpdateMonteCarloProgress;
                simulator.OnMonteCarloComplete -= UpdateMonteCarloResults;

                if (simulator.SiteSelector != null)
                {
                    simulator.SiteSelector.OnSiteSelected -= OnSiteSelected;
                    simulator.SiteSelector.OnCandidatesUpdated -= OnCandidatesUpdated;
                }
            }
        }
    }
}
