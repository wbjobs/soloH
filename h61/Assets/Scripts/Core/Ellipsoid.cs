using System;

namespace LanderSim.Core
{
    [Serializable]
    public struct Ellipsoid
    {
        public Vector3d center;
        public Vector3d radii;
        public Quaterniond orientation;

        public Ellipsoid(Vector3d center, Vector3d radii, Quaterniond orientation = default)
        {
            this.center = center;
            this.radii = radii;
            this.orientation = orientation.w == 0 ? Quaterniond.identity : orientation;
        }

        public bool Contains(Vector3d point)
        {
            Vector3d local = Quaterniond.Conjugate(orientation) * (point - center);
            double nx = local.x / radii.x;
            double ny = local.y / radii.y;
            double nz = local.z / radii.z;
            return nx * nx + ny * ny + nz * nz <= 1.0;
        }

        public double Distance(Vector3d point)
        {
            Vector3d local = Quaterniond.Conjugate(orientation) * (point - center);
            double nx = local.x / radii.x;
            double ny = local.y / radii.y;
            double nz = local.z / radii.z;
            double val = nx * nx + ny * ny + nz * nz;
            return Math.Sqrt(val) - 1.0;
        }

        public double SignedDistance(Vector3d point)
        {
            Vector3d local = Quaterniond.Conjugate(orientation) * (point - center);
            double nx = local.x / radii.x;
            double ny = local.y / radii.y;
            double nz = local.z / radii.z;
            double val = nx * nx + ny * ny + nz * nz;
            return Math.Sqrt(val) - 1.0;
        }

        public bool Intersects(Ellipsoid other, double safetyMargin = 0)
        {
            Vector3d delta = other.center - center;
            Quaterniond invOrient = Quaterniond.Conjugate(orientation);
            Vector3d localDelta = invOrient * delta;
            Quaterniond relativeRot = invOrient * other.orientation;

            double minDistSq = MinEllipsoidDistanceSquared(
                radii, other.radii, localDelta, relativeRot
            );

            double margin = safetyMargin * safetyMargin;
            return minDistSq <= margin;
        }

        private static double MinEllipsoidDistanceSquared(
            Vector3d r1, Vector3d r2, Vector3d delta, Quaterniond relRot)
        {
            int maxIterations = 50;
            double tolerance = 1e-8;

            Vector3d u = Vector3d.zero;

            for (int iter = 0; iter < maxIterations; iter++)
            {
                Vector3d v = new Vector3d(
                    r1.x * Math.Cos(u.y) * Math.Cos(u.z),
                    r1.y * Math.Sin(u.y),
                    r1.z * Math.Cos(u.y) * Math.Sin(u.z)
                );

                Vector3d wLocal = new Vector3d(
                    r2.x * Math.Cos(u.x) * Math.Cos(u.z),
                    r2.y * Math.Sin(u.x),
                    r2.z * Math.Cos(u.x) * Math.Sin(u.z)
                );
                Vector3d w = relRot * wLocal;

                Vector3d d = v + delta - w;
                double dist = d.sqrMagnitude;

                if (dist < tolerance) return 0;

                Vector3d gradU = new Vector3d(
                    2 * Vector3d.Dot(d, relRot * new Vector3d(
                        -r2.x * Math.Sin(u.x) * Math.Cos(u.z),
                        r2.y * Math.Cos(u.x),
                        -r2.z * Math.Sin(u.x) * Math.Sin(u.z)
                    )),
                    2 * Vector3d.Dot(d, new Vector3d(
                        -r1.x * Math.Sin(u.y) * Math.Cos(u.z),
                        r1.y * Math.Cos(u.y),
                        -r1.z * Math.Sin(u.y) * Math.Sin(u.z)
                    )),
                    2 * Vector3d.Dot(d, new Vector3d(
                        -r1.x * Math.Cos(u.y) * Math.Sin(u.z),
                        0,
                        r1.z * Math.Cos(u.y) * Math.Cos(u.z)
                    ) - relRot * new Vector3d(
                        -r2.x * Math.Cos(u.x) * Math.Sin(u.z),
                        0,
                        r2.z * Math.Cos(u.x) * Math.Cos(u.z)
                    ))
                );

                double gradMag = gradU.magnitude;
                if (gradMag < tolerance) break;

                double stepSize = 0.01;
                Vector3d newU = u - stepSize * gradU / gradMag;

                double newVx = r1.x * Math.Cos(newU.y) * Math.Cos(newU.z);
                double newVy = r1.y * Math.Sin(newU.y);
                double newVz = r1.z * Math.Cos(newU.y) * Math.Sin(newU.z);
                Vector3d newV = new Vector3d(newVx, newVy, newVz);

                double newWLocalX = r2.x * Math.Cos(newU.x) * Math.Cos(newU.z);
                double newWLocalY = r2.y * Math.Sin(newU.x);
                double newWLocalZ = r2.z * Math.Cos(newU.x) * Math.Sin(newU.z);
                Vector3d newW = relRot * new Vector3d(newWLocalX, newWLocalY, newWLocalZ);

                Vector3d newD = newV + delta - newW;
                double newDist = newD.sqrMagnitude;

                if (newDist >= dist)
                {
                    stepSize *= 0.5;
                    continue;
                }

                u = newU;
                if (Math.Abs(newDist - dist) < tolerance) break;
            }

            Vector3d finalV = new Vector3d(
                r1.x * Math.Cos(u.y) * Math.Cos(u.z),
                r1.y * Math.Sin(u.y),
                r1.z * Math.Cos(u.y) * Math.Sin(u.z)
            );
            Vector3d finalWLocal = new Vector3d(
                r2.x * Math.Cos(u.x) * Math.Cos(u.z),
                r2.y * Math.Sin(u.x),
                r2.z * Math.Cos(u.x) * Math.Sin(u.z)
            );
            Vector3d finalW = relRot * finalWLocal;
            Vector3d finalD = finalV + delta - finalW;

            return finalD.sqrMagnitude;
        }

        public override string ToString()
        {
            return $"Ellipsoid(Center={center}, Radii={radii})";
        }
    }

    public static class QuaterniondExtensions
    {
        public static Quaterniond Conjugate(this Quaterniond q)
        {
            return new Quaterniond(-q.x, -q.y, -q.z, q.w);
        }
    }
}
