using System.Collections.Generic;
using UnityEngine;
using FlowVisualization.Core;
using FlowVisualization.Particles;

namespace FlowVisualization.Rendering
{
    public class LineRendererManager : MonoBehaviour
    {
        public Material LineMaterial;
        public float LineWidth = 0.005f;
        public bool UseColorMapping = true;
        public float TrailFadeStart = 0.2f;
        public int MaxLinePointsPerSeed = 512;

        private class SeedRenderData
        {
            public GameObject GameObject;
            public LineRenderer MainLineRenderer;
            public TrailRenderer TrailRenderer;
            public readonly List<LineRenderer> SubLineRenderers = new List<LineRenderer>();
            public readonly List<GameObject> SubLineObjects = new List<GameObject>();
        }

        private readonly Dictionary<int, SeedRenderData> _seedRenderers = new Dictionary<int, SeedRenderData>();
        private ColorMapManager _colorMap;
        private ParticleSystemManager _particleSystem;

        private void Awake()
        {
            _colorMap = GetComponent<ColorMapManager>() ?? gameObject.AddComponent<ColorMapManager>();
            _particleSystem = GetComponent<ParticleSystemManager>();

            if (LineMaterial == null)
            {
                LineMaterial = new Material(Shader.Find("Sprites/Default"));
            }
        }

        public void UpdateRendering(List<SeedPoint> seedPoints, ParticleSystemManager manager)
        {
            if (_particleSystem == null) _particleSystem = manager;

            foreach (var seed in seedPoints)
            {
                SeedRenderData renderData;
                if (!_seedRenderers.TryGetValue(seed.ID, out renderData))
                {
                    renderData = CreateSeedRenderer(seed);
                    _seedRenderers[seed.ID] = renderData;
                }

                UpdateSeedRenderer(seed, renderData, manager);
            }

            List<int> seedsToRemove = new List<int>();
            foreach (var kvp in _seedRenderers)
            {
                bool found = false;
                foreach (var seed in seedPoints)
                {
                    if (seed.ID == kvp.Key)
                    {
                        found = true;
                        break;
                    }
                }
                if (!found)
                {
                    seedsToRemove.Add(kvp.Key);
                }
            }

            foreach (int id in seedsToRemove)
            {
                SeedRenderData data = _seedRenderers[id];
                foreach (var subObj in data.SubLineObjects)
                {
                    if (subObj != null) Destroy(subObj);
                }
                data.SubLineObjects.Clear();
                data.SubLineRenderers.Clear();
                Destroy(data.GameObject);
                _seedRenderers.Remove(id);
            }
        }

        private SeedRenderData CreateSeedRenderer(SeedPoint seed)
        {
            GameObject lineObj = new GameObject($"LineRenderer_Seed{seed.ID}");
            lineObj.transform.SetParent(transform);

            LineRenderer lr = lineObj.AddComponent<LineRenderer>();
            lr.material = LineMaterial;
            lr.widthMultiplier = LineWidth;
            lr.positionCount = 0;
            lr.useWorldSpace = true;
            lr.numCapVertices = 2;
            lr.numCornerVertices = 2;
            lr.sortingOrder = 1;

            TrailRenderer tr = lineObj.AddComponent<TrailRenderer>();
            tr.widthMultiplier = LineWidth * 0.8f;
            tr.time = 0.5f;
            tr.material = LineMaterial;
            tr.sortingOrder = 2;
            tr.enabled = false;

            return new SeedRenderData
            {
                GameObject = lineObj,
                MainLineRenderer = lr,
                TrailRenderer = tr
            };
        }

        private LineRenderer CreateSubLineRenderer(GameObject parent, int index)
        {
            GameObject subObj = new GameObject($"SubLine_{index}");
            subObj.transform.SetParent(parent.transform);

            LineRenderer lr = subObj.AddComponent<LineRenderer>();
            lr.material = LineMaterial;
            lr.widthMultiplier = LineWidth * 0.9f;
            lr.positionCount = 0;
            lr.useWorldSpace = true;
            lr.numCapVertices = 1;
            lr.numCornerVertices = 1;
            lr.sortingOrder = 1;

            return lr;
        }

