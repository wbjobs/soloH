using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;
using LanderSim.Terrain;
using LanderSim.PathPlanning;
using LanderSim.Physics;
using LanderSim.RiskAssessment;
using LanderSim.Visualization;
using LanderSim.Interaction;
using LanderSim.Simulation;

namespace LanderSim.Main
{
    public enum PathAlgorithm
    {
        AStar,
        RRT,
        RRTStar
    }

    public class LanderSimulator : MonoBehaviour
    {
        [Header("Simulation Settings")]
        public PathAlgorithm pathAlgorithm = PathAlgorithm.AStar;
        public float timeScale = 1.0f;
        public bool autoStartSimulation = true;

        [Header("Terrain Settings")]
        public Vector3 terrainOrigin = new Vector3(-128, 0, -128);
        public int terrainResolution = 128;
        public float terrainCellSize = 2.0f;
        public int randomSeed = 42;

        [Header("Grid Settings")]
        public int gridSizeX = 64;
        public int gridSizeY = 32;
        public int gridSizeZ = 64;
        public float gridCellSize = 4.0f;

        [Header("Lander Settings")]
        public Vector3 initialPosition = new Vector3(0, 150, 0);
        public Vector3 initialVelocity = Vector3.zero;
        public float dryMass = 500f;
        public float initialFuel = 300f;

        [Header("References")]
        public Camera mainCamera;
        public Material terrainMaterial;

        [Header("Dynamic Obstacles")]
        public bool enableDynamicObstacles = true;
        public float dustStormProbability = 0.02f;
        public float minDustStormInterval = 15f;
        public float maxDustStormInterval = 45f;

        [Header("Replanning")]
        public bool enableReplanning = true;
        public int replanAttempts = 3;
        public double emergencyHoverAltitude = 50.0;

        private TerrainGenerator terrainGenerator;
        private TerrainVisualizer terrainVisualizer;
        private Grid3D grid3D;
        private AStarPathfinder aStarPathfinder;
        private RRTPathfinder rrtPathfinder;
        private FuelConsumptionModel fuelModel;
        private AttitudeController attitudeController;
        private LanderDynamics landerDynamics;
        private RiskEvaluator riskEvaluator;
        private RiskHeatmap riskHeatmap;
        private TrajectoryVisualizer trajectoryVisualizer;
        private LandingErrorEllipse landingErrorEllipse;
        private LandingSiteSelector landingSiteSelector;
        private MonteCarloSimulator monteCarloSimulator;

        private LanderState landerState;
        private List<Vector3d> plannedPath;
        private List<TrajectoryPoint> simulatedTrajectory;
        private double simulationTime;
        private bool isSimulating;
        private int currentTrajectoryIndex;

        public TerrainGenerator TerrainGenerator => terrainGenerator;
        public TerrainData TerrainData => terrainGenerator?.TerrainData;
        public Grid3D Grid3D => grid3D;
        public LanderState LanderState => landerState;
        public List<Vector3d> PlannedPath => plannedPath;
        public List<TrajectoryPoint> SimulatedTrajectory => simulatedTrajectory;
        public RiskMap RiskMap => riskHeatmap?.riskMap;
        public MonteCarloSimulator MonteCarlo => monteCarloSimulator;
        public LandingSiteSelector SiteSelector => landingSiteSelector;
        public TrajectoryVisualizer TrajectoryViz => trajectoryVisualizer;
        public LandingErrorEllipse ErrorEllipse => landingErrorEllipse;
        public RiskHeatmap Heatmap => riskHeatmap;

        public event Action OnTerrainGenerated;
        public event Action OnRiskMapGenerated;
        public event Action OnPathPlanned;
        public event Action OnSimulationStarted;
        public event Action OnSimulationCompleted;
        public event Action<int, int> OnMonteCarloProgress;
        public event Action<MonteCarloStatistics> OnMonteCarloComplete;

