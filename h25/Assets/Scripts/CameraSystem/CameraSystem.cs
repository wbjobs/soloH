using UnityEngine;

namespace CitySimulator
{
    public class CameraSystem : MonoBehaviour
    {
        public static CameraSystem Instance { get; private set; }

        [SerializeField] private Camera mainCamera;
        [SerializeField] private Transform target;
        [SerializeField] private CameraMode currentMode = CameraMode.TopDown;

        [Header("Top Down Settings")]
        [SerializeField] private float topDownHeight = 100f;
        [SerializeField] private float topDownDistance = 100f;
        [SerializeField] private float topDownMoveSpeed = 50f;
        [SerializeField] private float topDownZoomSpeed = 20f;

        [Header("Follow Settings")]
        [SerializeField] private Vector3 followOffset = new Vector3(0f, 8f, -15f);
        [SerializeField] private float followSmoothTime = 0.1f;
        [SerializeField] private float followRotationSmoothTime = 0.2f;

        [Header("First Person Settings")]
        [SerializeField] private Vector3 firstPersonOffset = new Vector3(0f, 1.5f, 0.2f);

        [Header("Edge Detection")]
        [SerializeField] private float edgeScrollSpeed = 30f;
        [SerializeField] private float edgeBorder = 30f;

        private Vector3 _targetPosition;
        private Quaternion _targetRotation;
        private Vector3 _currentVelocity;
        private Vector3 _topDownPosition;
        private float _topDownZoom = 50f;
        private Vector3 _freeRoamingPosition;
        private bool _isRoaming = false;

        public CameraMode CurrentMode => currentMode;
        public Camera MainCamera => mainCamera;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            if (mainCamera == null)
            {
                mainCamera = Camera.main;
                if (mainCamera == null)
                {
                    mainCamera = GetComponentInChildren<Camera>();
                }
            }
        }

        private void Start()
        {
            mainCamera.transform.position = new Vector3(0, topDownHeight, -topDownDistance);
            mainCamera.transform.rotation = Quaternion.Euler(60f, 0, 0);
            _topDownPosition = mainCamera.transform.position;
        }

        private void Update()
        {
            if (SimulationManager.Instance == null) return;

            HandleCameraInput();

            switch (currentMode)
            {
                case CameraMode.TopDown:
                    UpdateTopDownCamera();
                    break;
                case CameraMode.Follow:
                    UpdateFollowCamera();
                    break;
                case CameraMode.FirstPerson:
                    UpdateFirstPersonCamera();
                    break;
            }
        }

        private void HandleCameraInput()
        {
            if (Input.GetKeyDown(KeyCode.F1))
            {
                SetCameraMode(CameraMode.TopDown);
            }
            else if (Input.GetKeyDown(KeyCode.F2))
            {
                SetCameraMode(CameraMode.Follow);
            }
            else if (Input.GetKeyDown(KeyCode.F3))
            {
                SetCameraMode(CameraMode.FirstPerson);
            }

            if (Input.GetKeyDown(KeyCode.Tab))
            {
                CycleCameraMode();
            }

            if (Input.GetKey(KeyCode.LeftAlt) && Input.GetMouseButtonDown(0))
            {
                _isRoaming = !_isRoaming;
                SimulationManager.Instance.Log(_isRoaming ? "Free camera mode enabled" : "Free camera mode disabled");
            }
        }

        public void SetCameraMode(CameraMode mode)
        {
            currentMode = mode;
            SimulationManager.Instance.Log($"Camera mode: {mode}");
        }

        public void CycleCameraMode()
        {
            int nextMode = ((int)currentMode + 1) % 3;
            SetCameraMode((CameraMode)nextMode);
        }

        public void SetTarget(Transform newTarget)
        {
            target = newTarget;
        }

        private void UpdateTopDownCamera()
        {
            if (_isRoaming)
            {
                HandleFreeCameraMovement();
                return;
            }

            if (target != null)
            {
                _topDownPosition = new Vector3(
                    target.position.x,
                    target.position.y + topDownHeight,
                    target.position.z - topDownDistance
                );
            }
            else
            {
                HandleEdgeScrolling();
                HandleZoom();
            }

            mainCamera.transform.position = Vector3.Lerp(mainCamera.transform.position, _topDownPosition, Time.deltaTime * 5f);
            mainCamera.transform.rotation = Quaternion.Euler(60f, 0, 0);
        }

