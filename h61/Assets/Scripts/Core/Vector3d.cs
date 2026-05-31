using System;

namespace LanderSim.Core
{
    [Serializable]
    public struct Vector3d : IEquatable<Vector3d>
    {
        public double x;
        public double y;
        public double z;

        public Vector3d(double x, double y, double z)
        {
            this.x = x;
            this.y = y;
            this.z = z;
        }

        public static Vector3d zero => new Vector3d(0, 0, 0);
        public static Vector3d one => new Vector3d(1, 1, 1);
        public static Vector3d up => new Vector3d(0, 1, 0);
        public static Vector3d forward => new Vector3d(0, 0, 1);
        public static Vector3d right => new Vector3d(1, 0, 0);

        public double magnitude => Math.Sqrt(x * x + y * y + z * z);
        public double sqrMagnitude => x * x + y * y + z * z;

        public Vector3d normalized
        {
            get
            {
                double mag = magnitude;
                if (mag < 1e-10) return zero;
                return new Vector3d(x / mag, y / mag, z / mag);
            }
        }

        public static double Distance(Vector3d a, Vector3d b)
        {
            double dx = a.x - b.x;
            double dy = a.y - b.y;
            double dz = a.z - b.z;
            return Math.Sqrt(dx * dx + dy * dy + dz * dz);
        }

        public static double Dot(Vector3d a, Vector3d b)
        {
            return a.x * b.x + a.y * b.y + a.z * b.z;
        }

        public static Vector3d Cross(Vector3d a, Vector3d b)
        {
            return new Vector3d(
                a.y * b.z - a.z * b.y,
                a.z * b.x - a.x * b.z,
                a.x * b.y - a.y * b.x
            );
        }

        public static Vector3d Lerp(Vector3d a, Vector3d b, double t)
        {
            t = Math.Max(0, Math.Min(1, t));
            return new Vector3d(
                a.x + (b.x - a.x) * t,
                a.y + (b.y - a.y) * t,
                a.z + (b.z - a.z) * t
            );
        }

        public static Vector3d operator +(Vector3d a, Vector3d b) =>
            new Vector3d(a.x + b.x, a.y + b.y, a.z + b.z);

        public static Vector3d operator -(Vector3d a, Vector3d b) =>
            new Vector3d(a.x - b.x, a.y - b.y, a.z - b.z);

        public static Vector3d operator -(Vector3d a) =>
            new Vector3d(-a.x, -a.y, -a.z);

        public static Vector3d operator *(Vector3d a, double d) =>
            new Vector3d(a.x * d, a.y * d, a.z * d);

        public static Vector3d operator *(double d, Vector3d a) =>
            new Vector3d(a.x * d, a.y * d, a.z * d);

        public static Vector3d operator /(Vector3d a, double d) =>
            new Vector3d(a.x / d, a.y / d, a.z / d);

        public static bool operator ==(Vector3d a, Vector3d b) =>
            Math.Abs(a.x - b.x) < 1e-10 &&
            Math.Abs(a.y - b.y) < 1e-10 &&
            Math.Abs(a.z - b.z) < 1e-10;

        public static bool operator !=(Vector3d a, Vector3d b) => !(a == b);

        public bool Equals(Vector3d other) => this == other;

        public override bool Equals(object obj) => obj is Vector3d other && Equals(other);

        public override int GetHashCode()
        {
            unchecked
            {
                int hash = x.GetHashCode();
                hash = (hash * 397) ^ y.GetHashCode();
                hash = (hash * 397) ^ z.GetHashCode();
                return hash;
            }
        }

        public override string ToString() => $"({x:F3}, {y:F3}, {z:F3})";

        public UnityEngine.Vector3 ToVector3() =>
            new UnityEngine.Vector3((float)x, (float)y, (float)z);

        public static Vector3d FromVector3(UnityEngine.Vector3 v) =>
            new Vector3d(v.x, v.y, v.z);
    }
}
