using System.Collections.Generic;
using UnityEngine;
using FlowVisualization.Core;
using FlowVisualization.Particles;

namespace FlowVisualization.Interaction
{
    public class SeedPointPlacer : MonoBehaviour
    {
        [Header("References")]
        public ParticleSystemManager ParticleSystem;
        public Camera MainCamera;

        [Header("Placement Settings")]
        public LayerMask PlacementLayer = ~0;
        public float RaycastDistance = 100f;
        public bool ShowPlacementPreview = true;
        public Material PreviewMaterial;
        public Color PreviewColor = Color.yellow;
        public float PreviewSize = 0.02f;

        [Header("Input")]
        public KeyCode PlacePathlineKey = KeyCode.Alpha1;
        public KeyCode PlaceStreaklineKey = KeyCode.Alpha2;
        public KeyCode PlaceStriplineKey = KeyCode.Alpha3;
        public KeyCode DeleteKey = KeyCode.LeftControl;

        private LineType _currentLineType = LineType.Pathline;
        private GameObject _previewMarker;
        private bool _isPreviewValid;
        private Vector3 _previewPosition;
        private readonly Dictionary<int, GameObject> _seedMarkers = new Dictionary<int, GameObject>();

        private void Awake()
        {
            if (MainCamera == null)
            {
                MainCamera = Camera.main;
            }

            CreatePreviewMarker();
        }

        private void Update()
        {
            if (Input.GetKeyDown(PlacePathlineKey)) _currentLineType = LineType.Pathline;
            if (Input.GetKeyDown(PlaceStreaklineKey)) _currentLineType = LineType.Streakline;
            if (Input.GetKeyDown(PlaceStriplineKey)) _currentLineType = LineType.Stripline;

            UpdatePreview();

            if (Input.GetMouseButtonDown(0) && !Input.GetMouseButton(1))
            {
                if (Input.GetKey(DeleteKey))
                {
                    TryDeleteSeed();
                }
                else
                {
                    TryPlaceSeed();
                }
            }
        }

        private void CreatePreviewMarker()
        {
            _previewMarker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            _previewMarker.transform.localScale = Vector3.one * PreviewSize;
            Destroy(_previewMarker.GetComponent<Collider>());
            _previewMarker.name = "SeedPreview";

            if (PreviewMaterial == null)
            {
                PreviewMaterial = new Material(Shader.Find("Standard"));
            }

            MeshRenderer renderer = _previewMarker.GetComponent<MeshRenderer>();
            renderer.material = PreviewMaterial;
            renderer.material.color = PreviewColor;
            renderer.enabled = false;
        }

        private void UpdatePreview()
        {
            if (!ShowPlacementPreview)
            {
                if (_previewMarker.GetComponent<MeshRenderer>().enabled)
                {
                    _previewMarker.GetComponent<MeshRenderer>().enabled = false;
                }
                return;
            }

            Ray ray = MainCamera.ScreenPointToRay(Input.mousePosition);
            RaycastHit hit;

            _isPreviewValid = false;

            if (Physics.Raycast(ray, out hit, RaycastDistance, PlacementLayer))
            {
                _previewPosition = hit.point;
                _isPreviewValid = true;
            }
            else
            {
                Plane plane = new Plane(Vector3.up, 0.5f);
                float enter;
                if (plane.Raycast(ray, out enter))
                {
                    _previewPosition = ray.GetPoint(enter);
                    _isPreviewValid = true;
                }
            }

            if (_isPreviewValid)
            {
                if (ParticleSystem != null && ParticleSystem.Field != null)
                {
                    Vector3Field field = ParticleSystem.Field[0];
                    if (!field.IsInsideBounds(_previewPosition))
                    {
                        _previewPosition.x = Mathf.Clamp(_previewPosition.x, field.MinBounds.x, field.MaxBounds.x);
                        _previewPosition.y = Mathf.Clamp(_previewPosition.y, field.MinBounds.y, field.MaxBounds.y);
                        _previewPosition.z = Mathf.Clamp(_previewPosition.z, field.MinBounds.z, field.MaxBounds.z);
                    }
                }

                _previewMarker.transform.position = _previewPosition;
                _previewMarker.GetComponent<MeshRenderer>().enabled = true;

                Color color = _currentLineType switch
                {
                    LineType.Pathline => Color.blue,
                    LineType.Streakline => Color.green,
                    LineType.Stripline => Color.red,
                    _ => Color.white
                };
                _previewMarker.GetComponent<MeshRenderer>().material.color = color;
            }
            else
            {
                _previewMarker.GetComponent<MeshRenderer>().enabled = false;
            }
        }

        private void TryPlaceSeed()
        {
            if (!_isPreviewValid || ParticleSystem == null) return;

            SeedPoint seed = ParticleSystem.AddSeedPoint(_previewPosition, _currentLineType);
            
            GameObject marker = CreateSeedMarker(seed);
            _seedMarkers[seed.ID] = marker;

            Debug.Log($"Placed {_currentLineType} seed at {_previewPosition}");
        }

        private void TryDeleteSeed()
        {
            if (ParticleSystem == null || _seedMarkers.Count == 0) return;

            Ray ray = MainCamera.ScreenPointToRay(Input.mousePosition);
            RaycastHit hit;

            if (Physics.Raycast(ray, out hit, RaycastDistance))
            {
                foreach (var kvp in _seedMarkers)
                {
                    if (kvp.Value == hit.collider.gameObject)
                    {
                        ParticleSystem.RemoveSeedPoint(kvp.Key);
                        Destroy(kvp.Value);
                        _seedMarkers.Remove(kvp.Key);
                        Debug.Log($"Removed seed {kvp.Key}");
                        break;
                    }
                }
            }
        }

        private GameObject CreateSeedMarker(SeedPoint seed)
        {
            GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            marker.transform.position = seed.Position;
            marker.transform.localScale = Vector3.one * 0.015f;
            marker.name = $"SeedMarker_{seed.ID}";

            Material mat = new Material(Shader.Find("Standard"));
            mat.color = seed.LineType switch
            {
                LineType.Pathline => Color.blue,
                LineType.Streakline => Color.green,
                LineType.Stripline => Color.red,
                _ => Color.white
            };

            marker.GetComponent<MeshRenderer>().material = mat;
            marker.layer = LayerMask.NameToLayer("Default");

            return marker;
        }

        public void SetLineType(LineType type)
        {
            _currentLineType = type;
        }

        public void ClearAllSeeds()
        {
            foreach (var marker in _seedMarkers.Values)
            {
                Destroy(marker);
            }
            _seedMarkers.Clear();
            ParticleSystem?.ClearAllSeedPoints();
        }
    }
}
