using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;
using LanderSim.RiskAssessment;

namespace LanderSim.Visualization
{
    public class TrajectoryVisualizer : MonoBehaviour
    {
        public Color trajectoryColor = Color.cyan;
        public float trajectoryWidth = 0.05f;
        public bool showVelocityVectors = false;
        public float velocityScale = 0.5f;
        public bool showThrustVectors = false;
        public float thrustScale = 0.3f;

        public Color landedColor = Color.green;
        public Color crashedColor = Color.red;
        public Color inFlightColor = Color.yellow;

        private LineRenderer trajectoryLine;
        private List<GameObject> velocityArrows;
        private List<GameObject> thrustArrows;
        private GameObject landerVisual;

        public List<TrajectoryPoint> trajectoryPoints;

        public void Initialize()
        {
            CreateTrajectoryLine();
            velocityArrows = new List<GameObject>();
            thrustArrows = new List<GameObject>();
        }

        private void CreateTrajectoryLine()
        {
            if (trajectoryLine != null)
            {
                Destroy(trajectoryLine.gameObject);
            }

            GameObject lineObj = new GameObject("TrajectoryLine");
            lineObj.transform.parent = transform;

            trajectoryLine = lineObj.AddComponent<LineRenderer>();
            trajectoryLine.material = new Material(Shader.Find("Sprites/Default"));
            trajectoryLine.startColor = trajectoryColor;
            trajectoryLine.endColor = trajectoryColor;
            trajectoryLine.startWidth = trajectoryWidth;
            trajectoryLine.endWidth = trajectoryWidth;
            trajectoryLine.positionCount = 0;
            trajectoryLine.useWorldSpace = true;
            trajectoryLine.numCapVertices = 5;
            trajectoryLine.numCornerVertices = 5;
        }

        public void SetTrajectory(List<TrajectoryPoint> points)
        {
            trajectoryPoints = points;
            UpdateTrajectoryVisualization();
        }

        public void SetPath(List<Vector3d> path)
        {
            if (path == null || path.Count < 2) return;

            trajectoryPoints = new List<TrajectoryPoint>();
            for (int i = 0; i < path.Count; i++)
            {
                trajectoryPoints.Add(new TrajectoryPoint(
                    path[i],
                    Vector3d.zero,
                    Quaterniond.identity,
                    800, 300, i
                ));
            }

            UpdateTrajectoryVisualization();
        }

        private void UpdateTrajectoryVisualization()
        {
            if (trajectoryPoints == null || trajectoryPoints.Count < 2)
            {
                if (trajectoryLine != null)
                {
                    trajectoryLine.positionCount = 0;
                }
                return;
            }

            trajectoryLine.positionCount = trajectoryPoints.Count;

            for (int i = 0; i < trajectoryPoints.Count; i++)
            {
                trajectoryLine.SetPosition(i, trajectoryPoints[i].position.ToVector3());
            }

            UpdateGradientColors();

            if (showVelocityVectors)
            {
                CreateVelocityVectors();
            }

            if (showThrustVectors)
            {
                CreateThrustVectors();
            }
        }

        private void UpdateGradientColors()
        {
            Gradient gradient = new Gradient();
            GradientColorKey[] colorKeys = new GradientColorKey[trajectoryPoints.Count];
            GradientAlphaKey[] alphaKeys = new GradientAlphaKey[2];

            for (int i = 0; i < trajectoryPoints.Count; i++)
            {
                float t = (float)i / (trajectoryPoints.Count - 1);
                double risk = trajectoryPoints[i].risk;
                Color pointColor = RiskMap.GetRiskColor(risk);

                if (i == trajectoryPoints.Count - 1)
                {
                    pointColor = trajectoryPoints[i].position.y < 1.0 ? landedColor : inFlightColor;
                }

                colorKeys[i] = new GradientColorKey(pointColor, t);
            }

            alphaKeys[0] = new GradientAlphaKey(0.8f, 0.0f);
            alphaKeys[1] = new GradientAlphaKey(1.0f, 1.0f);

            gradient.SetKeys(colorKeys, alphaKeys);
            trajectoryLine.colorGradient = gradient;
        }

        private void CreateVelocityVectors()
        {
            ClearArrows(velocityArrows);

            if (trajectoryPoints == null) return;

            int step = Math.Max(1, trajectoryPoints.Count / 20);

            for (int i = 0; i < trajectoryPoints.Count; i += step)
            {
                Vector3 pos = trajectoryPoints[i].position.ToVector3();
                Vector3 vel = trajectoryPoints[i].velocity.ToVector3() * velocityScale;

                GameObject arrow = CreateArrow(pos, pos + vel, Color.blue);
                arrow.name = $"VelocityArrow_{i}";
                arrow.transform.parent = transform;
                velocityArrows.Add(arrow);
            }
        }

