using UnityEngine;
using UnityEngine.EventSystems;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.Controllers
{
    public class SceneController : MonoBehaviour
    {
        [Header("Camera Settings")]
        [SerializeField] private Camera _mainCamera;
        [SerializeField] private Transform _target;
        [SerializeField] private float _rotationSpeed = 5f;
        [SerializeField] private float _panSpeed = 0.01f;
        [SerializeField] private float _zoomSpeed = 0.1f;
        [SerializeField] private float _minDistance = 0.5f;
        [SerializeField] private float _maxDistance = 3f;

        [Header("Lighting")]
        [SerializeField] private Light _mainLight;
        [SerializeField] private Light _fillLight;
        [SerializeField] private Light _rimLight;

        [Header("Background")]
        [SerializeField] private Color _backgroundColor = new Color(0.1f, 0.1f, 0.18f);
        [SerializeField] private Color _ambientColor = new Color(0.2f, 0.2f, 0.25f);

        [Header("Ground")]
        [SerializeField] private GameObject _groundPlane;
        [SerializeField] private Material _groundMaterial;

        [Header("Post Processing")]
        [SerializeField] private float _bloomIntensity = 0.4f;
        [SerializeField] private float _depthOfField = 0f;

        private Vector3 _cameraOffset;
        private float _currentDistance;
        private float _yaw;
        private float _pitch;
        private bool _isRotating;
        private bool _isPanning;
        private Vector3 _panStart;
        private Vector2 _mouseStart;

        public GroundType CurrentGroundType { get; private set; } = GroundType.DryAsphalt;

        private void Awake()
        {
            InitializeScene();
            InitializeCamera();
        }

        private void Start()
        {
            UpdateGroundMaterial(CurrentGroundType);
        }

        private void InitializeScene()
        {
            if (_mainCamera != null)
            {
                _mainCamera.clearFlags = CameraClearFlags.SolidColor;
                _mainCamera.backgroundColor = _backgroundColor;
                _mainCamera.fieldOfView = 45f;
                _mainCamera.nearClipPlane = 0.01f;
                _mainCamera.farClipPlane = 10f;
            }

            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = _ambientColor;

            if (_mainLight != null)
            {
                _mainLight.type = LightType.Directional;
                _mainLight.intensity = 1.2f;
                _mainLight.color = new Color(1f, 0.98f, 0.95f);
                _mainLight.transform.rotation = Quaternion.Euler(45f, 45f, 0f);
                _mainLight.shadows = LightShadows.Soft;
                _mainLight.shadowStrength = 0.7f;
            }

            if (_fillLight != null)
            {
                _fillLight.type = LightType.Directional;
                _fillLight.intensity = 0.4f;
                _fillLight.color = new Color(0.7f, 0.8f, 1f);
                _fillLight.transform.rotation = Quaternion.Euler(45f, -45f, 0f);
                _fillLight.shadows = LightShadows.None;
            }

            if (_rimLight != null)
            {
                _rimLight.type = LightType.Directional;
                _rimLight.intensity = 0.6f;
                _rimLight.color = new Color(1f, 0.9f, 0.7f);
                _rimLight.transform.rotation = Quaternion.Euler(-30f, 180f, 0f);
                _rimLight.shadows = LightShadows.None;
            }
        }

        private void InitializeCamera()
        {
            if (_mainCamera == null || _target == null) return;

            _currentDistance = 1.5f;
            _yaw = 45f;
            _pitch = 30f;

            UpdateCameraPosition();
        }

        private void Update()
        {
            HandleCameraInput();
            HandleKeyboardInput();
        }

        private void HandleCameraInput()
        {
            if (EventSystem.current != null && EventSystem.current.IsPointerOverGameObject())
                return;

            if (Input.GetMouseButtonDown(1))
            {
                _isRotating = true;
                _mouseStart = Input.mousePosition;
            }

            if (Input.GetMouseButtonUp(1))
            {
                _isRotating = false;
            }

            if (Input.GetMouseButtonDown(2))
            {
                _isPanning = true;
                _panStart = Input.mousePosition;
            }

            if (Input.GetMouseButtonUp(2))
            {
                _isPanning = false;
            }

            if (_isRotating)
            {
                Vector2 delta = (Vector2)Input.mousePosition - _mouseStart;
                _yaw += delta.x * _rotationSpeed * Time.deltaTime;
                _pitch -= delta.y * _rotationSpeed * Time.deltaTime;
                _pitch = Mathf.Clamp(_pitch, -89f, 89f);
                _mouseStart = Input.mousePosition;
                UpdateCameraPosition();
            }

            if (_isPanning)
            {
                Vector3 delta = Input.mousePosition - _panStart;
                Vector3 pan = _mainCamera.transform.right * (-delta.x * _panSpeed) +
                             _mainCamera.transform.up * (-delta.y * _panSpeed);
                _target.position += pan;
                _panStart = Input.mousePosition;
                UpdateCameraPosition();
            }

            float scroll = Input.GetAxis("Mouse ScrollWheel");
            if (Mathf.Abs(scroll) > 0.01f)
            {
                _currentDistance -= scroll * _zoomSpeed * _currentDistance;
                _currentDistance = Mathf.Clamp(_currentDistance, _minDistance, _maxDistance);
                UpdateCameraPosition();
            }
        }

        private void HandleKeyboardInput()
        {
            if (Input.GetKeyDown(KeyCode.R))
            {
                ResetCamera();
            }

            if (Input.GetKeyDown(KeyCode.Space))
            {
                UnityEngine.Debug.Log("Space pressed - start/pause simulation");
            }

            if (Input.GetControlKey() && Input.GetKeyDown(KeyCode.S))
            {
                UnityEngine.Debug.Log("Ctrl+S pressed - save screenshot");
            }
        }

        private void UpdateCameraPosition()
        {
            if (_mainCamera == null || _target == null) return;

            Quaternion rotation = Quaternion.Euler(_pitch, _yaw, 0f);
            Vector3 direction = rotation * Vector3.back;
            _mainCamera.transform.position = _target.position + direction * _currentDistance;
            _mainCamera.transform.LookAt(_target.position);
        }

        public void ResetCamera()
        {
            _currentDistance = 1.5f;
            _yaw = 45f;
            _pitch = 30f;
            _target.position = Vector3.zero;
            UpdateCameraPosition();
        }

        public void SetCameraDistance(float distance)
        {
            _currentDistance = Mathf.Clamp(distance, _minDistance, _maxDistance);
            UpdateCameraPosition();
        }

        public void UpdateGroundMaterial(GroundType groundType)
        {
            CurrentGroundType = groundType;

            if (_groundMaterial == null) return;

            Color groundColor;
            float smoothness;
            float metallic;

            switch (groundType)
            {
                case GroundType.DryAsphalt:
                    groundColor = new Color(0.15f, 0.15f, 0.15f);
                    smoothness = 0.1f;
                    metallic = 0f;
                    break;
                case GroundType.WetAsphalt:
                    groundColor = new Color(0.08f, 0.08f, 0.1f);
                    smoothness = 0.5f;
                    metallic = 0.1f;
                    break;
                case GroundType.DryTile:
                    groundColor = new Color(0.9f, 0.85f, 0.75f);
                    smoothness = 0.3f;
                    metallic = 0f;
                    break;
                case GroundType.WetTile:
                    groundColor = new Color(0.95f, 0.9f, 0.85f);
                    smoothness = 0.7f;
                    metallic = 0.05f;
                    break;
                case GroundType.Ice:
                    groundColor = new Color(0.85f, 0.95f, 1f);
                    smoothness = 0.9f;
                    metallic = 0.0f;
                    break;
                default:
                    groundColor = new Color(0.2f, 0.2f, 0.2f);
                    smoothness = 0.2f;
                    metallic = 0f;
                    break;
            }

            _groundMaterial.color = groundColor;
            _groundMaterial.SetFloat("_Glossiness", smoothness);
            _groundMaterial.SetFloat("_Metallic", metallic);

            if (_groundPlane != null)
            {
                var renderer = _groundPlane.GetComponent<Renderer>();
                if (renderer != null)
                {
                    renderer.material = _groundMaterial;
                }
            }

            UpdateLightingForGround(groundType);
        }

        private void UpdateLightingForGround(GroundType groundType)
        {
            switch (groundType)
            {
                case GroundType.Ice:
                    _ambientColor = new Color(0.3f, 0.35f, 0.4f);
                    _backgroundColor = new Color(0.15f, 0.18f, 0.25f);
                    break;
                case GroundType.WetAsphalt:
                case GroundType.WetTile:
                    _ambientColor = new Color(0.18f, 0.18f, 0.22f);
                    _backgroundColor = new Color(0.08f, 0.08f, 0.12f);
                    break;
                default:
                    _ambientColor = new Color(0.2f, 0.2f, 0.25f);
                    _backgroundColor = new Color(0.1f, 0.1f, 0.18f);
                    break;
            }

            if (_mainCamera != null)
            {
                _mainCamera.backgroundColor = _backgroundColor;
            }
            RenderSettings.ambientLight = _ambientColor;
        }

        public void FrameTarget()
        {
            if (_target == null) return;

            var renderers = _target.GetComponentsInChildren<Renderer>();
            if (renderers.Length == 0) return;

            Bounds bounds = renderers[0].bounds;
            foreach (var renderer in renderers)
            {
                bounds.Encapsulate(renderer.bounds);
            }

            float maxDim = Mathf.Max(bounds.size.x, bounds.size.y, bounds.size.z);
            _currentDistance = maxDim * 1.5f;
            _target.position = bounds.center;

            UpdateCameraPosition();
        }

        public void SetTarget(Transform target)
        {
            _target = target;
            UpdateCameraPosition();
        }
    }
}
