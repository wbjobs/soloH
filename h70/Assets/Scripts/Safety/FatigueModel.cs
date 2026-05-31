using System;
using System.Collections.Generic;
using UnityEngine;
using GaitSimulation.Core;

namespace GaitSimulation.Safety
{
    [Serializable]
    public class MuscleGroup
    {
        public string name;
        public float fatigueLevel;
        public float maxForceReduction;
        public float recoveryRate;
        public float activationLevel;
    }

    [Serializable]
    public class FatigueModel
    {
        [Header("Physiological Parameters")]
        public float muscleGlycogen = 1.0f;
        public float lacticAcid = 0.0f;
        public float perceivedExertion = 0.0f;
        public float overallFatigueLevel = 0.0f;

        [Header("Muscle Groups")]
        public MuscleGroup quadriceps = new MuscleGroup { name = "Quadriceps" };
        public MuscleGroup hamstrings = new MuscleGroup { name = "Hamstrings" };
        public MuscleGroup gastrocnemius = new MuscleGroup { name = "Gastrocnemius" };
        public MuscleGroup tibialisAnterior = new MuscleGroup { name = "Tibialis Anterior" };

        [Header("Model Parameters")]
        public float glycogenConsumptionRate = 0.002f;
        public float glycogenRecoveryRate = 0.001f;
        public float lacticAcidProductionRate = 0.003f;
        public float lacticAcidClearanceRate = 0.002f;
        public float fatiguePerceptionRate = 0.001f;
        public float maxLacticAcidThreshold = 0.6f;

        [Header("Exoskeleton Adaptation")]
        public float assistAdaptationRate = 0.5f;
        public float maxAssistIncrease = 0.3f;
        public float currentAssistBoost = 0.0f;
        public float minFatigueThreshold = 0.3f;

        [Header("Recovery Parameters")]
        public float recoveryTimeConstant = 60.0f;
        public bool isRecovering = false;

        public event Action<float> OnFatigueLevelChanged;
        public event Action<float> OnAssistStrategyChanged;
        public event Action OnFatigueCritical;

        private float _simulationTime;
        private float _restTime;
        private readonly SimulationConfig _config;

        public FatigueModel(SimulationConfig config)
        {
            _config = config;
            InitializeParameters();
        }

        private void InitializeParameters()
        {
            quadriceps.fatigueLevel = 0.0f;
            quadriceps.maxForceReduction = 0.0f;
            quadriceps.recoveryRate = glycogenRecoveryRate;
            quadriceps.activationLevel = 0.0f;

            hamstrings.fatigueLevel = 0.0f;
            hamstrings.maxForceReduction = 0.0f;
            hamstrings.recoveryRate = glycogenRecoveryRate * 0.8f;
            hamstrings.activationLevel = 0.0f;

            gastrocnemius.fatigueLevel = 0.0f;
            gastrocnemius.maxForceReduction = 0.0f;
            gastrocnemius.recoveryRate = glycogenRecoveryRate * 0.7f;
            gastrocnemius.activationLevel = 0.0f;

            tibialisAnterior.fatigueLevel = 0.0f;
            tibialisAnterior.maxForceReduction = 0.0f;
            tibialisAnterior.recoveryRate = glycogenRecoveryRate * 1.2f;
            tibialisAnterior.activationLevel = 0.0f;
        }

        public void Update(float deltaTime,
            Dictionary<(Side side, JointType joint), JointState> jointStates,
            float walkingIntensity = 1.0f)
        {
            _simulationTime += deltaTime;

            UpdateMuscleActivation(jointStates, walkingIntensity);

            if (isRecovering)
            {
                UpdateRecovery(deltaTime);
            }
            else
            {
                UpdateFatigue(deltaTime, walkingIntensity);
            }

            UpdateOverallFatigue();

            UpdateAssistStrategy();

            if (overallFatigueLevel > 0.8f && OnFatigueCritical != null)
            {
                OnFatigueCritical?.Invoke();
            }

            OnFatigueLevelChanged?.Invoke(overallFatigueLevel);
        }