        private void CreateThrustVectors()
        {
            ClearArrows(thrustArrows);

            if (trajectoryPoints == null) return;

            int step = Math.Max(1, trajectoryPoints.Count / 15);

            for (int i = 0; i < trajectoryPoints.Count; i += step)
            {
                Vector3 pos = trajectoryPoints[i].position.ToVector3();
                Vector3d thrustDir = trajectoryPoints[i].attitude * Vector3d.up;
                Vector3 thrust = thrustDir.ToVector3() * thrustScale *
                    (float)trajectoryPoints[i].throttle;

                GameObject arrow = CreateArrow(pos, pos + thrust, Color.magenta);
                arrow.name = $"ThrustArrow_{i}";
                arrow.transform.parent = transform;
                thrustArrows.Add(arrow);
            }
        }

        private GameObject CreateArrow(Vector3 start, Vector3 end, Color color)
        {
            GameObject arrow = new GameObject();
            LineRenderer line = arrow.AddComponent<LineRenderer>();

            line.material = new Material(Shader.Find("Sprites/Default"));
            line.startColor = color;
            line.endColor = color;
            line.startWidth = 0.02f;
            line.endWidth = 0.02f;
            line.positionCount = 2;
            line.SetPosition(0, start);
            line.SetPosition(1, end);

            Vector3 dir = (end - start).normalized;
            GameObject head = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            head.transform.position = end;
            head.transform.localScale = Vector3.one * 0.1f;
            head.transform.parent = arrow.transform;
            Destroy(head.GetComponent<Collider>());

            Renderer headRenderer = head.GetComponent<Renderer>();
            headRenderer.material = new Material(Shader.Find("Standard"));
            headRenderer.material.color = color;

            return arrow;
        }

        private void ClearArrows(List<GameObject> arrows)
        {
            foreach (var arrow in arrows)
            {
                if (arrow != null)
                {
                    Destroy(arrow);
                }
            }
            arrows.Clear();
        }

        public void CreateLanderVisual(GameObject prefab = null)
        {
            if (landerVisual != null)
            {
                Destroy(landerVisual);
            }

            if (prefab != null)
            {
                landerVisual = Instantiate(prefab, transform);
            }
            else
            {
                landerVisual = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                landerVisual.transform.localScale = new Vector3(1.5f, 3f, 1.5f);
                landerVisual.name = "LanderVisual";
                landerVisual.transform.parent = transform;
                Destroy(landerVisual.GetComponent<Collider>());

                Renderer renderer = landerVisual.GetComponent<Renderer>();
                renderer.material = new Material(Shader.Find("Standard"));
                renderer.material.color = inFlightColor;
            }
        }

        public void UpdateLanderPosition(int pointIndex)
        {
            if (landerVisual == null || trajectoryPoints == null ||
                pointIndex < 0 || pointIndex >= trajectoryPoints.Count) return;

            TrajectoryPoint point = trajectoryPoints[pointIndex];
            landerVisual.transform.position = point.position.ToVector3();
            landerVisual.transform.rotation =
                new Quaternion((float)point.attitude.x, (float)point.attitude.y,
                              (float)point.attitude.z, (float)point.attitude.w);

            Renderer renderer = landerVisual.GetComponent<Renderer>();
            if (pointIndex == trajectoryPoints.Count - 1)
            {
                if (point.position.y < 1.0 && point.velocity.magnitude < 3.0)
                {
                    renderer.material.color = landedColor;
                }
                else if (point.position.y < 1.0)
                {
                    renderer.material.color = crashedColor;
                }
            }
        }

        public void ToggleVelocityVectors(bool show)
        {
            showVelocityVectors = show;
            if (show) CreateVelocityVectors();
            else ClearArrows(velocityArrows);
        }

        public void ToggleThrustVectors(bool show)
        {
            showThrustVectors = show;
            if (show) CreateThrustVectors();
            else ClearArrows(thrustArrows);
        }

        public void SetTrajectoryWidth(float width)
        {
            trajectoryWidth = Mathf.Max(0.01f, width);
            if (trajectoryLine != null)
            {
                trajectoryLine.startWidth = trajectoryWidth;
                trajectoryLine.endWidth = trajectoryWidth;
            }
        }

        public void Clear()
        {
            if (trajectoryLine != null)
            {
                trajectoryLine.positionCount = 0;
            }
            ClearArrows(velocityArrows);
            ClearArrows(thrustArrows);
            trajectoryPoints = null;
        }

        public void Cleanup()
        {
            if (trajectoryLine != null)
            {
                Destroy(trajectoryLine.gameObject);
            }
            ClearArrows(velocityArrows);
            ClearArrows(thrustArrows);
            if (landerVisual != null)
            {
                Destroy(landerVisual);
            }
        }

        void OnDestroy()
        {
            Cleanup();
        }
    }
}
