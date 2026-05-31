using System;

namespace LanderSim.Core
{
    [Serializable]
    public struct LandingSite
    {
        public Vector3d position;
        public Vector3d normal;
        public double slope;
        public double roughness;
        public double shadowFactor;
        public double totalRisk;
        public bool isSelected;

        public double elevation => position.y;

        public LandingSite(Vector3d pos, Vector3d normal,
                          double slope, double roughness,
                          double shadowFactor, double totalRisk)
        {
            position = pos;
            this.normal = normal;
            this.slope = slope;
            this.roughness = roughness;
            this.shadowFactor = shadowFactor;
            this.totalRisk = totalRisk;
            isSelected = false;
        }

        public override string ToString()
        {
            return $"Site: Pos={position} Slope={slope:F1}° Rough={roughness:F3} " +
                   $"Shadow={shadowFactor:F2} Risk={totalRisk:F3}";
        }
    }
}