        private void UpdateMuscleActivation(
            Dictionary<(Side side, JointType joint), JointState> jointStates,
            float walkingIntensity)
        {
            foreach (Side side in Enum.GetValues(typeof(Side)))
            {
                var knee = jointStates[(side, JointType.Knee)];
                var ankle = jointStates[(side, JointType.Ankle)];

                float kneeExtensorActivation = Mathf.Abs(knee.torque) / 80.0f;
                float kneeFlexorActivation = Mathf.Abs(knee.angularVelocity) * 0.1f;
                float anklePlantarFlexorActivation = Mathf.Abs(ankle.torque) / 40.0f;
                float ankleDorsiflexorActivation = Mathf.Abs(ankle.angularVelocity) * 0.1f;

                quadriceps.activationLevel = Mathf.Lerp(quadriceps.activationLevel,
                    Mathf.Clamp01(kneeExtensorActivation), 0.1f);
                hamstrings.activationLevel = Mathf.Lerp(hamstrings.activationLevel,
                    Mathf.Clamp01(kneeFlexorActivation), 0.1f);
                gastrocnemius.activationLevel = Mathf.Lerp(gastrocnemius.activationLevel,
                    Mathf.Clamp01(anklePlantarFlexorActivation), 0.1f);
                tibialisAnterior.activationLevel = Mathf.Lerp(tibialisAnterior.activationLevel,
                    Mathf.Clamp01(ankleDorsiflexorActivation), 0.1f);
            }

            quadriceps.activationLevel *= walkingIntensity;
            hamstrings.activationLevel *= walkingIntensity;
            gastrocnemius.activationLevel *= walkingIntensity;
            tibialisAnterior.activationLevel *= walkingIntensity;
        }

        private void UpdateFatigue(float deltaTime, float walkingIntensity)
        {
            float massFactor = _config.bodyMass / 70.0f;
            float slopeFactor = 1.0f + Mathf.Abs(_config.slopeAngle) * 0.02f;
            float intensityFactor = walkingIntensity * massFactor * slopeFactor;

            float glycogenConsumption = (quadriceps.activationLevel * 0.35f +
                                       hamstrings.activationLevel * 0.25f +
                                       gastrocnemius.activationLevel * 0.25f +
                                       tibialisAnterior.activationLevel * 0.15f) *
                                       glycogenConsumptionRate * deltaTime * intensityFactor;

            muscleGlycogen = Mathf.Max(0.0f, muscleGlycogen - glycogenConsumption);

            float lacticProduction = (quadriceps.activationLevel * 0.4f +
                                hamstrings.activationLevel * 0.3f +
                                gastrocnemius.activationLevel * 0.2f +
                                tibialisAnterior.activationLevel * 0.1f) *
                                lacticAcidProductionRate * deltaTime * intensityFactor;

            lacticAcid = Mathf.Clamp01(lacticAcid + lacticProduction);

            if (lacticAcid > maxLacticAcidThreshold)
            {
                perceivedExertion = Mathf.Clamp01(perceivedExertion +
                    (lacticAcid - maxLacticAcidThreshold) * fatiguePerceptionRate * deltaTime);
            }

            UpdateMuscleFatigue(quadriceps, deltaTime, intensityFactor);
            UpdateMuscleFatigue(hamstrings, deltaTime, intensityFactor);
            UpdateMuscleFatigue(gastrocnemius, deltaTime, intensityFactor);
            UpdateMuscleFatigue(tibialisAnterior, deltaTime, intensityFactor);
        }

        private void UpdateMuscleFatigue(MuscleGroup muscle, float deltaTime, float intensityFactor)
        {
            float fatigueIncrease = muscle.activationLevel * intensityFactor * deltaTime * 0.01f;
            float recoveryDecrease = muscle.recoveryRate * deltaTime * (1.0f - muscle.activationLevel);
            muscle.fatigueLevel = Mathf.Clamp01(muscle.fatigueLevel + fatigueIncrease - recoveryDecrease);

            muscle.maxForceReduction = muscle.fatigueLevel * 0.5f;
        }

        private void UpdateRecovery(float deltaTime)
        {
            _restTime += deltaTime;

            float recoveryFactor = Mathf.Exp(-_restTime / recoveryTimeConstant);

            muscleGlycogen = Mathf.Lerp(muscleGlycogen, 1.0f,
                glycogenRecoveryRate * deltaTime * 2.0f);

            lacticAcid = Mathf.Lerp(lacticAcid, 0.0f,
                lacticAcidClearanceRate * deltaTime * 1.5f);

            perceivedExertion = Mathf.Lerp(perceivedExertion, 0.0f,
                fatiguePerceptionRate * deltaTime * 3.0f);

            RecoverMuscle(quadriceps, deltaTime, recoveryFactor);
            RecoverMuscle(hamstrings, deltaTime, recoveryFactor);
            RecoverMuscle(gastrocnemius, deltaTime, recoveryFactor);
            RecoverMuscle(tibialisAnterior, deltaTime, recoveryFactor);
        }

        private void RecoverMuscle(MuscleGroup muscle, float deltaTime, float recoveryFactor)
        {
            muscle.fatigueLevel = Mathf.Lerp(muscle.fatigueLevel, 0.0f,
                muscle.recoveryRate * deltaTime * 3.0f * (1.0f + recoveryFactor));
            muscle.maxForceReduction = muscle.fatigueLevel * 0.5f;
        }

