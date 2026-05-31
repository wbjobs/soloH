using UnityEngine;
using GaitSimulation.Core;
using System.Collections.Generic;

namespace GaitSimulation.Gait
{
    public class GaitModel
    {
        private readonly SimulationConfig _config;
        private readonly JointTrajectoryGenerator _trajectoryGenerator;
        private readonly InverseKinematics _ik;

        public Dictionary<(Side, JointType), JointState> JointStates { get; private set; }

        public GaitModel(SimulationConfig config)
        {
            _config = config;
            _trajectoryGenerator = new JointTrajectoryGenerator(config);
            _ik = new InverseKinematics(config);

            InitializeJointStates();
        }

        private void InitializeJointStates()
        {
            JointStates = new Dictionary<(Side, JointType), JointState>();

            foreach (Side side in System.Enum.GetValues(typeof(Side)))
            {
                foreach (JointType joint in System.Enum.GetValues(typeof(JointType)))
                {
                    JointStates[(side, joint)] = new JointState(joint, side);
                }
            }
        }

        public void Update(float time, float deltaTime)
        {
            foreach (Side side in System.Enum.GetValues(typeof(Side)))
            {
                UpdateSide(side, time, deltaTime);
            }
        }

        private void UpdateSide(Side side, float time, float deltaTime)
        {
            var hip = JointStates[(side, JointType.Hip)];
            var knee = JointStates[(side, JointType.Knee)];
            var ankle = JointStates[(side, JointType.Ankle)];

            hip.angle = _trajectoryGenerator.GetJointAngle(JointType.Hip, side, time);
            knee.angle = _trajectoryGenerator.GetJointAngle(JointType.Knee, side, time);
            ankle.angle = _trajectoryGenerator.GetJointAngle(JointType.Ankle, side, time);

            hip.angularVelocity = _trajectoryGenerator.GetJointAngularVelocity(JointType.Hip, side, time);
            knee.angularVelocity = _trajectoryGenerator.GetJointAngularVelocity(JointType.Knee, side, time);
            ankle.angularVelocity = _trajectoryGenerator.GetJointAngularVelocity(JointType.Ankle, side, time);

            hip.angularAcceleration = _trajectoryGenerator.GetJointAngularAcceleration(JointType.Hip, side, time);
            knee.angularAcceleration = _trajectoryGenerator.GetJointAngularAcceleration(JointType.Knee, side, time);
            ankle.angularAcceleration = _trajectoryGenerator.GetJointAngularAcceleration(JointType.Ankle, side, time);

            var torques = _ik.CalculateJointTorques(side, time, hip, knee, ankle);

            hip.torque = torques[JointType.Hip];
            knee.torque = torques[JointType.Knee];
            ankle.torque = torques[JointType.Ankle];

            hip.CalculateMechanicalPower();
            knee.CalculateMechanicalPower();
            ankle.CalculateMechanicalPower();
        }

        public JointState GetJointState(Side side, JointType jointType)
        {
            return JointStates[(side, jointType)];
        }

        public GaitPhase GetCurrentGaitPhase(float time, Side side)
        {
            return _trajectoryGenerator.GetGaitPhase(time, side);
        }

        public float GetNormalizedPhase(float time, Side side)
        {
            float phase = (time % _config.gaitCycleDuration) / _config.gaitCycleDuration;
            if (side == Side.Right)
            {
                phase = (phase + 0.5f) % 1f;
            }
            return phase;
        }

        public Vector3 GetFootPosition(Side side, float time)
        {
            return _ik.CalculateFootPosition(side, time);
        }

        public void Reset()
        {
            foreach (var joint in JointStates.Values)
            {
                joint.Reset();
            }
        }
    }
}
