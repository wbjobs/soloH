using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;

namespace LanderSim.Visualization
{
    public class LandingErrorEllipse : MonoBehaviour
    {
        public Color ellipseColor = Color.yellow;
        public float lineWidth = 0.03f;
        public int segments = 60;
        public bool showDeviationVectors = true;

        private LineRenderer[] ellipseLines;
        private List<GameObject> deviationVectors;
        private List<Vector3d> landingPoints;

        public Vector3 meanPosition;
        public Vector3 covariance;
        public Vector3 correlationXY;

        public void Initialize()
        {
            ellipseLines = new LineRenderer[3];
            deviationVectors = new List<GameObject>();
        }

        public void CalculateEllipse(List<Vector3d> points)
        {
            landingPoints = points;

            if (points == null || points.Count < 2) return;

            CalculateStatistics(points);
            CalculateCovariance(points);
            DrawEllipses();

            if (showDeviationVectors)
            {
                DrawDeviationVectors();
            }
        }

        private void CalculateStatistics(List<Vector3d> points)
        {
            double sumX = 0, sumY = 0, sumZ = 0;

            foreach (var p in points)
            {
                sumX += p.x;
                sumY += p.y;
                sumZ += p.z;
            }

            meanPosition = new Vector3d(
                sumX / points.Count,
                sumY / points.Count,
                sumZ / points.Count
            );
        }

        private void CalculateCovariance(List<Vector3d> points)
        {
            double n = points.Count;
            double sumXX = 0, sumYY = 0, sumZZ = 0;
            double sumXY = 0, sumXZ = 0, sumYZ = 0;

            foreach (var p in points)
            {
                double dx = p.x - meanPosition.x;
                double dy = p.y - meanPosition.y;
                double dz = p.z - meanPosition.z;

                sumXX += dx * dx;
                sumYY += dy * dy;
                sumZZ += dz * dz;
                sumXY += dx * dy;
                sumXZ += dx * dz;
                sumYZ += dy * dz;
            }

            double varX = sumXX / (n - 1);
            double varY = sumYY / (n - 1);
            double varZ = sumZZ / (n - 1);

            covariance = new Vector3d(varX, varY, varZ);
            correlationXY = new Vector3d(
                sumXY / (n - 1) / Math.Sqrt(varX * varY),
                sumXZ / (n - 1) / Math.Sqrt(varX * varZ),
                sumYZ / (n - 1) / Math.Sqrt(varY * varZ)
            );
        }

        private void DrawEllipses()
        {
            ClearEllipses();

            Vector3 center = meanPosition.ToVector3();

            Vector3 horizontalAxis = new Vector3((float)Math.Sqrt(covariance.x) * 3,
                                                 0,
                                                 (float)Math.Sqrt(covariance.z) * 3);
            Vector3 verticalAxis = new Vector3(0, (float)Math.Sqrt(covariance.y) * 3, 0);

            ellipseLines[0] = CreateEllipse(center, horizontalAxis, Vector3.up, ellipseColor);
            ellipseLines[1] = CreateEllipse(center,
                new Vector3(horizontalAxis.x, 0, 0),
                Vector3.right,
                new Color(ellipseColor.r, ellipseColor.g, ellipseColor.b, 0.5f));
            ellipseLines[2] = CreateEllipse(center,
                new Vector3(0, 0, horizontalAxis.z),
                Vector3.forward,
                new Color(ellipseColor.r, ellipseColor.g, ellipseColor.b, 0.5f));

            DrawCenterMarker(center);
        }

        private LineRenderer CreateEllipse(Vector3 center, Vector3 axis, Vector3 normal, Color color)
        {
            GameObject ellipseObj = new GameObject($"Ellipse_{normal}");
            ellipseObj.transform.parent = transform;

            LineRenderer line = ellipseObj.AddComponent<LineRenderer>();
            line.material = new Material(Shader.Find("Sprites/Default"));
            line.startColor = color;
            line.endColor = color;
            line.startWidth = lineWidth;
            line.endWidth = lineWidth;
            line.positionCount = segments + 1;
            line.useWorldSpace = true;
            line.loop = true;

            Vector3 perp1 = Vector3.Cross(normal, axis).normalized;
            Vector3 perp2 = Vector3.Cross(normal, perp1).normalized;
            float axis1Mag = axis.magnitude;
            float axis2Mag = axis1Mag * 0.5f;

            for (int i = 0; i <= segments; i++)
            {
                float angle = (float)i / segments * Mathf.PI * 2;
                Vector3 point = center +
                    perp1 * Mathf.Cos(angle) * axis1Mag +
                    perp2 * Mathf.Sin(angle) * axis2Mag;
                line.SetPosition(i, point);
            }

            return line;
        }

