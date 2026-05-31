using System;
using System.Collections.Generic;
using UnityEngine;
using GaitSimulation.Core;
using GaitSimulation.Gait;

namespace GaitSimulation.Safety
{
    [Serializable]
    public class IMUSensorData
    {
        public Vector3 acceleration;
        public Vector3 angularVelocity;
        public Vector3 orientation;
        public float timestamp;
    }

    [Serializable]
    public class GaitStabilityMetrics
    {
        public float marginOfStability;
        public float dynamicGaitIndex;
        public float stepWidthVariability;
        public float stepLengthVariability;
        public float trunkSwayAngle;
        public float trunkSwayVelocity;
        public float overallStabilityScore;
    }

    public enum FallRiskLevel
    {
        None = 0,
        Low = 1,
        Moderate = 2,
        High = 3,
        Critical = 4,
        Imminent = 5
    }

    public enum BrakingLevel
    {
        None = 0,
        Cautious = 1,
        ReducedAssist = 2,
        PartialBrake = 3,
        FullBrake = 4,
        EmergencyLock = 5
    }

    public class FallDetector
    {
        private readonly SimulationConfig _config;
        private readonly GaitModel _gaitModel;

        [Header("Sensor Configuration")]
        private readonly IMUSensorData _trunkIMU = new IMUSensorData();
        private readonly IMUSensorData _leftThighIMU = new IMUSensorData();
        private readonly IMUSensorData _rightThighIMU = new IMUSensorData();
        private readonly IMUSensorData _leftShankIMU = new IMUSensorData();
        private readonly IMUSensorData _rightShankIMU = new IMUSensorData();

        [Header("Detection Parameters")]
        public float trunkPitchThreshold = 30f;
        public float trunkRollThreshold = 20f;
        public float verticalAccelerationThreshold = 15f;
        public float angularVelocityThreshold = 3.5f;
        public float stabilityThreshold = 0.4f;
        public float minimumFallDetectionTime = 0.3f;

        [Header("Braking Parameters")]
        public float brakingDeceleration = 2.5f;
        public float brakingTransitionTime = 0.2f;
        public float emergencyLockTorque = 150f;
        public float recoveryDelay = 2.0f;

        [Header("State Variables")]
        public FallRiskLevel CurrentRiskLevel { get; private set; }
        public BrakingLevel CurrentBrakingLevel { get; private set; }
        public GaitStabilityMetrics StabilityMetrics { get; private set; }

        private bool _isFallDetected = false;
        private bool _isBrakingActive = false;
        private float _fallDetectionTimer = 0f;
        private float _brakingTimer = 0f;
        private float _recoveryTimer = 0f;
        private float _lastStableTime = 0f;

        private readonly Queue<IMUSensorData> _imuHistory = new Queue<IMUSensorData>();
        private readonly int _imuHistorySize = 50;
        private readonly float _sensorUpdateRate = 100f;

        private float[] _leftStepLengths = new float[10];
        private float[] _rightStepLengths = new float[10];
        private float[] _leftStepWidths = new float[10];
        private float[] _rightStepWidths = new float[10];
        private int _stepCounter = 0;

        private Vector3 _lastLeftFootPos;
        private Vector3 _lastRightFootPos;
        private float _lastStepTimeLeft;
        private float _lastStepTimeRight;

        public event Action<FallRiskLevel> OnFallRiskChanged;
        public event Action<BrakingLevel> OnBrakingLevelChanged;
        public event Action OnFallDetected;
        public event Action OnRecoveryComplete;

        public FallDetector(SimulationConfig config, GaitModel gaitModel)
        {
            _config = config;
            _gaitModel = gaitModel;
            StabilityMetrics = new GaitStabilityMetrics();
        }

        public void Update(float time, float deltaTime,
            Dictionary<(Side, JointType), JointState> jointStates,
            float gaitPhaseLeft, float gaitPhaseRight)
        {
            if (!_isFallDetected && !_isBrakingActive)
            {
                SimulateIMUData(time, jointStates);
                DetectGaitEvents(time, gaitPhaseLeft, gaitPhaseRight);
                CalculateStabilityMetrics(time, deltaTime);
                AssessFallRisk(time, deltaTime);
            }
            else if (_isBrakingActive)
            {
                UpdateBraking(time, deltaTime, jointStates);
            }
            else if (_isFallDetected)
            {
                HandlePostFallRecovery(time, deltaTime);
            }
        }