        void Awake()
        {
            if (mainCamera == null)
            {
                mainCamera = Camera.main;
            }

            InitializeComponents();
        }

        void Start()
        {
            if (autoStartSimulation)
            {
                StartCoroutine(FullSimulationRoutine());
            }
        }

        private void InitializeComponents()
        {
            terrainGenerator = gameObject.AddComponent<TerrainGenerator>();
            terrainGenerator.terrainOrigin = terrainOrigin;
            terrainGenerator.resolution = terrainResolution;
            terrainGenerator.cellSize = terrainCellSize;
            terrainGenerator.seed = randomSeed;

            GameObject terrainVizObj = new GameObject("TerrainVisualizer");
            terrainVizObj.transform.parent = transform;
            terrainVisualizer = terrainVizObj.AddComponent<TerrainVisualizer>();

            GameObject heatmapObj = new GameObject("RiskHeatmap");
            heatmapObj.transform.parent = transform;
            riskHeatmap = heatmapObj.AddComponent<RiskHeatmap>();

            GameObject trajectoryObj = new GameObject("TrajectoryVisualizer");
            trajectoryObj.transform.parent = transform;
            trajectoryVisualizer = trajectoryObj.AddComponent<TrajectoryVisualizer>();

            GameObject ellipseObj = new GameObject("LandingErrorEllipse");
            ellipseObj.transform.parent = transform;
            landingErrorEllipse = ellipseObj.AddComponent<LandingErrorEllipse>();

            GameObject selectorObj = new GameObject("LandingSiteSelector");
            selectorObj.transform.parent = transform;
            landingSiteSelector = selectorObj.AddComponent<LandingSiteSelector>();

            monteCarloSimulator = gameObject.AddComponent<MonteCarloSimulator>();
            monteCarloSimulator.OnProgress += (c, t) => OnMonteCarloProgress?.Invoke(c, t);
            monteCarloSimulator.OnComplete += (s) => OnMonteCarloComplete?.Invoke(s);

            fuelModel = new FuelConsumptionModel();
            attitudeController = new AttitudeController();
            landerDynamics = new LanderDynamics(fuelModel, attitudeController);
        }

        private System.Collections.IEnumerator FullSimulationRoutine()
        {
            Debug.Log("Starting full simulation...");

            GenerateTerrain();
            yield return new WaitForSeconds(0.1f);

            GenerateGrid();
            yield return new WaitForSeconds(0.1f);

            GenerateRiskMap();
            yield return new WaitForSeconds(0.1f);

            GenerateCandidates();
            yield return new WaitForSeconds(0.1f);

            if (landingSiteSelector.SelectedSite.HasValue)
            {
                PlanPathToSite(landingSiteSelector.SelectedSite.Value);
                yield return new WaitForSeconds(0.1f);
            }

            if (plannedPath != null && plannedPath.Count > 0)
            {
                SimulateTrajectory();
                trajectoryVisualizer.CreateLanderVisual();
                OnSimulationStarted?.Invoke();
            }
        }

        public void GenerateTerrain()
        {
            Debug.Log("Generating terrain...");
            terrainGenerator.GenerateTerrain();

            terrainVisualizer.Initialize(terrainGenerator, terrainMaterial);
            terrainVisualizer.Visualize();

            landerState = new LanderState
            {
                position = Vector3d.FromVector3(initialPosition),
                velocity = Vector3d.FromVector3(initialVelocity),
                dryMass = dryMass,
                fuelMass = initialFuel,
                mass = dryMass + initialFuel
            };

            riskEvaluator = new RiskEvaluator(terrainGenerator.TerrainData, terrainGenerator);

            OnTerrainGenerated?.Invoke();
            Debug.Log($"Terrain generated: {terrainGenerator.TerrainData.resolutionX}x" +
                     $"{terrainGenerator.TerrainData.resolutionZ}, " +
                     $"Height range: {terrainGenerator.TerrainData.minHeight:F1} - " +
                     $"{terrainGenerator.TerrainData.maxHeight:F1}");
        }

