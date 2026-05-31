using UnityEngine;
using GaitSimulation.Core;

namespace GaitSimulation.Visualization
{
    public class EnergyFlowGraph : GraphBase
    {
        private float _motorPower;
        private float _generatorPower;
        private float _batteryPower;
        private float _batterySOC;

        protected override void InitializeDataSeries()
        {
            dataSeries = new List<float>[3];
            for (int i = 0; i < 3; i++)
            {
                dataSeries[i] = new List<float>();
            }

            seriesColors = new Color[]
            {
                new Color(0.3f, 0.8f, 0.3f),
                new Color(0.8f, 0.3f, 0.3f),
                new Color(0.3f, 0.5f, 1f)
            };

            seriesNames = new string[]
            {
                "Motor Power (W)",
                "Generator Power (W)",
                "Net Power (W)"
            };

            yMin = -200f;
            yMax = 200f;
            graphTitle = "System Energy Flow";
            yAxisLabel = "Power (W)";
        }

        public void AddData(TimePointData data)
        {
            _motorPower = data.totalMotorPower;
            _generatorPower = data.totalGeneratorPower;
            _batteryPower = data.netPower;
            _batterySOC = data.batterySOC;

            AddDataPoints(new float[]
            {
                data.totalMotorPower,
                data.totalGeneratorPower,
                data.netPower
            });
        }

        protected override void OnGUI()
        {
            base.OnGUI();

            DrawEnergyFlowDiagram();
        }

        private void DrawEnergyFlowDiagram()
        {
            float diagramX = _graphRect.x + _graphRect.width + 160f;
            float diagramY = _graphRect.y;
            float diagramWidth = 280f;
            float diagramHeight = _graphRect.height;

            GUIStyle titleStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 12,
                fontStyle = FontStyle.Bold,
                alignment = TextAnchor.UpperCenter,
                normal = { textColor = Color.white }
            };

            GUI.Label(new Rect(diagramX, diagramY - 20f, diagramWidth, 20f),
                "Energy Flow Diagram", titleStyle);

            GUIStyle boxStyle = new GUIStyle(GUI.skin.box)
            {
                fontSize = 11,
                alignment = TextAnchor.MiddleCenter,
                normal = { textColor = Color.white }
            };

            float humanBoxX = diagramX;
            float humanBoxY = diagramY + diagramHeight * 0.3f;
            float humanBoxW = 80f;
            float humanBoxH = 50f;

            float exoBoxX = diagramX + diagramWidth * 0.5f - 40f;
            float exoBoxY = diagramY + diagramHeight * 0.3f;
            float exoBoxW = 80f;
            float exoBoxH = 50f;

            float batteryBoxX = diagramX + diagramWidth - 80f;
            float batteryBoxY = diagramY + diagramHeight * 0.3f;
            float batteryBoxW = 80f;
            float batteryBoxH = 50f;

            GUI.color = new Color(0.8f, 0.6f, 0.4f);
            GUI.Box(new Rect(humanBoxX, humanBoxY, humanBoxW, humanBoxH),
                "Human\nBiomechanical\nEnergy", boxStyle);

            GUI.color = new Color(0.4f, 0.7f, 0.9f);
            GUI.Box(new Rect(exoBoxX, exoBoxY, exoBoxW, exoBoxH),
                "Exoskeleton\nActuators", boxStyle);

            float batteryLevel = _batterySOC;
            GUI.color = Color.gray;
            GUI.Box(new Rect(batteryBoxX, batteryBoxY, batteryBoxW, batteryBoxH), "", boxStyle);
            GUI.color = Color.green;
            GUI.DrawTexture(new Rect(batteryBoxX + 2f, batteryBoxY + batteryBoxH - 4f -
                (batteryBoxH - 8f) * batteryLevel, batteryBoxW - 4f, (batteryBoxH - 8f) * batteryLevel),
                Texture2D.whiteTexture);
            GUI.color = Color.white;
            GUI.Label(new Rect(batteryBoxX, batteryBoxY, batteryBoxW, batteryBoxH),
                $"Battery\nSOC: {_batterySOC * 100:F1}%", boxStyle);

