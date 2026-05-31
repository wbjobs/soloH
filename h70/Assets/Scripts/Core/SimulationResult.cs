using System;
using System.Collections.Generic;
using UnityEngine;

namespace GaitSimulation.Core
{
    [Serializable]
    public class SimulationResult
    {
        public float gaitCycleDuration;
        public float bodyMass;
        public float slopeAngle;

        public float totalGeneratorPower;
        public float totalMotorPower;
        public float netEnergyConsumption;
        public float finalSOC;
        public float initialSOC;
        public float totalGeneratorEnergy;
        public float totalMotorEnergy;
        public float totalSimulationTime;

        public List<TimePointData> timeSeriesData = new List<TimePointData>();

        public void AddTimePoint(TimePointData data)
        {
            timeSeriesData.Add(data);
        }

        public void CalculateSummary()
        {
            if (timeSeriesData.Count == 0) return;

            totalGeneratorEnergy = 0f;
            totalMotorEnergy = 0f;
            totalSimulationTime = timeSeriesData[timeSeriesData.Count - 1].time;

            for (int i = 1; i < timeSeriesData.Count; i++)
            {
                float dt = timeSeriesData[i].time - timeSeriesData[i - 1].time;
                float avgGenPower = (timeSeriesData[i].totalGeneratorPower + timeSeriesData[i - 1].totalGeneratorPower) * 0.5f;
                float avgMotPower = (timeSeriesData[i].totalMotorPower + timeSeriesData[i - 1].totalMotorPower) * 0.5f;

                totalGeneratorEnergy += avgGenPower * dt;
                totalMotorEnergy += avgMotPower * dt;
            }

            totalGeneratorPower = totalGeneratorEnergy / totalSimulationTime;
            totalMotorPower = totalMotorEnergy / totalSimulationTime;
            netEnergyConsumption = totalMotorEnergy - totalGeneratorEnergy;

            if (timeSeriesData.Count > 0)
            {
                initialSOC = timeSeriesData[0].batterySOC;
                finalSOC = timeSeriesData[timeSeriesData.Count - 1].batterySOC;
            }
        }

        public string GetSummaryText()
        {
            return $"Simulation Summary:\n" +
                   $"  Gait Cycle: {gaitCycleDuration:F2}s\n" +
                   $"  Body Mass: {bodyMass:F1}kg\n" +
                   $"  Slope: {slopeAngle:F1}°\n" +
                   $"  Duration: {totalSimulationTime:F2}s\n" +
                   $"  Avg Generator Power: {totalGeneratorPower:F2}W\n" +
                   $"  Avg Motor Power: {totalMotorPower:F2}W\n" +
                   $"  Net Energy: {netEnergyConsumption:F2}J ({netEnergyConsumption / 3600f:F4}Wh)\n" +
                   $"  Initial SOC: {initialSOC * 100:F1}%\n" +
                   $"  Final SOC: {finalSOC * 100:F1}%\n" +
                   $"  SOC Change: {(finalSOC - initialSOC) * 100:F1}%";
        }
    }

    [Serializable]
    public class TimePointData
    {
        public float time;
        public float gaitPhase;
        public float totalGeneratorPower;
        public float totalMotorPower;
        public float netPower;
        public float batterySOC;
        public float batteryCurrent;
        public float hipAngleL, hipAngleR;
        public float kneeAngleL, kneeAngleR;
        public float ankleAngleL, ankleAngleR;
        public float kneePowerL, kneePowerR;
        public float anklePowerL, anklePowerR;
        public ExoskeletonMode kneeModeL, kneeModeR;
        public ExoskeletonMode ankleModeL, ankleModeR;
    }
}
