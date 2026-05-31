using UnityEngine;
using UnityEngine.UI;
using System.Collections.Generic;

namespace GaitSimulation.Visualization
{
    public class GraphBase : MonoBehaviour
    {
        [Header("Graph Settings")]
        public int maxDataPoints = 500;
        public float graphWidth = 400f;
        public float graphHeight = 200f;
        public Vector2 graphOffset = new Vector2(20f, 20f);

        [Header("Colors")]
        public Color backgroundColor = new Color(0.1f, 0.1f, 0.1f, 0.8f);
        public Color gridColor = new Color(0.3f, 0.3f, 0.3f, 0.5f);
        public Color axisColor = Color.white;

        protected List<float>[] dataSeries;
        protected Color[] seriesColors;
        protected string[] seriesNames;
        protected float yMin = -100f;
        protected float yMax = 100f;
        protected string yAxisLabel = "Value";
        protected string xAxisLabel = "Time (s)";
        protected string graphTitle = "Graph";

        private Texture2D _graphTexture;
        private Rect _graphRect;

        protected virtual void Awake()
        {
            _graphTexture = new Texture2D((int)graphWidth, (int)graphHeight);
            _graphTexture.filterMode = FilterMode.Point;
            _graphRect = new Rect(graphOffset.x, graphOffset.y, graphWidth, graphHeight);

            InitializeDataSeries();
            ClearGraph();
        }

        protected virtual void InitializeDataSeries()
        {
            dataSeries = new List<float>[1];
            dataSeries[0] = new List<float>();
            seriesColors = new Color[] { Color.cyan };
            seriesNames = new string[] { "Data" };
        }

        public virtual void AddDataPoint(float value, int seriesIndex = 0)
        {
            if (seriesIndex < 0 || seriesIndex >= dataSeries.Length) return;

            dataSeries[seriesIndex].Add(value);

            if (dataSeries[seriesIndex].Count > maxDataPoints)
            {
                dataSeries[seriesIndex].RemoveAt(0);
            }

            UpdateYRange();
            RedrawGraph();
        }

        public virtual void AddDataPoints(float[] values)
        {
            for (int i = 0; i < values.Length && i < dataSeries.Length; i++)
            {
                AddDataPoint(values[i], i);
            }
        }

        protected virtual void UpdateYRange()
        {
            float min = float.MaxValue;
            float max = float.MinValue;

            foreach (var series in dataSeries)
            {
                foreach (float val in series)
                {
                    min = Mathf.Min(min, val);
                    max = Mathf.Max(max, val);
                }
            }

            if (min == float.MaxValue || max == float.MinValue) return;

            float margin = (max - min) * 0.1f;
            yMin = min - margin;
            yMax = max + margin;

            if (Mathf.Abs(yMin - yMax) < 0.1f)
            {
                yMin -= 10f;
                yMax += 10f;
            }
        }

        protected virtual void ClearGraph()
        {
            for (int x = 0; x < graphWidth; x++)
            {
                for (int y = 0; y < graphHeight; y++)
                {
                    _graphTexture.SetPixel(x, y, backgroundColor);
                }
            }

            DrawGrid();
            DrawAxes();
            _graphTexture.Apply();

            foreach (var series in dataSeries)
            {
                series.Clear();
            }
        }

        protected virtual void DrawGrid()
        {
            int numGridLinesX = 5;
            int numGridLinesY = 5;

            for (int i = 0; i <= numGridLinesX; i++)
            {
                int x = (int)(i * graphWidth / numGridLinesX);
                for (int y = 0; y < graphHeight; y++)
                {
                    _graphTexture.SetPixel(x, y, gridColor);
                }
            }

            for (int i = 0; i <= numGridLinesY; i++)
            {
                int y = (int)(i * graphHeight / numGridLinesY);
                for (int x = 0; x < graphWidth; x++)
                {
                    _graphTexture.SetPixel(x, y, gridColor);
                }
            }

            int zeroY = Mathf.Clamp(Mathf.RoundToInt((-yMin) / (yMax - yMin) * graphHeight), 0, (int)graphHeight - 1);
            for (int x = 0; x < graphWidth; x++)
            {
                _graphTexture.SetPixel(x, zeroY, axisColor * 0.5f);
            }
        }

        protected virtual void DrawAxes()
        {
            for (int x = 0; x < graphWidth; x++)
            {
                _graphTexture.SetPixel(x, 0, axisColor);
                _graphTexture.SetPixel(x, (int)graphHeight - 1, axisColor);
            }

            for (int y = 0; y < graphHeight; y++)
            {
                _graphTexture.SetPixel(0, y, axisColor);
                _graphTexture.SetPixel((int)graphWidth - 1, y, axisColor);
            }
        }

