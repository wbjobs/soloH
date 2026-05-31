using System;
using System.Collections.Generic;
using UnityEngine;
using GaitSimulation.Core;
using GaitSimulation.Gait;
using GaitSimulation.Exoskeleton;
using GaitSimulation.Battery;

namespace GaitSimulation.Optimization
{
    public class DynamicPlanner
    {
        private readonly SimulationConfig _simConfig;
        private readonly ExoskeletonConfig _exoConfig;
        private readonly BatteryState _batteryState;
        private readonly JointTrajectoryGenerator _trajectoryGenerator;

        private int _numTimeSteps;
        private int _numSOCStates;
        private float _dt;
        private float _cycleDuration;

        private ExoskeletonMode[,][] _optimalPolicy;
        private float[,] _valueFunction;

        private const int NumModes = 3;
        private const float ModeSwitchCost = 0.5f;

        public bool PolicyComputed { get; private set; }

        public DynamicPlanner(SimulationConfig simConfig, ExoskeletonConfig exoConfig, BatteryState batteryState)
        {
            _simConfig = simConfig;
            _exoConfig = exoConfig;
            _batteryState = batteryState;
            _trajectoryGenerator = new JointTrajectoryGenerator(simConfig);
        }

        public void ComputeOptimalPolicy(int numTimeSteps = 60, int numSOCStates = 20)
        {
            _numTimeSteps = numTimeSteps;
            _numSOCStates = numSOCStates;
            _cycleDuration = _simConfig.gaitCycleDuration;
            _dt = _cycleDuration / _numTimeSteps;

            int numModeCombinations = NumModes * NumModes;
            _optimalPolicy = new ExoskeletonMode[numTimeSteps, numSOCStates][];
            _valueFunction = new float[numTimeSteps + 1, numSOCStates];

            float[,] predictedPowers = PredictPowerProfile();
            float[] minSOCForTime = new float[numTimeSteps];
            float[] maxSOCForTime = new float[numTimeSteps];

            InitializeValueFunction(numTimeSteps, numSOCStates, numModeCombinations);

            for (int t = numTimeSteps - 1; t >= 0; t--)
            {
                float time = t * _dt;
                minSOCForTime[t] = float.MaxValue;
                maxSOCForTime[t] = float.MinValue;

                for (int s = 0; s < numSOCStates; s++)
                {
                    float currentSOC = (float)s / (numSOCStates - 1);
                    float minCost = float.MaxValue;
                    ExoskeletonMode[] bestModes = new ExoskeletonMode[2];

                    for (int mKnee = 0; mKnee < NumModes; mKnee++)
                    {
                        for (int mAnkle = 0; mAnkle < NumModes; mAnkle++)
                        {
                            ExoskeletonMode kneeMode = (ExoskeletonMode)mKnee;
                            ExoskeletonMode ankleMode = (ExoskeletonMode)mAnkle;

                            float cost = EvaluatePolicyStep(time, t, s, currentSOC, kneeMode, ankleMode,
                                predictedPowers, out float nextSOC);

                            int nextSOCIndex = Mathf.RoundToInt(nextSOC * (numSOCStates - 1));
                            nextSOCIndex = Mathf.Clamp(nextSOCIndex, 0, numSOCStates - 1);

                            float totalCost = cost + _valueFunction[t + 1, nextSOCIndex];

                            if (totalCost < minCost)
                            {
                                minCost = totalCost;
                                bestModes[0] = kneeMode;
                                bestModes[1] = ankleMode;
                            }
                        }
                    }

                    _valueFunction[t, s] = minCost;
                    _optimalPolicy[t, s] = bestModes;

                    minSOCForTime[t] = Mathf.Min(minSOCForTime[t], currentSOC);
                    maxSOCForTime[t] = Mathf.Max(maxSOCForTime[t], currentSOC);
                }
            }

            PolicyComputed = true;
            Debug.Log("Dynamic programming policy computation completed.");
        }

        private void InitializeValueFunction(int numTimeSteps, int numSOCStates, int numModeCombinations)
        {
            for (int s = 0; s < numSOCStates; s++)
            {
                float soc = (float)s / (numSOCStates - 1);
                _valueFunction[numTimeSteps, s] = TerminalCost(soc);
            }
        }