            GUI.color = Color.white;

            DrawArrow(humanBoxX + humanBoxW, humanBoxY + humanBoxH * 0.3f,
                exoBoxX, exoBoxY + exoBoxH * 0.3f,
                new Color(0.9f, 0.6f, 0.3f), _generatorPower > 5f);

            DrawArrow(exoBoxX + exoBoxW, exoBoxY + exoBoxH * 0.3f,
                batteryBoxX, batteryBoxY + batteryBoxH * 0.3f,
                new Color(0.3f, 0.9f, 0.3f), _generatorPower > 5f);

            DrawArrow(batteryBoxX, batteryBoxY + batteryBoxH * 0.7f,
                exoBoxX + exoBoxW, exoBoxY + exoBoxH * 0.7f,
                new Color(0.9f, 0.3f, 0.3f), _motorPower > 5f);

            DrawArrow(exoBoxX, exoBoxY + exoBoxH * 0.7f,
                humanBoxX + humanBoxW, humanBoxY + humanBoxH * 0.7f,
                new Color(0.3f, 0.6f, 0.9f), _motorPower > 5f);

            GUIStyle labelStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 10,
                alignment = TextAnchor.MiddleCenter,
                normal = { textColor = Color.white }
            };

            GUI.Label(new Rect(humanBoxX + 50f, humanBoxY - 25f, 100f, 20f),
                $"{_generatorPower:F1} W", labelStyle);
            GUI.Label(new Rect(exoBoxX + 50f, exoBoxY - 25f, 100f, 20f),
                $"{_motorPower:F1} W", labelStyle);

            GUI.Label(new Rect(diagramX, diagramY + diagramHeight * 0.7f, diagramWidth, 20f),
                $"Generator: {_generatorPower:F1} W  |  Motor: {_motorPower:F1} W  |  Net: {_batteryPower:F1} W",
                new GUIStyle(labelStyle) { fontSize = 11, fontStyle = FontStyle.Bold });
        }

        private void DrawArrow(float x1, float y1, float x2, float y2, Color color, bool animated = false)
        {
            float t = animated ? (Mathf.Sin(Time.time * 5f) + 1f) * 0.5f : 1f;
            Color arrowColor = color * t;

            Vector2 start = new Vector2(x1, y1);
            Vector2 end = new Vector2(x2, y2);
            Vector2 dir = (end - start).normalized;
            Vector2 perp = new Vector2(-dir.y, dir.x);

            Vector2[] points = new Vector2[7];
            points[0] = start;
            points[1] = start + perp * 2f;
            points[2] = end - dir * 10f + perp * 2f;
            points[3] = end - dir * 10f + perp * 6f;
            points[4] = end;
            points[5] = end - dir * 10f - perp * 6f;
            points[6] = end - dir * 10f - perp * 2f;

            Vector2 prev = points[0];
            for (int i = 1; i < points.Length; i++)
            {
                DrawLineOnGUI((int)prev.x, (int)prev.y, (int)points[i].x, (int)points[i].y, arrowColor);
                prev = points[i];
            }
            DrawLineOnGUI((int)points[6].x, (int)points[6].y, (int)points[1].x, (int)points[1].y, arrowColor);
        }

        private void DrawLineOnGUI(int x1, int y1, int x2, int y2, Color color)
        {
            int dx = Mathf.Abs(x2 - x1);
            int dy = Mathf.Abs(y2 - y1);
            int sx = x1 < x2 ? 1 : -1;
            int sy = y1 < y2 ? 1 : -1;
            int err = dx - dy;

            Texture2D pixel = new Texture2D(1, 1);
            pixel.SetPixel(0, 0, color);
            pixel.Apply();

            while (true)
            {
                GUI.DrawTexture(new Rect(x1, y1, 2, 2), pixel);

                if (x1 == x2 && y1 == y2) break;

                int e2 = 2 * err;
                if (e2 > -dy) { err -= dy; x1 += sx; }
                if (e2 < dx) { err += dx; y1 += sy; }
            }
        }
    }
}