        public void GenerateGrid()
        {
            Debug.Log("Generating 3D grid...");

            Vector3d gridOrigin = new Vector3d(
                terrainOrigin.x,
                terrainGenerator.TerrainData.minHeight,
                terrainOrigin.z
            );

            grid3D = new Grid3D(
                gridSizeX, gridSizeY, gridSizeZ,
                gridCellSize, gridOrigin,
                terrainGenerator.TerrainData,
                terrainGenerator
            );

            aStarPathfinder = new AStarPathfinder(grid3D, terrainGenerator);
            rrtPathfinder = new RRTPathfinder(grid3D, terrainGenerator);

            Debug.Log($"Grid generated: {gridSizeX}x{gridSizeY}x{gridSizeZ}, " +
                     $"Walkable cells: {grid3D.GetWalkableCells()}");
        }

        public void GenerateRiskMap()
        {
            Debug.Log("Generating risk map...");

            riskHeatmap.Initialize(terrainGenerator, riskEvaluator);
            riskHeatmap.GenerateHeatmap();

            landingSiteSelector.Initialize(terrainGenerator, riskHeatmap.riskMap);

            OnRiskMapGenerated?.Invoke();
            Debug.Log("Risk map generated successfully");
        }

        public void GenerateCandidates()
        {
            Debug.Log("Generating landing site candidates...");
            landingSiteSelector.GenerateCandidates();
            Debug.Log($"Found {landingSiteSelector.CandidateSites.Count} candidate sites");
        }

        public void PlanPathToSite(LandingSite site)
        {
            Debug.Log($"Planning path to site: {site.position}");

            Vector3d startPos = landerState.position;
            Vector3d endPos = site.position + new Vector3d(0, 2, 0);

            switch (pathAlgorithm)
            {
                case PathAlgorithm.AStar:
                    plannedPath = aStarPathfinder.FindPath(startPos, endPos);
                    break;
                case PathAlgorithm.RRT:
                    plannedPath = rrtPathfinder.FindPath(startPos, endPos);
                    break;
                case PathAlgorithm.RRTStar:
                    plannedPath = rrtPathfinder.FindPathRRTStar(startPos, endPos);
                    break;
            }

            if (plannedPath == null || plannedPath.Count == 0)
            {
                Debug.LogError("Failed to plan path!");
                return;
            }

            if (pathAlgorithm == PathAlgorithm.AStar)
            {
                plannedPath = aStarPathfinder.OptimizePathForFuel(plannedPath);
            }

            trajectoryVisualizer.Initialize();
            trajectoryVisualizer.SetPath(plannedPath);

            OnPathPlanned?.Invoke();
            Debug.Log($"Path planned: {plannedPath.Count} waypoints");
        }

