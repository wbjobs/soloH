using System;
using System.Threading.Tasks;
using UnityEngine;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.Core
{
    public class HydrodynamicsModule
    {
        public float CalculateHydrodynamicFriction(float velocity, ContactResult contactData,
            GroundSurface ground, RubberMaterial material)
        {
            if (velocity <= 0 || ground.waterFilmThickness <= 0) return 0f;

            float viscosity = ground.fluidViscosity;
            float baseFilmThickness = ground.waterFilmThickness * 1e-6f;

            float avgPressure = contactData.averagePressure;
            float contactRatio = contactData.contactAreaRatio;

            float lambda = CalculateFlowFactor(baseFilmThickness, material.rmsRoughness * 1e-6f);
            float avgFilmThickness = CalculateAverageFilmThickness(velocity, viscosity, avgPressure, baseFilmThickness);

            float shearStress = CalculateViscousShear(viscosity, velocity, avgFilmThickness);
            float asperityLoad = CalculateAsperityLoad(contactRatio, avgPressure, avgFilmThickness, material);

            float frictionCoeff = shearStress / Mathf.Max(avgPressure - asperityLoad, 1e3f);

            return Mathf.Clamp(frictionCoeff, 0.001f, 0.5f);
        }

        public float[,] CalculateWaterFilmPressure(float[,] contactPressure, GroundSurface ground, float velocity)
        {
            int n = contactPressure.GetLength(0);
            float[,] hydroPressure = new float[n, n];

            float viscosity = ground.fluidViscosity;
            float baseFilm = ground.waterFilmThickness * 1e-6f;
            float cellSize = 0.3f / n;

            Parallel.For(0, n, i =>
            {
                for (int j = 0; j < n; j++)
                {
                    float pContact = contactPressure[i, j];
                    float h = baseFilm * Mathf.Exp(-pContact / (ground.hardness * 1e9f) * 0.5f);

                    float dpdx = 0f;
                    if (i > 0 && i < n - 1)
                    {
                        dpdx = (contactPressure[i + 1, j] - contactPressure[i - 1, j]) / (2f * cellSize);
                    }

                    float reynoldsTerm = 6f * viscosity * velocity * h * dpdx;
                    hydroPressure[i, j] = Mathf.Max(0, reynoldsTerm);
                }
            });

            return hydroPressure;
        }

        public float[,] CalculateFilmThicknessDistribution(float[,] contactPressure,
            GroundSurface ground, RubberMaterial material, float velocity)
        {
            int n = contactPressure.GetLength(0);
            float[,] filmThickness = new float[n, n];

            float baseFilm = ground.waterFilmThickness * 1e-6f;
            float effectiveModulus = material.GetEffectiveModulus();

            Parallel.For(0, n, i =>
            {
                for (int j = 0; j < n; j++)
                {
                    float p = contactPressure[i, j];
                    float elasticDeformation = p / effectiveModulus * 1e-6f;
                    float squeezeEffect = Mathf.Exp(-p / effectiveModulus * 2f);
                    float entrainment = CalculateEntrainmentThickness(velocity, ground.fluidViscosity, p, effectiveModulus);

                    filmThickness[i, j] = Mathf.Max(0, baseFilm * squeezeEffect + entrainment - elasticDeformation);
                }
            });

            return filmThickness;
        }

        private float CalculateFlowFactor(float filmThickness, float rmsRoughness)
        {
            if (rmsRoughness <= 0) return 1f;

            float hSigma = filmThickness / rmsRoughness;

            if (hSigma > 5f) return 1f;
            if (hSigma < 0.5f) return hSigma * hSigma;

            return 1f - Mathf.Exp(-1.5f * hSigma);
        }

        private float CalculateAverageFilmThickness(float velocity, float viscosity, float load, float h0)
        {
            if (load <= 0) return h0;

            float hamrockDowson = 2.69f * Mathf.Pow(viscosity * velocity / load, 0.67f) * h0;

            return Mathf.Max(h0 * 0.1f, Mathf.Min(h0 * 2f, hamrockDowson));
        }

        private float CalculateViscousShear(float viscosity, float velocity, float filmThickness)
        {
            if (filmThickness <= 0) return 0f;

            float shearRate = velocity / filmThickness;
            float tau = viscosity * shearRate;

            float tauMax = 1e6f;
            return Mathf.Min(tau, tauMax);
        }

        private float CalculateAsperityLoad(float contactRatio, float avgPressure, float filmThickness, RubberMaterial material)
        {
            if (filmThickness <= 0) return avgPressure;

            float criticalFilm = material.rmsRoughness * 1e-6f * 3f;
            float asperityFactor = Mathf.Exp(-filmThickness / criticalFilm);

            return avgPressure * contactRatio * asperityFactor;
        }

        private float CalculateEntrainmentThickness(float velocity, float viscosity, float pressure, float effectiveModulus)
        {
            if (pressure <= 0) return 0f;

            float alpha = 2e-8f;
            float ubar = velocity * 0.5f;
            float gV = alpha * effectiveModulus;
            float gE = 1f;

            float hMin = 3.63f * Mathf.Pow(viscosity * ubar / (effectiveModulus * 1e-3f), 0.68f) *
                         Mathf.Pow(gE, -0.49f) * Mathf.Pow(gV, 0.06f);

            return hMin * 1e-3f;
        }

        public float CalculateLoadCarryingCapacity(float[,] hydroPressure, float cellSize)
        {
            int n = hydroPressure.GetLength(0);
            int m = hydroPressure.GetLength(1);
            float totalLoad = 0f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < m; j++)
                {
                    totalLoad += hydroPressure[i, j] * cellSize * cellSize;
                }
            }

            return totalLoad;
        }

        public float CalculateFrictionFromReynolds(float[,] pressure, float[,] filmThickness,
            GroundSurface ground, float velocity, float cellSize)
        {
            int n = pressure.GetLength(0);
            float viscosity = ground.fluidViscosity;

            float totalForce = 0f;
            float totalShear = 0f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float p = pressure[i, j];
                    float h = filmThickness[i, j];
                    float area = cellSize * cellSize;

                    totalForce += p * area;

                    if (h > 1e-9f)
                    {
                        float dpdx = 0f;
                        if (i > 0 && i < n - 1)
                        {
                            dpdx = (pressure[i + 1, j] - pressure[i - 1, j]) / (2f * cellSize);
                        }

                        float shear = viscosity * velocity / h + 0.5f * h * dpdx;
                        totalShear += Mathf.Abs(shear) * area;
                    }
                }
            }

            return totalForce > 0 ? totalShear / totalForce : 0f;
        }
    }
}
