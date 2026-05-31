using UnityEngine;

namespace FlowVisualization.Interaction
{
    [RequireComponent(typeof(Camera))]
    public class FlyCameraController : MonoBehaviour
    {
        [Header("Movement Settings")]
        public float MovementSpeed = 5.0f;
        public float FastMovementSpeed = 15.0f;
        public float MovementSmoothing = 0.1f;

        [Header("Rotation Settings")]
        public float MouseSensitivity = 2.0f;
        public float RotationSmoothing = 0.1f;

        [Header("Input")]
        public KeyCode ForwardKey = KeyCode.W;
        public KeyCode BackwardKey = KeyCode.S;
        public KeyCode LeftKey = KeyCode.A;
        public KeyCode RightKey = KeyCode.D;
        public KeyCode UpKey = KeyCode.E;
        public KeyCode DownKey = KeyCode.Q;
        public KeyCode FastMoveKey = KeyCode.LeftShift;

        private Camera _camera;
        private Vector3 _targetPosition;
        private Quaternion _targetRotation;
        private float _yaw;
        private float _pitch;
        private bool _isRotating;
        private Vector3 _currentVelocity;
        private Vector2 _currentRotationVelocity;

        private void Awake()
        {
            _camera = GetComponent<Camera>();
            _targetPosition = transform.position;
            _targetRotation = transform.rotation;
            _yaw = transform.eulerAngles.y;
            _pitch = transform.eulerAngles.x;
        }

        private void Update()
        {
            HandleRotationInput();
            HandleMovementInput();
            UpdateTransform();
        }

        private void HandleRotationInput()
        {
            if (Input.GetMouseButton(1))
            {
                Cursor.visible = false;
                Cursor.lockState = CursorLockMode.Locked;
                _isRotating = true;

                float mouseX = Input.GetAxis("Mouse X") * MouseSensitivity;
                float mouseY = Input.GetAxis("Mouse Y") * MouseSensitivity;

                _yaw += mouseX;
                _pitch -= mouseY;
                _pitch = Mathf.Clamp(_pitch, -89f, 89f);

                _targetRotation = Quaternion.Euler(_pitch, _yaw, 0f);
            }
            else
            {
                Cursor.visible = true;
                Cursor.lockState = CursorLockMode.None;
                _isRotating = false;
            }
        }

        private void HandleMovementInput()
        {
            Vector3 moveDirection = Vector3.zero;
            float currentSpeed = Input.GetKey(FastMoveKey) ? FastMovementSpeed : MovementSpeed;

            if (Input.GetKey(ForwardKey)) moveDirection += transform.forward;
            if (Input.GetKey(BackwardKey)) moveDirection -= transform.forward;
            if (Input.GetKey(LeftKey)) moveDirection -= transform.right;
            if (Input.GetKey(RightKey)) moveDirection += transform.right;
            if (Input.GetKey(UpKey)) moveDirection += Vector3.up;
            if (Input.GetKey(DownKey)) moveDirection -= Vector3.up;

            if (moveDirection.sqrMagnitude > 0f)
            {
                moveDirection.Normalize();
                _targetPosition += moveDirection * currentSpeed * Time.deltaTime;
            }
        }

        private void UpdateTransform()
        {
            transform.position = Vector3.SmoothDamp(
                transform.position,
                _targetPosition,
                ref _currentVelocity,
                MovementSmoothing
            );

            transform.rotation = Quaternion.Slerp(
                transform.rotation,
                _targetRotation,
                1f - Mathf.Exp(-Time.deltaTime / RotationSmoothing)
            );
        }

        public void FocusOnPoint(Vector3 point, float distance = 2f)
        {
            Vector3 direction = (transform.position - point).normalized;
            _targetPosition = point + direction * distance;
            _yaw = Mathf.Atan2(direction.x, direction.z) * Mathf.Rad2Deg;
            _pitch = -Mathf.Asin(direction.y) * Mathf.Rad2Deg;
            _targetRotation = Quaternion.Euler(_pitch, _yaw, 0f);
        }

        public void ResetCamera(Vector3 position, Quaternion rotation)
        {
            _targetPosition = position;
            _targetRotation = rotation;
            _yaw = rotation.eulerAngles.y;
            _pitch = rotation.eulerAngles.x;
        }
    }
}
