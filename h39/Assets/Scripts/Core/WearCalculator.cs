using System;
using System.Threading.Tasks;
using UnityEngine;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.Core
{
    public class WearCalculator
    {
        public ContactResult CalculateWear(ContactResult contactResult, RubberMaterial material,
            GroundSurface ground, SimulationParams simParams)
        {
            if (contactResult?.contactPressure == null) return contactResult;

            int n = contactResult.contactPressure.GetLength(0);
            int m = contactResult.contactPressure.GetLength(1);

            float[,] wearRate = new float[n, m];
            float[,] wearDepth = new float[n, m];

            float wearCoeff = simParams.wearCoefficient;
            float slidingDistance = simParams.slidingDistance;
            float hardness = material.ShoreToHardness(material.shoreHardness) * material.wearHardnessFactor;

            Parallel.For(0, n, i =>
            {
                for (int j = 0; j < m; j++)
                {
                    float pressure = contactResult.contactPressure[i, j];

                    float localWearRate = CalculateLocalWearRate(
                        pressure,
                        material,
                        wearCoeff,
                        hardness,
                        contactResult.temperatureField != null ? contactResult.temperatureField[i, j] : simParams.ambientTemperature);

                    wearRate[i, j] = localWearRate;
                    wearDepth[i, j] = localWearRate * slidingDistance;
                }
            });

            contactResult.wearRate = wearRate;
            contactResult.wearDepth = wearDepth;

            float patternDepth = simParams is PatternConfig pc ? pc.patternDepth * 0.001f : 0.003f;
            float maxWear = Max2D(wearDepth);
            contactResult.predictedLifeKm = maxWear > 0
                ? (patternDepth * 0.5f / maxWear) * slidingDistance / 1000f
                : float.PositiveInfinity;

            return contactResult;
        }

        public float CalculateLocalWearRate(float pressure, RubberMaterial material,
            float wearCoeff, float hardness, float temperature)
        {
            if (pressure <= 0) return 0f;

            float tempFactor = 1f;
            if (temperature > material.referenceTemperature)
            {
                float deltaT = temperature - material.referenceTemperature;
                tempFactor = 1f + 0.02f * deltaT;
                if (temperature > material.glassTransitionTemperature)
                {
                    tempFactor *= 2f;
                }
            }

            float pressureFactor = pressure;
            if (pressure > 1e6f)
            {
                pressureFactor = 1e6f * Mathf.Pow(pressure / 1e6f, 1.2f);
            }

            return wearCoeff * pressureFactor * tempFactor / Mathf.Max(hardness, 1e6f);
        }

        public float[,] SimulateWearProgression(float[,] initialHeightField,
            float[,] pressure, RubberMaterial material, float totalDistance, int steps = 10)
        {
            int n = initialHeightField.GetLength(0);
            int m = initialHeightField.GetLength(1);
            float[,] height = (float[,])initialHeightField.Clone();

            float hardness = material.ShoreToHardness(material.shoreHardness);
            float stepDistance = totalDistance / steps;

            for (int step = 0; step < steps; step++)
            {
                float maxWear = 0f;

                Parallel.For(0, n, i =>
                {
                    for (int j = 0; j < m; j++)
                    {
                        float localWearRate = CalculateLocalWearRate(
                            pressure[i, j],
                            material,
                            material.wearCoefficient,
                            hardness,
                            25f);

                        float wearAmount = localWearRate * stepDistance;
                        height[i, j] = Mathf.Max(0f, height[i, j] - wearAmount);

                        if (wearAmount > maxWear) maxWear = wearAmount;
                    }
                });

                if (maxWear < 1e-9f) break;
            }

            return height;
        }

        public float PredictRemainingLife(float currentWearDepth, float wearRate,
            float patternDepth, float wearThreshold = 0.5f)
        {
            float allowableWear = patternDepth * wearThreshold;
            float remainingWear = Mathf.Max(0f, allowableWear - currentWearDepth);

            return wearRate > 0 ? remainingWear / wearRate : float.PositiveInfinity;
        }

        public float[,] CalculateWearLifeMap(float[,] wearRate, float patternDepth, float wearThreshold = 0.5f)
        {
            int n = wearRate.GetLength(0);
            int m = wearRate.GetLength(1);
            float[,] lifeMap = new float[n, m];

            float allowableWear = patternDepth * wearThreshold;

            Parallel.For(0, n, i =>
            {
                for (int j = 0; j < m; j++)
                {
                    lifeMap[i, j] = wearRate[i, j] > 0
                        ? allowableWear / wearRate[i, j]
                        : float.PositiveInfinity;
                }
            });

            return lifeMap;
        }

        public float CalculateSpecificWearEnergy(float pressure, float velocity,
            float frictionCoeff, float wearRate)
        {
            if (pressure <= 0 || velocity <= 0 || frictionCoeff <= 0) return 0f;

            float frictionalPower = frictionCoeff * pressure * velocity;
            return wearRate > 0 ? frictionalPower / wearRate : float.PositiveInfinity;
        }

        private float Max2D(float[,] data)
        {
            if (data == null) return 0f;
            float max = 0f;
            for (int i = 0; i < data.GetLength(0); i++)
                for (int j = 0; j < data.GetLength(1); j++)
                    if (data[i, j] > max) max = data[i, j];
            return max;
        }
    }
}