        private void DrawCenterMarker(Vector3 center)
        {
            GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            marker.transform.position = center;
            marker.transform.localScale = Vector3.one * 0.3f;
            marker.transform.parent = transform;
            Destroy(marker.GetComponent<Collider>());

            Renderer renderer = marker.GetComponent<Renderer>();
            renderer.material = new Material(Shader.Find("Standard"));
            renderer.material.color = Color.white;
            marker.name = "EllipseCenter";
        }

        private void DrawDeviationVectors()
        {
            ClearDeviationVectors();

            if (landingPoints == null) return;

            Vector3 mean = meanPosition.ToVector3();

            foreach (var point in landingPoints)
            {
                Vector3 end = point.ToVector3();
                GameObject arrow = CreateDeviationArrow(mean, end);
                arrow.transform.parent = transform;
                deviationVectors.Add(arrow);
            }
        }

        private GameObject CreateDeviationArrow(Vector3 start, Vector3 end)
        {
            GameObject arrow = new GameObject("DeviationVector");
            LineRenderer line = arrow.AddComponent<LineRenderer>();

            Vector3 dir = (end - start).normalized;
            float dist = Vector3.Distance(start, end);

            Color color;
            if (dist < 1.0f)
                color = Color.green;
            else if (dist < 3.0f)
                color = Color.yellow;
            else
                color = Color.red;

            line.material = new Material(Shader.Find("Sprites/Default"));
            line.startColor = color;
            line.endColor = color;
            line.startWidth = 0.02f;
            line.endWidth = 0.02f;
            line.positionCount = 2;
            line.SetPosition(0, start);
            line.SetPosition(1, end);

            GameObject point = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            point.transform.position = end;
            point.transform.localScale = Vector3.one * 0.15f;
            point.transform.parent = arrow;
            Destroy(point.GetComponent<Collider>());

            Renderer renderer = point.GetComponent<Renderer>();
            renderer.material = new Material(Shader.Find("Standard"));
            renderer.material.color = color;

            return arrow;
        }

        private void ClearEllipses()
        {
            if (ellipseLines != null)
            {
                for (int i = 0; i < ellipseLines.Length; i++)
                {
                    if (ellipseLines[i] != null)
                    {
                        Destroy(ellipseLines[i].gameObject);
                        ellipseLines[i] = null;
                    }
                }
            }

            GameObject center = transform.Find("EllipseCenter")?.gameObject;
            if (center != null) Destroy(center);
        }

        private void ClearDeviationVectors()
        {
            foreach (var vec in deviationVectors)
            {
                if (vec != null) Destroy(vec);
            }
            deviationVectors.Clear();
        }

        public void SetEllipseColor(Color color)
        {
            ellipseColor = color;
            if (landingPoints != null && landingPoints.Count > 0)
            {
                DrawEllipses();
            }
        }

        public void ToggleDeviationVectors(bool show)
        {
            showDeviationVectors = show;
            if (show && landingPoints != null)
            {
                DrawDeviationVectors();
            }
            else
            {
                ClearDeviationVectors();
            }
        }

        public string GetStatisticsText()
        {
            if (landingPoints == null || landingPoints.Count < 2)
                return "Not enough data";

            return $"Mean: {meanPosition}\n" +
                   $"Std Dev: ({Math.Sqrt(covariance.x):F2}, " +
                   $"{Math.Sqrt(covariance.y):F2}, " +
                   $"{Math.Sqrt(covariance.z):F2})\n" +
                   $"Correlation XY: {correlationXY.x:F3}\n" +
                   $"Samples: {landingPoints.Count}";
        }

        public void Clear()
        {
            ClearEllipses();
            ClearDeviationVectors();
            landingPoints = null;
            meanPosition = Vector3d.zero;
            covariance = Vector3d.zero;
            correlationXY = Vector3d.zero;
        }

        public void Cleanup()
        {
            Clear();
        }

        void OnDestroy()
        {
            Cleanup();
        }
    }
}