        private float TerminalCost(float finalSOC)
        {
            float targetSOC = 0.7f;
            return 100f * Mathf.Pow(finalSOC - targetSOC, 2);
        }

        private float[,] PredictPowerProfile()
        {
            float[,] powers = new float[_numTimeSteps, 4];

            for (int t = 0; t < _numTimeSteps; t++)
            {
                float time = t * _dt;

                foreach (Side side in Enum.GetValues(typeof(Side)))
                {
                    float kneeAngVel = _trajectoryGenerator.GetJointAngularVelocity(JointType.Knee, side, time);
                    float kneeTorque = EstimateJointTorque(JointType.Knee, side, time);
                    float kneePower = kneeAngVel * kneeTorque;

                    float ankleAngVel = _trajectoryGenerator.GetJointAngularVelocity(JointType.Ankle, side, time);
                    float ankleTorque = EstimateJointTorque(JointType.Ankle, side, time);
                    float anklePower = ankleAngVel * ankleTorque;

                    int sideOffset = side == Side.Left ? 0 : 2;
                    powers[t, sideOffset] = kneePower;
                    powers[t, sideOffset + 1] = anklePower;
                }
            }

            return powers;
        }

        private float EstimateJointTorque(JointType jointType, Side side, float time)
        {
            float m = _simConfig.bodyMass;
            float g = _simConfig.gravity;
            float phase = (time % _simConfig.gaitCycleDuration) / _simConfig.gaitCycleDuration;
            if (side == Side.Right) phase = (phase + 0.5f) % 1f;

            float torque = 0f;
            float contactFactor = phase < 0.6f ? 1f : 0f;

            switch (jointType)
            {
                case JointType.Knee:
                    torque = m * g * 0.15f * Mathf.Sin(2f * Mathf.PI * phase) * contactFactor;
                    break;
                case JointType.Ankle:
                    torque = m * g * 0.1f * Mathf.Sin(2f * Mathf.PI * phase + 0.5f) * contactFactor;
                    break;
            }

            return torque;
        }

        private float EvaluatePolicyStep(float time, int timeStep, int socIndex, float currentSOC,
            ExoskeletonMode kneeMode, ExoskeletonMode ankleMode, float[,] predictedPowers, out float nextSOC)
        {
            float totalPower = 0f;

            foreach (Side side in Enum.GetValues(typeof(Side)))
            {
                int sideOffset = side == Side.Left ? 0 : 2;
                float kneePower = predictedPowers[timeStep, sideOffset];
                float anklePower = predictedPowers[timeStep, sideOffset + 1];

                totalPower += CalculateModePower(JointType.Knee, kneeMode, kneePower,
                    _exoConfig.GetMaxTorque(JointType.Knee),
                    _exoConfig.GetMotorEfficiency(JointType.Knee),
                    _exoConfig.GetGeneratorEfficiency(JointType.Knee));

                totalPower += CalculateModePower(JointType.Ankle, ankleMode, anklePower,
                    _exoConfig.GetMaxTorque(JointType.Ankle),
                    _exoConfig.GetMotorEfficiency(JointType.Ankle),
                    _exoConfig.GetGeneratorEfficiency(JointType.Ankle));
            }

            float energyChange = totalPower * _dt;
            float socChange = CalculateSOCChange(energyChange, currentSOC);
            nextSOC = Mathf.Clamp01(currentSOC + socChange);

            float cost = energyChange + 0.1f * Mathf.Max(0f, 0.2f - currentSOC) * 100f
                        + 0.1f * Mathf.Max(0f, currentSOC - 0.9f) * 100f;

            return Mathf.Max(0f, cost);
        }

        private float CalculateModePower(JointType jointType, ExoskeletonMode mode, float mechanicalPower,
            float maxTorque, float motorEff, float genEff)
        {
            switch (mode)
            {
                case ExoskeletonMode.Motor:
                    if (mechanicalPower <= 0) return 0.1f;
                    float assistPower = mechanicalPower * _exoConfig.assistRatio;
                    return assistPower / motorEff;

                case ExoskeletonMode.Generator:
                    if (mechanicalPower >= 0) return -0.1f;
                    float recoverPower = Mathf.Abs(mechanicalPower) * _exoConfig.regenerationRatio;
                    return -recoverPower * genEff;

                case ExoskeletonMode.Idle:
                default:
                    return 0f;
            }
        }