        public void SimulateTrajectory()
        {
            if (plannedPath == null || plannedPath.Count < 2)
            {
                Debug.LogError("No path to simulate!");
                return;
            }

            Debug.Log("Simulating trajectory with dynamic obstacle support...");

            simulatedTrajectory = new List<TrajectoryPoint>();
            LanderState simState = landerState.Clone();
            simulationTime = 0;
            double dt = 0.05;
            int pathIndex = 0;
            int replanCount = 0;
            double lastDustStormTime = -100;
            bool isInEmergency = false;
            List<Vector3d> currentPath = new List<Vector3d>(plannedPath);
            Vector3d emergencyTarget = Vector3d.zero;

            double terrainHeight = terrainGenerator.TerrainData.GetHeight(
                (float)simState.position.x, (float)simState.position.z);

            while (!simState.isLanded && !simState.isCrashed &&
                   simulationTime < 180.0 && pathIndex < currentPath.Count)
            {
                if (enableDynamicObstacles)
                {
                    grid3D.UpdateDynamicObstacles(dt);
                    UpdateDustStorms(simulationTime, ref lastDustStormTime, simState);
                }

                if (enableReplanning && !isInEmergency)
                {
                    if (grid3D.IsPathBlocked(currentPath, pathIndex, 25.0))
                    {
                        Debug.LogWarning($"Path blocked at t={simulationTime:F1}s, initiating replan...");
                        bool replanSuccess = AttemptReplan(simState, currentPath, pathIndex, ref replanCount);

                        if (!replanSuccess)
                        {
                            isInEmergency = true;
                            emergencyTarget = CalculateEmergencyTarget(simState);
                            Debug.LogWarning($"Replanning failed after {replanCount} attempts. Emergency mode activated.");
                        }
                        else
                        {
                            pathIndex = 0;
                            replanCount++;
                            Debug.Log($"Replanned successfully (attempt {replanCount}). New path has {currentPath.Count} waypoints.");
                        }
                    }
                }

                Vector3d target;
                Vector3d toTarget;

                if (isInEmergency)
                {
                    target = emergencyTarget;
                    toTarget = target - simState.position;
                    ExecuteEmergencyManeuver(simState, toTarget);
                }
                else
                {
                    target = currentPath[Math.Min(pathIndex + 1, currentPath.Count - 1)];
                    toTarget = target - simState.position;

                    double distToTarget = toTarget.magnitude;
                    if (distToTarget < 3.0 && pathIndex < currentPath.Count - 1)
                    {
                        pathIndex++;
                    }

                    double desiredThrottle = CalculateThrottle(simState, toTarget, distToTarget);
                    simState.throttle = Math.Max(0.1, Math.Min(1.0, desiredThrottle));

                    Quaterniond desiredAttitude = CalculateAttitude(simState, toTarget);
                    attitudeController.targetAttitude = desiredAttitude;
                }

                terrainHeight = terrainGenerator.TerrainData.GetHeight(
                    (float)simState.position.x, (float)simState.position.z);

                TrajectoryPoint point = landerDynamics.CreateTrajectoryPoint(simState, simulationTime);

                if (riskEvaluator != null)
                {
                    point.risk = riskEvaluator.EvaluateTrajectoryRisk(
                        new List<Vector3d> { simState.position });
                }

                simulatedTrajectory.Add(point);

                landerDynamics.UpdateState(simState, dt);
                landerDynamics.CheckLanding(simState, terrainHeight);

                if (simState.fuelMass <= 0 && !simState.isLanded)
                {
                    Debug.LogWarning("Fuel exhausted!");
                    break;
                }

                if (simState.position.y < terrainHeight - 1.0)
                {
                    simState.isCrashed = true;
                    break;
                }

                if (isInEmergency && CheckEmergencyLanding(simState, terrainHeight))
                {
                    Debug.Log($"Emergency landing executed at t={simulationTime:F1}s");
                    break;
                }

                simulationTime += dt;
            }

            trajectoryVisualizer.SetTrajectory(simulatedTrajectory);

            isSimulating = false;
            currentTrajectoryIndex = 0;

            OnSimulationCompleted?.Invoke();

            if (simState.isLanded)
            {
                Debug.Log($"Landing successful! Time: {simulationTime:F1}s, " +
                         $"Fuel used: {initialFuel - simState.fuelMass:F1}kg, " +
                         $"Replans: {replanCount}");
            }
            else if (simState.isCrashed)
            {
                Debug.LogError($"Crash detected! Time: {simulationTime:F1}s, " +
                              $"Replans: {replanCount}");
            }
            else
            {
                Debug.LogWarning($"Simulation ended without landing. Time: {simulationTime:F1}s");
            }
        }

