using System;
using System.Threading.Tasks;
using UnityEngine;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.Core
{
    public class ThermalCalculator
    {
        public ContactResult CalculateTemperatureField(ContactResult contactResult,
            RubberMaterial material, GroundSurface ground, SimulationParams simParams,
            float referenceVelocity = 1f)
        {
            if (contactResult?.contactPressure == null) return contactResult;

            int n = contactResult.contactPressure.GetLength(0);
            int m = contactResult.contactPressure.GetLength(1);

            float[,] heatFlux = CalculateHeatFlux(
                contactResult.contactPressure,
                contactResult.frictionCoefficients,
                contactResult.slipVelocities,
                referenceVelocity,
                simParams.heatPartitionCoeff);

            float[,] temperature = new float[n, m];
            for (int i = 0; i < n; i++)
                for (int j = 0; j < m; j++)
                    temperature[i, j] = simParams.ambientTemperature;

            float cellSize = 0.1f / n;
            float dt = 1e-4f;
            int iterations = simParams.thermalIterations * 50;

            for (int iter = 0; iter < iterations; iter++)
            {
                temperature = SolveHeatConductionStep(
                    temperature,
                    heatFlux,
                    simParams.ambientTemperature,
                    simParams.thermalConductivity,
                    simParams.specificHeat,
                    simParams.rubberDensity,
                    cellSize,
                    dt);
            }

            contactResult.heatFlux = heatFlux;
            contactResult.temperatureField = temperature;

            contactResult.temperatureDependentModulus = new float[n, m];
            for (int i = 0; i < n; i++)
                for (int j = 0; j < m; j++)
                    contactResult.temperatureDependentModulus[i, j] = material.GetModulusAtTemperature(temperature[i, j]);

            return contactResult;
        }

        public float[,] CalculateHeatFlux(float[,] pressure, float[] frictionCoeffs,
            float[] velocities, float referenceVelocity, float heatPartition = 0.5f)
        {
            int n = pressure.GetLength(0);
            int m = pressure.GetLength(1);
            float[,] heatFlux = new float[n, m];

            float mu = 0.5f;
            if (frictionCoeffs != null && frictionCoeffs.Length > 0)
            {
                int closestIdx = 0;
                float minDist = float.MaxValue;
                for (int i = 0; i < velocities?.Length; i++)
                {
                    float dist = Mathf.Abs(velocities[i] - referenceVelocity);
                    if (dist < minDist)
                    {
                        minDist = dist;
                        closestIdx = i;
                    }
                }
                mu = frictionCoeffs[closestIdx];
            }

            Parallel.For(0, n, i =>
            {
                for (int j = 0; j < m; j++)
                {
                    float p = pressure[i, j];
                    heatFlux[i, j] = p > 0 ? heatPartition * mu * p * referenceVelocity : 0f;
                }
            });

            return heatFlux;
        }

        public float[,] SolveHeatConductionStep(float[,] temperature, float[,] heatFlux,
            float ambientTemp, float k, float cp, float rho, float dx, float dt)
        {
            int n = temperature.GetLength(0);
            int m = temperature.GetLength(1);
            float[,] newTemp = (float[,])temperature.Clone();

            float alpha = k / (rho * cp);
            float hCoeff = 10f;
            float thickness = 0.01f;

            Parallel.For(1, n - 1, i =>
            {
                for (int j = 1; j < m - 1; j++)
                {
                    float laplacian = (temperature[i + 1, j] + temperature[i - 1, j] +
                                     temperature[i, j + 1] + temperature[i, j - 1] -
                                     4f * temperature[i, j]) / (dx * dx);

                    float sourceTerm = heatFlux[i, j] / (rho * cp * thickness);
                    float convectionTerm = hCoeff * (ambientTemp - temperature[i, j]) / (rho * cp * thickness);

                    newTemp[i, j] = temperature[i, j] + dt * (alpha * laplacian + sourceTerm + convectionTerm);
                    newTemp[i, j] = Mathf.Clamp(newTemp[i, j], -50f, 200f);
                }
            });

            for (int i = 0; i < n; i++)
            {
                newTemp[i, 0] = ambientTemp;
                newTemp[i, m - 1] = ambientTemp;
            }
            for (int j = 0; j < m; j++)
            {
                newTemp[0, j] = ambientTemp;
                newTemp[n - 1, j] = ambientTemp;
            }

            return newTemp;
        }

        public float[,] CalculateCoupledTemperature(float[,] pressure, float frictionCoeff,
            float velocity, SimulationParams simParams, RubberMaterial material,
            out float[,] modulusField)
        {
            int n = pressure.GetLength(0);
            int m = pressure.GetLength(1);

            float[,] temperature = new float[n, m];
            float[,] heatFlux = new float[n, m];
            modulusField = new float[n, m];

            float cellSize = 0.1f / n;
            float dt = 1e-4f;
            int iterations = simParams.thermalIterations * 100;

            for (int iter = 0; iter < iterations; iter++)
            {
                Parallel.For(0, n, i =>
                {
                    for (int j = 0; j < m; j++)
                    {
                        float p = pressure[i, j];
                        float localModulus = material.GetModulusAtTemperature(temperature[i, j]);
                        float localMu = frictionCoeff * (1f - 0.005f * Mathf.Max(0f, temperature[i, j] - 25f));
                        heatFlux[i, j] = p > 0 ? simParams.heatPartitionCoeff * localMu * p * velocity : 0f;
                        modulusField[i, j] = localModulus;
                    }
                });

                temperature = SolveHeatConductionStep(
                    temperature, heatFlux, simParams.ambientTemperature,
                    simParams.thermalConductivity, simParams.specificHeat,
                    simParams.rubberDensity, cellSize, dt);
            }

            return temperature;
        }

        public float CalculateContactTemperature(float pressure, float frictionCoeff,
            float velocity, float ambientTemp, float k_ground, float k_rubber)
        {
            if (pressure <= 0 || frictionCoeff <= 0 || velocity <= 0)
                return ambientTemp;

            float q = frictionCoeff * pressure * velocity;
            float sqrtK_rho_cp = Mathf.Sqrt(k_rubber * 1100f * 1500f);
            float sqrtK_rho_cp_ground = Mathf.Sqrt(k_ground * 2700f * 900f);

            float heatToRubber = sqrtK_rho_cp / (sqrtK_rho_cp + sqrtK_rho_cp_ground);
            float q_rubber = q * heatToRubber;

            float contactSize = 1e-3f;
            float maxTemp = ambientTemp + 2f * q_rubber * Mathf.Sqrt(velocity * contactSize) /
                           (k_rubber * Mathf.Sqrt(Mathf.PI));

            return Mathf.Clamp(maxTemp, ambientTemp, 250f);
        }

        public float CalculateFlashTemperature(float pressure, float frictionCoeff,
            float velocity, float roughness = 50e-6f)
        {
            if (pressure <= 0 || frictionCoeff <= 0 || velocity <= 0)
                return 0f;

            float asperitySize = roughness * 0.1f;
            float k = 0.3f;
            float rho_cp = 1100f * 1500f;

            float q = frictionCoeff * pressure * velocity;
            float pe = velocity * asperity * rho_cp / k;

            float tempRise;
            if (pe > 10f)
            {
                tempRise = 0.75f * q / k * Mathf.Sqrt(asperity * asperity / pe);
            }
            else
            {
                tempRise = q * asperity / (4f * k) * (1.62f / Mathf.Sqrt(pe) + 1.0f);
            }

            return Mathf.Clamp(tempRise, 0f, 200f);
        }

        public float[,] CalculateFlashTemperatureField(float[,] pressure, float frictionCoeff,
            float velocity, float roughness)
        {
            int n = pressure.GetLength(0);
            int m = pressure.GetLength(1);
            float[,] flashTemp = new float[n, m];

            Parallel.For(0, n, i =>
            {
                for (int j = 0; j < m; j++)
                {
                    flashTemp[i, j] = CalculateFlashTemperature(
                        pressure[i, j], frictionCoeff, velocity, roughness);
                }
            });

            return flashTemp;
        }

        public float CalculateTemperatureDependentFriction(float baseFriction,
            float temperature, float referenceTemp = 25f)
        {
            float deltaT = temperature - referenceTemp;
            float tempFactor = 1f - 0.008f * deltaT;

            if (temperature > 70f)
            {
                float tNorm = (temperature - 70f) / 30f;
                tempFactor *= Mathf.Exp(-tNorm * tNorm);
            }

            return baseFriction * Mathf.Clamp(tempFactor, 0.1f, 1.5f);
        }
    }
}
