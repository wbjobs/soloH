using UnityEngine;
using GaitSimulation.Core;

namespace GaitSimulation.Visualization
{
    public class JointPowerGraph : GraphBase
    {
        protected override void InitializeDataSeries()
        {
            dataSeries = new List<float>[4];
            for (int i = 0; i < 4; i++)
            {
                dataSeries[i] = new List<float>();
            }

            seriesColors = new Color[]
            {
                new Color(1f, 0.3f, 0.3f),
                new Color(1f, 0.7f, 0.3f),
                new Color(0.3f, 0.7f, 1f),
                new Color(0.5f, 0.5f, 1f)
            };

            seriesNames = new string[]
            {
                "Knee Left (W)",
                "Knee Right (W)",
                "Ankle Left (W)",
                "Ankle Right (W)"
            };

            yMin = -150f;
            yMax = 150f;
            graphTitle = "Joint Exoskeleton Power";
            yAxisLabel = "Power (W)";
        }

        public void AddData(TimePointData data)
        {
            AddDataPoints(new float[]
            {
                data.kneePowerL,
                data.kneePowerR,
                data.anklePowerL,
                data.anklePowerR
            });
        }
    }
}