        private void SimulateIMUData(float time,
            Dictionary<(Side, JointType), JointState> jointStates)
        {
            var leftHip = jointStates[(Side.Left, JointType.Hip)];
            var rightHip = jointStates[(Side.Right, JointType.Hip)];
            var leftKnee = jointStates[(Side.Left, JointType.Knee)];
            var rightKnee = jointStates[(Side.Right, JointType.Knee)];

            float avgHipAngle = (leftHip.angle + rightHip.angle) * 0.5f;
            float avgHipAngVel = (leftHip.angularVelocity + rightHip.angularVelocity) * 0.5f;
            float avgHipAngAcc = (leftHip.angularAcceleration + rightHip.angularAcceleration) * 0.5f;

            _trunkIMU.orientation = new Vector3(avgHipAngle * Mathf.Rad2Deg, 0f, 0f);
            _trunkIMU.angularVelocity = new Vector3(avgHipAngVel, 0f, 0f);
            _trunkIMU.acceleration = new Vector3(
                avgHipAngAcc * _config.ThighLength * 0.5f,
                _config.gravity + avgHipAngVel * avgHipAngVel * _config.ThighLength * 0.5f,
                0f
            );
            _trunkIMU.timestamp = time;

            _leftThighIMU.orientation = new Vector3(leftHip.angle * Mathf.Rad2Deg, 0f, 0f);
            _leftThighIMU.angularVelocity = new Vector3(leftHip.angularVelocity, 0f, 0f);
            _leftThighIMU.acceleration = new Vector3(
                leftHip.angularAcceleration * _config.ThighLength * 0.5f,
                _config.gravity,
                0f
            );
            _leftThighIMU.timestamp = time;

            _rightThighIMU.orientation = new Vector3(rightHip.angle * Mathf.Rad2Deg, 0f, 0f);
            _rightThighIMU.angularVelocity = new Vector3(rightHip.angularVelocity, 0f, 0f);
            _rightThighIMU.acceleration = new Vector3(
                rightHip.angularAcceleration * _config.ThighLength * 0.5f,
                _config.gravity,
                0f
            );
            _rightThighIMU.timestamp = time;

            float leftShankAngle = leftHip.angle - leftKnee.angle;
            float rightShankAngle = rightHip.angle - rightKnee.angle;

            _leftShankIMU.orientation = new Vector3(leftShankAngle * Mathf.Rad2Deg, 0f, 0f);
            _leftShankIMU.angularVelocity = new Vector3(leftHip.angularVelocity - leftKnee.angularVelocity, 0f, 0f);
            _leftShankIMU.timestamp = time;

            _rightShankIMU.orientation = new Vector3(rightShankAngle * Mathf.Rad2Deg, 0f, 0f);
            _rightShankIMU.angularVelocity = new Vector3(rightHip.angularVelocity - rightKnee.angularVelocity, 0f, 0f);
            _rightShankIMU.timestamp = time;

            _imuHistory.Enqueue(_trunkIMU);
            if (_imuHistory.Count > _imuHistorySize)
            {
                _imuHistory.Dequeue();
            }
        }

        private void DetectGaitEvents(float time, float gaitPhaseLeft, float gaitPhaseRight)
        {
            Vector3 leftFootPos = _gaitModel.GetFootPosition(Side.Left, time);
            Vector3 rightFootPos = _gaitModel.GetFootPosition(Side.Right, time);

            if (gaitPhaseLeft < 0.02f && _lastStepTimeLeft < time - 0.5f)
            {
                float stepLength = Mathf.Abs(leftFootPos.x - _lastLeftFootPos.x);
                float stepWidth = Mathf.Abs(leftFootPos.z - _lastLeftFootPos.z);
                _leftStepLengths[_stepCounter % 10] = stepLength;
                _leftStepWidths[_stepCounter % 10] = stepWidth;
                _lastStepTimeLeft = time;
                _lastLeftFootPos = leftFootPos;
                _stepCounter++;
            }

            if (gaitPhaseRight < 0.02f && _lastStepTimeRight < time - 0.5f)
            {
                float stepLength = Mathf.Abs(rightFootPos.x - _lastRightFootPos.x);
                float stepWidth = Mathf.Abs(rightFootPos.z - _lastRightFootPos.z);
                _rightStepLengths[_stepCounter % 10] = stepLength;
                _rightStepWidths[_stepCounter % 10] = stepWidth;
                _lastStepTimeRight = time;
                _lastRightFootPos = rightFootPos;
            }
        }

