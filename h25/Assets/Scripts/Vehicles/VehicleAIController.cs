using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class VehicleAIController : MonoBehaviour
    {
        [SerializeField] private float maxSpeed = 20f;
        [SerializeField] private float acceleration = 5f;
        [SerializeField] private float deceleration = 8f;
        [SerializeField] private float maxDeceleration = 12f;
        [SerializeField] private float steeringSpeed = 2f;
        [SerializeField] private float safetyDistance = 3f;

        [Header("IDM Parameters")]
        [SerializeField] private float jamDistance = 2.5f;
        [SerializeField] private float timeHeadway = 1.2f;
        [SerializeField] private float comfortableDeceleration = 4f;
        [SerializeField] private float accelerationExponent = 4f;
        [SerializeField] private float minGapForSpeedZero = 1.5f;

        [Header("Imitation Learning")]
        [SerializeField] private bool useImitationLearning = true;
        [SerializeField] private DrivingStyle drivingStyle = DrivingStyle.Normal;

        private LaneData _currentLane;
        private int _currentWaypointIndex;
        private Rigidbody _rb;
        private bool _isPlayer;
        private SceneParameters _parameters;
        private float _currentSpeed;
        private float _frontVehicleSpeed;
        private VehicleAIController _frontVehicle;
        private float _laneOffset;
        private float _leftLaneDistance = 100f;
        private float _rightLaneDistance = 100f;
        private bool _isPerformingLaneChange;
        private int _targetLaneIndex;
        private Vector3 _laneChangeStartPos;
        private Vector3 _laneChangeEndPos;
        private float _laneChangeProgress;
        private VehicleAIController _yieldTarget;
        private VehicleAIController _cooperativePartner;
        private bool _isYielding;

        public string CurrentLaneId { get; private set; }
        public float CurrentSpeed => _currentSpeed;
        public float SteeringAngle { get; private set; }
        public float Throttle { get; private set; }
        public float Brake { get; private set; }

        public void Initialize(string laneId, int startWaypoint, SceneParameters parameters, bool isPlayer)
        {
            _parameters = parameters;
            _isPlayer = isPlayer;
            CurrentLaneId = laneId;
            _currentWaypointIndex = startWaypoint;
            maxSpeed = parameters.maxSpeed;
            safetyDistance = parameters.safetyDistance;

            _currentLane = RoadGenerator.Instance.GetLaneById(laneId);
            _rb = GetComponent<Rigidbody>();

            var values = Enum.GetValues(typeof(DrivingStyle));
            drivingStyle = (DrivingStyle)values.GetValue(UnityEngine.Random.Range(0, values.Length));
            useImitationLearning = UnityEngine.Random.value > 0.3f;
        }

        private void Start()
        {
            if (_rb == null)
                _rb = GetComponent<Rigidbody>();
        }

        private void FixedUpdate()
        {
            if (!enabled) return;
            if (SimulationManager.Instance == null) return;
            if (SimulationManager.Instance.State != SimulationState.Playing &&
                SimulationManager.Instance.State != SimulationState.Replaying) return;
            if (_currentLane == null || _currentLane.waypoints.Count < 2) return;

            UpdateVehicleAI();
        }

        private void UpdateVehicleAI()
        {
            if (_currentWaypointIndex >= _currentLane.waypoints.Count - 1)
            {
                ChangeToRandomLane();
                return;
            }

            Vector3 targetPos = _currentLane.waypoints[_currentWaypointIndex].ToVector3();
            targetPos.y = transform.position.y;

            Vector3 toTarget = targetPos - transform.position;
            float distance = toTarget.magnitude;

            if (distance < 2f)
            {
                _currentWaypointIndex++;
                if (_currentWaypointIndex >= _currentLane.waypoints.Count)
                {
                    ChangeToRandomLane();
                    return;
                }
            }

            Vector3 desiredDir = toTarget.normalized;
            Quaternion targetRot = Quaternion.LookRotation(desiredDir);

            float angleDiff = Quaternion.Angle(transform.rotation, targetRot);
            SteeringAngle = Mathf.Clamp(angleDiff * Mathf.Sign(Vector3.Cross(transform.forward, desiredDir).y), -45f, 45f);

            _laneOffset = CalculateLaneOffset();
            CheckAdjacentLanes();

            float distanceToNextVehicle = CheckForwardDistance();
            float trafficLightDistance;
            TrafficLightState tlState;
            float trafficLightFactor = CheckTrafficLight(out trafficLightDistance, out tlState);
            float maxAllowedSpeed = maxSpeed * trafficLightFactor;

            if (useImitationLearning && ILDriverModel.Instance != null)
            {
                ApplyImitationLearningControl(distanceToNextVehicle, trafficLightDistance, tlState, targetRot, maxAllowedSpeed);
            }
            else
            {
                ApplyIDMControl(distanceToNextVehicle, maxAllowedSpeed);
                transform.rotation = Quaternion.Slerp(transform.rotation, targetRot, steeringSpeed * Time.fixedDeltaTime);
            }

            Vector3 moveDir = transform.forward * _currentSpeed;
            _rb.MovePosition(_rb.position + moveDir * Time.fixedDeltaTime);

            if (_yieldTarget != null)
            {
                float distToYield = Vector3.Distance(transform.position, _yieldTarget.transform.position);
                if (distToYield < 15f)
                {
                    _isYielding = true;
                    _currentSpeed = Mathf.Min(_currentSpeed, _yieldTarget.CurrentSpeed * 0.8f);
                }
                else
                {
                    _isYielding = false;
                }
            }

            if (_cooperativePartner != null)
            {
                float partnerSpeed = _cooperativePartner.CurrentSpeed;
                float targetSpeed = Mathf.Min(_currentSpeed, partnerSpeed);
                _currentSpeed = Mathf.Lerp(_currentSpeed, targetSpeed, 0.05f);
            }

            if (_isPlayer && CameraSystem.Instance != null)
            {
                CameraSystem.Instance.SetTarget(transform);
            }
        }

        private void SetYieldTarget(VehicleAIController target)
        {
            _yieldTarget = target;
            _isYielding = true;
        }

        private void ClearYieldTarget()
        {
            _yieldTarget = null;
            _isYielding = false;
        }

        private void SetCooperativePartner(VehicleAIController partner)
        {
            _cooperativePartner = partner;
        }

        private void InitiateLaneChange(bool toRight)
        {
            if (!_isPerformingLaneChange)
            {
                StartCoroutine(CooperativeLaneChange(toRight));
            }
        }

        private float CalculateLaneOffset()
        {
            if (_currentLane == null || _currentLane.waypoints.Count < 2) return 0f;

            int idx = Mathf.Clamp(_currentWaypointIndex, 0, _currentLane.waypoints.Count - 2);
            Vector3 p1 = _currentLane.waypoints[idx].ToVector3();
            Vector3 p2 = _currentLane.waypoints[idx + 1].ToVector3();
            Vector3 laneDir = (p2 - p1).normalized;
            Vector3 toCar = transform.position - p1;

            float dot = Vector3.Dot(toCar, laneDir);
            Vector3 projected = p1 + laneDir * dot;
            Vector3 offset = transform.position - projected;

            return Vector3.Dot(offset, transform.right);
        }

        private void CheckAdjacentLanes()
        {
            _leftLaneDistance = 100f;
            _rightLaneDistance = 100f;

            Vector3 leftOrigin = transform.position - transform.right * _parameters.laneWidth + Vector3.up * 0.5f;
            Vector3 rightOrigin = transform.position + transform.right * _parameters.laneWidth + Vector3.up * 0.5f;

            if (Physics.Raycast(leftOrigin, transform.forward, out RaycastHit leftHit, 30f))
            {
                if (leftHit.collider.GetComponentInParent<VehicleAIController>() != null)
                {
                    _leftLaneDistance = leftHit.distance;
                }
            }

            if (Physics.Raycast(rightOrigin, transform.forward, out RaycastHit rightHit, 30f))
            {
                if (rightHit.collider.GetComponentInParent<VehicleAIController>() != null)
                {
                    _rightLaneDistance = rightHit.distance;
                }
            }
        }

        private void ApplyImitationLearningControl(float distanceToFront, float tlDistance, TrafficLightState tlState,
            Quaternion targetRot, float maxAllowedSpeed)
        {
            var stateFeature = ILDriverModel.Instance.ExtractVehicleState(
                this, _laneOffset,
                distanceToFront, _frontVehicle,
                _leftLaneDistance, _rightLaneDistance,
                tlDistance, tlState);

            var action = ILDriverModel.Instance.PredictAction(stateFeature, drivingStyle);

            Throttle = action.throttle;
            Brake = action.brake;

            float steeringCorrection = action.steering * 45f;
            float baseSteering = Mathf.DeltaAngle(transform.rotation.eulerAngles.y, targetRot.eulerAngles.y);
            float totalSteering = Mathf.Lerp(baseSteering, steeringCorrection, 0.7f);
            SteeringAngle = Mathf.Clamp(totalSteering, -45f, 45f);

            Quaternion steeringRot = Quaternion.Euler(0, transform.rotation.eulerAngles.y + SteeringAngle * Time.fixedDeltaTime, 0);
            transform.rotation = Quaternion.Slerp(transform.rotation, steeringRot, steeringSpeed * Time.fixedDeltaTime);

            if (action.laneChange != 0 && !_isPerformingLaneChange)
            {
                StartCoroutine(CooperativeLaneChange(action.laneChange > 0));
            }

            if (Throttle > Brake)
            {
                _currentSpeed = Mathf.Min(_currentSpeed + acceleration * Throttle * Time.fixedDeltaTime, maxAllowedSpeed);
            }
            else if (Brake > 0.1f)
            {
                _currentSpeed = Mathf.Max(_currentSpeed - deceleration * Brake * Time.fixedDeltaTime, 0f);
            }
        }

        private void ApplyIDMControl(float distanceToNextVehicle, float maxAllowedSpeed)
        {
            float targetSpeed = CalculateIDMTargetSpeed(distanceToNextVehicle, maxAllowedSpeed);
            targetSpeed = Mathf.Clamp(targetSpeed, 0, maxAllowedSpeed);

            if (distanceToNextVehicle < minGapForSpeedZero)
            {
                targetSpeed = 0f;
            }

            float desiredAcceleration = (targetSpeed - _currentSpeed) / Time.fixedDeltaTime;
            desiredAcceleration = Mathf.Clamp(desiredAcceleration, -maxDeceleration, acceleration);

            if (desiredAcceleration > 0.1f)
            {
                Throttle = Mathf.Clamp01(desiredAcceleration / acceleration);
                Brake = 0f;
                _currentSpeed = Mathf.Min(_currentSpeed + acceleration * Time.fixedDeltaTime, targetSpeed);
            }
            else if (desiredAcceleration < -0.5f)
            {
                Throttle = 0f;
                Brake = Mathf.Clamp01(Mathf.Abs(desiredAcceleration) / deceleration);
                _currentSpeed = Mathf.Max(_currentSpeed + desiredAcceleration * Time.fixedDeltaTime, 0f);
            }
            else if (_currentSpeed < 0.5f && distanceToNextVehicle < jamDistance + 1f)
            {
                Throttle = 0f;
                Brake = 0.1f;
                _currentSpeed = 0f;
            }
            else
            {
                Throttle = 0.15f;
                Brake = 0f;
            }
        }

        private float CheckForwardDistance()
        {
            float minDistance = 100f;
            _frontVehicleSpeed = maxSpeed;
            Vector3 origin = transform.position + transform.forward * 1f + Vector3.up * 0.5f;
            Vector3 direction = transform.forward;

            if (Physics.Raycast(origin, direction, out RaycastHit hit, 50f))
            {
                if (hit.collider.CompareTag("Vehicle") || hit.collider.GetComponent<VehicleAIController>() != null)
                {
                    minDistance = hit.distance;
                    var frontVehicle = hit.collider.GetComponentInParent<VehicleAIController>();
                    if (frontVehicle != null)
                    {
                        _frontVehicleSpeed = frontVehicle.CurrentSpeed;
                    }
                }
            }
            return Mathf.Max(minDistance, 0.1f);
        }

        private float CheckTrafficLight(out float distance, out TrafficLightState state)
        {
            distance = 100f;
            state = TrafficLightState.Green;

            Vector3 origin = transform.position + transform.forward * 2f + Vector3.up * 1f;
            Vector3 direction = transform.forward;

            if (Physics.Raycast(origin, direction, out RaycastHit hit, 40f, 1 << 0, QueryTriggerInteraction.Ignore))
            {
                var trafficLight = hit.collider.GetComponentInParent<TrafficLightController>();
                if (trafficLight != null)
                {
                    float distanceToStopLine = Mathf.Max(0, hit.distance - 2f);
                    distance = distanceToStopLine;
                    state = trafficLight.CurrentState;

                    if (!trafficLight.CanPass(_currentSpeed, distanceToStopLine))
                    {
                        float stoppingDistance = CalculateStoppingDistance(_currentSpeed);
                        if (distanceToStopLine < stoppingDistance + 5f)
                        {
                            float brakeFactor = Mathf.Clamp01(distanceToStopLine / Mathf.Max(stoppingDistance, 1f));
                            return Mathf.Max(0f, brakeFactor * 0.3f);
                        }
                    }

                    if (trafficLight.IsApproachingRedLight(_currentSpeed, distanceToStopLine))
                    {
                        float approachFactor = Mathf.Clamp01(distanceToStopLine / 30f);
                        return Mathf.Max(0.3f, approachFactor);
                    }
                }
            }
            return 1f;
        }

        private System.Collections.IEnumerator CooperativeLaneChange(bool toRight)
        {
            if (_isPerformingLaneChange) yield break;
            _isPerformingLaneChange = true;

            float laneWidth = _parameters.laneWidth;
            Vector3 lateralDir = toRight ? transform.right : -transform.right;

            float gapCheckDistance = 50f;
            float rearCheckDistance = 20f;
            bool safeToChange = true;

            Vector3 frontCheckOrigin = transform.position + lateralDir * laneWidth + transform.forward * 5f;
            Vector3 rearCheckOrigin = transform.position + lateralDir * laneWidth - transform.forward * rearCheckDistance;
            Vector3 sideCheckOrigin = transform.position + lateralDir * laneWidth * 0.5f;

            if (Physics.Raycast(frontCheckOrigin, transform.forward, out _, gapCheckDistance))
                safeToChange = false;
            if (Physics.Raycast(rearCheckOrigin, transform.forward, out _, rearCheckDistance))
                safeToChange = false;
            if (Physics.Raycast(sideCheckOrigin, lateralDir, out _, laneWidth))
                safeToChange = false;

            if (CollaborativeLaneChangeManager.Instance != null)
            {
                var request = new LaneChangeRequest
                {
                    Requester = this,
                    TargetLaneSide = toRight ? 1 : -1,
                    CurrentSpeed = _currentSpeed,
                    GapFront = _frontVehicleSpeed > 0 ? _frontVehicleSpeed : 50f,
                    GapRear = rearCheckDistance
                };

                safeToChange = CollaborativeLaneChangeManager.Instance.RequestLaneChange(request);
            }

            if (!safeToChange)
            {
                _isPerformingLaneChange = false;
                yield break;
            }

            _laneChangeStartPos = transform.position;
            _laneChangeEndPos = transform.position + lateralDir * laneWidth;
            _laneChangeProgress = 0f;

            float duration = 3f;
            float elapsed = 0f;

            Vector3 forwardVel = transform.forward * _currentSpeed * 0.8f;

            while (elapsed < duration)
            {
                elapsed += Time.fixedDeltaTime;
                _laneChangeProgress = elapsed / duration;

                float t = _laneChangeProgress;
                float smoothT = t * t * (3f - 2f * t);

                Vector3 lateralOffset = Vector3.Lerp(_laneChangeStartPos, _laneChangeEndPos, smoothT) - _laneChangeStartPos;
                Vector3 newPos = _laneChangeStartPos + lateralOffset + forwardVel * elapsed;
                newPos.y = transform.position.y;

                _rb.MovePosition(newPos);

                float targetYaw = Mathf.Lerp(0, toRight ? 15f : -15f, Mathf.Sin(t * Mathf.PI));
                transform.rotation = Quaternion.Lerp(
                    transform.rotation,
                    Quaternion.Euler(0, transform.rotation.eulerAngles.y + targetYaw * 0.1f, 0),
                    0.3f);

                yield return new WaitForFixedUpdate();
            }

            transform.rotation = Quaternion.LookRotation(Vector3.Scale(transform.forward, new Vector3(1, 0, 1)).normalized);

            int currentIdx = int.Parse(CurrentLaneId.Split('_')[1]);
            int newIdx = toRight ? currentIdx + 1 : currentIdx - 1;
            string newLaneId = CurrentLaneId.Replace($"_{currentIdx}", $"_{newIdx}");

            var newLane = RoadGenerator.Instance.GetLaneById(newLaneId);
            if (newLane != null)
            {
                _currentLane = newLane;
                CurrentLaneId = newLaneId;
                _currentWaypointIndex = FindNearestWaypointIndex(transform.position);
            }

            if (CollaborativeLaneChangeManager.Instance != null)
            {
                CollaborativeLaneChangeManager.Instance.NotifyLaneChangeComplete(this);
            }

            _isPerformingLaneChange = false;
        }

        private int FindNearestWaypointIndex(Vector3 position)
        {
            int nearestIdx = 0;
            float minDist = float.MaxValue;
            for (int i = 0; i < _currentLane.waypoints.Count; i++)
            {
                float d = Vector3.Distance(position, _currentLane.waypoints[i].ToVector3());
                if (d < minDist)
                {
                    minDist = d;
                    nearestIdx = i;
                }
            }
            return Mathf.Clamp(nearestIdx, 0, _currentLane.waypoints.Count - 2);
        }

        private float CalculateStoppingDistance(float speed)
        {
            float deceleration = 8f;
            float reactionTime = 0.5f;
            float reactionDistance = speed * reactionTime;
            float brakingDistance = (speed * speed) / (2f * deceleration);
            return reactionDistance + brakingDistance + 1f;
        }

        private float CalculateIDMTargetSpeed(float gap, float maxAllowedSpeed)
        {
            if (gap >= 100f)
            {
                return maxAllowedSpeed;
            }

            float effectiveGap = Mathf.Max(gap - jamDistance, 0.01f);
            float speedDiff = _currentSpeed - _frontVehicleSpeed;

            float desiredGap = jamDistance +
                              Mathf.Max(0f, _currentSpeed * timeHeadway +
                                         (_currentSpeed * speedDiff) /
                                         (2f * Mathf.Sqrt(acceleration * comfortableDeceleration)));

            desiredGap = Mathf.Max(desiredGap, minGapForSpeedZero);

            if (effectiveGap <= minGapForSpeedZero)
            {
                return 0f;
            }

            float freeRoadTerm = Mathf.Pow(Mathf.Clamp01(_currentSpeed / Mathf.Max(maxAllowedSpeed, 0.1f)), accelerationExponent);
            float interactionTerm = Mathf.Pow(desiredGap / effectiveGap, 2f);

            float idmAcceleration = acceleration * (1f - freeRoadTerm - interactionTerm);

            float predictedSpeed = _currentSpeed + idmAcceleration * Time.fixedDeltaTime;
            predictedSpeed = Mathf.Clamp(predictedSpeed, 0f, maxAllowedSpeed);

            if (effectiveGap < jamDistance + 0.5f && _frontVehicleSpeed < 0.5f)
            {
                predictedSpeed = Mathf.Min(predictedSpeed, 1f);
            }

            if (gap < jamDistance && _currentSpeed > 0.5f)
            {
                float emergencyBrakeFactor = Mathf.Clamp01((jamDistance - gap) / jamDistance);
                predictedSpeed *= (1f - emergencyBrakeFactor);
            }

            return predictedSpeed;
        }

        private void ChangeToRandomLane()
        {
            var directions = new[] { LaneDirection.Forward, LaneDirection.Backward };
            var targetDir = directions[Random.Range(0, 2)];
            var newLane = RoadGenerator.Instance.GetRandomLane(targetDir);

            if (newLane != null && newLane.waypoints.Count > 2)
            {
                _currentLane = newLane;
                CurrentLaneId = newLane.id;
                _currentWaypointIndex = Random.Range(0, 2);

                Vector3 targetPos = _currentLane.waypoints[0].ToVector3();
                Vector3 nextPos = _currentLane.waypoints[1].ToVector3();
                transform.position = targetPos + Vector3.up * 0.5f;
                transform.rotation = Quaternion.LookRotation((nextPos - targetPos).normalized);
                _currentSpeed = 0f;
            }
        }

        public void SetSpeed(float speed)
        {
            _currentSpeed = Mathf.Clamp(speed, 0, maxSpeed);
        }

        public void SetPositionRotation(Vector3 pos, Quaternion rot)
        {
            if (_rb != null)
            {
                _rb.MovePosition(pos);
                _rb.MoveRotation(rot);
            }
            else
            {
                transform.position = pos;
                transform.rotation = rot;
            }
        }
    }
}
