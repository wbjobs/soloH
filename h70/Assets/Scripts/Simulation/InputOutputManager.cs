using System;
using System.Collections.Generic;
using UnityEngine;
using GaitSimulation.Core;
using GaitSimulation.Gait;
using GaitSimulation.Exoskeleton;
using GaitSimulation.Battery;

namespace GaitSimulation.Simulation
{
    public class InputOutputManager
    {
        public SimulationConfig Config { get; private set; }
        public SimulationResult Result { get; private set; }

        private float _currentTime;
        private float _lastRecordTime;
        private float _recordInterval = 0.01f;

        public event Action<TimePointData> OnDataRecorded;
        public event Action<SimulationResult> OnSimulationComplete;

        public InputOutputManager(SimulationConfig config)
        {
            Config = config;
            Result = new SimulationResult
            {
                gaitCycleDuration = config.gaitCycleDuration,
                bodyMass = config.bodyMass,
                slopeAngle = config.slopeAngle
            };
        }

        public void SetInputParameters(float gaitCycleDuration, float bodyMass, float slopeAngle)
        {
            Config.gaitCycleDuration = Mathf.Clamp(gaitCycleDuration, 0.5f, 3.0f);
            Config.bodyMass = Mathf.Clamp(bodyMass, 30f, 150f);
            Config.slopeAngle = Mathf.Clamp(slopeAngle, -15f, 15f);

            Result.gaitCycleDuration = Config.gaitCycleDuration;
            Result.bodyMass = Config.bodyMass;
            Result.slopeAngle = Config.slopeAngle;

            Debug.Log($"Input parameters updated: Cycle={Config.gaitCycleDuration:F2}s, " +
                      $"Mass={Config.bodyMass:F1}kg, Slope={Config.slopeAngle:F1}°");
        }

        public void Update(float time, float deltaTime,
            GaitModel gaitModel,
            ExoskeletonController exoskeletonController,
            BatteryManagementSystem bms)
        {
            _currentTime = time;

            if (time - _lastRecordTime >= _recordInterval)
            {
                RecordTimePoint(gaitModel, exoskeletonController, bms);
                _lastRecordTime = time;
            }
        }

        private void RecordTimePoint(GaitModel gaitModel,
            ExoskeletonController exoskeletonController,
            BatteryManagementSystem bms)
        {
            var timePoint = new TimePointData
            {
                time = _currentTime,
                gaitPhase = gaitModel.GetNormalizedPhase(_currentTime, Side.Left),
                batterySOC = bms.Battery.currentSOC,
                batteryCurrent = bms.Battery.currentCurrent
            };

            var (totalMotorPower, totalGeneratorPower) =
                exoskeletonController.GetTotalPowers(gaitModel.JointStates);

            timePoint.totalMotorPower = totalMotorPower;
            timePoint.totalGeneratorPower = totalGeneratorPower;
            timePoint.netPower = totalMotorPower - totalGeneratorPower;

            var leftHip = gaitModel.GetJointState(Side.Left, JointType.Hip);
            var leftKnee = gaitModel.GetJointState(Side.Left, JointType.Knee);
            var leftAnkle = gaitModel.GetJointState(Side.Left, JointType.Ankle);
            var rightHip = gaitModel.GetJointState(Side.Right, JointType.Hip);
            var rightKnee = gaitModel.GetJointState(Side.Right, JointType.Knee);
            var rightAnkle = gaitModel.GetJointState(Side.Right, JointType.Ankle);

            timePoint.hipAngleL = leftHip.angle * Mathf.Rad2Deg;
            timePoint.kneeAngleL = leftKnee.angle * Mathf.Rad2Deg;
            timePoint.ankleAngleL = leftAnkle.angle * Mathf.Rad2Deg;
            timePoint.hipAngleR = rightHip.angle * Mathf.Rad2Deg;
            timePoint.kneeAngleR = rightKnee.angle * Mathf.Rad2Deg;
            timePoint.ankleAngleR = rightAnkle.angle * Mathf.Rad2Deg;

            timePoint.kneePowerL = leftKnee.exoskeletonPower;
            timePoint.kneePowerR = rightKnee.exoskeletonPower;
            timePoint.anklePowerL = leftAnkle.exoskeletonPower;
            timePoint.anklePowerR = rightAnkle.exoskeletonPower;

            timePoint.kneeModeL = leftKnee.exoskeletonMode;
            timePoint.kneeModeR = rightKnee.exoskeletonMode;
            timePoint.ankleModeL = leftAnkle.exoskeletonMode;
            timePoint.ankleModeR = rightAnkle.exoskeletonMode;

            Result.AddTimePoint(timePoint);
            OnDataRecorded?.Invoke(timePoint);
        }

        public void FinalizeSimulation()
        {
            Result.CalculateSummary();
            OnSimulationComplete?.Invoke(Result);
        }

        public Dictionary<string, float> GetCurrentMetrics()
        {
            var metrics = new Dictionary<string, float>
            {
                ["Time"] = _currentTime,
                ["Gait Phase (%)"] = Result.timeSeriesData.Count > 0
                    ? Result.timeSeriesData[Result.timeSeriesData.Count - 1].gaitPhase * 100f
                    : 0f,
                ["Battery SOC (%)"] = Result.timeSeriesData.Count > 0
                    ? Result.timeSeriesData[Result.timeSeriesData.Count - 1].batterySOC * 100f
                    : 100f,
                ["Battery Current (A)"] = Result.timeSeriesData.Count > 0
                    ? Result.timeSeriesData[Result.timeSeriesData.Count - 1].batteryCurrent
                    : 0f,
                ["Motor Power (W)"] = Result.timeSeriesData.Count > 0
                    ? Result.timeSeriesData[Result.timeSeriesData.Count - 1].totalMotorPower
                    : 0f,
                ["Generator Power (W)"] = Result.timeSeriesData.Count > 0
                    ? Result.timeSeriesData[Result.timeSeriesData.Count - 1].totalGeneratorPower
                    : 0f,
                ["Net Power (W)"] = Result.timeSeriesData.Count > 0
                    ? Result.timeSeriesData[Result.timeSeriesData.Count - 1].netPower
                    : 0f
            };

            return metrics;
        }

        public string GetMetricsDisplayText()
        {
            var metrics = GetCurrentMetrics();
            string text = "=== Current Metrics ===\n";
            foreach (var kvp in metrics)
            {
                text += $"{kvp.Key}: {kvp.Value:F2}\n";
            }
            return text;
        }

        public void Reset()
        {
            Result = new SimulationResult
            {
                gaitCycleDuration = Config.gaitCycleDuration,
                bodyMass = Config.bodyMass,
                slopeAngle = Config.slopeAngle
            };
            _currentTime = 0f;
            _lastRecordTime = -_recordInterval;
        }
    }
}
