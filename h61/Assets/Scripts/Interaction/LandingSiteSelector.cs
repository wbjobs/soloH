using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;
using LanderSim.RiskAssessment;
using LanderSim.Terrain;

namespace LanderSim.Interaction
{
    public class LandingSiteSelector : MonoBehaviour
    {
        public TerrainGenerator terrainGenerator;
        public RiskMap riskMap;
        public Camera mainCamera;

        public Color candidateColor = Color.cyan;
        public Color selectedColor = Color.green;
        public float markerSize = 1.0f;

        public int maxCandidates = 10;
        public double autoSelectRiskThreshold = 0.3;

        private List<GameObject> candidateMarkers;
        private List<LandingSite> candidateSites;
        private LandingSite? selectedSite;

        public bool autoSelectBestSite = true;
        public bool allowManualSelection = true;

        public event Action<LandingSite> OnSiteSelected;
        public event Action<List<LandingSite>> OnCandidatesUpdated;

        public LandingSite? SelectedSite => selectedSite;
        public List<LandingSite> CandidateSites => candidateSites;

        void Awake()
        {
            candidateMarkers = new List<GameObject>();
            candidateSites = new List<LandingSite>();
            selectedSite = null;

            if (mainCamera == null)
            {
                mainCamera = Camera.main;
            }
        }

        public void Initialize(TerrainGenerator terrainGen, RiskMap riskM)
        {
            terrainGenerator = terrainGen;
            riskMap = riskM;
        }

        public void GenerateCandidates()
        {
            if (riskMap == null || terrainGenerator == null) return;

            ClearCandidates();

            RiskWeights weights = new RiskWeights();
            candidateSites = riskMap.GetBestLandingSites(maxCandidates, weights);

            CreateCandidateMarkers();

            if (autoSelectBestSite && candidateSites.Count > 0)
            {
                SelectSite(0);
            }

            OnCandidatesUpdated?.Invoke(candidateSites);
        }

        public void GenerateCandidatesInArea(Vector3 center, float radius)
        {
            if (riskMap == null || terrainGenerator == null) return;

            ClearCandidates();

            TerrainData terrainData = terrainGenerator.TerrainData;
            int centerX = (int)((center.x - terrainData.origin.x) / terrainData.cellSize);
            int centerZ = (int)((center.z - terrainData.origin.z) / terrainData.cellSize);
            int cellRadius = (int)(radius / terrainData.cellSize);

            List<LandingSite> sitesInArea = new List<LandingSite>();

            for (int x = centerX - cellRadius; x <= centerX + cellRadius; x++)
            {
                for (int z = centerZ - cellRadius; z <= centerZ + cellRadius; z++)
                {
                    if (x >= 0 && x < riskMap.resolutionX && z >= 0 && z < riskMap.resolutionZ)
                    {
                        double dx = (x - centerX) * terrainData.cellSize;
                        double dz = (z - centerZ) * terrainData.cellSize;
                        if (dx * dx + dz * dz <= radius * radius)
                        {
                            LandingSite site = riskMap.landingSites[x, z];
                            if (site.totalRisk < autoSelectRiskThreshold * 2)
                            {
                                sitesInArea.Add(site);
                            }
                        }
                    }
                }
            }

            sitesInArea.Sort((a, b) => a.totalRisk.CompareTo(b.totalRisk));

            int count = Math.Min(maxCandidates, sitesInArea.Count);
            candidateSites = sitesInArea.GetRange(0, count);

            CreateCandidateMarkers();

            if (autoSelectBestSite && candidateSites.Count > 0)
            {
                SelectSite(0);
            }

            OnCandidatesUpdated?.Invoke(candidateSites);
        }

        private void CreateCandidateMarkers()
        {
            for (int i = 0; i < candidateSites.Count; i++)
            {
                LandingSite site = candidateSites[i];
                GameObject marker = CreateMarker(site.position.ToVector3(), candidateColor, i + 1);
                marker.name = $"Candidate_{i + 1}";
                candidateMarkers.Add(marker);
            }
        }

