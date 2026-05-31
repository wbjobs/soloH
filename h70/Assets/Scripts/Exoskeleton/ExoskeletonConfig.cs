using System;
using UnityEngine;
using GaitSimulation.Core;

namespace GaitSimulation.Exoskeleton
{
    [Serializable]
    public class ExoskeletonConfig
    {
        [Header("Knee Actuator")]
        public float kneeMaxTorque = 80f;
        public float kneeMaxAngularVelocity = 10f;
        public float kneeMotorEfficiency = 0.85f;
        public float kneeGeneratorEfficiency = 0.75f;
        public float kneeInertia = 0.02f;
        public float kneeDamping = 0.1f;

        [Header("Ankle Actuator")]
        public float ankleMaxTorque = 40f;
        public float ankleMaxAngularVelocity = 15f;
        public float ankleMotorEfficiency = 0.82f;
        public float ankleGeneratorEfficiency = 0.72f;
        public float ankleInertia = 0.01f;
        public float ankleDamping = 0.08f;

        [Header("Control Parameters")]
        public float assistRatio = 0.3f;
        public float regenerationRatio = 0.5f;
        public float modeSwitchThreshold = 5f;
        public float minModeDuration = 0.05f;

        [Header("Safety Limits")]
        public float maxJointSpeed = 20f;
        public float temperatureLimit = 80f;

        public float GetMaxTorque(JointType jointType)
        {
            return jointType == JointType.Knee ? kneeMaxTorque : ankleMaxTorque;
        }

        public float GetMotorEfficiency(JointType jointType)
        {
            return jointType == JointType.Knee ? kneeMotorEfficiency : ankleMotorEfficiency;
        }

        public float GetGeneratorEfficiency(JointType jointType)
        {
            return jointType == JointType.Knee ? kneeGeneratorEfficiency : ankleGeneratorEfficiency;
        }

        public float GetMaxAngularVelocity(JointType jointType)
        {
            return jointType == JointType.Knee ? kneeMaxAngularVelocity : ankleMaxAngularVelocity;
        }

        public float GetInertia(JointType jointType)
        {
            return jointType == JointType.Knee ? kneeInertia : ankleInertia;
        }

        public float GetDamping(JointType jointType)
        {
            return jointType == JointType.Knee ? kneeDamping : ankleDamping;
        }
    }
}
