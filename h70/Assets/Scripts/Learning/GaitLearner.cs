using System;
using System.Collections.Generic;
using UnityEngine;
using GaitSimulation.Core;

namespace GaitSimulation.Learning
{
    [Serializable]
    public class GaitCycleData
    {
        public float cycleStartTime;
        public float cycleDuration;
        public float[] hipAngleProfile;
        public float[] kneeAngleProfile;
        public float[] ankleAngleProfile;
        public float[] kneePowerProfile;
        public float[] anklePowerProfile;
        public float[] kneeTorqueProfile;
        public float[] ankleTorqueProfile;
        public float averageWalkingSpeed;
        public float stepLength;
        public float cadence;
    }

    [Serializable]
    public class PersonalizedGaitModel
    {
        public int trainingCycles;
        public float learningConfidence;

        public float avgHipFlexion;
        public float avgHipExtension;
        public float avgKneeFlexion;
        public float avgKneeExtension;
        public float avgAnkleDorsiflexion;
        public float avgAnklePlantarflexion;

        public float preferredCadence;
        public float preferredStepLength;
        public float avgWalkingSpeed;

        public float[] kneePowerPattern;
        public float[] anklePowerPattern;

        public float optimalRegenerationPointKnee;
        public float optimalRegenerationPointAnkle;
        public float regenerationEfficiencyKnee;
        public float regenerationEfficiencyAnkle;

        public float energyConsumptionPerKm;
        public float userStrengthLevel;

        public PersonalizedGaitModel(int profileLength = 60)
        {
            kneePowerPattern = new float[profileLength];
            anklePowerPattern = new float[profileLength];
        }
    }

    public class GaitLearner
    {
        private readonly SimulationConfig _config;
        private readonly int _profileLength = 60;

        private readonly Queue<GaitCycleData> _trainingData = new Queue<GaitCycleData>();
        private readonly int _maxTrainingCycles = 50;
        private readonly int _minTrainingCycles = 5;

        private GaitCycleData _currentCycle;
        private int _currentSampleIndex;
        private float _lastCycleEndTime;
        private float _cycleStartTime;

        private bool _isLearning = true;
        private bool _modelConverged = false;
        private float _convergenceThreshold = 0.05f;

        public PersonalizedGaitModel PersonalizedModel { get; private set; }
        public PersonalizedGaitModel BaselineModel { get; private set; }

        public event Action<PersonalizedGaitModel> OnModelUpdated;
        public event Action OnModelConverged;
        public event Action<float> OnLearningProgress;

        private float[] _currentHipAngles;
        private float[] _currentKneeAngles;
        private float[] _currentAnkleAngles;
        private float[] _currentKneePowers;
        private float[] _currentAnklePowers;
        private float[] _currentKneeTorques;
        private float[] _currentAnkleTorques;

        private int _lastHipMaxIndex = -1;
        private int _cycleCount = 0;
        private float _hipFlexionThreshold = 10f;

        public float learningRate = 0.3f;
        public float forgettingFactor = 0.98f;
        public bool enableAdaptiveRecovery = true;

        public GaitLearner(SimulationConfig config)
        {
            _config = config;
            PersonalizedModel = new PersonalizedGaitModel(_profileLength);
            BaselineModel = new PersonalizedGaitModel(_profileLength);
            InitializeCycleBuffers();
        }

        private void InitializeCycleBuffers()
        {
            _currentHipAngles = new float[_profileLength];
            _currentKneeAngles = new float[_profileLength];
            _currentAnkleAngles = new float[_profileLength];
            _currentKneePowers = new float[_profileLength];
            _currentAnklePowers = new float[_profileLength];
            _currentKneeTorques = new float[_profileLength];
            _currentAnkleTorques = new float[_profileLength];
        }

        public void Update(float time,
            Dictionary<(Side, JointType), JointState> jointStates,
            float gaitPhaseLeft, float gaitPhaseRight)
        {
            if (!_isLearning) return;

            SampleJointData(jointStates);

            DetectGaitCycle(time, gaitPhaseLeft);

            if (_cycleCount % 10 == 0 && _cycleCount > 0)
            {
                UpdatePersonalizedModel();
            }

            if (_trainingData.Count >= _minTrainingCycles)
            {
                float progress = (float)_trainingData.Count / _maxTrainingCycles;
                OnLearningProgress?.Invoke(progress);
            }
        }

