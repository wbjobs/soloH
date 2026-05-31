using UnityEngine;

namespace SoleFrictionSim.Data
{
    [CreateAssetMenu(fileName = "GroundSurface_", menuName = "SoleFriction/Ground Surface")]
    public class GroundSurface : ScriptableObject
    {
        [Header("Ground Type")]
        public GroundType groundType = GroundType.DryAsphalt;

        [Header("Surface Properties")]
        [Range(0.1f, 1000f)] public float roughness = 500f;
        [Range(1f, 100f)] public float hardness = 20f;
        [Range(10f, 2000f)] public float correlationLength = 500f;

        [Header("Fluid Properties")]
        [Range(0f, 200f)] public float waterFilmThickness = 0f;
        [Range(0.0001f, 0.01f)] public float fluidViscosity = 0.001f;

        [Header("Roughness Spectrum")]
        [Range(0.1f, 0.9f)] public float hurstExponent = 0.8f;
        [Range(1e-10f, 1e-8f)] public float minimumLengthScale = 1e-9f;
        public float[] powerSpectrum;

        public void InitializeSpectrum(int size = 256)
        {
            powerSpectrum = new float[size];
            float rmsHeight = roughness * 1e-6f;
            float corrLength = correlationLength * 1e-6f;

            float q0 = 1f / corrLength;
            float q1 = 1f / minimumLengthScale;

            float c0 = rmsHeight * rmsHeight * Mathf.Pow(q0, 2f * (hurstExponent + 1f)) / (2f * Mathf.PI * hurstExponent);

            for (int i = 0; i < size; i++)
            {
                float t = (float)i / (size - 1);
                float q = Mathf.Exp(Mathf.Log(q0) + t * Mathf.Log(q1 / q0));
                powerSpectrum[i] = c0 * Mathf.Pow(q / q0, -2f * (hurstExponent + 1f));
            }
        }

        public float GetRmsHeight()
        {
            if (powerSpectrum == null || powerSpectrum.Length < 2) return roughness * 1e-6f;

            float integral = 0f;
            float corrLength = correlationLength * 1e-6f;
            float q0 = 1f / corrLength;
            float q1 = 1f / minimumLengthScale;

            for (int i = 0; i < powerSpectrum.Length - 1; i++)
            {
                float t1 = (float)i / (powerSpectrum.Length - 1);
                float t2 = (float)(i + 1) / (powerSpectrum.Length - 1);
                float q_i = Mathf.Exp(Mathf.Log(q0) + t1 * Mathf.Log(q1 / q0));
                float q_next = Mathf.Exp(Mathf.Log(q0) + t2 * Mathf.Log(q1 / q0));
                float dq = q_next - q_i;
                integral += 0.5f * (powerSpectrum[i] + powerSpectrum[i + 1]) * q_i * dq;
            }

            return Mathf.Sqrt(2f * Mathf.PI * integral);
        }

        public float GetPowerSpectrum(float q)
        {
            float rmsHeight = roughness * 1e-6f;
            float corrLength = correlationLength * 1e-6f;
            float q0 = 1f / corrLength;
            float q_cutoff = 1f / minimumLengthScale;

            if (q < q0)
            {
                float c0 = rmsHeight * rmsHeight * Mathf.Pow(q0, 2f * (hurstExponent + 1f)) / (2f * Mathf.PI * hurstExponent);
                return c0;
            }
            else if (q > q_cutoff)
            {
                float c0 = rmsHeight * rmsHeight * Mathf.Pow(q0, 2f * (hurstExponent + 1f)) / (2f * Mathf.PI * hurstExponent);
                float rolloffFactor = Mathf.Exp(-(q - q_cutoff) * minimumLengthScale * 0.5f);
                return c0 * Mathf.Pow(q_cutoff / q0, -2f * (hurstExponent + 1f)) * rolloffFactor;
            }
            else
            {
                float c0 = rmsHeight * rmsHeight * Mathf.Pow(q0, 2f * (hurstExponent + 1f)) / (2f * Mathf.PI * hurstExponent);
                return c0 * Mathf.Pow(q / q0, -2f * (hurstExponent + 1f));
            }
        }
    }
}