        protected virtual void RedrawGraph()
        {
            for (int x = 0; x < graphWidth; x++)
            {
                for (int y = 0; y < graphHeight; y++)
                {
                    _graphTexture.SetPixel(x, y, backgroundColor);
                }
            }

            DrawGrid();
            DrawAxes();
            DrawDataSeries();
            _graphTexture.Apply();
        }

        protected virtual void DrawDataSeries()
        {
            for (int s = 0; s < dataSeries.Length; s++)
            {
                if (dataSeries[s].Count < 2) continue;

                Color color = seriesColors[s];
                int numPoints = dataSeries[s].Count;

                for (int i = 1; i < numPoints; i++)
                {
                    float t1 = (i - 1) / (float)maxDataPoints;
                    float t2 = i / (float)maxDataPoints;

                    if (numPoints < maxDataPoints)
                    {
                        t1 = (i - 1) / (float)(maxDataPoints - 1);
                        t2 = i / (float)(maxDataPoints - 1);
                    }

                    int x1 = Mathf.RoundToInt(t1 * (graphWidth - 4)) + 2;
                    int x2 = Mathf.RoundToInt(t2 * (graphWidth - 4)) + 2;

                    int y1 = Mathf.RoundToInt((dataSeries[s][i - 1] - yMin) / (yMax - yMin) * (graphHeight - 4)) + 2;
                    int y2 = Mathf.RoundToInt((dataSeries[s][i] - yMin) / (yMax - yMin) * (graphHeight - 4)) + 2;

                    y1 = Mathf.Clamp(y1, 2, (int)graphHeight - 3);
                    y2 = Mathf.Clamp(y2, 2, (int)graphHeight - 3);

                    DrawLine(x1, y1, x2, y2, color);
                }
            }
        }

        protected void DrawLine(int x1, int y1, int x2, int y2, Color color)
        {
            int dx = Mathf.Abs(x2 - x1);
            int dy = Mathf.Abs(y2 - y1);
            int sx = x1 < x2 ? 1 : -1;
            int sy = y1 < y2 ? 1 : -1;
            int err = dx - dy;

            while (true)
            {
                _graphTexture.SetPixel(x1, y1, color);

                if (x1 == x2 && y1 == y2) break;

                int e2 = 2 * err;
                if (e2 > -dy) { err -= dy; x1 += sx; }
                if (e2 < dx) { err += dx; y1 += sy; }
            }
        }

        protected virtual void OnGUI()
        {
            GUI.DrawTexture(_graphRect, _graphTexture);

            GUIStyle titleStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 14,
                fontStyle = FontStyle.Bold,
                alignment = TextAnchor.UpperCenter,
                normal = { textColor = Color.white }
            };

            GUI.Label(new Rect(_graphRect.x, _graphRect.y - 20f, _graphRect.width, 20f),
                graphTitle, titleStyle);

            DrawAxisLabels();
            DrawLegend();
        }

        protected virtual void DrawAxisLabels()
        {
            GUIStyle labelStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 10,
                normal = { textColor = Color.white }
            };

            GUI.Label(new Rect(_graphRect.x - 60f, _graphRect.y + _graphRect.height / 2f - 10f, 60f, 20f),
                yMax.ToString("F0"), labelStyle);
            GUI.Label(new Rect(_graphRect.x - 60f, _graphRect.y + _graphRect.height / 2f, 60f, 20f),
                ((yMin + yMax) / 2f).ToString("F0"), labelStyle);
            GUI.Label(new Rect(_graphRect.x - 60f, _graphRect.y + _graphRect.height - 10f, 60f, 20f),
                yMin.ToString("F0"), labelStyle);

            GUI.Label(new Rect(_graphRect.x + _graphRect.width / 2f - 30f, _graphRect.y + _graphRect.height, 60f, 20f),
                xAxisLabel, labelStyle);
        }

        protected virtual void DrawLegend()
        {
            GUIStyle legendStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 10,
                normal = { textColor = Color.white }
            };

            float legendX = _graphRect.x + _graphRect.width + 10f;
            float legendY = _graphRect.y;

            for (int i = 0; i < seriesNames.Length; i++)
            {
                GUI.color = seriesColors[i];
                GUI.DrawTexture(new Rect(legendX, legendY + i * 15f, 20f, 10f), Texture2D.whiteTexture);
                GUI.color = Color.white;
                GUI.Label(new Rect(legendX + 25f, legendY + i * 15f - 2f, 100f, 15f),
                    seriesNames[i], legendStyle);
            }
        }

        public void SetYRange(float min, float max)
        {
            yMin = min;
            yMax = max;
            RedrawGraph();
        }

        public void SetTitle(string title)
        {
            graphTitle = title;
        }

        public void SetAxisLabels(string yLabel, string xLabel)
        {
            yAxisLabel = yLabel;
            xAxisLabel = xLabel;
        }

        public Texture2D GetTexture()
        {
            return _graphTexture;
        }
    }
}
