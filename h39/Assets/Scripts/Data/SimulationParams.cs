using System;
using UnityEngine;

namespace SoleFrictionSim.Data
{
    [Serializable]
    public class PatternConfig
    {
        public PatternType patternType = PatternType.Herringbone;
        [Range(0.5f, 10f)] public float patternDepth = 3f;
        [Range(2f, 20f)] public float patternSpacing = 8f;
        [Range(0f, 90f)] public float patternAngle = 45f;
        [Range(5f, 15f)] public float soleWidth = 10f;
        [Range(20f, 35f)] public float soleLength = 28f;
        [Range(16, 256)] public int meshResolution = 64;
    }

    [Serializable]
    public class SimulationParams
    {
        [Header("Loading Conditions")]
        [Range(100f, 1000f)] public float normalLoad = 500f;

        [Header("Slip Velocity Range")]
        [Range(1e-7f, 0.001f)] public float minVelocity = 1e-6f;
        [Range(1f, 100f)] public float maxVelocity = 10f;
        [Range(50, 300)] public int velocitySamples = 100;

        [Header("Stick-Slip Model")]
        public bool enableStickSlip = true;
        [Range(0.1f, 5f)] public float staticFrictionMultiplier = 1.8f;
        [Range(0.0001f, 0.01f)] public float transitionVelocity = 0.001f;
        [Range(0.1f, 2f)] public float transitionSharpness = 0.8f;

        [Header("Edge Stress Correction")]
        public bool enableEdgeSmoothing = true;
        [Range(0.5f, 3f)] public float edgeSmoothingRadius = 1.5f;
        [Range(0.1f, 1f)] public float edgeStressReduction = 0.6f;

        [Header("BEM Solver Settings")]
        [Range(32, 256)] public int bemResolution = 64;
        [Range(50, 500)] public int maxIterations = 200;
        [Range(1e-8f, 1e-4f)] public float tolerance = 1e-6f;

        [Header("Physics Options")]
        public bool includeHydrodynamics = true;
        public bool useGpuAcceleration = true;

        [Header("Wear Simulation")]
        public bool enableWearSimulation = true;
        [Range(1e-8f, 1e-5f)] public float wearCoefficient = 1e-6f;
        [Range(100f, 10000f)] public float slidingDistance = 1000f;
        [Range(20f, 90f)] public float rubberHardnessShoreA = 60f;

        [Header("Thermal Simulation")]
        public bool enableThermalCoupling = true;
        [Range(-20f, 60f)] public float ambientTemperature = 25f;
        [Range(0.1f, 2f)] public float thermalConductivity = 0.3f;
        [Range(1000f, 2000f)] public float specificHeat = 1500f;
        [Range(900f, 1200f)] public float rubberDensity = 1100f;
        [Range(0.1f, 1f)] public float heatPartitionCoeff = 0.5f;
        [Range(1, 20)] public int thermalIterations = 5;
    }

    [Serializable]
    public class ContactResult
    {
        public float[,] contactPressure;
        public float[,] waterFilmThickness;
        public float[] slipVelocities;
        public float[] frictionCoefficients;
        public float contactAreaRatio;
        public float maxContactPressure;
        public float averagePressure;
        public float computeTime;
        public int iterations;
        public float residualError;

        public float[,] wearDepth;
        public float[,] wearRate;
        public float maxWearDepth;
        public float averageWearRate;
        public float predictedLifeKm;

        public float[,] temperatureField;
        public float[,] heatFlux;
        public float maxTemperature;
        public float averageTemperature;

        public float[,] temperatureDependentModulus;
        public float referenceVelocity = 1f;
        public float frictionAtReferenceVelocity;

        public int Resolution => contactPressure?.GetLength(0) ?? 0;

        public float GetPressureAt(int x, int y)
        {
            if (contactPressure == null || x < 0 || y < 0 ||
                x >= contactPressure.GetLength(0) || y >= contactPressure.GetLength(1))
                return 0f;
            return contactPressure[x, y];
        }

        public float GetWaterFilmAt(int x, int y)
        {
            if (waterFilmThickness == null || x < 0 || y < 0 ||
                x >= waterFilmThickness.GetLength(0) || y >= waterFilmThickness.GetLength(1))
                return 0f;
            return waterFilmThickness[x, y];
        }

        public float GetWearDepthAt(int x, int y)
        {
            if (wearDepth == null || x < 0 || y < 0 ||
                x >= wearDepth.GetLength(0) || y >= wearDepth.GetLength(1))
                return 0f;
            return wearDepth[x, y];
        }

        public float GetTemperatureAt(int x, int y)
        {
            if (temperatureField == null || x < 0 || y < 0 ||
                x >= temperatureField.GetLength(0) || y >= temperatureField.GetLength(1))
                return 0f;
            return temperatureField[x, y];
        }

        public void CalculateStatistics()
        {
            if (contactPressure == null) return;

            int n = contactPressure.GetLength(0);
            int m = contactPressure.GetLength(1);

            float sum = 0f;
            float max = 0f;
            int contactCount = 0;
            float threshold = 1f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < m; j++)
                {
                    float p = contactPressure[i, j];
                    sum += p;
                    if (p > max) max = p;
                    if (p > threshold) contactCount++;
                }
            }

            averagePressure = sum / (n * m);
            maxContactPressure = max;
            contactAreaRatio = (float)contactCount / (n * m);

            if (wearRate != null)
            {
                float wearSum = 0f;
                float wearMax = 0f;
                for (int i = 0; i < n; i++)
                {
                    for (int j = 0; j < m; j++)
                    {
                        float w = wearRate[i, j];
                        wearSum += w;
                        if (w > wearMax) wearMax = w;
                    }
                }
                averageWearRate = wearSum / (n * m);
                maxWearDepth = wearDepth != null ? Max2D(wearDepth) : 0f;
            }

            if (temperatureField != null)
            {
                float tempSum = 0f;
                float tempMax = 0f;
                for (int i = 0; i < n; i++)
                {
                    for (int j = 0; j < m; j++)
                    {
                        float t = temperatureField[i, j];
                        tempSum += t;
                        if (t > tempMax) tempMax = t;
                    }
                }
                averageTemperature = tempSum / (n * m);
                maxTemperature = tempMax;
            }

            if (slipVelocities != null && frictionCoefficients != null && slipVelocities.Length > 0)
            {
                for (int i = 0; i < slipVelocities.Length; i++)
                {
                    if (Mathf.Abs(slipVelocities[i] - referenceVelocity) < 0.01f)
                    {
                        frictionAtReferenceVelocity = frictionCoefficients[i];
                        break;
                    }
                }
            }
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

    [Serializable]
    public class BEMCell
    {
        public Vector2 position;
        public float pressure;
        public float displacement;
        public float gap;
        public bool inContact;
    }
}
