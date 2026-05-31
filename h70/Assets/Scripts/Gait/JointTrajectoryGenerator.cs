using UnityEngine;
using GaitSimulation.Core;
using System;

namespace GaitSimulation.Gait
{
    public class JointTrajectoryGenerator
    {
        private readonly SimulationConfig _config;

        private readonly float[] _baseHipCoeffs = { 0.0f, 25.0f, 2.0f, 1.5f };
        private readonly float[] _baseKneeCoeffs = { 15.0f, 30.0f, 8.0f, 3.0f };
        private readonly float[] _baseAnkleCoeffs = { 10.0f, 15.0f, 5.0f, 2.0f };

        private float[] _currentHipCoeffs;
        private float[] _currentKneeCoeffs;
        private float[] _currentAnkleCoeffs;

        private float _lastSlopeAngle = float.NaN;

        public JointTrajectoryGenerator(SimulationConfig config)
        {
            _config = config;
            InitializeCoefficients();
            UpdateAdaptationForSlope();
        }

        private void InitializeCoefficients()
        {
            _currentHipCoeffs = new float[_baseHipCoeffs.Length];
            _currentKneeCoeffs = new float[_baseKneeCoeffs.Length];
            _currentAnkleCoeffs = new float[_baseAnkleCoeffs.Length];
        }

        public float GetJointAngle(JointType jointType, Side side, float time)
        {
            CheckAndUpdateSlopeAdaptation();

            float gaitPhase = GetNormalizedGaitPhase(time, side);
            float phaseRad = gaitPhase * 2f * Mathf.PI;

            float angle = 0f;

            switch (jointType)
            {
                case JointType.Hip:
                    angle = CalculateFourierSeries(phaseRad, _currentHipCoeffs);
                    angle = ApplySlopeCorrection(angle, gaitPhase, JointType.Hip);
                    break;
                case JointType.Knee:
                    angle = CalculateFourierSeries(phaseRad, _currentKneeCoeffs);
                    angle = Mathf.Max(0f, angle);
                    angle = ApplySlopeCorrection(angle, gaitPhase, JointType.Knee);
                    break;
                case JointType.Ankle:
                    angle = CalculateFourierSeries(phaseRad, _currentAnkleCoeffs);
                    angle = ApplySlopeCorrection(angle, gaitPhase, JointType.Ankle);
                    break;
            }

            return angle * Mathf.Deg2Rad;
        }

        private void CheckAndUpdateSlopeAdaptation()
        {
            if (Mathf.Abs(_config.slopeAngle - _lastSlopeAngle) > 0.01f)
            {
                UpdateAdaptationForSlope();
                _lastSlopeAngle = _config.slopeAngle;
            }
        }

        private void UpdateAdaptationForSlope()
        {
            float slopeFactor = _config.GetSlopeAdaptationFactor();
            float absSlopeFactor = Mathf.Abs(slopeFactor);

            for (int i = 0; i < _baseHipCoeffs.Length; i++)
            {
                float hipMod = 1f + slopeFactor * 0.3f;
                _currentHipCoeffs[i] = _baseHipCoeffs[i] * hipMod;
            }

            for (int i = 0; i < _baseKneeCoeffs.Length; i++)
            {
                float kneeMod = 1f + absSlopeFactor * 0.4f;
                _currentKneeCoeffs[i] = _baseKneeCoeffs[i] * kneeMod;
            }

            for (int i = 0; i < _baseAnkleCoeffs.Length; i++)
            {
                float ankleMod = 1f + slopeFactor * 0.25f;
                if (slopeFactor < 0)
                {
                    ankleMod = 1f + absSlopeFactor * 0.35f;
                }
                _currentAnkleCoeffs[i] = _baseAnkleCoeffs[i] * ankleMod;
            }

            if (_config.slopeAngle > 5f)
            {
                _currentHipCoeffs[1] += 8f;
                _currentKneeCoeffs[1] -= 5f;
                _currentAnkleCoeffs[1] += 6f;
            }
            else if (_config.slopeAngle < -5f)
            {
                _currentHipCoeffs[1] -= 5f;
                _currentKneeCoeffs[1] += 10f;
                _currentAnkleCoeffs[1] -= 8f;
            }
        }

        public float GetJointAngularVelocity(JointType jointType, Side side, float time, float dt = 0.001f)
        {
            float angle1 = GetJointAngle(jointType, side, time - dt);
            float angle2 = GetJointAngle(jointType, side, time + dt);
            return (angle2 - angle1) / (2f * dt);
        }

        public float GetJointAngularAcceleration(JointType jointType, Side side, float time, float dt = 0.001f)
        {
            float vel1 = GetJointAngularVelocity(jointType, side, time - dt, dt);
            float vel2 = GetJointAngularVelocity(jointType, side, time + dt, dt);
            return (vel2 - vel1) / (2f * dt);
        }

        private float CalculateFourierSeries(float phaseRad, float[] coeffs)
        {
            float result = coeffs[0];
            for (int i = 1; i < coeffs.Length; i++)
            {
                result += coeffs[i] * Mathf.Sin(i * phaseRad - i * 0.5f);
            }
            return result;
        }