        private void UpdateDustStorms(double currentTime, ref double lastStormTime, LanderState state)
        {
            double timeSinceLastStorm = currentTime - lastStormTime;
            double minInterval = minDustStormInterval;

            if (timeSinceLastStorm < minInterval) return;

            float rand = UnityEngine.Random.value;
            if (rand < dustStormProbability * (currentTime - lastStormTime) / 100.0)
            {
                SpawnDustStorm(state);
                lastStormTime = currentTime;
            }
        }

        private void SpawnDustStorm(LanderState state)
        {
            Vector3d stormCenter;
            Vector3d stormSize;
            Vector3d stormVelocity;

            float distanceFromLander = UnityEngine.Random.Range(30f, 80f);
            float angle = UnityEngine.Random.Range(0f, Mathf.PI * 2f);

            stormCenter = new Vector3d(
                state.position.x + Math.Cos(angle) * distanceFromLander,
                UnityEngine.Random.Range(10f, 60f),
                state.position.z + Math.Sin(angle) * distanceFromLander
            );

            stormSize = new Vector3d(
                UnityEngine.Random.Range(15f, 35f),
                UnityEngine.Random.Range(20f, 50f),
                UnityEngine.Random.Range(15f, 35f)
            );

            Vector3d toLander = state.position - stormCenter;
            stormVelocity = toLander.normalized * UnityEngine.Random.Range(3f, 8f);

            double lifetime = UnityEngine.Random.Range(15f, 35f);
            double intensity = UnityEngine.Random.Range(0.6f, 1.0f);

            DynamicObstacle storm = new DynamicObstacle(
                $"DustStorm_{DateTime.Now:HHmmss}",
                stormCenter, stormSize, stormVelocity, intensity, lifetime
            );

            grid3D.AddDynamicObstacle(storm);
            Debug.Log($"Dust storm spawned at {stormCenter:F1}, moving at {stormVelocity.magnitude:F1} m/s");
        }

        private bool AttemptReplan(LanderState state, List<Vector3d> currentPath,
                                   int currentPathIndex, ref int replanCount)
        {
            if (replanCount >= replanAttempts) return false;

            Vector3d startPos = state.position;
            Vector3d originalEnd = currentPath[currentPath.Count - 1];

            List<Vector3d> newPath = null;
            int attempts = 0;
            int maxAttempts = 5;

            while (newPath == null && attempts < maxAttempts)
            {
                attempts++;
                grid3D.UpdateDynamicObstacles(0.1 * attempts);

                switch (pathAlgorithm)
                {
                    case PathAlgorithm.AStar:
                        newPath = aStarPathfinder.FindPath(startPos, originalEnd);
                        break;
                    case PathAlgorithm.RRT:
                        newPath = rrtPathfinder.FindPath(startPos, originalEnd);
                        break;
                    case PathAlgorithm.RRTStar:
                        newPath = rrtPathfinder.FindPathRRTStar(startPos, originalEnd);
                        break;
                }
            }

            if (newPath == null)
            {
                List<Vector3d> waypoints = grid3D.GetAvoidanceWaypoint(startPos, originalEnd);
                if (waypoints.Count >= 2)
                {
                    currentPath.Clear();
                    currentPath.AddRange(waypoints);
                    return true;
                }
                return false;
            }

            if (pathAlgorithm == PathAlgorithm.AStar)
            {
                newPath = aStarPathfinder.OptimizePathForFuel(newPath);
            }

            currentPath.Clear();
            currentPath.AddRange(newPath);
            return true;
        }

