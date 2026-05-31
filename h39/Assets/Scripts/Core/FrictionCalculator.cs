using System;
using System.Threading.Tasks;
using UnityEngine;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.Core
{
    public class FrictionCalculator
    {
        private readonly HydrodynamicsModule _hydrodynamics = new HydrodynamicsModule();

        public float[] CalculateFrictionCurve(
            ContactResult contactData,
            RubberMaterial material,
            GroundSurface ground,
            float[] velocities)
        {
            return CalculateFrictionCurve(contactData, material, ground, velocities, new SimulationParams());
        }

        public float[] CalculateFrictionCurve(
            ContactResult contactData,
            RubberMaterial material,
            GroundSurface ground,
            float[] velocities,
            SimulationParams simParams)
        {
            if (contactData == null || velocities == null) return null;

            int n = velocities.Length;
            float[] frictionCoeffs = new float[n];

            float averagePressure = contactData.averagePressure;
            float contactAreaRatio = contactData.contactAreaRatio;
            float rmsRoughness = material.rmsRoughness * 1e-6f;
            float correlationLength = material.correlationLength * 1e-6f;

            float[,] correctedPressure = contactData.contactPressure;
            if (simParams.enableEdgeSmoothing)
            {
                correctedPressure = ApplyEdgeStressCorrection(
                    contactData.contactPressure,
                    simParams.edgeSmoothingRadius,
                    simParams.edgeStressReduction);
                contactData.contactPressure = correctedPressure;
                contactData.CalculateStatistics();
                averagePressure = contactData.averagePressure;
            }

            Parallel.For(0, n, i =>
            {
                float velocity = velocities[i];

                float muAdhesion = CalculateAdhesiveFriction(velocity, material, averagePressure);
                float muViscoelastic = CalculateViscoelasticFriction(velocity, material, ground, rmsRoughness, correlationLength);
                float muHydro = _hydrodynamics.CalculateHydrodynamicFriction(velocity, contactData, ground, material);

                float dryContactRatio = contactAreaRatio;
                if (ground.waterFilmThickness > 0)
                {
                    float lambda = CalculateFilmParameter(rmsRoughness, ground.waterFilmThickness * 1e-6f);
                    dryContactRatio = CalculateDryContactRatio(lambda);
                }

                float muDry = muAdhesion + muViscoelastic;

                if (simParams.enableStickSlip)
                {
                    muDry = ApplyStickSlipModel(velocity, muDry, simParams);
                }

                frictionCoeffs[i] = muDry * dryContactRatio + muHydro * (1f - dryContactRatio);
                frictionCoeffs[i] = Mathf.Max(0.01f, Mathf.Min(frictionCoeffs[i], 3.0f));
            });

            return frictionCoeffs;
        }

        public float ApplyStickSlipModel(float velocity, float kineticFriction, SimulationParams simParams)
        {
            if (velocity <= 0) return kineticFriction * simParams.staticFrictionMultiplier;

            float vTrans = simParams.transitionVelocity;
            float alpha = simParams.transitionSharpness;
            float muRatio = simParams.staticFrictionMultiplier;

            float normalizedV = Mathf.Log10(Mathf.Max(velocity, 1e-10f) / vTrans);
            float transition = 0.5f * (1f + Erf(normalizedV / alpha));

            float staticFriction = kineticFriction * muRatio;
            return Mathf.Lerp(staticFriction, kineticFriction, transition);
        }

        public float[,] ApplyEdgeStressCorrection(float[,] pressure, float smoothingRadius, float edgeReduction)
        {
            int n = pressure.GetLength(0);
            int m = pressure.GetLength(1);
            float[,] result = (float[,])pressure.Clone();

            float[,] edgeMask = ComputeEdgeMask(pressure, smoothingRadius);

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < m; j++)
                {
                    float edgeFactor = edgeMask[i, j];
                    float reduction = 1f - edgeReduction * edgeFactor;
                    result[i, j] *= reduction;
                }
            }

            return GaussianSmooth(result, Mathf.Max(1, (int)smoothingRadius));
        }

        private float[,] ComputeEdgeMask(float[,] pressure, float radius)
        {
            int n = pressure.GetLength(0);
            int m = pressure.GetLength(1);
            float[,] mask = new float[n, m];

            float threshold = 10f;
            int r = Mathf.Max(1, (int)radius);

            Parallel.For(0, n, i =>
            {
                for (int j = 0; j < m; j++)
                {
                    if (pressure[i, j] <= threshold)
                    {
                        mask[i, j] = 0f;
                        continue;
                    }

                    bool isNearEdge = false;
                    float edgeDistance = float.MaxValue;

                    for (int di = -r; di <= r; di++)
                    {
                        for (int dj = -r; dj <= r; dj++)
                        {
                            int ni = i + di;
                            int nj = j + dj;

                            if (ni < 0 || ni >= n || nj < 0 || nj >= m)
                            {
                                isNearEdge = true;
                                edgeDistance = Mathf.Min(edgeDistance, Mathf.Sqrt(di * di + dj * dj));
                                continue;
                            }

                            if (pressure[ni, nj] <= threshold)
                            {
                                isNearEdge = true;
                                edgeDistance = Mathf.Min(edgeDistance, Mathf.Sqrt(di * di + dj * dj));
                            }
                        }
                    }

                    if (isNearEdge)
                    {
                        mask[i, j] = Mathf.Exp(-edgeDistance / radius);
                    }
                    else
                    {
                        mask[i, j] = 0f;
                    }
                }
            });

            return mask;
        }

        private float[,] GaussianSmooth(float[,] data, int radius)
        {
            int n = data.GetLength(0);
            int m = data.GetLength(1);
            float[,] result = new float[n, m];

            int size = 2 * radius + 1;
            float[,] kernel = new float[size, size];
            float sigma = radius / 3f;
            float sum = 0f;

            for (int di = -radius; di <= radius; di++)
            {
                for (int dj = -radius; dj <= radius; dj++)
                {
                    float value = Mathf.Exp(-(di * di + dj * dj) / (2f * sigma * sigma));
                    kernel[di + radius, dj + radius] = value;
                    sum += value;
                }
            }

            for (int di = 0; di < size; di++)
            {
                for (int dj = 0; dj < size; dj++)
                {
                    kernel[di, dj] /= sum;
                }
            }

            Parallel.For(0, n, i =>
            {
                for (int j = 0; j < m; j++)
                {
                    float value = 0f;

                    for (int di = -radius; di <= radius; di++)
                    {
                        for (int dj = -radius; dj <= radius; dj++)
                        {
                            int ni = Mathf.Clamp(i + di, 0, n - 1);
                            int nj = Mathf.Clamp(j + dj, 0, m - 1);
                            value += data[ni, nj] * kernel[di + radius, dj + radius];
                        }
                    }

                    result[i, j] = value;
                }
            });

            return result;
        }

        public float CalculateAdhesiveFriction(float velocity, RubberMaterial material, float pressure)
        {
            if (velocity <= 0) return 0f;

            float tau0 = 1e6f;
            float alpha = 1e-3f;
            float shearStrength = tau0 * (1f - Mathf.Exp(-alpha * velocity));
            float effectiveArea = Mathf.Min(1f, pressure / material.GetEffectiveModulus());

            return shearStrength * effectiveArea / Mathf.Max(pressure, 1e3f);
        }

        public float CalculateViscoelasticFriction(float velocity, RubberMaterial material,
            GroundSurface ground, float rmsHeight, float correlationLength)
        {
            if (velocity <= 0) return 0f;

            int spectrumSize = 512;
            float corrLength = correlationLength;
            float minLengthScale = material.minimumLengthScale;

            float q0 = 1f / corrLength;
            float q1 = 1f / minLengthScale;

            float integral = 0f;
            float dLogQ = Mathf.Log(q1 / q0) / spectrumSize;

            float groundCorrLength = ground.correlationLength * 1e-6f;
            float groundMinScale = ground.minimumLengthScale;
            float groundQ0 = 1f / groundCorrLength;
            float groundQ1 = 1f / groundMinScale;

            for (int i = 0; i < spectrumSize; i++)
            {
                float t = (float)i / spectrumSize;
                float q = Mathf.Exp(Mathf.Log(q0) + t * Mathf.Log(q1 / q0));
                float omega = velocity * q;

                float Cq = CalculatePowerSpectrum(q, rmsHeight, q0, material.hurstExponent, q0, q1);

                float Cq_ground = ground.GetPowerSpectrum(q);
                Cq = Mathf.Sqrt(Cq * Cq + Cq_ground * Cq_ground);

                float GDoublePrime = material.GetLossModulus(omega);
                float GStar = material.GetComplexModulus(omega);

                if (GStar > 0)
                {
                    float integrand = q * q * Cq * (GDoublePrime / GStar);
                    integral += integrand * dLogQ;
                }
            }

            return (2f / Mathf.PI) * integral;
        }

        private float CalculatePowerSpectrum(float q, float rmsHeight, float q0, float hurst, float q_low, float q_high)
        {
            if (q < q_low)
            {
                float c0 = rmsHeight * rmsHeight * Mathf.Pow(q0, 2f * (hurst + 1f)) / (2f * Mathf.PI * hurst);
                return c0 * Mathf.Exp(-(q_low - q) / q_low * 2f);
            }
            else if (q > q_high)
            {
                float c0 = rmsHeight * rmsHeight * Mathf.Pow(q0, 2f * (hurst + 1f)) / (2f * Mathf.PI * hurst);
                float cutoffValue = c0 * Mathf.Pow(q_high / q0, -2f * (hurst + 1f));
                float rolloff = Mathf.Exp(-(q - q_high) * (1f / q_high) * 5f);
                return cutoffValue * rolloff;
            }
            else
            {
                float c0 = rmsHeight * rmsHeight * Mathf.Pow(q0, 2f * (hurst + 1f)) / (2f * Mathf.PI * hurst);
                return c0 * Mathf.Pow(q / q0, -2f * (hurst + 1f));
            }
        }

        public float CalculateContactAreaRatio(float pressure, RubberMaterial material,
            float rmsHeight, float correlationLength)
        {
            if (pressure <= 0) return 0f;

            float effectiveModulus = material.GetEffectiveModulus();
            float hRms = rmsHeight;
            float rho = correlationLength;

            float argument = Mathf.Sqrt(Mathf.PI / 2f) * pressure / effectiveModulus * Mathf.Pow(hRms / rho, -0.5f);
            float erfValue = Erf(argument);

            return Mathf.Min(1f, Mathf.Max(0f, erfValue));
        }

        private float CalculateFilmParameter(float rmsRoughness, float filmThickness)
        {
            if (rmsRoughness <= 0) return float.MaxValue;
            return filmThickness / rmsRoughness;
        }

        private float CalculateDryContactRatio(float lambda)
        {
            if (lambda <= 0) return 1f;
            if (lambda >= 3f) return 0.05f;
            return Mathf.Exp(-lambda * 0.8f);
        }

        private float Erf(float x)
        {
            float sign = x >= 0 ? 1f : -1f;
            x = Mathf.Abs(x);

            float a1 = 0.254829592f;
            float a2 = -0.284496736f;
            float a3 = 1.421413741f;
            float a4 = -1.453152027f;
            float a5 = 1.061405429f;
            float p = 0.3275911f;

            float t = 1f / (1f + p * x);
            float y = 1f - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Mathf.Exp(-x * x);

            return sign * y;
        }

        public float CalculateStribeckNumber(float velocity, float viscosity, float load, float rmsRoughness)
        {
            if (load <= 0 || rmsRoughness <= 0) return 0f;
            return viscosity * velocity / (load * rmsRoughness);
        }

        public float[] GenerateVelocitySamples(float minVelocity, float maxVelocity, int count)
        {
            float[] velocities = new float[count];
            float logMin = Mathf.Log10(minVelocity);
            float logMax = Mathf.Log10(maxVelocity);

            for (int i = 0; i < count; i++)
            {
                float t = (float)i / (count - 1);
                float logV = logMin + t * (logMax - logMin);
                velocities[i] = Mathf.Pow(10f, logV);
            }

            return velocities;
        }

        public void UpdateContactResultWithFriction(ContactResult result, RubberMaterial material, GroundSurface ground)
        {
            UpdateContactResultWithFriction(result, material, ground, new SimulationParams());
        }

        public void UpdateContactResultWithFriction(ContactResult result, RubberMaterial material, GroundSurface ground, SimulationParams simParams)
        {
            if (result == null || result.contactPressure == null || simParams == null) return;

            var velocities = GenerateVelocitySamples(simParams.minVelocity, simParams.maxVelocity, simParams.velocitySamples);
            result.slipVelocities = velocities;

            if (simParams.enableThermalCoupling)
            {
                result.frictionCoefficients = CalculateTemperatureCoupledFrictionCurve(
                    result, material, ground, velocities, simParams);
            }
            else
            {
                result.frictionCoefficients = CalculateFrictionCurve(result, material, ground, velocities, simParams);
            }
        }

        public float[] CalculateTemperatureCoupledFrictionCurve(
            ContactResult contactData,
            RubberMaterial material,
            GroundSurface ground,
            float[] velocities,
            SimulationParams simParams)
        {
            if (contactData == null || velocities == null) return null;

            int n = velocities.Length;
            float[] frictionCoeffs = new float[n];
            float[,] temperatureField = contactData.temperatureField;
            float referenceTemp = material.referenceTemperature;

            if (temperatureField == null)
            {
                temperatureField = new float[contactData.Resolution, contactData.Resolution];
                for (int i = 0; i < contactData.Resolution; i++)
                    for (int j = 0; j < contactData.Resolution; j++)
                        temperatureField[i, j] = simParams.ambientTemperature;
            }

            float rmsRoughness = material.rmsRoughness * 1e-6f;
            float correlationLength = material.correlationLength * 1e-6f;

            Parallel.For(0, n, i =>
            {
                float velocity = velocities[i];

                float avgTemperature = CalculateAverageTemperature(temperatureField, contactData);

                float muAdhesion = CalculateAdhesiveFrictionAtTemperature(
                    velocity, material, contactData.averagePressure, avgTemperature);
                float muViscoelastic = CalculateViscoelasticFrictionAtTemperature(
                    velocity, material, ground, rmsRoughness, correlationLength, avgTemperature);
                float muHydro = _hydrodynamics.CalculateHydrodynamicFriction(velocity, contactData, ground, material);

                float dryContactRatio = contactData.contactAreaRatio;
                if (ground.waterFilmThickness > 0)
                {
                    float lambda = CalculateFilmParameter(rmsRoughness, ground.waterFilmThickness * 1e-6f);
                    dryContactRatio = CalculateDryContactRatio(lambda);
                }

                float muDry = muAdhesion + muViscoelastic;

                if (simParams.enableStickSlip)
                {
                    muDry = ApplyStickSlipModel(velocity, muDry, simParams);
                }

                float tempCorrection = CalculateTemperatureFrictionCorrection(avgTemperature, referenceTemp);

                frictionCoeffs[i] = (muDry * dryContactRatio + muHydro * (1f - dryContactRatio)) * tempCorrection;
                frictionCoeffs[i] = Mathf.Max(0.01f, Mathf.Min(frictionCoeffs[i], 3.0f));
            });

            return frictionCoeffs;
        }

        private float CalculateAdhesiveFrictionAtTemperature(
            float velocity, RubberMaterial material, float pressure, float temperature)
        {
            if (velocity <= 0) return 0f;

            float tau0 = 1e6f * Mathf.Exp(-0.008f * Mathf.Max(0f, temperature - 25f));
            float alpha = 1e-3f;
            float shearStrength = tau0 * (1f - Mathf.Exp(-alpha * velocity));
            float effectiveModulus = material.GetModulusAtTemperature(temperature);
            float effectiveArea = Mathf.Min(1f, pressure / effectiveModulus);

            return shearStrength * effectiveArea / Mathf.Max(pressure, 1e3f);
        }

        private float CalculateViscoelasticFrictionAtTemperature(
            float velocity, RubberMaterial material, GroundSurface ground,
            float rmsHeight, float correlationLength, float temperature)
        {
            if (velocity <= 0) return 0f;

            int spectrumSize = 512;
            float corrLength = correlationLength;
            float minLengthScale = material.minimumLengthScale;

            float q0 = 1f / corrLength;
            float q1 = 1f / minLengthScale;

            float integral = 0f;
            float dLogQ = Mathf.Log(q1 / q0) / spectrumSize;

            float groundCorrLength = ground.correlationLength * 1e-6f;
            float groundMinScale = ground.minimumLengthScale;
            float groundQ0 = 1f / groundCorrLength;
            float groundQ1 = 1f / groundMinScale;

            for (int i = 0; i < spectrumSize; i++)
            {
                float t = (float)i / spectrumSize;
                float q = Mathf.Exp(Mathf.Log(q0) + t * Mathf.Log(q1 / q0));
                float omega = velocity * q;

                float Cq = CalculatePowerSpectrum(q, rmsHeight, q0, material.hurstExponent, q0, q1);
                float Cq_ground = ground.GetPowerSpectrum(q);
                Cq = Mathf.Sqrt(Cq * Cq + Cq_ground * Cq_ground);

                float GDoublePrime = material.GetLossModulusAtTemperature(omega, temperature);
                float GStar = material.GetComplexModulusAtTemperature(omega, temperature);

                if (GStar > 0)
                {
                    float integrand = q * q * Cq * (GDoublePrime / GStar);
                    integral += integrand * dLogQ;
                }
            }

            return (2f / Mathf.PI) * integral;
        }

        private float CalculateAverageTemperature(float[,] temperatureField, ContactResult contactData)
        {
            if (temperatureField == null || contactData?.contactPressure == null) return 25f;

            int n = temperatureField.GetLength(0);
            int m = temperatureField.GetLength(1);

            float sumTemp = 0f;
            float sumWeight = 0f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < m; j++)
                {
                    float weight = contactData.contactPressure[i, j];
                    sumTemp += temperatureField[i, j] * weight;
                    sumWeight += weight;
                }
            }

            return sumWeight > 0 ? sumTemp / sumWeight : 25f;
        }

        private float CalculateTemperatureFrictionCorrection(float temperature, float referenceTemp)
        {
            float deltaT = temperature - referenceTemp;
            float correction = 1f - 0.008f * deltaT;

            if (temperature > 70f)
            {
                float tNorm = (temperature - 70f) / 30f;
                correction *= Mathf.Exp(-tNorm * tNorm);
            }

            if (temperature < 0f)
            {
                correction *= 1f + 0.01f * Mathf.Abs(deltaT);
            }

            return Mathf.Clamp(correction, 0.1f, 1.8f);
        }

        public float[,] CalculateTemperatureDependentFrictionMap(
            ContactResult contactData,
            RubberMaterial material,
            GroundSurface ground,
            float velocity,
            SimulationParams simParams)
        {
            if (contactData?.contactPressure == null || contactData?.temperatureField == null) return null;

            int n = contactData.contactPressure.GetLength(0);
            int m = contactData.contactPressure.GetLength(1);
            float[,] frictionMap = new float[n, m];

            Parallel.For(0, n, i =>
            {
                for (int j = 0; j < m; j++)
                {
                    float pressure = contactData.contactPressure[i, j];
                    float temperature = contactData.temperatureField[i, j];

                    if (pressure > 0)
                    {
                        float muAdhesion = CalculateAdhesiveFrictionAtTemperature(velocity, material, pressure, temperature);
                        float muVisco = CalculateViscoelasticFrictionAtTemperature(
                            velocity, material, ground,
                            material.rmsRoughness * 1e-6f,
                            material.correlationLength * 1e-6f, temperature);

                        float mu = muAdhesion + muVisco;
                        float correction = CalculateTemperatureFrictionCorrection(temperature, material.referenceTemperature);

                        frictionMap[i, j] = mu * correction;
                    }
                    else
                    {
                        frictionMap[i, j] = 0f;
                    }
                }
            });

            return frictionMap;
        }
    }
}
