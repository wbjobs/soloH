using UnityEngine;

namespace LanderSim.Core
{
    public class CameraController : MonoBehaviour
    {
        [Header("Movement Settings")]
        public float moveSpeed = 50f;
        public float fastMoveSpeed = 100f;
        public float rotationSpeed = 2f;
        public float scrollSpeed = 10f;

        [Header("Rotation Limits")]
        public float minPitch = 10f;
        public float maxPitch = 89f;

        [Header("Focus Settings")]
        public Vector3 focusPoint = Vector3.zero;
        public float orbitDistance = 200f;

        private float yaw = -135f;
        private float pitch = 45f;
        private bool isOrbiting = false;
        private bool isPanning = false;
        private Vector3 lastMousePosition;

        void Update()
        {
            HandleMouseInput();
            HandleKeyboardInput();
            HandleScrollWheel();
        }

        private void HandleMouseInput()
        {
            if (Input.GetMouseButtonDown(1))
            {
                isOrbiting = true;
                lastMousePosition = Input.mousePosition;
            }
            else if (Input.GetMouseButtonUp(1))
            {
                isOrbiting = false;
            }

            if (Input.GetMouseButtonDown(2))
            {
                isPanning = true;
                lastMousePosition = Input.mousePosition;
            }
            else if (Input.GetMouseButtonUp(2))
            {
                isPanning = false;
            }

            if (isOrbiting)
            {
                Vector3 delta = Input.mousePosition - lastMousePosition;
                yaw += delta.x * rotationSpeed;
                pitch -= delta.y * rotationSpeed;
                pitch = Mathf.Clamp(pitch, minPitch, maxPitch);
                lastMousePosition = Input.mousePosition;

                Quaternion rotation = Quaternion.Euler(pitch, yaw, 0);
                transform.position = focusPoint + rotation * (-Vector3.forward * orbitDistance);
                transform.rotation = rotation;
            }

            if (isPanning)
            {
                Vector3 delta = Input.mousePosition - lastMousePosition;
                Vector3 panMovement = new Vector3(
                    -delta.x * 0.1f,
                    0,
                    -delta.y * 0.1f
                );

                transform.Translate(panMovement, Space.Self);
                focusPoint = transform.position + transform.forward * orbitDistance;
                lastMousePosition = Input.mousePosition;
            }
        }

        private void HandleKeyboardInput()
        {
            float currentSpeed = Input.GetKey(KeyCode.LeftShift) ? fastMoveSpeed : moveSpeed;
            float deltaTime = Time.deltaTime;

            Vector3 movement = Vector3.zero;

            if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow))
            {
                movement += Vector3.forward;
            }
            if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow))
            {
                movement += Vector3.back;
            }
            if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow))
            {
                movement += Vector3.left;
            }
            if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow))
            {
                movement += Vector3.right;
            }
            if (Input.GetKey(KeyCode.E))
            {
                movement += Vector3.up;
            }
            if (Input.GetKey(KeyCode.Q))
            {
                movement += Vector3.down;
            }

            if (movement != Vector3.zero)
            {
                transform.Translate(movement * currentSpeed * deltaTime, Space.Self);
                focusPoint = transform.position + transform.forward * orbitDistance;
            }

            if (Input.GetKey(KeyCode.R) && Input.GetKey(KeyCode.LeftControl))
            {
                ResetCamera();
            }

            if (Input.GetKey(KeyCode.F))
            {
                focusPoint = Vector3.zero;
                orbitDistance = 200f;
                UpdateCameraPosition();
            }
        }

        private void HandleScrollWheel()
        {
            float scroll = Input.GetAxis("Mouse ScrollWheel");
            if (Mathf.Abs(scroll) > 0.01f)
            {
                orbitDistance -= scroll * scrollSpeed;
                orbitDistance = Mathf.Clamp(orbitDistance, 5f, 500f);
                UpdateCameraPosition();
            }
        }

        private void UpdateCameraPosition()
        {
            Quaternion rotation = Quaternion.Euler(pitch, yaw, 0);
            transform.position = focusPoint + rotation * (-Vector3.forward * orbitDistance);
            transform.rotation = rotation;
        }

        public void ResetCamera()
        {
            focusPoint = Vector3.zero;
            orbitDistance = 200f;
            yaw = -135f;
            pitch = 45f;
            UpdateCameraPosition();
        }

        public void FocusOnPoint(Vector3 point, float distance = 50f)
        {
            focusPoint = point;
            orbitDistance = distance;
            UpdateCameraPosition();
        }
    }
}