        private Vector3d CalculateEmergencyTarget(LanderState state)
        {
            double terrainHeight = terrainGenerator.TerrainData.GetHeight(
                (float)state.position.x, (float)state.position.z);

            Vector3d climbTarget = state.position + Vector3d.up * emergencyHoverAltitude;

            Vector3d bestLanding = state.position;
            double bestRisk = double.MaxValue;

            for (int i = 0; i < 10; i++)
            {
                float angle = i * Mathf.PI * 2f / 10f;
                float radius = 20f + i * 5f;
                Vector3d testPos = new Vector3d(
                    state.position.x + Math.Cos(angle) * radius,
                    0,
                    state.position.z + Math.Sin(angle) * radius
                );

                double testHeight = terrainGenerator.TerrainData.GetHeight(
                    (float)testPos.x, (float)testPos.z);
                testPos.y = testHeight;

                double risk = riskEvaluator != null ?
                    riskEvaluator.EvaluateTrajectoryRisk(new List<Vector3d> { testPos }) : 0.5;

                double distToObstacle = double.MaxValue;
                foreach (var obstacle in grid3D.GetDynamicObstacles())
                {
                    distToObstacle = Math.Min(distToObstacle, obstacle.GetDistance(testPos));
                }

                risk += distToObstacle < 10 ? 0.5 : 0;

                if (risk < bestRisk)
                {
                    bestRisk = risk;
                    bestLanding = testPos;
                }
            }

            return bestLanding + Vector3d.up * 5.0;
        }

        private void ExecuteEmergencyManeuver(LanderState state, Vector3d toTarget)
        {
            double distToTarget = toTarget.magnitude;
            double altitude = state.position.y - terrainGenerator.TerrainData.GetHeight(
                (float)state.position.x, (float)state.position.z);

            if (altitude < emergencyHoverAltitude)
            {
                state.throttle = Math.Min(1.0, 0.8 + (emergencyHoverAltitude - altitude) * 0.05);
            }
            else if (distToTarget > 10.0)
            {
                state.throttle = 0.6;
            }
            else
            {
                state.throttle = Math.Max(0.2, 0.5 + altitude * 0.02);
            }

            Quaterniond desiredAttitude = CalculateAttitude(state, toTarget);
            attitudeController.targetAttitude = desiredAttitude;
        }

        private bool CheckEmergencyLanding(LanderState state, double terrainHeight)
        {
            double altitude = state.position.y - terrainHeight;
            double verticalSpeed = state.velocity.y;

            if (altitude < 5.0 && verticalSpeed > -3.0 && state.velocity.magnitude < 5.0)
            {
                Vector3d thrustDir = state.attitude * Vector3d.up;
                double attitudeAngle = Math.Acos(Vector3d.Dot(thrustDir, Vector3d.up)) * 180.0 / Math.PI;

                if (attitudeAngle < 25.0)
                {
                    state.isLanded = true;
                    state.velocity = Vector3d.zero;
                    state.angularVelocity = Vector3d.zero;
                    state.throttle = 0;
                    return true;
                }
            }

            return false;
        }

        private double CalculateThrottle(LanderState state, Vector3d toTarget, double distToTarget)
        {
            double throttle = 0.5;

            double verticalSpeed = state.velocity.y;
            if (verticalSpeed < -2.0)
            {
                throttle = Math.Min(1.0, 0.6 + (-verticalSpeed - 2.0) * 0.1);
            }
            else if (verticalSpeed > 1.0)
            {
                throttle = Math.Max(0.2, 0.4 - (verticalSpeed - 1.0) * 0.05);
            }

            double terrainHeight = terrainGenerator.TerrainData.GetHeight(
                (float)state.position.x, (float)state.position.z);
            double altitude = state.position.y - terrainHeight;

            if (altitude < 10.0)
            {
                throttle = Math.Min(1.0, 0.7 + (10.0 - altitude) * 0.05);
            }

            if (distToTarget < 5.0 && altitude < 3.0)
            {
                throttle = 0.3 + altitude * 0.1;
            }

            return throttle;
        }

