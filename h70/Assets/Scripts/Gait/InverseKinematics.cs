using UnityEngine;
using GaitSimulation.Core;
using System;
using System.Collections.Generic;

namespace GaitSimulation.Gait
{
    public class InverseKinematics
    {
        private readonly SimulationConfig _config;

        private struct SegmentParams
        {
            public float massRatio;
            public float comRatio;
            public float radiusOfGyration;
        }

        private readonly SegmentParams _thighParams = new SegmentParams
        {
            massRatio = 0.100f,
            comRatio = 0.433f,
            radiusOfGyration = 0.323f
        };

        private readonly SegmentParams _shankParams = new SegmentParams
        {
            massRatio = 0.0465f,
            comRatio = 0.433f,
            radiusOfGyration = 0.302f
        };

        private readonly SegmentParams _footParams = new SegmentParams
        {
            massRatio = 0.0145f,
            comRatio = 0.429f,
            radiusOfGyration = 0.245f
        };

        public InverseKinematics(SimulationConfig config)
        {
            _config = config;
        }

        public Vector3 CalculateFootPosition(Side side, float time)
        {
            float gaitPhase = GetNormalizedGaitPhase(time, side);
            float stepLength = CalculateStepLength();
            float stepHeight = CalculateStepHeight();
            float slopeRad = _config.slopeAngle * Mathf.Deg2Rad;

            float x = (gaitPhase - 0.5f) * stepLength;
            float y = CalculateFootHeight(gaitPhase, stepHeight);
            float z = (side == Side.Left) ? 0.1f : -0.1f;

            Vector3 footPos = new Vector3(x, y, z);

            if (Mathf.Abs(slopeRad) > 0.001f)
            {
                float heightAdjustment = x * Mathf.Tan(slopeRad);
                footPos.y += heightAdjustment;
            }

            return footPos;
        }

        public (float hipAngle, float kneeAngle, float ankleAngle) SolveLegIK(Side side, Vector3 footPosition, Vector3 hipPosition)
        {
            float L1 = _config.ThighLength;
            float L2 = _config.ShankLength;
            float footLen = _config.FootLength;

            Vector3 hipToFoot = footPosition - hipPosition;
            hipToFoot.z = 0f;

            float d = hipToFoot.magnitude;
            d = Mathf.Clamp(d, 0.01f, L1 + L2 - 0.01f);

            float alpha = Mathf.Acos((L1 * L1 + d * d - L2 * L2) / (2f * L1 * d));
            float beta = Mathf.Acos((L1 * L1 + L2 * L2 - d * d) / (2f * L1 * L2));

            float gamma = Mathf.Atan2(hipToFoot.y, hipToFoot.x);

            float hipAngle = gamma + alpha;
            float kneeAngle = Mathf.PI - beta;

            float footAngle = Mathf.Atan2(footPosition.y - hipPosition.y - L1 * Mathf.Sin(hipAngle) - L2 * Mathf.Sin(hipAngle - kneeAngle),
                                          footPosition.x - hipPosition.x - L1 * Mathf.Cos(hipAngle) - L2 * Mathf.Cos(hipAngle - kneeAngle));
            float ankleAngle = -hipAngle + kneeAngle - footAngle;

            kneeAngle = Mathf.Clamp(kneeAngle, 0f, Mathf.PI * 0.9f);
            ankleAngle = Mathf.Clamp(ankleAngle, -0.8f, 0.8f);

            return (hipAngle, kneeAngle, ankleAngle);
        }

        public Dictionary<JointType, float> CalculateJointTorques(Side side, float time, JointState hip, JointState knee, JointState ankle)
        {
            var torques = new Dictionary<JointType, float>();

            float m = _config.bodyMass;
            float g = _config.gravity;
            float L1 = _config.ThighLength;
            float L2 = _config.ShankLength;
            float L3 = _config.FootLength;

            float m_thigh = m * _thighParams.massRatio;
            float m_shank = m * _shankParams.massRatio;
            float m_foot = m * _footParams.massRatio;

            float d_thigh = L1 * _thighParams.comRatio;
            float d_shank = L2 * _shankParams.comRatio;
            float d_foot = L3 * _footParams.comRatio;

            float I_thigh = m_thigh * Mathf.Pow(_thighParams.radiusOfGyration * L1, 2);
            float I_shank = m_shank * Mathf.Pow(_shankParams.radiusOfGyration * L2, 2);
            float I_foot = m_foot * Mathf.Pow(_footParams.radiusOfGyration * L3, 2);

            float contactRatio = GetFootContactRatio(time, side);
            float groundForce = contactRatio * m * g;
            if (_config.slopeAngle != 0)
            {
                groundForce *= Mathf.Cos(_config.slopeAngle * Mathf.Deg2Rad);
            }

            float slopeRad = _config.slopeAngle * Mathf.Deg2Rad;
            float gravityCompensation = m * g * Mathf.Sin(slopeRad) * 0.2f;

            float ankleTorque = CalculateAnkleTorque(ankle, m_foot, I_foot, L3, d_foot, groundForce, g, gravityCompensation);
            float kneeTorque = CalculateKneeTorque(knee, ankle, m_shank, I_shank, L2, d_shank, L3, g, gravityCompensation);
            float hipTorque = CalculateHipTorque(hip, knee, m_thigh, I_thigh, L1, d_thigh, L2, g, gravityCompensation);

            torques[JointType.Hip] = hipTorque;
            torques[JointType.Knee] = kneeTorque;
            torques[JointType.Ankle] = ankleTorque;

            return torques;
        }