        private GameObject CreateMarker(Vector3 position, Color color, int number)
        {
            GameObject marker = new GameObject($"LandingMarker_{number}");
            marker.transform.position = position + Vector3.up * 0.5f;
            marker.transform.parent = transform;

            GameObject cylinder = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            cylinder.transform.parent = marker.transform;
            cylinder.transform.localScale = new Vector3(markerSize, 0.1f, markerSize);
            Destroy(cylinder.GetComponent<Collider>());

            Renderer renderer = cylinder.GetComponent<Renderer>();
            renderer.material = new Material(Shader.Find("Standard"));
            renderer.material.color = color;
            renderer.material.EnableKeyword("_EMISSION");
            renderer.material.SetColor("_EmissionColor", color * 0.5f);

            GameObject ring = GameObject.CreatePrimitive(PrimitiveType.Torus);
            ring.transform.parent = marker.transform;
            ring.transform.localScale = new Vector3(markerSize * 1.5f, 0.1f, markerSize * 1.5f);
            ring.transform.rotation = Quaternion.Euler(90, 0, 0);
            Destroy(ring.GetComponent<Collider>());

            Renderer ringRenderer = ring.GetComponent<Renderer>();
            ringRenderer.material = new Material(Shader.Find("Standard"));
            ringRenderer.material.color = color;
            ringRenderer.material.EnableKeyword("_EMISSION");
            ringRenderer.material.SetColor("_EmissionColor", color * 0.3f);

            GameObject textObj = new GameObject("Label");
            textObj.transform.parent = marker.transform;
            textObj.transform.localPosition = new Vector3(0, 1.5f, 0);

            TextMesh textMesh = textObj.AddComponent<TextMesh>();
            textMesh.text = number.ToString();
            textMesh.characterSize = 0.3f;
            textMesh.fontSize = 48;
            textMesh.alignment = TextAlignment.Center;
            textMesh.anchor = TextAnchor.MiddleCenter;
            textMesh.color = Color.white;

            return marker;
        }

        public void SelectSite(int index)
        {
            if (index < 0 || index >= candidateSites.Count) return;

            ClearSelectedMarker();

            selectedSite = candidateSites[index];

            if (index < candidateMarkers.Count)
            {
                UpdateMarkerColor(candidateMarkers[index], selectedColor);
            }

            LandingSite site = candidateSites[index];
            site.isSelected = true;
            candidateSites[index] = site;

            OnSiteSelected?.Invoke(candidateSites[index]);
        }

        public void SelectSite(Vector3 worldPosition)
        {
            if (!allowManualSelection || candidateSites.Count == 0) return;

            int closestIndex = 0;
            double closestDist = double.MaxValue;

            for (int i = 0; i < candidateSites.Count; i++)
            {
                double dist = Vector3d.Distance(
                    Vector3d.FromVector3(worldPosition),
                    candidateSites[i].position
                );

                if (dist < closestDist)
                {
                    closestDist = dist;
                    closestIndex = i;
                }
            }

            if (closestDist < 5.0)
            {
                SelectSite(closestIndex);
            }
        }

        public bool RaycastToSelect(Ray ray)
        {
            if (!allowManualSelection) return false;

            RaycastHit hit;
            if (Physics.Raycast(ray, out hit, Mathf.Infinity))
            {
                SelectSite(hit.point);
                return true;
            }

            return false;
        }

        public void ClearSelectedMarker()
        {
            if (selectedSite.HasValue)
            {
                int selectedIndex = candidateSites.FindIndex(s =>
                    s.position == selectedSite.Value.position);

                if (selectedIndex >= 0 && selectedIndex < candidateMarkers.Count)
                {
                    UpdateMarkerColor(candidateMarkers[selectedIndex], candidateColor);
                }

                LandingSite site = candidateSites[selectedIndex];
                site.isSelected = false;
                candidateSites[selectedIndex] = site;
            }

            selectedSite = null;
        }

        private void UpdateMarkerColor(GameObject marker, Color color)
        {
            Renderer[] renderers = marker.GetComponentsInChildren<Renderer>();
            foreach (var renderer in renderers)
            {
                renderer.material.color = color;
                renderer.material.SetColor("_EmissionColor", color * 0.5f);
            }
        }

        public void ClearCandidates()
        {
            foreach (var marker in candidateMarkers)
            {
                if (marker != null)
                {
                    Destroy(marker);
                }
            }

            candidateMarkers.Clear();
            candidateSites.Clear();
            selectedSite = null;
        }

        void Update()
        {
            if (allowManualSelection && Input.GetMouseButtonDown(0))
            {
                if (mainCamera != null)
                {
                    Ray ray = mainCamera.ScreenPointToRay(Input.mousePosition);
                    RaycastToSelect(ray);
                }
            }

            if (Input.GetKeyDown(KeyCode.Alpha1)) SelectSite(0);
            if (Input.GetKeyDown(KeyCode.Alpha2)) SelectSite(1);
            if (Input.GetKeyDown(KeyCode.Alpha3)) SelectSite(2);
            if (Input.GetKeyDown(KeyCode.Alpha4)) SelectSite(3);
            if (Input.GetKeyDown(KeyCode.Alpha5)) SelectSite(4);
            if (Input.GetKeyDown(KeyCode.Alpha6)) SelectSite(5);
            if (Input.GetKeyDown(KeyCode.Alpha7)) SelectSite(6);
            if (Input.GetKeyDown(KeyCode.Alpha8)) SelectSite(7);
            if (Input.GetKeyDown(KeyCode.Alpha9)) SelectSite(8);
            if (Input.GetKeyDown(KeyCode.Alpha0)) SelectSite(9);
        }

        public void Cleanup()
        {
            ClearCandidates();
        }

        void OnDestroy()
        {
            Cleanup();
        }
    }
}