        private void SampleJointData(Dictionary<(Side, JointType), JointState> jointStates)
        {
            _currentHipAngles[_currentSampleIndex] =
                (jointStates[(Side.Left, JointType.Hip)].angle +
                 jointStates[(Side.Right, JointType.Hip)].angle) * 0.5f * Mathf.Rad2Deg;

            _currentKneeAngles[_currentSampleIndex] =
                (jointStates[(Side.Left, JointType.Knee)].angle +
                 jointStates[(Side.Right, JointType.Knee)].angle) * 0.5f * Mathf.Rad2Deg;

            _currentAnkleAngles[_currentSampleIndex] =
                (jointStates[(Side.Left, JointType.Ankle)].angle +
                 jointStates[(Side.Right, JointType.Ankle)].angle) * 0.5f * Mathf.Rad2Deg;

            _currentKneePowers[_currentSampleIndex] =
                (jointStates[(Side.Left, JointType.Knee)].mechanicalPower +
                 jointStates[(Side.Right, JointType.Knee)].mechanicalPower) * 0.5f;

            _currentAnklePowers[_currentSampleIndex] =
                (jointStates[(Side.Left, JointType.Ankle)].mechanicalPower +
                 jointStates[(Side.Right, JointType.Ankle)].mechanicalPower) * 0.5f;

            _currentKneeTorques[_currentSampleIndex] =
                (jointStates[(Side.Left, JointType.Knee)].torque +
                 jointStates[(Side.Right, JointType.Knee)].torque) * 0.5f;

            _currentAnkleTorques[_currentSampleIndex] =
                (jointStates[(Side.Left, JointType.Ankle)].torque +
                 jointStates[(Side.Right, JointType.Ankle)].torque) * 0.5f;

            _currentSampleIndex = (_currentSampleIndex + 1) % _profileLength;
        }

        private void DetectGaitCycle(float time, float gaitPhase)
        {
            int currentHipIndex = _currentSampleIndex;

            if (gaitPhase < 0.01f && _cycleStartTime == 0)
            {
                StartNewCycle(time);
            }
            else if (gaitPhase < 0.01f && time - _cycleStartTime > 0.5f)
            {
                CompleteCycle(time);
                StartNewCycle(time);
            }
        }

        private void StartNewCycle(float time)
        {
            _cycleStartTime = time;
            _currentCycle = new GaitCycleData
            {
                cycleStartTime = time,
                hipAngleProfile = new float[_profileLength],
                kneeAngleProfile = new float[_profileLength],
                ankleAngleProfile = new float[_profileLength],
                kneePowerProfile = new float[_profileLength],
                anklePowerProfile = new float[_profileLength],
                kneeTorqueProfile = new float[_profileLength],
                ankleTorqueProfile = new float[_profileLength]
            };
            _cycleCount++;
        }

        private void CompleteCycle(float time)
        {
            if (_currentCycle == null) return;

            _currentCycle.cycleDuration = time - _cycleStartTime;

            int startIndex = (_currentSampleIndex - _profileLength + _profileLength) % _profileLength;

            for (int i = 0; i < _profileLength; i++)
            {
                int idx = (startIndex + i) % _profileLength;
                _currentCycle.hipAngleProfile[i] = _currentHipAngles[idx];
                _currentCycle.kneeAngleProfile[i] = _currentKneeAngles[idx];
                _currentCycle.ankleAngleProfile[i] = _currentAnkleAngles[idx];
                _currentCycle.kneePowerProfile[i] = _currentKneePowers[idx];
                _currentCycle.anklePowerProfile[i] = _currentAnklePowers[idx];
                _currentCycle.kneeTorqueProfile[i] = _currentKneeTorques[idx];
                _currentCycle.ankleTorqueProfile[i] = _currentAnkleTorques[idx];
            }

            _currentCycle.cadence = 60.0f / _currentCycle.cycleDuration;
            _currentCycle.stepLength = _config.GetAdaptedStepLength();
            _currentCycle.averageWalkingSpeed = _currentCycle.stepLength * _currentCycle.cadence / 60.0f;

            AddTrainingCycle(_currentCycle);
        }

        public void AddTrainingCycle(GaitCycleData cycle)
        {
            _trainingData.Enqueue(cycle);

            if (_trainingData.Count > _maxTrainingCycles)
            {
                _trainingData.Dequeue();
            }

            if (_trainingData.Count >= _minTrainingCycles)
            {
                UpdatePersonalizedModel();
                CheckConvergence();
            }
        }