        private void UpdateSeedRenderer(SeedPoint seed, SeedRenderData renderData, ParticleSystemManager manager)
        {
            List<List<Vector3>> allTrails = seed.GetAllLineTrails();
            List<List<float>> allScalars = seed.GetAllLineScalars();

            if (seed.LineType == LineType.Stripline)
            {
                UpdateStriplineRenderer(seed, renderData, manager, allTrails, allScalars);
                renderData.MainLineRenderer.positionCount = 0;
            }
            else
            {
                UpdateSingleLineRenderer(seed, renderData, manager, allTrails, allScalars);
                
                for (int i = 0; i < renderData.SubLineRenderers.Count; i++)
                {
                    renderData.SubLineRenderers[i].positionCount = 0;
                }
            }

            UpdateTrailRenderer(seed, renderData);
        }

        private void UpdateSingleLineRenderer(SeedPoint seed, SeedRenderData renderData, 
            ParticleSystemManager manager, List<List<Vector3>> allTrails, List<List<float>> allScalars)
        {
            LineRenderer lr = renderData.MainLineRenderer;
            
            if (allTrails.Count == 0 || allTrails[0].Count < 2)
            {
                lr.positionCount = 0;
                return;
            }

            List<Vector3> linePoints = allTrails[0];
            List<float> scalars = allScalars.Count > 0 ? allScalars[0] : null;

            int pointCount = Mathf.Min(linePoints.Count, MaxLinePointsPerSeed);
            lr.positionCount = pointCount;

            Vector3[] positions = new Vector3[pointCount];
            Gradient colorGradient = new Gradient();
            List<GradientColorKey> colorKeys = new List<GradientColorKey>();

            for (int i = 0; i < pointCount; i++)
            {
                int idx = linePoints.Count - pointCount + i;
                positions[i] = linePoints[idx];

                if (UseColorMapping && scalars != null && idx < scalars.Count)
                {
                    float scalarValue = scalars[idx];
                    Color pointColor = manager.GetColorForScalar(scalarValue);
                    float alpha = i < pointCount * TrailFadeStart 
                        ? (float)i / (pointCount * TrailFadeStart) 
                        : 1.0f;
                    pointColor.a = alpha;
                    colorKeys.Add(new GradientColorKey(pointColor, (float)i / (pointCount - 1)));
                }
                else
                {
                    float alpha = i < pointCount * TrailFadeStart 
                        ? (float)i / (pointCount * TrailFadeStart) 
                        : 1.0f;
                    colorKeys.Add(new GradientColorKey(
                        new Color(seed.Color.r, seed.Color.g, seed.Color.b, alpha),
                        (float)i / (pointCount - 1)
                    ));
                }
            }

            lr.SetPositions(positions);

            GradientAlphaKey[] alphaKeys = new GradientAlphaKey[2];
            alphaKeys[0] = new GradientAlphaKey(0.3f, 0f);
            alphaKeys[1] = new GradientAlphaKey(1.0f, 1f);
            colorGradient.SetKeys(colorKeys.ToArray(), alphaKeys);
            lr.colorGradient = colorGradient;
        }

