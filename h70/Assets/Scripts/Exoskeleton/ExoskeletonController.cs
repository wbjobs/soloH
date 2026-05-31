using UnityEngine;
using GaitSimulation.Core;
using System.Collections.Generic;
using System;

namespace GaitSimulation.Exoskeleton
{
    public class ExoskeletonController
    {
        private readonly ExoskeletonConfig _config;
        private readonly SimulationConfig _simConfig;

        private Dictionary<(Side, JointType), ExoskeletonMode> _currentModes;
        private Dictionary<(Side, JointType), ExoskeletonMode> _previousModes;
        private Dictionary<(Side, JointType), float> _modeSwitchTimers;
        private Dictionary<(Side, JointType), float> _modeTransitionProgress;
        private Dictionary<(Side, JointType), float> _accumulatedEnergy;
        private Dictionary<(Side, JointType), float> _smoothedTorque;
        private Dictionary<(Side, JointType), float> _targetTorque;
        private Dictionary<(Side, JointType), float> _lastTorque;
        private Dictionary<(Side, JointType), float> _adaptiveAssistRatios;
        private Dictionary<(Side, JointType), float> _adaptiveRegenerationRatios;

        public float torqueSmoothingTime = 0.08f;
        public float maxTorqueSlewRate = 800f;
        public float modeTransitionDuration = 0.05f;

        public event Action<Side, JointType, ExoskeletonMode, ExoskeletonMode> OnModeChanged;

        public ExoskeletonController(ExoskeletonConfig config, SimulationConfig simConfig)
        {
            _config = config;
            _simConfig = simConfig;

            InitializeState();
        }

        private void InitializeState()
        {
            _currentModes = new Dictionary<(Side, JointType), ExoskeletonMode>();
            _previousModes = new Dictionary<(Side, JointType), ExoskeletonMode>();
            _modeSwitchTimers = new Dictionary<(Side, JointType), float>();
            _modeTransitionProgress = new Dictionary<(Side, JointType), float>();
            _accumulatedEnergy = new Dictionary<(Side, JointType), float>();
            _smoothedTorque = new Dictionary<(Side, JointType), float>();
            _targetTorque = new Dictionary<(Side, JointType), float>();
            _lastTorque = new Dictionary<(Side, JointType), float>();
            _adaptiveAssistRatios = new Dictionary<(Side, JointType), float>();
            _adaptiveRegenerationRatios = new Dictionary<(Side, JointType), float>();

            foreach (Side side in Enum.GetValues(typeof(Side)))
            {
                foreach (JointType joint in new[] { JointType.Knee, JointType.Ankle })
                {
                    _currentModes[(side, joint)] = ExoskeletonMode.Idle;
                    _previousModes[(side, joint)] = ExoskeletonMode.Idle;
                    _modeSwitchTimers[(side, joint)] = 0f;
                    _modeTransitionProgress[(side, joint)] = 1f;
                    _accumulatedEnergy[(side, joint)] = 0f;
                    _smoothedTorque[(side, joint)] = 0f;
                    _targetTorque[(side, joint)] = 0f;
                    _lastTorque[(side, joint)] = 0f;
                    _adaptiveAssistRatios[(side, joint)] = _config.assistRatio;
                    _adaptiveRegenerationRatios[(side, joint)] = _config.regenerationRatio;
                }
            }
        }

        public void Update(float time, float deltaTime,
            Dictionary<(Side, JointType), JointState> jointStates,
            Dictionary<(Side, JointType), ExoskeletonMode> overrideModes = null)
        {
            foreach (Side side in Enum.GetValues(typeof(Side)))
            {
                foreach (JointType joint in new[] { JointType.Knee, JointType.Ankle })
                {
                    var key = (side, joint);
                    var jointState = jointStates[key];

                    _modeSwitchTimers[key] += deltaTime;

                    ExoskeletonMode targetMode = overrideModes != null && overrideModes.ContainsKey(key)
                        ? overrideModes[key]
                        : DetermineOptimalMode(jointState, joint);

                    if (_modeSwitchTimers[key] >= _config.minModeDuration &&
                        targetMode != _currentModes[key])
                    {
                        ExoskeletonMode oldMode = _currentModes[key];
                        _previousModes[key] = oldMode;
                        _currentModes[key] = targetMode;
                        _modeSwitchTimers[key] = 0f;
                        _modeTransitionProgress[key] = 0f;
                        OnModeChanged?.Invoke(side, joint, oldMode, targetMode);
                    }

                    if (_modeTransitionProgress[key] < 1f)
                    {
                        _modeTransitionProgress[key] += deltaTime / modeTransitionDuration;
                        _modeTransitionProgress[key] = Mathf.Clamp01(_modeTransitionProgress[key]);
                    }

                    jointState.exoskeletonMode = _currentModes[key];

                    CalculateExoskeletonPowerSmooth(jointState, joint, key, deltaTime);

                    _accumulatedEnergy[key] += jointState.exoskeletonPower * deltaTime;
                }
            }
        }

