using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    [Serializable]
    public class LaneChangeRequest
    {
        public VehicleAIController Requester;
        public int TargetLaneSide;
        public float CurrentSpeed;
        public float GapFront;
        public float GapRear;
        public float RequestTime;
        public int Priority;
    }

    [Serializable]
    public class MergeGameState
    {
        public VehicleAIController VehicleA;
        public VehicleAIController VehicleB;
        public float DistanceToMergePoint;
        public float CooperativeScore;
        public bool AHasRightOfWay;
        public MergeResolution Resolution;
    }

    public enum MergeResolution
    {
        Unresolved,
        AGoesFirst,
        BGoesFirst,
        CooperativeMerge,
        AYields,
        BYields
    }

    public enum NegotiationResult
    {
        Accepted,
        Rejected,
        YieldRequested,
        RequiresCooperation,
        Deferred
    }

    public class CollaborativeLaneChangeManager : MonoBehaviour
    {
        public static CollaborativeLaneChangeManager Instance { get; private set; }

        [SerializeField] private float negotiationTimeout = 3f;
        [SerializeField] private float mergeZoneRadius = 50f;
        [SerializeField] private bool enableCooperativeMerging = true;
        [SerializeField] private bool enableGameTheory = true;

        private List<LaneChangeRequest> _pendingRequests = new List<LaneChangeRequest>();
        private List<MergeGameState> _activeMergeGames = new List<MergeGameState>();
        private Dictionary<int, List<VehicleAIController>> _laneVehicles = new Dictionary<int, List<VehicleAIController>>();

        private const float MIN_SAFE_GAP = 5f;
        private const float COOPERATION_BONUS = 0.3f;
        private const float DEFECT_PENALTY = 0.5f;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        private void Update()
        {
            if (SimulationManager.Instance == null ||
                SimulationManager.Instance.State != SimulationState.Playing) return;

            ProcessPendingRequests();
            UpdateMergeGames();
            CleanupStaleRequests();
        }

        public NegotiationResult RequestLaneChange(LaneChangeRequest request)
        {
            request.RequestTime = Time.time;
            request.Priority = CalculatePriority(request);

            int targetLaneId = GetTargetLaneId(request.Requester, request.TargetLaneSide);

            if (!enableCooperativeMerging)
            {
                return CheckSimpleGap(request.Requester, targetLaneId)
                    ? NegotiationResult.Accepted
                    : NegotiationResult.Rejected;
            }

            var nearbyVehicles = GetNearbyVehicles(request.Requester, targetLaneId, mergeZoneRadius);

            if (nearbyVehicles.Count == 0)
            {
                return NegotiationResult.Accepted;
            }

            if (enableGameTheory)
            {
                return RunGameTheoryNegotiation(request, nearbyVehicles);
            }

            return RunRuleBasedNegotiation(request, nearbyVehicles);
        }

        private NegotiationResult RunGameTheoryNegotiation(LaneChangeRequest request, List<VehicleAIController> others)
        {
            foreach (var other in others)
            {
                if (other == request.Requester) continue;

                var game = CreateMergeGame(request.Requester, other, request);
                var payoffMatrix = CalculatePayoffMatrix(game);

                var nashEquilibrium = FindNashEquilibrium(payoffMatrix);
                game.Resolution = nashEquilibrium;

                if (nashEquilibrium == MergeResolution.AGoesFirst)
                {
                    NotifyVehicleYield(other, request.Requester);
                    _activeMergeGames.Add(game);
                    return NegotiationResult.Accepted;
                }
                else if (nashEquilibrium == MergeResolution.CooperativeMerge)
                {
                    NotifyCooperativeMerge(request.Requester, other);
                    _activeMergeGames.Add(game);
                    return NegotiationResult.Accepted;
                }
                else if (nashEquilibrium == MergeResolution.BGoesFirst)
                {
                    _pendingRequests.Add(request);
                    return NegotiationResult.YieldRequested;
                }
            }

            return NegotiationResult.Rejected;
        }

        private MergeGameState CreateMergeGame(VehicleAIController a, VehicleAIController b, LaneChangeRequest request)
        {
            float distanceA = 100f;
            float distanceB = 100f;

            var aPos = a.transform.position;
            var bPos = b.transform.position;

            return new MergeGameState
            {
                VehicleA = a,
                VehicleB = b,
                DistanceToMergePoint = Vector3.Distance(aPos, bPos),
                AHasRightOfWay = request.Priority > CalculatePriority(b),
                Resolution = MergeResolution.Unresolved
            };
        }

        private float[,] CalculatePayoffMatrix(MergeGameState game)
        {
            float speedA = game.VehicleA.CurrentSpeed;
            float speedB = game.VehicleB.CurrentSpeed;
            float distance = game.DistanceToMergePoint;

            float utilityAccel = 1.0f;
            float utilityDecel = -0.5f;
            float utilityCollision = -10f;
            float utilityDelay = -0.1f * distance / Mathf.Max(speedA, speedB, 0.1f);

            float[,] payoff = new float[2, 2];

            payoff[0, 0] = utilityCollision;
            payoff[0, 1] = utilityAccel + (game.AHasRightOfWay ? 0.2f : -0.2f);
            payoff[1, 0] = utilityAccel + (game.AHasRightOfWay ? -0.2f : 0.2f);
            payoff[1, 1] = utilityDecel + utilityDelay;

            return payoff;
        }

        private MergeResolution FindNashEquilibrium(float[,] payoff)
        {
            float aGo = payoff[0, 0] + payoff[0, 1];
            float aWait = payoff[1, 0] + payoff[1, 1];
            float bGo = payoff[0, 0] + payoff[1, 0];
            float bWait = payoff[0, 1] + payoff[1, 1];

            bool aDominantGo = payoff[0, 1] > payoff[1, 1] && payoff[0, 0] > payoff[1, 0];
            bool bDominantGo = payoff[1, 0] > payoff[1, 1] && payoff[0, 0] > payoff[0, 1];

            if (aDominantGo && !bDominantGo)
                return MergeResolution.AGoesFirst;
            if (bDominantGo && !aDominantGo)
                return MergeResolution.BGoesFirst;

            float epsilon = 0.1f;
            if (Mathf.Abs(aGo - aWait) < epsilon && Mathf.Abs(bGo - bWait) < epsilon)
                return MergeResolution.CooperativeMerge;

            if (aGo > bWait)
                return MergeResolution.AGoesFirst;
            if (bGo > aWait)
                return MergeResolution.BGoesFirst;

            return MergeResolution.CooperativeMerge;
        }

        private NegotiationResult RunRuleBasedNegotiation(LaneChangeRequest request, List<VehicleAIController> others)
        {
            foreach (var other in others)
            {
                float relativeSpeed = request.Requester.CurrentSpeed - other.CurrentSpeed;
                float timeToCollision = relativeSpeed > 0.5f
                    ? request.GapRear / relativeSpeed
                    : float.MaxValue;

                if (request.Priority > CalculatePriority(other) && timeToCollision > 2f)
                {
                    NotifyVehicleYield(other, request.Requester);
                    return NegotiationResult.Accepted;
                }
                else if (timeToCollision < 3f)
                {
                    _pendingRequests.Add(request);
                    return NegotiationResult.YieldRequested;
                }
            }

            return NegotiationResult.Accepted;
        }

        private int CalculatePriority(LaneChangeRequest request)
        {
            int priority = 0;
            if (request.CurrentSpeed < 5f) priority += 3;
            if (request.GapFront > 30f) priority += 2;
            if (request.GapRear < 10f) priority += 1;
            return priority;
        }

        private int CalculatePriority(VehicleAIController vehicle)
        {
            int priority = 0;
            if (vehicle.CurrentSpeed < 5f) priority += 3;
            if (vehicle is ILDriverModel) priority += 1;
            return priority;
        }

        private bool CheckSimpleGap(VehicleAIController requester, int targetLaneId)
        {
            float gapFront = 50f;
            float gapRear = 50f;

            Vector3 origin = requester.transform.position + Vector3.up * 0.5f;

            if (Physics.Raycast(origin, requester.transform.forward, out RaycastHit frontHit, 50f))
            {
                if (frontHit.collider.GetComponentInParent<VehicleAIController>() != null)
                    gapFront = frontHit.distance;
            }

            if (Physics.Raycast(origin, -requester.transform.forward, out RaycastHit rearHit, 50f))
            {
                if (rearHit.collider.GetComponentInParent<VehicleAIController>() != null)
                    gapRear = rearHit.distance;
            }

            float minGap = MIN_SAFE_GAP + requester.CurrentSpeed * 0.5f;
            return gapFront > minGap && gapRear > minGap;
        }

        private List<VehicleAIController> GetNearbyVehicles(VehicleAIController requester, int targetLaneId, float radius)
        {
            var result = new List<VehicleAIController>();
            var allVehicles = FindObjectsOfType<VehicleAIController>();

            foreach (var v in allVehicles)
            {
                if (v == requester) continue;
                if (Vector3.Distance(requester.transform.position, v.transform.position) < radius)
                {
                    result.Add(v);
                }
            }

            return result;
        }

        private int GetTargetLaneId(VehicleAIController requester, int side)
        {
            int currentIdx = 0;
            int.TryParse(requester.CurrentLaneId?.Split('_')[1], out currentIdx);
            return currentIdx + side;
        }

        private void NotifyVehicleYield(VehicleAIController vehicle, VehicleAIController to)
        {
            var method = vehicle.GetType().GetMethod("SetYieldTarget",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            method?.Invoke(vehicle, new object[] { to });
        }

        private void NotifyCooperativeMerge(VehicleAIController a, VehicleAIController b)
        {
            var methodA = a.GetType().GetMethod("SetCooperativePartner",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            var methodB = b.GetType().GetMethod("SetCooperativePartner",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);

            methodA?.Invoke(a, new object[] { b });
            methodB?.Invoke(b, new object[] { a });
        }

        private void ProcessPendingRequests()
        {
            for (int i = _pendingRequests.Count - 1; i >= 0; i--)
            {
                var request = _pendingRequests[i];
                if (Time.time - request.RequestTime > negotiationTimeout)
                {
                    _pendingRequests.RemoveAt(i);
                    continue;
                }

                int targetLaneId = GetTargetLaneId(request.Requester, request.TargetLaneSide);
                if (CheckSimpleGap(request.Requester, targetLaneId))
                {
                    _pendingRequests.RemoveAt(i);
                    var yieldMethod = request.Requester.GetType().GetMethod("InitiateLaneChange",
                        System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                    yieldMethod?.Invoke(request.Requester, new object[] { request.TargetLaneSide > 0 });
                }
            }
        }

        private void UpdateMergeGames()
        {
            for (int i = _activeMergeGames.Count - 1; i >= 0; i--)
            {
                var game = _activeMergeGames[i];
                if (game.VehicleA == null || game.VehicleB == null)
                {
                    _activeMergeGames.RemoveAt(i);
                    continue;
                }

                float dist = Vector3.Distance(game.VehicleA.transform.position, game.VehicleB.transform.position);
                if (dist > mergeZoneRadius * 2f)
                {
                    _activeMergeGames.RemoveAt(i);
                }
            }
        }

        private void CleanupStaleRequests()
        {
            _pendingRequests.RemoveAll(r =>
                r.Requester == null ||
                Time.time - r.RequestTime > negotiationTimeout * 2);
        }

        public void NotifyLaneChangeComplete(VehicleAIController vehicle)
        {
            _pendingRequests.RemoveAll(r => r.Requester == vehicle);
            _activeMergeGames.RemoveAll(g => g.VehicleA == vehicle || g.VehicleB == vehicle);

            foreach (var game in _activeMergeGames)
            {
                if (game.VehicleA == vehicle || game.VehicleB == vehicle)
                {
                    var other = game.VehicleA == vehicle ? game.VehicleB : game.VehicleA;
                    if (other != null)
                    {
                        var method = other.GetType().GetMethod("ClearYieldTarget",
                            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                        method?.Invoke(other, null);
                    }
                }
            }
        }

        public List<MergeGameState> GetActiveMergeGames()
        {
            return new List<MergeGameState>(_activeMergeGames);
        }
    }
}
