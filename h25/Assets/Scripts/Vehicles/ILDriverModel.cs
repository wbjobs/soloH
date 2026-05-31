using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    [Serializable]
    public class DrivingDataset
    {
        public string datasetName;
        public int totalTrajectories;
        public List<TrajectoryData> trajectories = new List<TrajectoryData>();
        public List<StateActionPair> stateActionPairs = new List<StateActionPair>();
    }

    [Serializable]
    public class TrajectoryData
    {
        public string trajectoryId;
        public string driverProfile;
        public float duration;
        public List<TrajectoryPoint> points = new List<TrajectoryPoint>();
        public DrivingStyle style;
    }

    [Serializable]
    public class StateActionPair
    {
        public StateFeature state;
        public ActionFeature action;
        public float weight = 1f;
    }

    [Serializable]
    public struct StateFeature
    {
        public float egoSpeed;
        public float distanceToFront;
        public float frontVehicleSpeed;
        public float distanceToLeftLaneVehicle;
        public float distanceToRightLaneVehicle;
        public float laneOffset;
        public float curvature;
        public float timeToCollision;
        public float trafficLightDistance;
        public int trafficLightState;
        public float relativeSpeedToFront;
    }

    [Serializable]
    public struct ActionFeature
    {
        public float throttle;
        public float brake;
        public float steering;
        public int laneChange;
    }

    public enum DrivingStyle
    {
        Conservative,
        Normal,
        Aggressive,
        Cautious
    }

    public class ILDriverModel : MonoBehaviour
    {
        public static ILDriverModel Instance { get; private set; }

        [SerializeField] private DrivingStyle defaultStyle = DrivingStyle.Normal;
        [SerializeField] private bool useImitationLearning = true;

        private DrivingDataset _dataset;
        private Dictionary<DrivingStyle, List<StateActionPair>> _styleClusters;
        private bool _isInitialized;

        private const int K_NEAREST_NEIGHBORS = 7;
        private const float FEATURE_WEIGHT_SPEED = 0.2f;
        private const float FEATURE_WEIGHT_DISTANCE = 0.3f;
        private const float FEATURE_WEIGHT_TTC = 0.3f;
        private const float FEATURE_WEIGHT_LANE = 0.2f;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            InitializeDataset();
        }

        private void InitializeDataset()
        {
            _dataset = new DrivingDataset { datasetName = "SyntheticDrivingDataset" };
            _styleClusters = new Dictionary<DrivingStyle, List<StateActionPair>>();

            foreach (DrivingStyle style in Enum.GetValues(typeof(DrivingStyle)))
            {
                _styleClusters[style] = new List<StateActionPair>();
                GenerateSyntheticDataForStyle(style);
            }

            GenerateExpertDemonstrations();
            _isInitialized = true;
        }

        private void GenerateSyntheticDataForStyle(DrivingStyle style)
        {
            int samples = 500;
            var random = new System.Random((int)style + 1000);

            for (int i = 0; i < samples; i++)
            {
                var state = GenerateRandomState(random);
                var action = GenerateActionFromStyle(state, style, random);

                var pair = new StateActionPair
                {
                    state = state,
                    action = action,
                    weight = 1f
                };

                _dataset.stateActionPairs.Add(pair);
                _styleClusters[style].Add(pair);
            }
        }

        private StateFeature GenerateRandomState(System.Random random)
        {
            return new StateFeature
            {
                egoSpeed = (float)(random.NextDouble() * 30f),
                distanceToFront = (float)(random.NextDouble() * 50f),
                frontVehicleSpeed = (float)(random.NextDouble() * 25f),
                distanceToLeftLaneVehicle = (float)(random.NextDouble() * 40f),
                distanceToRightLaneVehicle = (float)(random.NextDouble() * 40f),
                laneOffset = (float)(random.NextDouble() * 2f - 1f),
                curvature = (float)(random.NextDouble() * 0.5f),
                timeToCollision = random.NextDouble() > 0.7 ? (float)(random.NextDouble() * 3f) : float.MaxValue,
                trafficLightDistance = (float)(random.NextDouble() * 100f),
                trafficLightState = random.Next(0, 3),
                relativeSpeedToFront = (float)(random.NextDouble() * 10f - 5f)
            };
        }

        private ActionFeature GenerateActionFromStyle(StateFeature state, DrivingStyle style, System.Random random)
        {
            float speedFactor = state.egoSpeed / 30f;
            float distanceFactor = Mathf.Clamp01(state.distanceToFront / 20f);

            switch (style)
            {
                case DrivingStyle.Conservative:
                    return new ActionFeature
                    {
                        throttle = Mathf.Clamp01(0.4f * distanceFactor - speedFactor * 0.3f),
                        brake = Mathf.Clamp01(0.8f * (1f - distanceFactor) + speedFactor * 0.2f),
                        steering = Mathf.Clamp(-state.laneOffset * 2f, -1f, 1f),
                        laneChange = 0
                    };

                case DrivingStyle.Aggressive:
                    return new ActionFeature
                    {
                        throttle = Mathf.Clamp01(0.8f * distanceFactor + 0.2f),
                        brake = Mathf.Clamp01(0.4f * (1f - distanceFactor)),
                        steering = Mathf.Clamp(-state.laneOffset * 4f, -1f, 1f),
                        laneChange = distanceFactor > 0.7f && random.NextDouble() > 0.85 ? (random.NextDouble() > 0.5 ? 1 : -1) : 0
                    };

                case DrivingStyle.Cautious:
                    return new ActionFeature
                    {
                        throttle = Mathf.Clamp01(0.3f * distanceFactor),
                        brake = Mathf.Clamp01(0.9f * (1f - distanceFactor) + (float.IsFinite(state.timeToCollision) ? 0.5f : 0f)),
                        steering = Mathf.Clamp(-state.laneOffset * 1.5f, -1f, 1f),
                        laneChange = 0
                    };

                default:
                    return new ActionFeature
                    {
                        throttle = Mathf.Clamp01(0.6f * distanceFactor),
                        brake = Mathf.Clamp01(0.6f * (1f - distanceFactor)),
                        steering = Mathf.Clamp(-state.laneOffset * 3f, -1f, 1f),
                        laneChange = distanceFactor > 0.5f && random.NextDouble() > 0.9 ? (random.NextDouble() > 0.5 ? 1 : -1) : 0
                    };
            }
        }

        private void GenerateExpertDemonstrations()
        {
            var carFollowingScenarios = new[]
            {
                new { Distance = 15f, Speed = 15f, FrontSpeed = 12f, Style = DrivingStyle.Normal },
                new { Distance = 30f, Speed = 25f, FrontSpeed = 20f, Style = DrivingStyle.Normal },
                new { Distance = 5f, Speed = 8f, FrontSpeed = 0f, Style = DrivingStyle.Normal },
                new { Distance = 8f, Speed = 10f, FrontSpeed = 0f, Style = DrivingStyle.Conservative },
                new { Distance = 20f, Speed = 28f, FrontSpeed = 25f, Style = DrivingStyle.Aggressive }
            };

            foreach (var scenario in carFollowingScenarios)
            {
                var state = new StateFeature
                {
                    egoSpeed = scenario.Speed,
                    distanceToFront = scenario.Distance,
                    frontVehicleSpeed = scenario.FrontSpeed,
                    relativeSpeedToFront = scenario.Speed - scenario.FrontSpeed,
                    timeToCollision = scenario.Speed > scenario.FrontSpeed ? scenario.Distance / (scenario.Speed - scenario.FrontSpeed) : float.MaxValue,
                    laneOffset = 0f,
                    distanceToLeftLaneVehicle = 100f,
                    distanceToRightLaneVehicle = 100f,
                    trafficLightDistance = 100f,
                    trafficLightState = 2
                };

                float distanceFactor = scenario.Distance / 20f;
                float action = Mathf.Clamp01(0.6f * distanceFactor);

                var pair = new StateActionPair
                {
                    state = state,
                    action = new ActionFeature { throttle = action, brake = 1f - action, steering = 0f, laneChange = 0 },
                    weight = 3f
                };

                _dataset.stateActionPairs.Add(pair);
                _styleClusters[scenario.Style].Add(pair);
            }

            _dataset.totalTrajectories = 100;
        }

        public ActionFeature PredictAction(StateFeature currentState, DrivingStyle style = DrivingStyle.Normal)
        {
            if (!_isInitialized || !useImitationLearning)
            {
                return GenerateFallbackAction(currentState);
            }

            var dataset = _styleClusters.ContainsKey(style) ? _styleClusters[style] : _dataset.stateActionPairs;
            var nearestNeighbors = FindKNearestNeighbors(currentState, dataset, K_NEAREST_NEIGHBORS);

            return WeightedMajorityVote(nearestNeighbors);
        }

        private List<(StateActionPair pair, float distance)> FindKNearestNeighbors(
            StateFeature target, List<StateActionPair> dataset, int k)
        {
            var distances = new List<(StateActionPair, float)>();

            foreach (var pair in dataset)
            {
                float dist = CalculateFeatureDistance(target, pair.state) * (1f / pair.weight);
                distances.Add((pair, dist));
            }

            distances.Sort((a, b) => a.Item2.CompareTo(b.Item2));
            return distances.GetRange(0, Mathf.Min(k, distances.Count));
        }

        private float CalculateFeatureDistance(StateFeature a, StateFeature b)
        {
            float dSpeed = Mathf.Abs(a.egoSpeed - b.egoSpeed) / 30f * FEATURE_WEIGHT_SPEED;
            float dDistance = Mathf.Abs(a.distanceToFront - b.distanceToFront) / 50f * FEATURE_WEIGHT_DISTANCE;
            float dRelative = Mathf.Abs(a.relativeSpeedToFront - b.relativeSpeedToFront) / 10f * 0.15f;
            float dLane = Mathf.Abs(a.laneOffset - b.laneOffset) * FEATURE_WEIGHT_LANE;
            float dCurvature = Mathf.Abs(a.curvature - b.curvature) * 0.1f;
            float dTLC = Mathf.Abs(a.trafficLightDistance - b.trafficLightDistance) / 100f * 0.05f;

            float ttcA = float.IsFinite(a.timeToCollision) ? a.timeToCollision : 10f;
            float ttcB = float.IsFinite(b.timeToCollision) ? b.timeToCollision : 10f;
            float dTTC = Mathf.Abs(ttcA - ttcB) / 10f * FEATURE_WEIGHT_TTC;

            return dSpeed + dDistance + dRelative + dLane + dCurvature + dTLC + dTTC;
        }

        private ActionFeature WeightedMajorityVote(List<(StateActionPair pair, float distance)> neighbors)
        {
            float totalWeight = 0f;
            float weightedThrottle = 0f;
            float weightedBrake = 0f;
            float weightedSteering = 0f;
            int[] laneChangeVotes = new int[3];

            foreach (var (pair, distance) in neighbors)
            {
                float weight = 1f / (distance + 0.001f) * pair.weight;
                totalWeight += weight;

                weightedThrottle += pair.action.throttle * weight;
                weightedBrake += pair.action.brake * weight;
                weightedSteering += pair.action.steering * weight;

                int voteIndex = pair.action.laneChange + 1;
                laneChangeVotes[voteIndex]++;
            }

            if (totalWeight > 0f)
            {
                weightedThrottle /= totalWeight;
                weightedBrake /= totalWeight;
                weightedSteering /= totalWeight;
            }

            int laneChange = 0;
            int maxVotes = 0;
            for (int i = 0; i < 3; i++)
            {
                if (laneChangeVotes[i] > maxVotes)
                {
                    maxVotes = laneChangeVotes[i];
                    laneChange = i - 1;
                }
            }

            return new ActionFeature
            {
                throttle = Mathf.Clamp01(weightedThrottle),
                brake = Mathf.Clamp01(weightedBrake),
                steering = Mathf.Clamp(weightedSteering, -1f, 1f),
                laneChange = laneChange
            };
        }

        private ActionFeature GenerateFallbackAction(StateFeature state)
        {
            float distanceFactor = Mathf.Clamp01(state.distanceToFront / 15f);
            float speedFactor = state.egoSpeed / 20f;

            return new ActionFeature
            {
                throttle = Mathf.Clamp01(distanceFactor - speedFactor * 0.3f),
                brake = Mathf.Clamp01(1f - distanceFactor),
                steering = Mathf.Clamp(-state.laneOffset * 2f, -1f, 1f),
                laneChange = 0
            };
        }

        public void RecordStateAction(StateFeature state, ActionFeature action, DrivingStyle style)
        {
            if (!_isInitialized) return;

            var pair = new StateActionPair
            {
                state = state,
                action = action,
                weight = 0.5f
            };

            _dataset.stateActionPairs.Add(pair);
            if (_styleClusters.ContainsKey(style))
            {
                _styleClusters[style].Add(pair);
            }

            if (_dataset.stateActionPairs.Count > 10000)
            {
                _dataset.stateActionPairs.RemoveRange(0, 1000);
            }
        }

        public StateFeature ExtractVehicleState(VehicleAIController vehicle, float laneOffset,
            float distanceToFront, VehicleAIController frontVehicle,
            float leftDistance, float rightDistance,
            float trafficLightDistance, TrafficLightState tlState)
        {
            float frontSpeed = frontVehicle != null ? frontVehicle.CurrentSpeed : 0f;
            float relativeSpeed = vehicle.CurrentSpeed - frontSpeed;
            float ttc = relativeSpeed > 0.1f && distanceToFront < 50f
                ? distanceToFront / relativeSpeed
                : float.MaxValue;

            return new StateFeature
            {
                egoSpeed = vehicle.CurrentSpeed,
                distanceToFront = distanceToFront,
                frontVehicleSpeed = frontSpeed,
                distanceToLeftLaneVehicle = leftDistance,
                distanceToRightLaneVehicle = rightDistance,
                laneOffset = laneOffset,
                curvature = 0f,
                timeToCollision = ttc,
                trafficLightDistance = trafficLightDistance,
                trafficLightState = (int)tlState,
                relativeSpeedToFront = relativeSpeed
            };
        }
    }
}