        private ExoskeletonMode DetermineOptimalMode(JointState jointState, JointType jointType)
        {
            float mechanicalPower = jointState.mechanicalPower;
            float angularVelocity = Mathf.Abs(jointState.angularVelocity);

            if (angularVelocity < 0.1f)
            {
                return ExoskeletonMode.Idle;
            }

            if (Mathf.Abs(mechanicalPower) < _config.modeSwitchThreshold)
            {
                return ExoskeletonMode.Idle;
            }

            if (mechanicalPower > 0)
            {
                return ExoskeletonMode.Motor;
            }
            else
            {
                return ExoskeletonMode.Generator;
            }
        }

        private void CalculateExoskeletonPowerSmooth(JointState jointState, JointType jointType,
            (Side, JointType) key, float deltaTime)
        {
            float maxTorque = _config.GetMaxTorque(jointType);
            float motorEff = _config.GetMotorEfficiency(jointType);
            float genEff = _config.GetGeneratorEfficiency(jointType);
            float inertia = _config.GetInertia(jointType);
            float damping = _config.GetDamping(jointType);

            float rawDesiredTorque = CalculateRawDesiredTorque(jointState, jointType, maxTorque, key);

            _targetTorque[key] = rawDesiredTorque;

            float filteredTorque = ApplyTorqueSmoothing(key, rawDesiredTorque, deltaTime);

            float blendedTorque = ApplyModeBlending(key, _previousModes[key], _currentModes[key],
                jointState, jointType, maxTorque, filteredTorque, key);

            float slewLimitedTorque = ApplySlewRateLimiter(key, blendedTorque, deltaTime);

            float exoskeletonPower = CalculatePowerFromTorque(slewLimitedTorque, jointState,
                jointType, motorEff, genEff, inertia, damping);

            jointState.exoskeletonTorque = slewLimitedTorque;
            jointState.exoskeletonPower = exoskeletonPower;

            _lastTorque[key] = slewLimitedTorque;
        }

        private float CalculateRawDesiredTorque(JointState jointState, JointType jointType, float maxTorque, (Side, JointType) key)
        {
            float assistRatio = _adaptiveAssistRatios[key];
            float regenRatio = _adaptiveRegenerationRatios[key];

            switch (jointState.exoskeletonMode)
            {
                case ExoskeletonMode.Motor:
                    return Mathf.Clamp(jointState.torque * assistRatio, -maxTorque, maxTorque);
                case ExoskeletonMode.Generator:
                    return Mathf.Clamp(-jointState.torque * regenRatio, -maxTorque, maxTorque);
                case ExoskeletonMode.Idle:
                default:
                    return 0f;
            }
        }

        private float ApplyTorqueSmoothing((Side, JointType) key, float rawTorque, float deltaTime)
        {
            float alpha = deltaTime / Mathf.Max(deltaTime, torqueSmoothingTime);
            _smoothedTorque[key] = alpha * rawTorque + (1f - alpha) * _smoothedTorque[key];
            return _smoothedTorque[key];
        }

        private float ApplyModeBlending((Side, JointType) key, ExoskeletonMode prevMode,
            ExoskeletonMode currMode, JointState jointState, JointType jointType,
            float maxTorque, float filteredTorque, (Side, JointType) jointKey)
        {
            float t = _modeTransitionProgress[key];

            if (t >= 1f)
            {
                return filteredTorque;
            }

            float prevTorque = CalculateRawDesiredTorqueForMode(prevMode, jointState, jointType, maxTorque, jointKey);
            float currTorque = CalculateRawDesiredTorqueForMode(currMode, jointState, jointType, maxTorque, jointKey);

            float blendFactor = 0.5f - 0.5f * Mathf.Cos(t * Mathf.PI);

            return Mathf.Lerp(prevTorque, currTorque, blendFactor);
        }