        private void HandleEdgeScrolling()
        {
            Vector3 moveDir = Vector3.zero;
            Vector3 mousePos = Input.mousePosition;

            if (mousePos.x < edgeBorder) moveDir.x = -1;
            if (mousePos.x > Screen.width - edgeBorder) moveDir.x = 1;
            if (mousePos.y < edgeBorder) moveDir.z = -1;
            if (mousePos.y > Screen.height - edgeBorder) moveDir.z = 1;

            if (moveDir != Vector3.zero)
            {
                Vector3 forward = mainCamera.transform.forward;
                forward.y = 0;
                forward.Normalize();
                Vector3 right = mainCamera.transform.right;
                right.y = 0;
                right.Normalize();

                Vector3 move = (forward * moveDir.z + right * moveDir.x).normalized;
                _topDownPosition += move * topDownMoveSpeed * Time.deltaTime;
            }
        }

        private void HandleZoom()
        {
            float scroll = Input.GetAxis("Mouse ScrollWheel");
            if (scroll != 0)
            {
                _topDownZoom = Mathf.Clamp(_topDownZoom - scroll * topDownZoomSpeed, 20f, 200f);
                topDownHeight = _topDownZoom;
                topDownDistance = _topDownZoom * 0.8f;
            }
        }

        private void HandleFreeCameraMovement()
        {
            Vector3 moveDir = Vector3.zero;

            if (Input.GetKey(KeyCode.W)) moveDir += mainCamera.transform.forward;
            if (Input.GetKey(KeyCode.S)) moveDir -= mainCamera.transform.forward;
            if (Input.GetKey(KeyCode.A)) moveDir -= mainCamera.transform.right;
            if (Input.GetKey(KeyCode.D)) moveDir += mainCamera.transform.right;
            if (Input.GetKey(KeyCode.Q)) moveDir -= Vector3.up;
            if (Input.GetKey(KeyCode.E)) moveDir += Vector3.up;

            float speed = Input.GetKey(KeyCode.LeftShift) ? topDownMoveSpeed * 2 : topDownMoveSpeed;
            mainCamera.transform.position += moveDir.normalized * speed * Time.deltaTime;

            if (Input.GetMouseButton(1))
            {
                float mouseX = Input.GetAxis("Mouse X");
                float mouseY = Input.GetAxis("Mouse Y");
                Vector3 rot = mainCamera.transform.eulerAngles;
                rot.y += mouseX * 2f;
                rot.x -= mouseY * 2f;
                mainCamera.transform.eulerAngles = rot;
            }
        }

        private void UpdateFollowCamera()
        {
            if (target == null)
            {
                SetCameraMode(CameraMode.TopDown);
                return;
            }

            Vector3 desiredPos = target.position + target.TransformDirection(followOffset);
            mainCamera.transform.position = Vector3.SmoothDamp(mainCamera.transform.position, desiredPos, ref _currentVelocity, followSmoothTime);

            Quaternion desiredRot = Quaternion.LookRotation(target.position - mainCamera.transform.position);
            mainCamera.transform.rotation = Quaternion.Slerp(mainCamera.transform.rotation, desiredRot, Time.deltaTime / followRotationSmoothTime);
        }

        private void UpdateFirstPersonCamera()
        {
            if (target == null)
            {
                SetCameraMode(CameraMode.TopDown);
                return;
            }

            Vector3 desiredPos = target.position + target.TransformDirection(firstPersonOffset);
            mainCamera.transform.position = Vector3.Lerp(mainCamera.transform.position, desiredPos, Time.deltaTime * 10f);
            mainCamera.transform.rotation = Quaternion.Slerp(mainCamera.transform.rotation, target.rotation, Time.deltaTime * 10f);
        }

        public void ResetCamera()
        {
            SetCameraMode(CameraMode.TopDown);
            mainCamera.transform.position = new Vector3(0, topDownHeight, -topDownDistance);
            mainCamera.transform.rotation = Quaternion.Euler(60f, 0, 0);
            _topDownPosition = mainCamera.transform.position;
        }
    }
}
