using System;
using UnityEngine;

namespace GaitSimulation.Core
{
    [Serializable]
    public class BatteryState
    {
        public float capacity = 25f;
        public float currentSOC = 1f;
        public float currentVoltage = 36f;
        public float currentCurrent = 0f;
        public float chargeEfficiency = 0.92f;
        public float dischargeEfficiency = 0.88f;
        public float maxChargeCurrent = 10f;
        public float maxDischargeCurrent = 15f;
        public float nominalVoltage = 36f;

        public float GetStoredEnergy()
        {
            return currentSOC * capacity * 3600f;
        }

        public float GetAvailableEnergy()
        {
            return currentSOC * capacity * dischargeEfficiency * 3600f;
        }

        public void UpdateEnergy(float power, float deltaTime)
        {
            float energyChange = power * deltaTime;

            if (power > 0)
            {
                float actualEnergy = energyChange / dischargeEfficiency;
                float maxEnergy = currentSOC * capacity * 3600f;
                actualEnergy = Mathf.Min(actualEnergy, maxEnergy);
                currentCurrent = actualEnergy / (deltaTime * currentVoltage);
                currentCurrent = Mathf.Min(currentCurrent, maxDischargeCurrent);
                actualEnergy = currentCurrent * currentVoltage * deltaTime;
                float energyUsed = actualEnergy * dischargeEfficiency;
                currentSOC -= energyUsed / (capacity * 3600f);
            }
            else if (power < 0)
            {
                float actualEnergy = -energyChange * chargeEfficiency;
                float maxAccept = (1f - currentSOC) * capacity * 3600f;
                actualEnergy = Mathf.Min(actualEnergy, maxAccept);
                currentCurrent = -actualEnergy / (deltaTime * currentVoltage);
                currentCurrent = Mathf.Max(currentCurrent, -maxChargeCurrent);
                actualEnergy = -currentCurrent * currentVoltage * deltaTime * chargeEfficiency;
                currentSOC += actualEnergy / (capacity * 3600f);
            }
            else
            {
                currentCurrent = 0f;
            }

            currentSOC = Mathf.Clamp01(currentSOC);
            UpdateVoltage();
        }

        private void UpdateVoltage()
        {
            float baseVoltage = nominalVoltage * (0.85f + 0.15f * currentSOC);
            currentVoltage = baseVoltage - currentCurrent * 0.05f;
        }

        public void Reset()
        {
            currentSOC = 1f;
            currentVoltage = nominalVoltage;
            currentCurrent = 0f;
        }
    }
}
