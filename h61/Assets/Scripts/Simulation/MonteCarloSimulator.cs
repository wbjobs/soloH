using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;
using LanderSim.Core;
using LanderSim.Physics;
using LanderSim.Terrain;
using LanderSim.PathPlanning;
using LanderSim.RiskAssessment;

namespace LanderSim.Simulation
{
    [Serializable]
    public class MonteCarloConfig
    {
        public int numSimulations = 100;
        public double timeStep = 0.05;
        public double maxSimulationTime = 120.0;

        public Vector3 positionStdDev = new Vector3(5, 2, 5);
        public Vector3 velocityStdDev = new Vector3(1, 0.5, 1);
        public Vector3 attitudeStdDev = new Vector3(5, 5, 5);

        public double thrustStdDev = 0.05;
        public double ispStdDev = 0.02;

        public double sensorNoiseStdDev = 0.1;
        public double actuatorDelayStdDev = 0.02;

        public double windSpeedMean = 0;
        public double windSpeedStdDev = 2.0;

        public override string ToString()
        {
            return $"Sims: {numSimulations}, PosSigma: {positionStdDev}, VelSigma: {velocityStdDev}";
        }
    }

    [Serializable]
    public class SimulationResult
    {
        public int simulationIndex;
        public bool success;
        public bool crashed;
        public bool ranOutOfFuel;
        public double totalTime;
        public double fuelUsed;
        public Vector3d landingPosition;
        public Vector3d landingVelocity;
        public double landingAttitudeError;
        public double minimumAltitude;
        public double minimumObstacleDistance;
        public List<TrajectoryPoint> trajectory;

        public override string ToString()
        {
            return $"Sim {simulationIndex}: Success={success}, Crash={crashed}, " +
                   $"FuelUsed={fuelUsed:F1}kg, Pos={landingPosition}";
        }
    }

    [Serializable]
    public class MonteCarloStatistics
    {
        public int totalSimulations;
        public int successfulLandings;
        public int crashes;
        public int fuelOuts;
        public double successRate;
        public double crashRate;
        public double meanFuelUsed;
        public double stdDevFuelUsed;
        public double meanFlightTime;
        public double stdDevFlightTime;
        public Vector3d meanLandingPosition;
        public Vector3d stdDevLandingPosition;
        public double meanLandingError;
        public double confidence95;

        public override string ToString()
        {
            return $"Success: {successRate:P2}, Crash: {crashRate:P2}, " +
                   $"Mean Fuel: {meanFuelUsed:F1}kg, Mean Error: {meanLandingError:F2}m";
        }
    }

    public class MonteCarloSimulator : MonoBehaviour
    {
        public MonteCarloConfig config = new MonteCarloConfig();
        public List<SimulationResult> results = new List<SimulationResult>();
        public MonteCarloStatistics statistics;

        public bool isRunning { get; private set; }
        public int currentSimulation { get; private set; }
        public int completedSimulations { get; private set; }

        public event Action<int, int> OnProgress;
        public event Action<MonteCarloStatistics> OnComplete;
        public event Action<SimulationResult> OnSimulationComplete;

        private TerrainData terrainData;
        private LanderState nominalState;
        private List<Vector3d> plannedPath;
        private FuelConsumptionModel fuelModel;
        private AttitudeController attitudeController;
        private LanderDynamics dynamics;
        private RiskEvaluator riskEvaluator;

        private System.Random random;

        public void Initialize(TerrainData terrainData,
                              LanderState nominalState,
                              List<Vector3d> plannedPath,
                              FuelConsumptionModel fuelModel,
                              AttitudeController attitudeController,
                              RiskEvaluator riskEvaluator = null)
        {
            this.terrainData = terrainData;
            this.nominalState = nominalState;
            this.plannedPath = plannedPath;
            this.fuelModel = fuelModel;
            this.attitudeController = attitudeController;
            this.riskEvaluator = riskEvaluator;

            dynamics = new LanderDynamics(fuelModel, attitudeController);
            random = new System.Random();
        }