        private float CalculateAnkleTorque(JointState ankle, float m_foot, float I_foot, float L3, float d_foot, float groundForce, float g, float slopeComp)
        {
            float inertiaTorque = I_foot * ankle.angularAcceleration;

            float gravityTorque = m_foot * g * d_foot * Mathf.Cos(ankle.angle);

            float groundTorque = 0f;
            if (groundForce > 0.01f)
            {
                float leverArm = L3 - d_foot;
                groundTorque = groundForce * leverArm * Mathf.Sign(ankle.angularVelocity);
            }

            float dampingTorque = 0.5f * ankle.angularVelocity;

            float contactFactor = 0.8f * (groundForce / (_config.bodyMass * _config.gravity));

            return inertiaTorque + gravityTorque + groundTorque + dampingTorque + slopeComp * 0.3f * contactFactor;
        }

        private float CalculateKneeTorque(JointState knee, JointState ankle, float m_shank, float I_shank, float L2, float d_shank, float L3, float g, float slopeComp)
        {
            float inertiaTorque = I_shank * knee.angularAcceleration;

            float gravityTorque = m_shank * g * d_shank * Mathf.Cos(knee.angle);

            float footInertiaEffect = 0.15f * ankle.angularAcceleration * I_shank * 0.5f;
            float couplingTorque = 0.4f * ankle.torque;
            float dampingTorque = 0.8f * knee.angularVelocity;

            float comToAnkle = d_shank * Mathf.Cos(knee.angle - ankle.angle);
            float dynamicEffect = m_shank * _shankParams.comRatio * 0.2f * L2 * ankle.angularVelocity * ankle.angularVelocity * Mathf.Sin(knee.angle - ankle.angle);

            return inertiaTorque + gravityTorque + couplingTorque + dampingTorque + footInertiaEffect + dynamicEffect + slopeComp * 0.4f;
        }

        private float CalculateHipTorque(JointState hip, JointState knee, float m_thigh, float I_thigh, float L1, float d_thigh, float L2, float g, float slopeComp)
        {
            float inertiaTorque = I_thigh * hip.angularAcceleration;

            float gravityTorque = m_thigh * g * d_thigh * Mathf.Cos(hip.angle);

            float shankInertiaEffect = 0.1f * knee.angularAcceleration * I_thigh * 0.3f;
            float couplingTorque = 0.3f * knee.torque;
            float dampingTorque = 0.6f * hip.angularVelocity;

            float coriolisEffect = m_thigh * _thighParams.comRatio * 0.15f * L1 * knee.angularVelocity * knee.angularVelocity * Mathf.Sin(hip.angle - knee.angle);

            return inertiaTorque + gravityTorque + couplingTorque + dampingTorque + shankInertiaEffect + coriolisEffect + slopeComp * 0.3f;
        }

        private float CalculateStepLength()
        {
            return _config.GetAdaptedStepLength();
        }

        private float CalculateStepHeight()
        {
            float baseHeight = 0.05f;
            float slopeFactor = _config.GetSlopeAdaptationFactor();
            float absSlopeFactor = Mathf.Abs(slopeFactor);
            float slopeEffect = 1f + absSlopeFactor * 0.4f;

            float adaptedCycle = _config.GetAdaptedGaitCycleDuration();
            float cadenceEffect = 1f + Mathf.Max(0f, (1.2f / adaptedCycle) - 1f) * 0.3f;

            if (slopeFactor > 0)
            {
                slopeEffect *= 1.2f;
            }

            return baseHeight * slopeEffect * cadenceEffect;
        }

        private float CalculateFootHeight(float gaitPhase, float stepHeight)
        {
            float supportRatio = _config.GetSupportPhaseRatio();

            if (gaitPhase < supportRatio)
            {
                return 0f;
            }
            else if (gaitPhase < supportRatio + (1f - supportRatio) * 0.5f)
            {
                float t = (gaitPhase - supportRatio) / ((1f - supportRatio) * 0.5f);
                return stepHeight * Mathf.Sin(t * Mathf.PI);
            }
            else
            {
                float t = (gaitPhase - supportRatio - (1f - supportRatio) * 0.5f) / ((1f - supportRatio) * 0.5f);
                return stepHeight * Mathf.Sin((1f - t) * Mathf.PI);
            }
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

        private float GetFootContactRatio(float time, Side side)
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