        private Quaterniond CalculateAttitude(LanderState state, Vector3d toTarget)
        {
            if (toTarget.sqrMagnitude < 1e-6) return Quaterniond.identity;

            Vector3d horizontalDir = new Vector3d(toTarget.x, 0, toTarget.z).normalized;
            double yaw = Math.Atan2(horizontalDir.x, horizontalDir.z) * 180.0 / Math.PI;

            double pitch = 0, roll = 0;
            double terrainHeight = terrainGenerator.TerrainData.GetHeight(
                (float)state.position.x, (float)state.position.z);
            double altitude = state.position.y - terrainHeight;

            if (altitude > 5.0)
            {
                double horizontalSpeed = Math.Sqrt(
                    state.velocity.x * state.velocity.x +
                    state.velocity.z * state.velocity.z);

                if (horizontalSpeed > 2.0)
                {
                    Vector3d velDir = new Vector3d(
                        state.velocity.x, 0, state.velocity.z).normalized;
                    pitch = -Math.Asin(velDir.z) * 180.0 / Math.PI * 0.3;
                    roll = Math.Asin(velDir.x) * 180.0 / Math.PI * 0.3;
                }
            }

            return Quaterniond.FromEuler(roll, pitch, yaw);
        }

        public async void RunMonteCarloSimulation(int numSimulations = 100)
        {
            if (plannedPath == null || plannedPath.Count == 0)
            {
                Debug.LogError("Plan a path first!");
                return;
            }

            MonteCarloConfig config = new MonteCarloConfig
            {
                numSimulations = numSimulations
            };

            monteCarloSimulator.Initialize(
                terrainGenerator.TerrainData,
                landerState,
                plannedPath,
                fuelModel,
                attitudeController,
                riskEvaluator
            );

            monteCarloSimulator.SetConfig(config);

            Debug.Log($"Starting Monte Carlo simulation with {numSimulations} runs...");
            await monteCarloSimulator.RunSimulationsAsync();

            if (monteCarloSimulator.statistics != null)
            {
                Debug.Log($"Monte Carlo complete: " +
                         $"{monteCarloSimulator.statistics}");

                landingErrorEllipse.Initialize();
                landingErrorEllipse.CalculateEllipse(
                    monteCarloSimulator.GetAllLandingPositions());
            }
        }

        void Update()
        {
            if (isSimulating && simulatedTrajectory != null && simulatedTrajectory.Count > 0)
            {
                float playbackSpeed = 2.0f;
                currentTrajectoryIndex = Math.Min(
                    simulatedTrajectory.Count - 1,
                    (int)(Time.time * playbackSpeed * 20) % simulatedTrajectory.Count
                );
                trajectoryVisualizer.UpdateLanderPosition(currentTrajectoryIndex);
            }

            if (Input.GetKeyDown(KeyCode.Space))
            {
                StartPlayback();
            }

            if (Input.GetKeyDown(KeyCode.R))
            {
                ResetSimulation();
            }
        }

        public void StartPlayback()
        {
            isSimulating = true;
            currentTrajectoryIndex = 0;
        }

        public void StopPlayback()
        {
            isSimulating = false;
        }

        public void ResetSimulation()
        {
            isSimulating = false;
            currentTrajectoryIndex = 0;
            simulationTime = 0;

            if (trajectoryVisualizer != null)
            {
                trajectoryVisualizer.UpdateLanderPosition(0);
            }

            landerState = new LanderState
            {
                position = Vector3d.FromVector3(initialPosition),
                velocity = Vector3d.FromVector3(initialVelocity),
                dryMass = dryMass,
                fuelMass = initialFuel,
                mass = dryMass + initialFuel
            };
        }

        public void Cleanup()
        {
            if (terrainVisualizer != null)
                terrainVisualizer.Cleanup();
            if (riskHeatmap != null)
                riskHeatmap.Cleanup();
            if (trajectoryVisualizer != null)
                trajectoryVisualizer.Cleanup();
            if (landingErrorEllipse != null)
                landingErrorEllipse.Cleanup();
            if (landingSiteSelector != null)
                landingSiteSelector.Cleanup();
            if (monteCarloSimulator != null)
                monteCarloSimulator.Stop();
        }

        void OnDestroy()
        {
            Cleanup();
        }
    }
}