        public void SetConfig(MonteCarloConfig newConfig)
        {
            config = newConfig;
        }

        public async Task RunSimulationsAsync()
        {
            if (isRunning || terrainData == null || nominalState == null) return;

            isRunning = true;
            results.Clear();
            completedSimulations = 0;
            currentSimulation = 0;

            int batchSize = Math.Max(1, Environment.ProcessorCount - 1);

            for (int batchStart = 0; batchStart < config.numSimulations; batchStart += batchSize)
            {
                int batchCount = Math.Min(batchSize, config.numSimulations - batchStart);
                Task<SimulationResult>[] batchTasks = new Task<SimulationResult>[batchCount];

                for (int i = 0; i < batchCount; i++)
                {
                    int simIndex = batchStart + i;
                    currentSimulation = simIndex;
                    batchTasks[i] = Task.Run(() => RunSingleSimulation(simIndex));
                }

                await Task.WhenAll(batchTasks);

                foreach (var task in batchTasks)
                {
                    SimulationResult result = task.Result;
                    results.Add(result);
                    completedSimulations++;
                    OnSimulationComplete?.Invoke(result);
                }

                OnProgress?.Invoke(completedSimulations, config.numSimulations);
                await Task.Delay(1);
            }

            CalculateStatistics();
            isRunning = false;
            OnComplete?.Invoke(statistics);
        }

        private SimulationResult RunSingleSimulation(int index)
        {
            LanderState state = PerturbInitialState(index);
            List<TrajectoryPoint> trajectory = new List<TrajectoryPoint>();
            SimulationResult result = new SimulationResult
            {
                simulationIndex = index,
                trajectory = trajectory,
                minimumAltitude = double.MaxValue,
                minimumObstacleDistance = double.MaxValue
            };

            double time = 0;
            int pathIndex = 0;
            Vector3d targetPosition = plannedPath[Math.Min(pathIndex + 1, plannedPath.Count - 1)];

            while (time < config.maxSimulationTime &&
                   !state.isLanded && !state.isCrashed)
            {
                Vector3d toTarget = targetPosition - state.position;
                double distToTarget = toTarget.magnitude;

                if (distToTarget < 3.0 && pathIndex < plannedPath.Count - 1)
                {
                    pathIndex++;
                    targetPosition = plannedPath[Math.Min(pathIndex + 1, plannedPath.Count - 1)];
                }

                double desiredThrottle = CalculateDesiredThrottle(state, toTarget, distToTarget);
                state.throttle = ApplyThrustNoise(desiredThrottle, index);

                Quaterniond desiredAttitude = CalculateDesiredAttitude(state, toTarget);
                attitudeController.targetAttitude = ApplyAttitudeNoise(desiredAttitude, index);

                double terrainHeight = terrainData.GetHeight(
                    (float)state.position.x, (float)state.position.z);

                double altitude = state.position.y - terrainHeight;
                result.minimumAltitude = Math.Min(result.minimumAltitude, altitude);

                if (riskEvaluator != null)
                {
                    double trajRisk = riskEvaluator.EvaluateTrajectoryRisk(
                        new List<Vector3d> { state.position });
                    result.minimumObstacleDistance = Math.Min(
                        result.minimumObstacleDistance, 10 * (1 - trajRisk));
                }

                trajectory.Add(dynamics.CreateTrajectoryPoint(state, time));

                dynamics.UpdateState(state, config.timeStep);
                dynamics.CheckLanding(state, terrainHeight);

                if (state.fuelMass <= 0 && !state.isLanded)
                {
                    result.ranOutOfFuel = true;
                }

                if (state.position.y < terrainHeight - 1.0)
                {
                    state.isCrashed = true;
                }

                time += config.timeStep;
            }

            result.totalTime = time;
            result.fuelUsed = nominalState.fuelMass - state.fuelMass;
            result.landingPosition = state.position;
            result.landingVelocity = state.velocity;
            result.success = state.isLanded && !state.isCrashed && !result.ranOutOfFuel;
            result.crashed = state.isCrashed;

            if (plannedPath.Count > 0)
            {
                Vector3d targetLanding = plannedPath[plannedPath.Count - 1];
                result.landingAttitudeError = Vector3d.Distance(
                    state.position, targetLanding);
            }

            return result;
        }

