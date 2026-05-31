using System;

namespace GaitSimulation.Core
{
    [Serializable]
    public class SimulationConfig
    {
        public float gaitCycleDuration = 1.2f;
        public float bodyMass = 70f;
        public float slopeAngle = 0f;
        public float gravity = 9.81f;
        public float simulationFrequency = 100f;

        public float ThighLength = 0.45f;
        public float ShankLength = 0.45f;
        public float FootLength = 0.25f;

        [Header("Slope Adaptation Parameters")]
        public float slopeAdaptationStrength = 1.0f;
        public float maxSlopeForAdaptation = 15f;
        public float uphillCadenceIncrease = 0.15f;
        public float downhillCadenceDecrease = 0.1f;
        public float uphillStepLengthReduction = 0.2f;
        public float downhillStepLengthIncrease = 0.15f;
        public float uphillSupportPhaseIncrease = 0.05f;
        public float downhillSupportPhaseDecrease = 0.03f;

        public float GetStepFrequency()
        {
            return 1f / gaitCycleDuration;
        }

        public float GetBodyWeight()
        {
            return bodyMass * gravity;
        }

        public float GetAdaptedGaitCycleDuration()
        {
            float slopeFactor = Mathf.Clamp(slopeAngle, -maxSlopeForAdaptation, maxSlopeForAdaptation) / maxSlopeForAdaptation;
            float cadenceAdjustment = 0f;

            if (slopeFactor > 0)
            {
                cadenceAdjustment = slopeFactor * uphillCadenceIncrease;
            }
            else
            {
                cadenceAdjustment = slopeFactor * downhillCadenceDecrease;
            }

            return gaitCycleDuration / (1f + cadenceAdjustment * slopeAdaptationStrength);
        }

        public float GetAdaptedStepLength()
        {
            float slopeFactor = Mathf.Clamp(slopeAngle, -maxSlopeForAdaptation, maxSlopeForAdaptation) / maxSlopeForAdaptation;
            float baseStepLength = 0.7f;
            float lengthAdjustment = 0f;

            if (slopeFactor > 0)
            {
                lengthAdjustment = -slopeFactor * uphillStepLengthReduction;
            }
            else
            {
                lengthAdjustment = -slopeFactor * downhillStepLengthIncrease;
            }

            return baseStepLength * (1f + lengthAdjustment * slopeAdaptationStrength);
        }

        public float GetSupportPhaseRatio()
        {
            float slopeFactor = Mathf.Clamp(slopeAngle, -maxSlopeForAdaptation, maxSlopeForAdaptation) / maxSlopeForAdaptation;
            float baseRatio = 0.6f;
            float ratioAdjustment = 0f;

            if (slopeFactor > 0)
            {
                ratioAdjustment = slopeFactor * uphillSupportPhaseIncrease;
            }
            else
            {
                ratioAdjustment = slopeFactor * downhillSupportPhaseDecrease;
            }

            return Mathf.Clamp01(baseRatio + ratioAdjustment * slopeAdaptationStrength);
        }

        public float GetSlopeAdaptationFactor()
        {
            return slopeAdaptationStrength * Mathf.Clamp(slopeAngle, -maxSlopeForAdaptation, maxSlopeForAdaptation) / maxSlopeForAdaptation;
        }
    }
}