        private float CalculateSOCChange(float energy, float currentSOC)
        {
            float batteryCapacity = _batteryState.capacity * 3600f;

            if (energy > 0)
            {
                float actualEnergy = energy / _batteryState.dischargeEfficiency;
                return -actualEnergy / batteryCapacity;
            }
            else if (energy < 0)
            {
                float actualEnergy = -energy * _batteryState.chargeEfficiency;
                return actualEnergy / batteryCapacity;
            }

            return 0f;
        }

        public (ExoskeletonMode kneeMode, ExoskeletonMode ankleMode) GetOptimalModes(
            Side side, float time, float currentSOC)
        {
            if (!PolicyComputed)
            {
                throw new InvalidOperationException("Policy not computed yet. Call ComputeOptimalPolicy first.");
            }

            float phase = (time % _cycleDuration) / _cycleDuration;
            if (side == Side.Right) phase = (phase + 0.5f) % 1f;

            int timeStep = Mathf.FloorToInt(phase * _numTimeSteps);
            timeStep = Mathf.Clamp(timeStep, 0, _numTimeSteps - 1);

            int socIndex = Mathf.RoundToInt(currentSOC * (_numSOCStates - 1));
            socIndex = Mathf.Clamp(socIndex, 0, _numSOCStates - 1);

            var modes = _optimalPolicy[timeStep, socIndex];
            return (modes[0], modes[1]);
        }

        public Dictionary<(Side, JointType), ExoskeletonMode> GetFullModeOverride(float time, float currentSOC)
        {
            var overrides = new Dictionary<(Side, JointType), ExoskeletonMode>();

            foreach (Side side in Enum.GetValues(typeof(Side)))
            {
                var (kneeMode, ankleMode) = GetOptimalModes(side, time, currentSOC);
                overrides[(side, JointType.Knee)] = kneeMode;
                overrides[(side, JointType.Ankle)] = ankleMode;
            }

            return overrides;
        }

        public float GetValueFunction(float time, float currentSOC)
        {
            if (!PolicyComputed) return 0f;

            float phase = (time % _cycleDuration) / _cycleDuration;
            int timeStep = Mathf.FloorToInt(phase * _numTimeSteps);
            timeStep = Mathf.Clamp(timeStep, 0, _numTimeSteps - 1);

            int socIndex = Mathf.RoundToInt(currentSOC * (_numSOCStates - 1));
            socIndex = Mathf.Clamp(socIndex, 0, _numSOCStates - 1);

            return _valueFunction[timeStep, socIndex];
        }

        public string GetPolicySummary()
        {
            if (!PolicyComputed) return "Policy not computed.";

            string summary = "Optimal Policy Summary:\n";
            summary += $"Time Steps: {_numTimeSteps}\n";
            summary += $"SOC States: {_numSOCStates}\n";
            summary += $"Time Resolution: {_dt * 1000:F0}ms\n\n";

            int[] modeCounts = new int[3];
            for (int t = 0; t < _numTimeSteps; t++)
            {
                for (int s = 0; s < _numSOCStates; s++)
                {
                    var modes = _optimalPolicy[t, s];
                    modeCounts[(int)modes[0]]++;
                    modeCounts[(int)modes[1]]++;
                }
            }

            int total = _numTimeSteps * _numSOCStates * 2;
            summary += "Mode Distribution:\n";
            summary += $"  Idle: {modeCounts[0]} ({(float)modeCounts[0] / total * 100:F1}%)\n";
            summary += $"  Motor: {modeCounts[1]} ({(float)modeCounts[1] / total * 100:F1}%)\n";
            summary += $"  Generator: {modeCounts[2]} ({(float)modeCounts[2] / total * 100:F1}%)\n";

            return summary;
        }

        public void Reset()
        {
            PolicyComputed = false;
            _optimalPolicy = null;
            _valueFunction = null;
        }
    }
}