        private void CalculateStabilityMetrics(float time, float deltaTime)
        {
            float trunkPitch = Mathf.Abs(_trunkIMU.orientation.x);
            float trunkPitchVel = Mathf.Abs(_trunkIMU.angularVelocity.x);

            float stepLengthVar = CalculateVariance(_leftStepLengths) + CalculateVariance(_rightStepLengths);
            float stepWidthVar = CalculateVariance(_leftStepWidths) + CalculateVariance(_rightStepWidths);

            float verticalAcc = Mathf.Abs(_trunkIMU.acceleration.y - _config.gravity);

            float baseOfSupport = 0.12f + stepWidthVar * 0.5f;
            float comVelocity = Mathf.Abs(_trunkIMU.acceleration.x * deltaTime);
            float marginOfStability = baseOfSupport - comVelocity * 0.1f;

            float dgi = CalculateDynamicGaitIndex(trunkPitch, stepLengthVar, verticalAcc);

            StabilityMetrics.trunkSwayAngle = trunkPitch;
            StabilityMetrics.trunkSwayVelocity = trunkPitchVel;
            StabilityMetrics.stepLengthVariability = stepLengthVar;
            StabilityMetrics.stepWidthVariability = stepWidthVar;
            StabilityMetrics.marginOfStability = Mathf.Clamp01(marginOfStability);
            StabilityMetrics.dynamicGaitIndex = Mathf.Clamp01(dgi);

            float score = 0.25f * (1f - trunkPitch / trunkPitchThreshold) +
                         0.25f * (1f - trunkPitchVel / angularVelocityThreshold) +
                         0.25f * StabilityMetrics.dynamicGaitIndex +
                         0.25f * StabilityMetrics.marginOfStability;

            StabilityMetrics.overallStabilityScore = Mathf.Clamp01(score);
        }

        private float CalculateVariance(float[] data)
        {
            if (data.Length < 2) return 0f;

            float mean = 0f;
            foreach (float v in data)
            {
                mean += v;
            }
            mean /= data.Length;

            float variance = 0f;
            foreach (float v in data)
            {
                variance += (v - mean) * (v - mean);
            }
            return Mathf.Sqrt(variance / data.Length) / (mean > 0.01f ? mean : 0.01f);
        }

        private float CalculateDynamicGaitIndex(float trunkPitch, float stepVar, float vertAcc)
        {
            float pitchScore = Mathf.Clamp01(1f - trunkPitch / 45f);
            float stepScore = Mathf.Clamp01(1f - stepVar / 0.3f);
            float accScore = Mathf.Clamp01(1f - vertAcc / 20f);
            return (pitchScore + stepScore + accScore) / 3f;
        }

        private void AssessFallRisk(float time, float deltaTime)
        {
            FallRiskLevel risk = FallRiskLevel.None;
            bool isUnstable = false;

            float trunkPitch = Mathf.Abs(_trunkIMU.orientation.x);
            float trunkAngVel = Mathf.Abs(_trunkIMU.angularVelocity.x);
            float vertAcc = Mathf.Abs(_trunkIMU.acceleration.y);
            float stability = StabilityMetrics.overallStabilityScore;

            if (stability < 0.3f) risk = FallRiskLevel.Low;
            if (stability < 0.2f) risk = FallRiskLevel.Moderate;

            if (trunkPitch > trunkPitchThreshold * 0.7f ||
                trunkAngVel > angularVelocityThreshold * 0.7f)
            {
                risk = FallRiskLevel.Moderate;
                isUnstable = true;
            }

            if (trunkPitch > trunkPitchThreshold ||
                trunkAngVel > angularVelocityThreshold ||
                vertAcc > verticalAccelerationThreshold ||
                stability < stabilityThreshold)
            {
                _fallDetectionTimer += deltaTime;
                isUnstable = true;

                if (_fallDetectionTimer >= minimumFallDetectionTime)
                {
                    if (trunkPitch > trunkPitchThreshold * 1.2f ||
                        trunkAngVel > angularVelocityThreshold * 1.2f ||
                        stability < 0.15f)
                    {
                        risk = FallRiskLevel.Imminent;
                        TriggerFallDetection();
                    }
                    else if (stability < 0.25f)
                    {
                        risk = FallRiskLevel.Critical;
                        InitiateBraking(BrakingLevel.FullBrake);
                    }
                    else
                    {
                        risk = FallRiskLevel.High;
                        InitiateBraking(BrakingLevel.PartialBrake);
                    }
                }
            }
            else
            {
                _fallDetectionTimer = Mathf.Max(0f, _fallDetectionTimer - deltaTime * 2f);
                _lastStableTime = time;

                if (_isBrakingActive && CurrentBrakingLevel <= BrakingLevel.PartialBrake)
                {
                    ReleaseBraking();
                }
            }

            if (risk != CurrentRiskLevel)
            {
                CurrentRiskLevel = risk;
                OnFallRiskChanged?.Invoke(risk);
            }
        }

