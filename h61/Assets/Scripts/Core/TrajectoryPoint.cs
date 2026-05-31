using System;

namespace LanderSim.Core
{
    [Serializable]
    public struct TrajectoryPoint
    {
        public Vector3d position;
        public Vector3d velocity;
        public Quaterniond attitude;
        public double mass;
        public double fuel;
        public double time;
        public double throttle;
        public double risk;

        public TrajectoryPoint(Vector3d pos, Vector3d vel, Quaterniond att,
                              double mass, double fuel, double time,
                              double throttle = 0, double risk = 0)
        {
            position = pos;
            velocity = vel;
            attitude = att;
            mass = mass;
            fuel = fuel;
            time = time;
            throttle = throttle;
            risk = risk;
        }

        public override string ToString()
        {
            return $"T={time:F2}s Pos={position} Vel={velocity} Fuel={fuel:F1}kg";
        }
    }
}