        private float CalculateRawDesiredTorqueForMode(ExoskeletonMode mode, JointState jointState,
            JointType jointType, float maxTorque, (Side, JointType) key)
        {
            float assistRatio = _adaptiveAssistRatios[key];
            float regenRatio = _adaptiveRegenerationRatios[key];

            switch (mode)
            {
                case ExoskeletonMode.Motor:
                    return Mathf.Clamp(jointState.torque * assistRatio, -maxTorque, maxTorque);
                case ExoskeletonMode.Generator:
                    return Mathf.Clamp(-jointState.torque * regenRatio, -maxTorque, maxTorque);
                case ExoskeletonMode.Idle:
                default:
                    return 0f;
            }
        }

        private float ApplySlewRateLimiter((Side, JointType) key, float desiredTorque, float deltaTime)
        {
            float maxDelta = maxTorqueSlewRate * deltaTime;
            float currentTorque = _lastTorque[key];
            float torqueDelta = desiredTorque - currentTorque;

            if (Mathf.Abs(torqueDelta) > maxDelta)
            {
                return currentTorque + Mathf.Sign(torqueDelta) * maxDelta;
            }

            return desiredTorque;
        }

        private float CalculatePowerFromTorque(float torque, JointState jointState, JointType jointType,
            float motorEff, float genEff, float inertia, float damping)
        {
            float mechanicalPower = torque * jointState.angularVelocity;
            float inertialPower = inertia * jointState.angularAcceleration * jointState.angularVelocity;
            float dampingPower = damping * jointState.angularVelocity * jointState.angularVelocity;

            if (jointState.exoskeletonMode == ExoskeletonMode.Motor)
            {
                return (Mathf.Max(0, mechanicalPower) + inertialPower + dampingPower) / motorEff;
            }
            else if (jointState.exoskeletonMode == ExoskeletonMode.Generator)
            {
                return (Mathf.Min(0, mechanicalPower) - inertialPower - dampingPower) * genEff;
            }
            else
            {
                return mechanicalPower * 0.1f;
            }
        }

        public ExoskeletonMode GetMode(Side side, JointType jointType)
        {
            return _currentModes[(side, jointType)];
        }

        public float GetAccumulatedEnergy(Side side, JointType jointType)
        {
            return _accumulatedEnergy[(side, jointType)];
        }

        public (float totalMotorPower, float totalGeneratorPower) GetTotalPowers(
            Dictionary<(Side, JointType), JointState> jointStates)
        {
            float motorPower = 0f;
            float generatorPower = 0f;

            foreach (Side side in Enum.GetValues(typeof(Side)))
            {
                foreach (JointType joint in new[] { JointType.Knee, JointType.Ankle })
                {
                    var state = jointStates[(side, joint)];
                    if (state.exoskeletonPower > 0)
                    {
                        motorPower += state.exoskeletonPower;
                    }
                    else if (state.exoskeletonPower < 0)
                    {
                        generatorPower += Mathf.Abs(state.exoskeletonPower);
                    }
                }
            }

            return (motorPower, generatorPower);
        }

        public void SetMode(Side side, JointType jointType, ExoskeletonMode mode)
        {
            _currentModes[(side, jointType)] = mode;
            _modeSwitchTimers[(side, jointType)] = 0f;
        }

        public void SetAdaptiveAssistRatio(Side side, JointType jointType, float ratio)
        {
            var key = (side, jointType);
            if (_adaptiveAssistRatios.ContainsKey(key))
            {
                _adaptiveAssistRatios[key] = Mathf.Clamp(ratio, 0f, 1f);
            }
        }

        public void SetAdaptiveRegenerationRatio(Side side, JointType jointType, float ratio)
        {
            var key = (side, jointType);
            if (_adaptiveRegenerationRatios.ContainsKey(key))
            {
                _adaptiveRegenerationRatios[key] = Mathf.Clamp(ratio, 0f, 1f);
            }
        }

        public float GetAdaptiveAssistRatio(Side side, JointType jointType)
        {
            var key = (side, jointType);
            return _adaptiveAssistRatios.ContainsKey(key) ? _adaptiveAssistRatios[key] : _config.assistRatio;
        }

        public float GetAdaptiveRegenerationRatio(Side side, JointType jointType)
        {
            var key = (side, jointType);
            return _adaptiveRegenerationRatios.ContainsKey(key) ? _adaptiveRegenerationRatios[key] : _config.regenerationRatio;
        }

        public void Reset()
        {
            InitializeState();
        }
    }
}