        private void UpdateOverallFatigue()
        {
            float previousFatigue = overallFatigueLevel;

            overallFatigueLevel = 0.3f * (1.0f - muscleGlycogen) +
                                   0.4f * lacticAcid +
                                   0.3f * perceivedExertion;

            overallFatigueLevel = Mathf.Lerp(previousFatigue, overallFatigueLevel, 0.1f);
            overallFatigueLevel = Mathf.Clamp01(overallFatigueLevel);
        }

        private void UpdateAssistStrategy()
        {
            float previousBoost = currentAssistBoost;

            if (overallFatigueLevel < minFatigueThreshold)
            {
                currentAssistBoost = Mathf.Lerp(currentAssistBoost, 0.0f, assistAdaptationRate * 0.1f);
                isRecovering = false;
            }
            else if (overallFatigueLevel > 0.7f)
            {
                float targetBoost = Mathf.Min(maxAssistIncrease,
                    (overallFatigueLevel - 0.3f) * maxAssistIncrease / 0.4f);
                currentAssistBoost = Mathf.Lerp(currentAssistBoost, targetBoost,
                    assistAdaptationRate * 0.1f);
                isRecovering = false;
            }
            else if (overallFatigueLevel > 0.5f)
            {
                float targetBoost = (overallFatigueLevel - 0.3f) * maxAssistIncrease / 0.4f;
                currentAssistBoost = Mathf.Lerp(currentAssistBoost, targetBoost,
                    assistAdaptationRate * 0.1f);
                isRecovering = false;
            }

            if (Mathf.Abs(currentAssistBoost - previousBoost) > 0.01f &&
                OnAssistStrategyChanged != null)
            {
                OnAssistStrategyChanged?.Invoke(currentAssistBoost);
            }
        }

        public float GetAdjustedAssistRatio(float baseRatio, JointType jointType)
        {
            float muscleFatigue = 0.0f;

            switch (jointType)
            {
                case JointType.Knee:
                    muscleFatigue = Mathf.Max(quadriceps.fatigueLevel, hamstrings.fatigueLevel);
                    break;
                case JointType.Ankle:
                    muscleFatigue = Mathf.Max(gastrocnemius.fatigueLevel, tibialisAnterior.fatigueLevel);
                    break;
                case JointType.Hip:
                    muscleFatigue = overallFatigueLevel * 0.5f;
                    break;
            }

            float fatigueBoost = muscleFatigue * currentAssistBoost;
            float adjustedRatio = baseRatio * (1.0f + fatigueBoost);

            return Mathf.Clamp(adjustedRatio, baseRatio, 0.8f);
        }

        public float GetAdjustedRegenerationRatio(float baseRatio, JointType jointType)
        {
            if (overallFatigueLevel > 0.6f)
            {
                return baseRatio * 0.5f;
            }
            return baseRatio;
        }

        public void StartRecovery()
        {
            isRecovering = true;
            _restTime = 0.0f;
        }

        public void StopRecovery()
        {
            isRecovering = false;
            _restTime = 0.0f;
        }

        public FatigueLevel GetFatigueLevel()
        {
            if (overallFatigueLevel > 0.8f) return FatigueLevel.Critical;
            if (overallFatigueLevel > 0.6f) return FatigueLevel.High;
            if (overallFatigueLevel > 0.3f) return FatigueLevel.Moderate;
            if (overallFatigueLevel > 0.1f) return FatigueLevel.Low;
            return FatigueLevel.None;
        }

        public string GetStatusText()
        {
            return $"Fatigue Status:\n" +
                   $"  Level: {GetFatigueLevel()} ({overallFatigueLevel * 100:F1}%\n" +
                   $"  Glycogen: {muscleGlycogen * 100:F1}%\n" +
                   $"  Lactic Acid: {lacticAcid * 100:F1}%\n" +
                   $"  Perceived Exertion: {perceivedExertion * 100:F1}%\n" +
                   $"  Assist Boost: {currentAssistBoost * 100:F1}%\n" +
                   $"  Recovery Mode: {(isRecovering ? "Active" : "Inactive")}\n" +
                   $"\nMuscle Fatigue:\n" +
                   $"  Quadriceps: {quadriceps.fatigueLevel * 100:F1}%\n" +
                   $"  Hamstrings: {hamstrings.fatigueLevel * 100:F1}%\n" +
                   $"  Gastrocnemius: {gastrocnemius.fatigueLevel * 100:F1}%\n" +
                   $"  Tibialis Anterior: {tibialisAnterior.fatigueLevel * 100:F1}%";
        }

        public void Reset()
        {
            muscleGlycogen = 1.0f;
            lacticAcid = 0.0f;
            perceivedExertion = 0.0f;
            overallFatigueLevel = 0.0f;
            currentAssistBoost = 0.0f;
            _simulationTime = 0.0f;
            _restTime = 0.0f;
            isRecovering = false;
            InitializeParameters();
        }
    }

    public enum FatigueLevel
    {
        None,
        Low,
        Moderate,
        High,
        Critical
    }
}
