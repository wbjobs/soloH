using UnityEngine;

namespace SoleFrictionSim.Data
{
    [CreateAssetMenu(fileName = "RubberMaterial_", menuName = "SoleFriction/Rubber Material")]
    public class RubberMaterial : ScriptableObject
    {
        [Header("Mechanical Properties")]
        [Range(30f, 80f)] public float shoreHardness = 55f;
        [Range(0.5f, 10f)] public float elasticModulus = 2.5f;
        [Range(0.1f, 1f)] public float lossFactor = 0.25f;
        [Range(0.45f, 0.499f)] public float poissonRatio = 0.495f;

        [Header("Viscoelastic Properties")]
        public float[] relaxationTimes = new float[] { 1e-6f, 1e-5f, 1e-4f, 1e-3f, 1e-2f };
        public float[] relaxationModuli = new float[] { 5f, 3f, 2f, 1.5f, 1.2f };

        [Header("Surface Properties")]
        [Range(0.1f, 0.9f)] public float hurstExponent = 0.7f;
        [Range(1f, 500f)] public float rmsRoughness = 50f;
        [Range(10f, 1000f)] public float correlationLength = 200f;
        [Range(1e-10f, 1e-8f)] public float minimumLengthScale = 1e-9f;

        [Header("Thermal Properties")]
        [Range(-40f, 120f)] public float referenceTemperature = 25f;
        [Range(0.001f, 0.02f)] public float modulusTemperatureCoeff = 0.005f;
        [Range(0.1f, 2f)] public float thermalConductivity = 0.3f;
        [Range(1000f, 2000f)] public float specificHeat = 1500f;
        [Range(900f, 1200f)] public float density = 1100f;
        [Range(50f, 100f)] public float glassTransitionTemperature = 70f;

        [Header("Wear Properties")]
        [Range(1e-8f, 1e-5f)] public float wearCoefficient = 1e-6f;
        [Range(0.1f, 5f)] public float wearHardnessFactor = 1.0f;

        public float GetComplexModulus(float frequency)
        {
            float gPrime = 0f;
            float gDoublePrime = 0f;

            for (int i = 0; i < relaxationTimes.Length; i++)
            {
                float omegaTau = frequency * relaxationTimes[i];
                float denom = 1f + omegaTau * omegaTau;
                gPrime += relaxationModuli[i] * omegaTau * omegaTau / denom;
                gDoublePrime += relaxationModuli[i] * omegaTau / denom;
            }

            return new System.Numerics.Complex(gPrime, gDoublePrime).Magnitude;
        }

        public float GetLossModulus(float frequency)
        {
            float gDoublePrime = 0f;

            for (int i = 0; i < relaxationTimes.Length; i++)
            {
                float omegaTau = frequency * relaxationTimes[i];
                float denom = 1f + omegaTau * omegaTau;
                gDoublePrime += relaxationModuli[i] * omegaTau / denom;
            }

            return gDoublePrime;
        }

        public float GetEffectiveModulus()
        {
            return elasticModulus * 1e6f / (1f - poissonRatio * poissonRatio);
        }

        public float GetModulusAtTemperature(float temperature)
        {
            float deltaT = temperature - referenceTemperature;
            float modulusRatio = 1f - modulusTemperatureCoeff * deltaT;

            if (temperature > glassTransitionTemperature)
            {
                float tNorm = (temperature - glassTransitionTemperature) / 30f;
                modulusRatio *= Mathf.Exp(-tNorm * tNorm);
            }

            return GetEffectiveModulus() * Mathf.Clamp(modulusRatio, 0.05f, 1.5f);
        }

        public float GetComplexModulusAtTemperature(float frequency, float temperature)
        {
            float tempFactor = GetModulusAtTemperature(temperature) / GetEffectiveModulus();

            float shiftFactor = CalculateWLFShiftFactor(temperature);
            float shiftedFrequency = frequency * shiftFactor;

            return GetComplexModulus(shiftedFrequency) * tempFactor;
        }

        public float GetLossModulusAtTemperature(float frequency, float temperature)
        {
            float tempFactor = GetModulusAtTemperature(temperature) / GetEffectiveModulus();
            float shiftFactor = CalculateWLFShiftFactor(temperature);
            float shiftedFrequency = frequency * shiftFactor;

            return GetLossModulus(shiftedFrequency) * tempFactor;
        }

        private float CalculateWLFShiftFactor(float temperature)
        {
            float Tg = glassTransitionTemperature;
            if (temperature <= Tg) return 1f;

            float C1 = 17.44f;
            float C2 = 51.6f;
            float logShift = -C1 * (temperature - Tg) / (C2 + (temperature - Tg));

            return Mathf.Pow(10f, logShift);
        }

        public float ShoreToHardness(float shoreA)
        {
            return 0.0981f * Mathf.Exp(0.0235f * shoreA) * 1e9f;
        }
    }
}