        private void TriggerFallDetection()
        {
            if (_isFallDetected) return;

            _isFallDetected = true;
            InitiateBraking(BrakingLevel.EmergencyLock);
            OnFallDetected?.Invoke();

            Debug.LogWarning("⚠️ FALL DETECTED! Emergency brake activated.");
        }

        private void InitiateBraking(BrakingLevel level)
        {
            if (level == CurrentBrakingLevel) return;

            _isBrakingActive = level > BrakingLevel.None;
            _brakingTimer = 0f;
            CurrentBrakingLevel = level;

            UpdateJointBrakingTorques();
            OnBrakingLevelChanged?.Invoke(level);

            if (level >= BrakingLevel.FullBrake)
            {
                Debug.LogWarning($"⚠️ BRAKING ACTIVATED - Level: {level}");
            }
        }

        private void UpdateBraking(float time, float deltaTime,
            Dictionary<(Side, JointType), JointState> jointStates)
        {
            _brakingTimer += deltaTime;

            float brakingProgress = Mathf.Clamp01(_brakingTimer / brakingTransitionTime);

            foreach (Side side in Enum.GetValues(typeof(Side)))
            {
                foreach (JointType joint in new[] { JointType.Knee, JointType.Ankle })
                {
                    var key = (side, joint);
                    var jointState = jointStates[key];

                    float brakeTorque = CalculateBrakingTorque(joint, CurrentBrakingLevel, brakingProgress);
                    float brakingResistance = CalculateBrakingResistance(jointState, brakingProgress);

                    jointState.exoskeletonTorque = brakeTorque - brakingResistance;
                    jointState.exoskeletonMode = ExoskeletonMode.Generator;

                    float angularVelMag = Mathf.Abs(jointState.angularVelocity);
                    jointState.exoskeletonPower = -jointState.exoskeletonTorque * angularVelMag * 0.5f;
                }
            }

            float trunkPitch = Mathf.Abs(_trunkIMU.orientation.x);
            float trunkAngVel = Mathf.Abs(_trunkIMU.angularVelocity.x);

            if (CurrentBrakingLevel >= BrakingLevel.EmergencyLock &&
                _brakingTimer > 1.0f &&
                trunkPitch < 10f &&
                trunkAngVel < 0.5f)
            {
                _recoveryTimer += deltaTime;

                if (_recoveryTimer >= recoveryDelay)
                {
                    ResetSystem();
                }
            }
            else if (CurrentBrakingLevel < BrakingLevel.EmergencyLock &&
                     _brakingTimer > 0.5f)
            {
                float stability = StabilityMetrics.overallStabilityScore;
                if (stability > 0.6f && trunkPitch < 15f)
                {
                    ReleaseBraking();
                }
            }
        }

        private float CalculateBrakingTorque(JointType jointType, BrakingLevel level, float progress)
        {
            float maxTorque = jointType == JointType.Knee ? 80f : 40f;

            float levelFactor = 0f;
            switch (level)
            {
                case BrakingLevel.Cautious: levelFactor = 0.2f; break;
                case BrakingLevel.ReducedAssist: levelFactor = 0.4f; break;
                case BrakingLevel.PartialBrake: levelFactor = 0.6f; break;
                case BrakingLevel.FullBrake: levelFactor = 0.9f; break;
                case BrakingLevel.EmergencyLock: levelFactor = 1.0f; break;
            }

            float transitionFactor = progress * progress * (3f - 2f * progress);
            return -maxTorque * levelFactor * transitionFactor;
        }

        private float CalculateBrakingResistance(JointState jointState, float progress)
        {
            float damping = 15f * progress;
            return damping * jointState.angularVelocity;
        }

        private void UpdateJointBrakingTorques()
        {
        }

        private void ReleaseBraking()
        {
            _isBrakingActive = false;
            _brakingTimer = 0f;
            CurrentBrakingLevel = BrakingLevel.None;
            OnBrakingLevelChanged?.Invoke(BrakingLevel.None);
            Debug.Log("Braking released - system back to normal operation.");
        }