        private void UpdatePersonalizedModel()
        {
            if (_trainingData.Count == 0) return;

            float avgHipFlex = 0f, avgHipExt = 0f;
            float avgKneeFlex = 0f, avgKneeExt = 0f;
            float avgAnkleDors = 0f, avgAnklePlant = 0f;
            float avgCadence = 0f, avgStepLen = 0f, avgSpeed = 0f;

            float[] avgKneePower = new float[_profileLength];
            float[] avgAnklePower = new float[_profileLength];

            int cycleCount = _trainingData.Count;
            float[] weights = CalculateForgettingWeights(cycleCount);

            int wIdx = 0;
            foreach (var cycle in _trainingData)
            {
                float w = weights[wIdx];

                float hMax = FindMax(cycle.hipAngleProfile);
                float hMin = FindMin(cycle.hipAngleProfile);
                float kMax = FindMax(cycle.kneeAngleProfile);
                float kMin = FindMin(cycle.kneeAngleProfile);
                float aMax = FindMax(cycle.ankleAngleProfile);
                float aMin = FindMin(cycle.ankleAngleProfile);

                avgHipFlex += hMax * w;
                avgHipExt += hMin * w;
                avgKneeFlex += kMax * w;
                avgKneeExt += kMin * w;
                avgAnkleDors += aMax * w;
                avgAnklePlant += aMin * w;
                avgCadence += cycle.cadence * w;
                avgStepLen += cycle.stepLength * w;
                avgSpeed += cycle.averageWalkingSpeed * w;

                for (int i = 0; i < _profileLength; i++)
                {
                    avgKneePower[i] += cycle.kneePowerProfile[i] * w;
                    avgAnklePower[i] += cycle.anklePowerProfile[i] * w;
                }

                wIdx++;
            }

            PersonalizedModel.avgHipFlexion = avgHipFlex;
            PersonalizedModel.avgHipExtension = avgHipExt;
            PersonalizedModel.avgKneeFlexion = avgKneeFlex;
            PersonalizedModel.avgKneeExtension = avgKneeExt;
            PersonalizedModel.avgAnkleDorsiflexion = avgAnkleDors;
            PersonalizedModel.avgAnklePlantarflexion = avgAnklePlant;

            PersonalizedModel.preferredCadence = avgCadence;
            PersonalizedModel.preferredStepLength = avgStepLen;
            PersonalizedModel.avgWalkingSpeed = avgSpeed;

            for (int i = 0; i < _profileLength; i++)
            {
                PersonalizedModel.kneePowerPattern[i] = avgKneePower[i];
                PersonalizedModel.anklePowerPattern[i] = avgAnklePower[i];
            }

            CalculateOptimalRecoveryPoints();

            PersonalizedModel.trainingCycles = _trainingData.Count;
            PersonalizedModel.learningConfidence = Mathf.Min(1.0f,
                (float)_trainingData.Count / _maxTrainingCycles);

            CalculateUserStrengthLevel();
            CalculateEnergyConsumption();

            OnModelUpdated?.Invoke(PersonalizedModel);
        }

        private float[] CalculateForgettingWeights(int count)
        {
            float[] weights = new float[count];
            float sum = 0f;

            for (int i = 0; i < count; i++)
            {
                weights[i] = Mathf.Pow(forgettingFactor, count - 1 - i);
                sum += weights[i];
            }

            for (int i = 0; i < count; i++)
            {
                weights[i] /= sum;
            }

            return weights;
        }

        private void CalculateOptimalRecoveryPoints()
        {
            float minKneePower = float.MaxValue;
            int kneeOptIdx = 0;
            float minAnklePower = float.MaxValue;
            int ankleOptIdx = 0;

            for (int i = 0; i < _profileLength; i++)
            {
                if (PersonalizedModel.kneePowerPattern[i] < minKneePower)
                {
                    minKneePower = PersonalizedModel.kneePowerPattern[i];
                    kneeOptIdx = i;
                }

                if (PersonalizedModel.anklePowerPattern[i] < minAnklePower)
                {
                    minAnklePower = PersonalizedModel.anklePowerPattern[i];
                    ankleOptIdx = i;
                }
            }

            PersonalizedModel.optimalRegenerationPointKnee = (float)kneeOptIdx / _profileLength;
            PersonalizedModel.optimalRegenerationPointAnkle = (float)ankleOptIdx / _profileLength;

            float totalKneeEnergy = 0f;
            float recoverableKneeEnergy = 0f;
            float totalAnkleEnergy = 0f;
            float recoverableAnkleEnergy = 0f;

            for (int i = 0; i < _profileLength; i++)
            {
                totalKneeEnergy += Mathf.Abs(PersonalizedModel.kneePowerPattern[i]);
                totalAnkleEnergy += Mathf.Abs(PersonalizedModel.anklePowerPattern[i]);

                if (PersonalizedModel.kneePowerPattern[i] < 0)
                {
                    recoverableKneeEnergy += Mathf.Abs(PersonalizedModel.kneePowerPattern[i]);
                }
                if (PersonalizedModel.anklePowerPattern[i] < 0)
                {
                    recoverableAnkleEnergy += Mathf.Abs(PersonalizedModel.anklePowerPattern[i]);
                }
            }

            PersonalizedModel.regenerationEfficiencyKnee = totalKneeEnergy > 0 ?
                recoverableKneeEnergy / totalKneeEnergy : 0f;
            PersonalizedModel.regenerationEfficiencyAnkle = totalAnkleEnergy > 0 ?
                recoverableAnkleEnergy / totalAnkleEnergy : 0f;
        }