        private void UpdateStriplineRenderer(SeedPoint seed, SeedRenderData renderData,
            ParticleSystemManager manager, List<List<Vector3>> allTrails, List<List<float>> allScalars)
        {
            int requiredRenderers = allTrails.Count;
            
            while (renderData.SubLineRenderers.Count < requiredRenderers)
            {
                int index = renderData.SubLineRenderers.Count;
                LineRenderer newLr = CreateSubLineRenderer(renderData.GameObject, index);
                renderData.SubLineRenderers.Add(newLr);
                renderData.SubLineObjects.Add(newLr.gameObject);
            }
            
            for (int i = requiredRenderers; i < renderData.SubLineRenderers.Count; i++)
            {
                renderData.SubLineRenderers[i].positionCount = 0;
            }

            for (int trailIdx = 0; trailIdx < requiredRenderers; trailIdx++)
            {
                LineRenderer lr = renderData.SubLineRenderers[trailIdx];
                List<Vector3> linePoints = allTrails[trailIdx];
                List<float> scalars = allScalars.Count > trailIdx ? allScalars[trailIdx] : null;

                if (linePoints.Count < 2)
                {
                    lr.positionCount = 0;
                    continue;
                }

                int pointCount = Mathf.Min(linePoints.Count, MaxLinePointsPerSeed);
                lr.positionCount = pointCount;

                Vector3[] positions = new Vector3[pointCount];
                Gradient colorGradient = new Gradient();
                List<GradientColorKey> colorKeys = new List<GradientColorKey>();

                for (int i = 0; i < pointCount; i++)
                {
                    positions[i] = linePoints[i];

                    if (UseColorMapping && scalars != null && i < scalars.Count)
                    {
                        float scalarValue = scalars[i];
                        Color pointColor = manager.GetColorForScalar(scalarValue);
                        float alpha = i < pointCount * TrailFadeStart 
                            ? (float)i / (pointCount * TrailFadeStart) 
                            : 1.0f;
                        pointColor.a = alpha;
                        colorKeys.Add(new GradientColorKey(pointColor, (float)i / (pointCount - 1)));
                    }
                    else
                    {
                        float alpha = i < pointCount * TrailFadeStart 
                            ? (float)i / (pointCount * TrailFadeStart) 
                            : 1.0f;
                        colorKeys.Add(new GradientColorKey(
                            new Color(seed.Color.r, seed.Color.g, seed.Color.b, alpha),
                            (float)i / (pointCount - 1)
                        ));
                    }
                }

                lr.SetPositions(positions);

                GradientAlphaKey[] alphaKeys = new GradientAlphaKey[2];
                alphaKeys[0] = new GradientAlphaKey(0.3f, 0f);
                alphaKeys[1] = new GradientAlphaKey(1.0f, 1f);
                colorGradient.SetKeys(colorKeys.ToArray(), alphaKeys);
                lr.colorGradient = colorGradient;
            }
        }

        private void UpdateTrailRenderer(SeedPoint seed, SeedRenderData renderData)
        {
            TrailRenderer tr = renderData.TrailRenderer;

            if (seed.LineType == LineType.Pathline && seed.Particles.Count > 0)
            {
                tr.enabled = true;
                tr.transform.position = seed.Particles[0].Data.Position;

                if (UseColorMapping)
                {
                    Color startColor = _particleSystem.GetColorForScalar(seed.Particles[0].Data.ScalarValue);
                    Gradient trailGradient = new Gradient();
                    GradientColorKey[] colorKeys = new GradientColorKey[2];
                    colorKeys[0] = new GradientColorKey(startColor, 0f);
                    colorKeys[1] = new GradientColorKey(startColor, 1f);
                    
                    GradientAlphaKey[] alphaKeys = new GradientAlphaKey[2];
                    alphaKeys[0] = new GradientAlphaKey(1.0f, 0f);
                    alphaKeys[1] = new GradientAlphaKey(0.0f, 1f);
                    
                    trailGradient.SetKeys(colorKeys, alphaKeys);
                    tr.colorGradient = trailGradient;
                }
                else
                {
                    Gradient trailGradient = new Gradient();
                    GradientColorKey[] colorKeys = new GradientColorKey[2];
                    colorKeys[0] = new GradientColorKey(seed.Color, 0f);
                    colorKeys[1] = new GradientColorKey(seed.Color, 1f);
                    
                    GradientAlphaKey[] alphaKeys = new GradientAlphaKey[2];
                    alphaKeys[0] = new GradientAlphaKey(1.0f, 0f);
                    alphaKeys[1] = new GradientAlphaKey(0.0f, 1f);
                    
                    trailGradient.SetKeys(colorKeys, alphaKeys);
                    tr.colorGradient = trailGradient;
                }
            }
            else
            {
                tr.enabled = false;
            }
        }

        public void SetLineMaterial(Material material)
        {
            LineMaterial = material;
            foreach (var renderData in _seedRenderers.Values)
            {
                renderData.MainLineRenderer.material = material;
                renderData.TrailRenderer.material = material;
                foreach (var subLr in renderData.SubLineRenderers)
                {
                    subLr.material = material;
                }
            }
        }

        public void SetLineWidth(float width)
        {
            LineWidth = width;
            foreach (var renderData in _seedRenderers.Values)
            {
                renderData.MainLineRenderer.widthMultiplier = width;
                renderData.TrailRenderer.widthMultiplier = width * 0.8f;
                foreach (var subLr in renderData.SubLineRenderers)
                {
                    subLr.widthMultiplier = width * 0.9f;
                }
            }
        }
    }
}