        private LanderState PerturbInitialState(int seed)
        {
            System.Random rand = new System.Random(seed * 1000 + seed);
            LanderState perturbed = nominalState.Clone();

            perturbed.position += new Vector3d(
                NormalRandom(rand) * config.positionStdDev.x,
                NormalRandom(rand) * config.positionStdDev.y,
                NormalRandom(rand) * config.positionStdDev.z
            );

            perturbed.velocity += new Vector3d(
                NormalRandom(rand) * config.velocityStdDev.x,
                NormalRandom(rand) * config.velocityStdDev.y,
                NormalRandom(rand) * config.velocityStdDev.z
            );

            Quaterniond attPerturb = Quaterniond.FromEuler(
                NormalRandom(rand) * config.attitudeStdDev.x,
                NormalRandom(rand) * config.attitudeStdDev.y,
                NormalRandom(rand) * config.attitudeStdDev.z
            );
            perturbed.attitude = (attPerturb * perturbed.attitude).normalized;

            perturbed.fuelMass *= (1.0 + NormalRandom(rand) * 0.02);
            perturbed.mass = perturbed.dryMass + perturbed.fuelMass;

            return perturbed;
        }

        private double CalculateDesiredThrottle(LanderState state,
                                               Vector3d toTarget, double distToTarget)
        {
            double desiredThrottle = 0.5;

            double verticalSpeed = state.velocity.y;
            if (verticalSpeed < -2.0)
            {
                desiredThrottle = Math.Min(1.0, 0.6 + (-verticalSpeed - 2.0) * 0.1);
            }
            else if (verticalSpeed > 1.0)
            {
                desiredThrottle = Math.Max(0.2, 0.4 - (verticalSpeed - 1.0) * 0.05);
            }

            double terrainHeight = terrainData.GetHeight(
                (float)state.position.x, (float)state.position.z);
            double altitude = state.position.y - terrainHeight;

            if (altitude < 10.0)
            {
                desiredThrottle = Math.Min(1.0, 0.7 + (10.0 - altitude) * 0.05);
            }

            if (distToTarget < 5.0 && altitude < 3.0)
            {
                desiredThrottle = 0.3 + altitude * 0.1;
            }

            return desiredThrottle;
        }

        private Quaterniond CalculateDesiredAttitude(LanderState state, Vector3d toTarget)
        {
            if (toTarget.sqrMagnitude < 1e-6) return Quaterniond.identity;

            Vector3d horizontalDir = new Vector3d(toTarget.x, 0, toTarget.z).normalized;

            double targetRoll = 0;
            double targetPitch = 0;
            double targetYaw = Math.Atan2(horizontalDir.x, horizontalDir.z) * 180.0 / Math.PI;

            double terrainHeight = terrainData.GetHeight(
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
                    targetPitch = -Math.Asin(velDir.z) * 180.0 / Math.PI * 0.3;
                    targetRoll = Math.Asin(velDir.x) * 180.0 / Math.PI * 0.3;
                }
            }

            return Quaterniond.FromEuler(targetRoll, targetPitch, targetYaw);
        }

        private double ApplyThrustNoise(double throttle, int seed)
        {
            double noise = NormalRandom(new System.Random(seed * 100 + 1)) * config.thrustStdDev;
            return Math.Max(0.1, Math.Min(1.0, throttle * (1.0 + noise)));
        }

        private Quaterniond ApplyAttitudeNoise(Quaterniond attitude, int seed)
        {
            System.Random rand = new System.Random(seed * 100 + 2);
            Quaterniond noise = Quaterniond.FromEuler(
                NormalRandom(rand) * 1.0,
                NormalRandom(rand) * 1.0,
                NormalRandom(rand) * 1.0
            );
            return (noise * attitude).normalized;
        }

