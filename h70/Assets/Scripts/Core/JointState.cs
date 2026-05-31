using System;
using UnityEngine;

namespace GaitSimulation.Core
{
    [Serializable]
    public class JointState
    {
        public JointType jointType;
        public Side side;
        public float angle;
        public float angularVelocity;
        public float angularAcceleration;
        public float torque;
        public float mechanicalPower;
        public ExoskeletonMode exoskeletonMode;
        public float exoskeletonPower;
        public float exoskeletonTorque;

        public JointState(JointType type, Side side)
        {
            jointType = type;
            this.side = side;
            exoskeletonMode = ExoskeletonMode.Idle;
        }

        public void Reset()
        {
            angle = 0f;
            angularVelocity = 0f;
            angularAcceleration = 0f;
            torque = 0f;
            mechanicalPower = 0f;
            exoskeletonPower = 0f;
            exoskeletonTorque = 0f;
        }

        public void CalculateMechanicalPower()
        {
            mechanicalPower = torque * angularVelocity;
        }
    }
}
