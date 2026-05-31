using System;
using UnityEngine;
using LanderSim.Core;
using LanderSim.RiskAssessment;
using LanderSim.Terrain;

namespace LanderSim.Visualization
{
    public class RiskHeatmap : MonoBehaviour
    {
        public TerrainGenerator terrainGenerator;
        public RiskEvaluator riskEvaluator;
        public RiskMap riskMap;

        public bool showHeatmap = true;
        public bool showSlopeOverlay = false;
        public bool showRoughnessOverlay = false;
        public bool showShadowOverlay = false;

        public float heatmapOpacity = 0.7f;

        private Texture2D heatmapTexture;
        private Material heatmapMaterial;
        private GameObject heatmapPlane;

        public void Initialize(TerrainGenerator terrainGen, RiskEvaluator evaluator)
        {
            terrainGenerator = terrainGen;
            riskEvaluator = evaluator;
        }

        public void GenerateHeatmap()
        {
            if (riskEvaluator == null || terrainGenerator == null) return;

            riskMap = riskEvaluator.EvaluateRisk();

            if (riskMap == null) return;

            CreateHeatmapTexture();
            CreateHeatmapPlane();
            UpdateHeatmapTexture();
        }

        private void CreateHeatmapTexture()
        {
            heatmapTexture = new Texture2D(
                riskMap.resolutionX,
                riskMap.resolutionZ,
                TextureFormat.RGBA32,
                false
            );

            heatmapTexture.filterMode = FilterMode.Bilinear;
            heatmapTexture.wrapMode = TextureWrapMode.Clamp;
        }

        private void CreateHeatmapPlane()
        {
            if (heatmapPlane != null)
            {
                Destroy(heatmapPlane);
            }

            TerrainData terrainData = terrainGenerator.TerrainData;

            heatmapPlane = GameObject.CreatePrimitive(PrimitiveType.Plane);
            heatmapPlane.name = "RiskHeatmap";
            heatmapPlane.transform.parent = transform;
            heatmapPlane.transform.position = new Vector3(
                terrainData.origin.x + terrainData.resolutionX * terrainData.cellSize * 0.5f,
                terrainData.maxHeight + 0.1f,
                terrainData.origin.z + terrainData.resolutionZ * terrainData.cellSize * 0.5f
            );

            float scaleX = (terrainData.resolutionX * terrainData.cellSize) / 10.0f;
            float scaleZ = (terrainData.resolutionZ * terrainData.cellSize) / 10.0f;
            heatmapPlane.transform.localScale = new Vector3(scaleX, 1, scaleZ);

            MeshRenderer renderer = heatmapPlane.GetComponent<MeshRenderer>();
            heatmapMaterial = new Material(Shader.Find("Transparent/Diffuse"));
            heatmapMaterial.mainTexture = heatmapTexture;
            renderer.material = heatmapMaterial;
            renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            renderer.receiveShadows = false;

            heatmapPlane.SetActive(showHeatmap);
        }

        private void UpdateHeatmapTexture()
        {
            if (heatmapTexture == null || riskMap == null) return;

            Color[] colors = new Color[riskMap.resolutionX * riskMap.resolutionZ];

            for (int x = 0; x < riskMap.resolutionX; x++)
            {
                for (int z = 0; z < riskMap.resolutionZ; z++)
                {
                    Color color;

                    if (showSlopeOverlay)
                    {
                        double risk = riskMap.slopeRisk[x, z];
                        color = RiskMap.GetRiskColor(risk);
                    }
                    else if (showRoughnessOverlay)
                    {
                        double risk = riskMap.roughnessRisk[x, z];
                        color = RiskMap.GetRiskColor(risk);
                    }
                    else if (showShadowOverlay)
                    {
                        double risk = riskMap.shadowRisk[x, z];
                        color = RiskMap.GetRiskColor(risk);
                    }
                    else
                    {
                        double risk = riskMap.totalRisk[x, z];
                        color = riskMap.GetRiskColor(x, z);
                    }

                    color.a = heatmapOpacity;
                    colors[z * riskMap.resolutionX + x] = color;
                }
            }

            heatmapTexture.SetPixels(colors);
            heatmapTexture.Apply();
        }

        public void ToggleHeatmap(bool show)
        {
            showHeatmap = show;
            if (heatmapPlane != null)
            {
                heatmapPlane.SetActive(showHeatmap);
            }
        }

        public void SetOverlayMode(int mode)
        {
            showSlopeOverlay = mode == 1;
            showRoughnessOverlay = mode == 2;
            showShadowOverlay = mode == 3;

            if (mode == 0)
            {
                showSlopeOverlay = false;
                showRoughnessOverlay = false;
                showShadowOverlay = false;
            }

            UpdateHeatmapTexture();
        }

        public void UpdateOpacity(float opacity)
        {
            heatmapOpacity = Mathf.Clamp01(opacity);
            UpdateHeatmapTexture();
        }

        public Color GetRiskColorAtPosition(Vector3 worldPos)
        {
            if (riskMap == null || terrainGenerator == null) return Color.white;

            TerrainData terrainData = terrainGenerator.TerrainData;
            int x = (int)((worldPos.x - terrainData.origin.x) / terrainData.cellSize);
            int z = (int)((worldPos.z - terrainData.origin.z) / terrainData.cellSize);

            return riskMap.GetRiskColor(x, z);
        }

        public double GetRiskAtPosition(Vector3 worldPos)
        {
            if (riskMap == null || terrainGenerator == null) return 1.0;

            TerrainData terrainData = terrainGenerator.TerrainData;
            int x = (int)((worldPos.x - terrainData.origin.x) / terrainData.cellSize);
            int z = (int)((worldPos.z - terrainData.origin.z) / terrainData.cellSize);

            return riskMap.GetTotalRisk(x, z);
        }

        public void Cleanup()
        {
            if (heatmapPlane != null)
            {
                Destroy(heatmapPlane);
            }
            if (heatmapTexture != null)
            {
                Destroy(heatmapTexture);
            }
            if (heatmapMaterial != null)
            {
                Destroy(heatmapMaterial);
            }
        }

        void OnDestroy()
        {
            Cleanup();
        }
    }
}