        private double NormalRandom(System.Random rand)
        {
            double u1 = 1.0 - rand.NextDouble();
            double u2 = 1.0 - rand.NextDouble();
            return Math.Sqrt(-2.0 * Math.Log(u1)) *
                   Math.Cos(2.0 * Math.PI * u2);
        }

        public void CalculateStatistics()
        {
            if (results.Count == 0) return;

            statistics = new MonteCarloStatistics
            {
                totalSimulations = results.Count
            };

            double sumFuel = 0, sumFuelSq = 0;
            double sumTime = 0, sumTimeSq = 0;
            Vector3d sumPos = Vector3d.zero;
            Vector3d sumPosSq = Vector3d.zero;
            double sumError = 0;

            foreach (var result in results)
            {
                if (result.success) statistics.successfulLandings++;
                if (result.crashed) statistics.crashes++;
                if (result.ranOutOfFuel) statistics.fuelOuts++;

                sumFuel += result.fuelUsed;
                sumFuelSq += result.fuelUsed * result.fuelUsed;
                sumTime += result.totalTime;
                sumTimeSq += result.totalTime * result.totalTime;
                sumPos += result.landingPosition;
                sumPosSq += new Vector3d(
                    result.landingPosition.x * result.landingPosition.x,
                    result.landingPosition.y * result.landingPosition.y,
                    result.landingPosition.z * result.landingPosition.z
                );
                sumError += result.landingAttitudeError;
            }

            int n = results.Count;
            statistics.successRate = (double)statistics.successfulLandings / n;
            statistics.crashRate = (double)statistics.crashes / n;
            statistics.meanFuelUsed = sumFuel / n;
            statistics.stdDevFuelUsed = Math.Sqrt(Math.Max(0, sumFuelSq / n -
                statistics.meanFuelUsed * statistics.meanFuelUsed));
            statistics.meanFlightTime = sumTime / n;
            statistics.stdDevFlightTime = Math.Sqrt(Math.Max(0, sumTimeSq / n -
                statistics.meanFlightTime * statistics.meanFlightTime));
            statistics.meanLandingPosition = sumPos / n;
            statistics.stdDevLandingPosition = new Vector3d(
                Math.Sqrt(Math.Max(0, sumPosSq.x / n -
                    statistics.meanLandingPosition.x * statistics.meanLandingPosition.x)),
                Math.Sqrt(Math.Max(0, sumPosSq.y / n -
                    statistics.meanLandingPosition.y * statistics.meanLandingPosition.y)),
                Math.Sqrt(Math.Max(0, sumPosSq.z / n -
                    statistics.meanLandingPosition.z * statistics.meanLandingPosition.z))
            );
            statistics.meanLandingError = sumError / n;

            double z = 1.96;
            double p = statistics.successRate;
            statistics.confidence95 = z * Math.Sqrt(p * (1 - p) / n);

            List<Vector3d> landingPositions = new List<Vector3d>();
            foreach (var r in results)
            {
                landingPositions.Add(r.landingPosition);
            }
        }

        public List<Vector3d> GetSuccessfulLandingPositions()
        {
            List<Vector3d> positions = new List<Vector3d>();
            foreach (var result in results)
            {
                if (result.success)
                {
                    positions.Add(result.landingPosition);
                }
            }
            return positions;
        }

        public List<Vector3d> GetAllLandingPositions()
        {
            List<Vector3d> positions = new List<Vector3d>();
            foreach (var result in results)
            {
                positions.Add(result.landingPosition);
            }
            return positions;
        }

        public void Stop()
        {
            isRunning = false;
        }

        public void Reset()
        {
            results.Clear();
            statistics = null;
            completedSimulations = 0;
            currentSimulation = 0;
            isRunning = false;
        }
    }
}