        private void CalculateUserStrengthLevel()
        {
            float avgTorque = 0f;
            foreach (var cycle in _trainingData)
            {
                avgTorque += FindAbsAverage(cycle.kneeTorqueProfile) +
                             FindAbsAverage(cycle.ankleTorqueProfile);
            }
            avgTorque /= _trainingData.Count * 2f;

            float normalizedTorque = avgTorque / 60.0f;
            PersonalizedModel.userStrengthLevel = Mathf.Clamp01(normalizedTorque * 0.7f + 0.3f);
        }

        private void CalculateEnergyConsumption()
        {
            float totalPower = 0f;
            foreach (var cycle in _trainingData)
            {
                float cycleAvgPower = 0f;
                for (int i = 0; i < _profileLength; i++)
                {
                    cycleAvgPower += Mathf.Abs(cycle.kneePowerProfile[i]) +
                                     Mathf.Abs(cycle.anklePowerProfile[i]);
                }
                totalPower += cycleAvgPower / _profileLength;
            }

            float avgPower = totalPower / _trainingData.Count;
            float speed = PersonalizedModel.avgWalkingSpeed;

            PersonalizedModel.energyConsumptionPerKm = speed > 0.1f ?
                avgPower / (speed * 1000f / 3600f) : 0f;
        }

        private void CheckConvergence()
        {
            if (_modelConverged || _trainingData.Count < _minTrainingCycles) return;

            float parameterChange = 0f;
            parameterChange += Mathf.Abs(PersonalizedModel.avgKneeFlexion - BaselineModel.avgKneeFlexion) / 30f;
            parameterChange += Mathf.Abs(PersonalizedModel.avgAnklePlantarflexion - BaselineModel.avgAnklePlantarflexion) / 20f;
            parameterChange += Mathf.Abs(PersonalizedModel.preferredCadence - BaselineModel.preferredCadence) / 120f;
            parameterChange /= 3f;

            BaselineModel.avgKneeFlexion = PersonalizedModel.avgKneeFlexion;
            BaselineModel.avgAnklePlantarflexion = PersonalizedModel.avgAnklePlantarflexion;
            BaselineModel.preferredCadence = PersonalizedModel.preferredCadence;

            if (parameterChange < _convergenceThreshold && _trainingData.Count >= 20)
            {
                _modelConverged = true;
                OnModelConverged?.Invoke();
            }
        }

        public float GetAdjustedRegenerationRatio(float baseRatio, JointType jointType, float gaitPhase)
        {
            if (!enableAdaptiveRecovery || _trainingData.Count < _minTrainingCycles)
            {
                return baseRatio;
            }

            float optimalPhase = jointType == JointType.Knee ?
                PersonalizedModel.optimalRegenerationPointKnee :
                PersonalizedModel.optimalRegenerationPointAnkle;

            float phaseDiff = Mathf.Abs(gaitPhase - optimalPhase);
            if (phaseDiff > 0.5f) phaseDiff = 1f - phaseDiff;

            float phaseBoost = Mathf.Max(0f, 1f - phaseDiff / 0.25f);
            float efficiencyBoost = jointType == JointType.Knee ?
                PersonalizedModel.regenerationEfficiencyKnee :
                PersonalizedModel.regenerationEfficiencyAnkle;

            float adjustedRatio = baseRatio * (1f + phaseBoost * 0.3f) * (0.8f + efficiencyBoost * 0.4f);
            return Mathf.Clamp(adjustedRatio, baseRatio * 0.5f, baseRatio * 1.5f);
        }

