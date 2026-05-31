using System;

namespace LanderSim.Core
{
    [Serializable]
    public class LanderState
    {
        public Vector3d position;
        public Vector3d velocity;
        public Quaterniond attitude;
        public Vector3d angularVelocity;
        public double mass;
        public double fuelMass;
        public double dryMass;

        public double throttle;
        public Vector3d thrustDirection;

        public bool isLanded;
        public bool isCrashed;

        public LanderState()
        {
            position = new Vector3d(0, 100, 0);
            velocity = Vector3d.zero;
            attitude = Quaterniond.identity;
            angularVelocity = Vector3d.zero;
            dryMass = 500.0;
            fuelMass = 300.0;
            mass = dryMass + fuelMass;
            throttle = 0;
            thrustDirection = Vector3d.up;
            isLanded = false;
            isCrashed = false;
        }

        public LanderState Clone()
        {
            return (LanderState)MemberwiseClone();
        }

        public override string ToString()
        {
            return $"Pos: {position}, Vel: {velocity}, Fuel: {fuelMass:F1}kg, Landed: {isLanded}, Crashed: {isCrashed}";
        }
    }
}