        private void HandlePostFallRecovery(float time, float deltaTime)
        {
            _recoveryTimer += deltaTime;

            if (_recoveryTimer >= recoveryDelay * 2f)
            {
                float trunkPitch = Mathf.Abs(_trunkIMU.orientation.x);
                float trunkAngVel = Mathf.Abs(_trunkIMU.angularVelocity.x);

                if (trunkPitch < 5f && trunkAngVel < 0.2f)
                {
                    ResetSystem();
                    OnRecoveryComplete?.Invoke();
                    Debug.Log("Recovery complete - normal operation resumed.");
                }
            }
        }

        public void TriggerEmergencyBrake()
        {
            TriggerFallDetection();
        }

        public float GetModifiedAssistRatio(float baseRatio, JointType jointType)
        {
            if (CurrentBrakingLevel == BrakingLevel.None) return baseRatio;

            float reductionFactor = 1f;
            switch (CurrentBrakingLevel)
            {
                case BrakingLevel.Cautious: reductionFactor = 0.8f; break;
                case BrakingLevel.ReducedAssist: reductionFactor = 0.5f; break;
                case BrakingLevel.PartialBrake: reductionFactor = 0.2f; break;
                case BrakingLevel.FullBrake: reductionFactor = 0f; break;
                case BrakingLevel.EmergencyLock: reductionFactor = 0f; break;
            }

            return baseRatio * reductionFactor;
        }

        public float GetModifiedRegenerationRatio(float baseRatio, JointType jointType)
        {
            if (CurrentBrakingLevel == BrakingLevel.None) return baseRatio;

            float boostFactor = 1f;
            switch (CurrentBrakingLevel)
            {
                case BrakingLevel.Cautious: boostFactor = 1.2f; break;
                case BrakingLevel.ReducedAssist: boostFactor = 1.5f; break;
                case BrakingLevel.PartialBrake: boostFactor = 2.0f; break;
                case BrakingLevel.FullBrake: boostFactor = 3.0f; break;
                case BrakingLevel.EmergencyLock: boostFactor = 5.0f; break;
            }

            return Mathf.Min(baseRatio * boostFactor, 1.0f);
        }

        private void ResetSystem()
        {
            _isFallDetected = false;
            _isBrakingActive = false;
            CurrentBrakingLevel = BrakingLevel.None;
            CurrentRiskLevel = FallRiskLevel.None;
            _fallDetectionTimer = 0f;
            _brakingTimer = 0f;
            _recoveryTimer = 0f;
            _imuHistory.Clear();
        }

        public string GetStatusText()
        {
            return $"Fall Detection Status:\n" +
                   $"  Risk Level: {CurrentRiskLevel}\n" +
                   $"  Braking Level: {CurrentBrakingLevel}\n" +
                   $"  Fall Detected: {_isFallDetected}\n" +
                   $"  Stability Score: {StabilityMetrics.overallStabilityScore * 100:F1}%\n" +
                   $"\nIMU Readings:\n" +
                   $"  Trunk Pitch: {_trunkIMU.orientation.x:F1}° (threshold: {trunkPitchThreshold}°)\n" +
                   $"  Trunk Ang Vel: {_trunkIMU.angularVelocity.x:F2} rad/s (threshold: {angularVelocityThreshold})\n" +
                   $"  Vertical Acc: {_trunkIMU.acceleration.y:F1} m/s² (threshold: {verticalAccelerationThreshold})\n" +
                   $"\nStability Metrics:\n" +
                   $"  Margin of Stability: {StabilityMetrics.marginOfStability * 100:F1}%\n" +
                   $"  Dynamic Gait Index: {StabilityMetrics.dynamicGaitIndex * 100:F1}%\n" +
                   $"  Trunk Sway: {StabilityMetrics.trunkSwayAngle:F1}°\n" +
                   $"  Step Length CV: {StabilityMetrics.stepLengthVariability * 100:F1}%";
        }

        public void Reset()
        {
            ResetSystem();
            _stepCounter = 0;
            _lastStepTimeLeft = 0f;
            _lastStepTimeRight = 0f;
            _lastStableTime = 0f;
            Array.Clear(_leftStepLengths, 0, _leftStepLengths.Length);
            Array.Clear(_rightStepLengths, 0, _rightStepLengths.Length);
            Array.Clear(_leftStepWidths, 0, _leftStepWidths.Length);
            Array.Clear(_rightStepWidths, 0, _rightStepWidths.Length);
        }
    }
}