        public float GetPersonalizedAssistRatio(float baseRatio, JointType jointType)
        {
            if (_trainingData.Count < _minTrainingCycles)
            {
                return baseRatio;
            }

            float strengthFactor = 1f - PersonalizedModel.userStrengthLevel * 0.3f;
            float adjustedRatio = baseRatio * strengthFactor;

            return Mathf.Clamp(adjustedRatio, baseRatio * 0.7f, baseRatio * 1.3f);
        }

        public GaitPhase GetPreferredRecoveryPhase(JointType jointType)
        {
            if (_trainingData.Count < _minTrainingCycles)
            {
                return jointType == JointType.Knee ? GaitPhase.MidStance : GaitPhase.HeelOff;
            }

            float optimalPhase = jointType == JointType.Knee ?
                PersonalizedModel.optimalRegenerationPointKnee :
                PersonalizedModel.optimalRegenerationPointAnkle;

            if (optimalPhase < 0.02) return GaitPhase.HeelStrike;
            if (optimalPhase < 0.12) return GaitPhase.FootFlat;
            if (optimalPhase < 0.30) return GaitPhase.MidStance;
            if (optimalPhase < 0.45) return GaitPhase.HeelOff;
            if (optimalPhase < 0.60) return GaitPhase.ToeOff;
            if (optimalPhase < 0.80) return GaitPhase.EarlySwing;
            return GaitPhase.LateSwing;
        }

        public string GetLearningStatus()
        {
            return $"Gait Learning Status:\n" +
                   $"  Is Learning: {_isLearning}\n" +
                   $"  Training Cycles: {_trainingData.Count}/{_maxTrainingCycles}\n" +
                   $"  Converged: {_modelConverged}\n" +
                   $"  Confidence: {PersonalizedModel.learningConfidence * 100:F1}%\n" +
                   $"\nPersonalized Parameters:\n" +
                   $"  Preferred Cadence: {PersonalizedModel.preferredCadence:F1} steps/min\n" +
                   $"  Preferred Step Length: {PersonalizedModel.preferredStepLength:F2} m\n" +
                   $"  Walking Speed: {PersonalizedModel.avgWalkingSpeed * 3.6f:F1} km/h\n" +
                   $"  Knee Flexion: {PersonalizedModel.avgKneeFlexion:F1}°\n" +
                   $"  Ankle Plantarflexion: {PersonalizedModel.avgAnklePlantarflexion:F1}°\n" +
                   $"\nRecovery Optimization:\n" +
                   $"  Knee Efficiency: {PersonalizedModel.regenerationEfficiencyKnee * 100:F1}%\n" +
                   $"  Ankle Efficiency: {PersonalizedModel.regenerationEfficiencyAnkle * 100:F1}%\n" +
                   $"  Optimal Knee Phase: {PersonalizedModel.optimalRegenerationPointKnee * 100:F0}%\n" +
                   $"  Optimal Ankle Phase: {PersonalizedModel.optimalRegenerationPointAnkle * 100:F0}%\n" +
                   $"\nUser Profile:\n" +
                   $"  Strength Level: {PersonalizedModel.userStrengthLevel * 100:F1}%\n" +
                   $"  Energy Consumption: {PersonalizedModel.energyConsumptionPerKm:F1} J/km";
        }

        private float FindMax(float[] data)
        {
            float max = float.MinValue;
            foreach (float v in data)
            {
                if (v > max) max = v;
            }
            return max;
        }

        private float FindMin(float[] data)
        {
            float min = float.MaxValue;
            foreach (float v in data)
            {
                if (v < min) min = v;
            }
            return min;
        }

        private float FindAbsAverage(float[] data)
        {
            float sum = 0f;
            foreach (float v in data)
            {
                sum += Mathf.Abs(v);
            }
            return sum / data.Length;
        }

        public void Reset()
        {
            _trainingData.Clear();
            _currentCycle = null;
            _currentSampleIndex = 0;
            _lastCycleEndTime = 0f;
            _cycleStartTime = 0f;
            _cycleCount = 0;
            _modelConverged = false;
            PersonalizedModel = new PersonalizedGaitModel(_profileLength);
            BaselineModel = new PersonalizedGaitModel(_profileLength);
            InitializeCycleBuffers();
        }

        public void PauseLearning()
        {
            _isLearning = false;
        }

        public void ResumeLearning()
        {
            _isLearning = true;
        }
    }
}
