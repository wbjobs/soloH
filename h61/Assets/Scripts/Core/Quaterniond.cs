using System;

namespace LanderSim.Core
{
    [Serializable]
    public struct Quaterniond : IEquatable<Quaterniond>
    {
        public double x;
        public double y;
        public double z;
        public double w;

        public Quaterniond(double x, double y, double z, double w)
        {
            this.x = x;
            this.y = y;
            this.z = z;
            this.w = w;
        }

        public static Quaterniond identity => new Quaterniond(0, 0, 0, 1);

        public Vector3d eulerAngles
        {
            get
            {
                double sqw = w * w;
                double sqx = x * x;
                double sqy = y * y;
                double sqz = z * z;

                double roll = Math.Atan2(2.0 * (y * z + x * w), -sqx - sqy + sqz + sqw);
                double pitch = Math.Asin(-2.0 * (x * z - y * w));
                double yaw = Math.Atan2(2.0 * (x * y + z * w), sqx - sqy - sqz + sqw);

                return new Vector3d(
                    roll * 180.0 / Math.PI,
                    pitch * 180.0 / Math.PI,
                    yaw * 180.0 / Math.PI
                );
            }
        }

        public Quaterniond normalized
        {
            get
            {
                double mag = Math.Sqrt(x * x + y * y + z * z + w * w);
                if (mag < 1e-10) return identity;
                return new Quaterniond(x / mag, y / mag, z / mag, w / mag);
            }
        }

        public static Quaterniond FromEuler(double roll, double pitch, double yaw)
        {
            double r = roll * Math.PI / 360.0;
            double p = pitch * Math.PI / 360.0;
            double y = yaw * Math.PI / 360.0;

            double cr = Math.Cos(r);
            double sr = Math.Sin(r);
            double cp = Math.Cos(p);
            double sp = Math.Sin(p);
            double cy = Math.Cos(y);
            double sy = Math.Sin(y);

            return new Quaterniond(
                sr * cp * cy - cr * sp * sy,
                cr * sp * cy + sr * cp * sy,
                cr * cp * sy - sr * sp * cy,
                cr * cp * cy + sr * sp * sy
            ).normalized;
        }

        public static Quaterniond Slerp(Quaterniond a, Quaterniond b, double t)
        {
            double cosOmega = Dot(a, b);

            if (cosOmega < 0)
            {
                b = new Quaterniond(-b.x, -b.y, -b.z, -b.w);
                cosOmega = -cosOmega;
            }

            if (cosOmega > 0.9999)
            {
                return Lerp(a, b, t).normalized;
            }

            double omega = Math.Acos(cosOmega);
            double sinOmega = Math.Sin(omega);

            double s1 = Math.Sin((1 - t) * omega) / sinOmega;
            double s2 = Math.Sin(t * omega) / sinOmega;

            return new Quaterniond(
                s1 * a.x + s2 * b.x,
                s1 * a.y + s2 * b.y,
                s1 * a.z + s2 * b.z,
                s1 * a.w + s2 * b.w
            ).normalized;
        }

        public static Quaterniond Lerp(Quaterniond a, Quaterniond b, double t)
        {
            t = Math.Max(0, Math.Min(1, t));
            return new Quaterniond(
                a.x + (b.x - a.x) * t,
                a.y + (b.y - a.y) * t,
                a.z + (b.z - a.z) * t,
                a.w + (b.w - a.w) * t
            ).normalized;
        }

        public static double Dot(Quaterniond a, Quaterniond b)
        {
            return a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w;
        }

        public static Quaterniond operator *(Quaterniond a, Quaterniond b)
        {
            return new Quaterniond(
                a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
                a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
                a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
                a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z
            ).normalized;
        }

        public static Vector3d operator *(Quaterniond q, Vector3d v)
        {
            double xx = q.x * q.x;
            double yy = q.y * q.y;
            double zz = q.z * q.z;
            double xy = q.x * q.y;
            double xz = q.x * q.z;
            double yz = q.y * q.z;
            double wx = q.w * q.x;
            double wy = q.w * q.y;
            double wz = q.w * q.z;

            return new Vector3d(
                (1 - 2 * (yy + zz)) * v.x + 2 * (xy - wz) * v.y + 2 * (xz + wy) * v.z,
                2 * (xy + wz) * v.x + (1 - 2 * (xx + zz)) * v.y + 2 * (yz - wx) * v.z,
                2 * (xz - wy) * v.x + 2 * (yz + wx) * v.y + (1 - 2 * (xx + yy)) * v.z
            );
        }

        public static bool operator ==(Quaterniond a, Quaterniond b)
        {
            return Math.Abs(a.x - b.x) < 1e-10 &&
                   Math.Abs(a.y - b.y) < 1e-10 &&
                   Math.Abs(a.z - b.z) < 1e-10 &&
                   Math.Abs(a.w - b.w) < 1e-10;
        }

        public static bool operator !=(Quaterniond a, Quaterniond b) => !(a == b);

        public bool Equals(Quaterniond other) => this == other;

        public override bool Equals(object obj) => obj is Quaterniond other && Equals(other);

        public override int GetHashCode()
        {
            unchecked
            {
                int hash = x.GetHashCode();
                hash = (hash * 397) ^ y.GetHashCode();
                hash = (hash * 397) ^ z.GetHashCode();
                hash = (hash * 397) ^ w.GetHashCode();
                return hash;
            }
        }

        public override string ToString()
        {
            var e = eulerAngles;
            return $"({e.x:F1}°, {e.y:F1}°, {e.z:F1}°)";
        }
    }
}
