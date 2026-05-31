using System;
using UnityEngine;
using GaitSimulation.Core;

namespace GaitSimulation.Battery
{
    public class BatteryManagementSystem
    {
        public BatteryState Battery { get; private set; }

        public float TotalEnergyIn { get; private set; }
        public float TotalEnergyOut { get; private set; }
        public float PeakChargePower { get; private set; }
        public float PeakDischargePower { get; private set; }

        public event Action<float> OnSOCChanged;
        public event Action<float, float> OnEnergyFlow;

        private float _minSOC = 0.1f;
        private float _maxSOC = 0.95f;

        public BatteryManagementSystem(BatteryState batteryState)
        {
            Battery = batteryState;
        }

        public void Update(float netPower, float deltaTime)
        {
            float clampedPower = ClampPower(netPower);

            Battery.UpdateEnergy(clampedPower, deltaTime);

            if (clampedPower < 0)
            {
                float energyIn = Mathf.Abs(clampedPower) * deltaTime;
                TotalEnergyIn += energyIn;
                PeakChargePower = Mathf.Max(PeakChargePower, Mathf.Abs(clampedPower));
            }
            else if (clampedPower > 0)
            {
                float energyOut = clampedPower * deltaTime;
                TotalEnergyOut += energyOut;
                PeakDischargePower = Mathf.Max(PeakDischargePower, clampedPower);
            }

            OnSOCChanged?.Invoke(Battery.currentSOC);
            OnEnergyFlow?.Invoke(clampedPower, deltaTime);
        }

        private float ClampPower(float power)
        {
            if (power > 0)
            {
                if (Battery.currentSOC <= _minSOC)
                {
                    Debug.LogWarning($"Battery SOC below minimum ({_minSOC * 100:F1}%), discharging disabled.");
                    return 0f;
                }

                float maxDischargePower = Battery.maxDischargeCurrent * Battery.currentVoltage;
                float socLimitedPower = maxDischargePower * ((Battery.currentSOC - _minSOC) / (1f - _minSOC));
                return Mathf.Min(power, Mathf.Min(maxDischargePower, socLimitedPower));
            }
            else if (power < 0)
            {
                if (Battery.currentSOC >= _maxSOC)
                {
                    Debug.LogWarning($"Battery SOC above maximum ({_maxSOC * 100:F1}%), charging disabled.");
                    return 0f;
                }

                float maxChargePower = Battery.maxChargeCurrent * Battery.currentVoltage;
                float socLimitedPower = -maxChargePower * ((_maxSOC - Battery.currentSOC) / (_maxSOC));
                return Mathf.Max(power, Mathf.Max(-maxChargePower, socLimitedPower));
            }

            return 0f;
        }

        public float GetEstimatedRemainingTime(float averagePowerDraw)
        {
            if (averagePowerDraw <= 0) return float.PositiveInfinity;

            float availableEnergy = Battery.GetAvailableEnergy();
            return availableEnergy / averagePowerDraw;
        }

        public float GetRoundTripEfficiency()
        {
            if (TotalEnergyIn == 0) return 1f;
            return TotalEnergyOut / TotalEnergyIn;
        }

        public BatteryHealthStatus GetHealthStatus()
        {
            if (Battery.currentSOC <= _minSOC)
                return BatteryHealthStatus.Critical;
            if (Battery.currentSOC <= 0.2f)
                return BatteryHealthStatus.Low;
            if (Battery.currentSOC >= _maxSOC)
                return BatteryHealthStatus.Full;
            return BatteryHealthStatus.Normal;
        }

        public string GetStatusText()
        {
            return $"Battery Status:\n" +
                   $"  SOC: {Battery.currentSOC * 100:F1}%\n" +
                   $"  Voltage: {Battery.currentVoltage:F2}V\n" +
                   $"  Current: {Battery.currentCurrent:F2}A\n" +
                   $"  Total Energy In: {TotalEnergyIn:F1}J ({TotalEnergyIn / 3600f:F3}Wh)\n" +
                   $"  Total Energy Out: {TotalEnergyOut:F1}J ({TotalEnergyOut / 3600f:F3}Wh)\n" +
                   $"  Peak Charge Power: {PeakChargePower:F1}W\n" +
                   $"  Peak Discharge Power: {PeakDischargePower:F1}W\n" +
                   $"  Round Trip Efficiency: {GetRoundTripEfficiency() * 100:F1}%\n" +
                   $"  Health: {GetHealthStatus()}";
        }

        public void Reset()
        {
            Battery.Reset();
            TotalEnergyIn = 0f;
            TotalEnergyOut = 0f;
            PeakChargePower = 0f;
            PeakDischargePower = 0f;
        }
    }

    public enum BatteryHealthStatus
    {
        Normal,
        Low,
        Critical,
        Full
    }
}