        private float GetNormalizedGaitPhase(float time, Side side)
        {
            float adaptedCycle = _config.GetAdaptedGaitCycleDuration();
            float phase = (time % adaptedCycle) / adaptedCycle;
            if (side == Side.Right)
            {
                phase = (phase + 0.5f) % 1f;
            }
            return phase;
        }

        private float ApplySlopeCorrection(float angle, float gaitPhase, JointType jointType)
        {
            float slopeRad = _config.slopeAngle * Mathf.Deg2Rad;

            if (Mathf.Abs(slopeRad) < 0.001f) return angle;

            float slopeFactor = slopeRad * Mathf.Rad2Deg;
            float adaptationStrength = _config.slopeAdaptationStrength;
            float supportRatio = _config.GetSupportPhaseRatio();

            switch (jointType)
            {
                case JointType.Hip:
                    if (gaitPhase < supportRatio)
                    {
                        float peakPhase = supportRatio * 0.5f;
                        float phaseWidth = supportRatio;
                        float envelope = Mathf.Max(0f, 1f - Mathf.Abs(gaitPhase - peakPhase) / phaseWidth);

                        float uphillAdjust = slopeFactor > 0 ? 1.5f : 0.8f;
                        angle += slopeFactor * envelope * uphillAdjust * adaptationStrength;
                    }
                    else
                    {
                        float swingPhase = (gaitPhase - supportRatio) / (1f - supportRatio);
                        float envelope = Mathf.Sin(swingPhase * Mathf.PI);

                        float downhillAdjust = slopeFactor < 0 ? 1.3f : 0.9f;
                        angle += slopeFactor * 0.6f * envelope * downhillAdjust * adaptationStrength;
                    }
                    break;

                case JointType.Knee:
                    if (gaitPhase < supportRatio * 0.6f)
                    {
                        float peakPhase = supportRatio * 0.25f;
                        float envelope = Mathf.Exp(-Mathf.Pow((gaitPhase - peakPhase) / (supportRatio * 0.3f), 2));

                        float uphillAdjust = slopeFactor > 0 ? 0.7f : 1.4f;
                        angle += slopeFactor * 0.6f * envelope * uphillAdjust * adaptationStrength;
                    }

                    if (gaitPhase > supportRatio && gaitPhase < supportRatio + 0.2f)
                    {
                        float swingEarly = (gaitPhase - supportRatio) / 0.2f;
                        float envelope = Mathf.Sin(swingEarly * Mathf.PI);

                        float downhillKneeAdjust = slopeFactor < 0 ? 2.0f : 0.8f;
                        angle += Mathf.Abs(slopeFactor) * 0.8f * envelope * downhillKneeAdjust * adaptationStrength;
                    }
                    break;

                case JointType.Ankle:
                    if (gaitPhase > 0.1f && gaitPhase < supportRatio)
                    {
                        float peakPhase = supportRatio * 0.6f;
                        float envelope = Mathf.Exp(-Mathf.Pow((gaitPhase - peakPhase) / (supportRatio * 0.4f), 2));

                        float uphillAnkleAdjust = slopeFactor > 0 ? 1.8f : 1.2f;
                        angle += slopeFactor * envelope * uphillAnkleAdjust * adaptationStrength;
                    }

                    if (gaitPhase > supportRatio * 0.8f && gaitPhase < supportRatio + 0.15f)
                    {
                        float transitionPhase = (gaitPhase - supportRatio * 0.8f) / (supportRatio * 0.2f + 0.15f);
                        float envelope = Mathf.Sin(transitionPhase * Mathf.PI);

                        float downhillPushOff = slopeFactor < 0 ? 1.5f : 0.6f;
                        angle += -slopeFactor * 0.5f * envelope * downhillPushOff * adaptationStrength;
                    }
                    break;
            }

            return angle;
        }

        public GaitPhase GetGaitPhase(float time, Side side)
        {
            float phase = GetNormalizedGaitPhase(time, side);
            float supportRatio = _config.GetSupportPhaseRatio();

            float heelStrikeEnd = 0.02f * supportRatio / 0.6f;
            float footFlatEnd = 0.12f * supportRatio / 0.6f;
            float midStanceEnd = 0.30f * supportRatio / 0.6f;
            float heelOffEnd = 0.45f * supportRatio / 0.6f;
            float toeOffEnd = supportRatio;
            float earlySwingEnd = supportRatio + 0.80f * (1f - supportRatio) / 0.4f;

            if (phase < heelStrikeEnd) return GaitPhase.HeelStrike;
            if (phase < footFlatEnd) return GaitPhase.FootFlat;
            if (phase < midStanceEnd) return GaitPhase.MidStance;
            if (phase < heelOffEnd) return GaitPhase.HeelOff;
            if (phase < toeOffEnd) return GaitPhase.ToeOff;
            if (phase < earlySwingEnd) return GaitPhase.EarlySwing;
            return GaitPhase.LateSwing;
        }

        public float GetFootContactRatio(float time, Side side)
        {
            float phase = GetNormalizedGaitPhase(time, side);
            float supportRatio = _config.GetSupportPhaseRatio();
            float transitionTime = 0.05f;

            if (phase < supportRatio) return 1f;
            if (phase < supportRatio + transitionTime)
            {
                return 1f - (phase - supportRatio) / transitionTime;
            }
            if (phase < 1f - transitionTime) return 0f;
            return (phase - (1f - transitionTime)) / transitionTime;
        }
    }
}
