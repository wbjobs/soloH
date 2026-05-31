using UnityEngine;

namespace CitySimulator
{
    public class PlayerVehicleController : MonoBehaviour
    {
        [SerializeField] private float maxSpeed = 25f;
        [SerializeField] private float acceleration = 10f;
        [SerializeField] private float brakeForce = 15f;
        [SerializeField] private float steeringSensitivity = 2f;
        [SerializeField] private float maxSteerAngle = 30f;
        [SerializeField] private float downForce = 100f;

        private Rigidbody _rb;
        private float _horizontalInput;
        private float _verticalInput;
        private float _currentSpeed;
        private float _steerAngle;
        private bool _isBraking;

        public float CurrentSpeed => _currentSpeed;
        public float SteeringAngle => _steerAngle;
        public float Throttle { get; private set; }
        public float Brake { get; private set; }

        private void Awake()
        {
            _rb = GetComponent<Rigidbody>();
            if (_rb == null)
            {
                _rb = gameObject.AddComponent<Rigidbody>();
            }
            _rb.mass = 1500f;
            _rb.centerOfMass = new Vector3(0, -0.3f, 0);
            _rb.drag = 0.5f;
            _rb.angularDrag = 2f;
        }

        private void Update()
        {
            if (!enabled) return;
            if (SimulationManager.Instance == null) return;
            if (SimulationManager.Instance.State != SimulationState.Playing) return;

            HandleInput();
        }

        private void FixedUpdate()
        {
            if (!enabled) return;
            if (SimulationManager.Instance == null) return;
            if (SimulationManager.Instance.State != SimulationState.Playing) return;

            _currentSpeed = _rb.velocity.magnitude;

            ApplySteering();
            ApplyAcceleration();
            ApplyBraking();
            ApplyDownForce();

            if (CameraSystem.Instance != null)
            {
                CameraSystem.Instance.SetTarget(transform);
            }
        }

        private void HandleInput()
        {
            _horizontalInput = Input.GetAxis("Horizontal");
            _verticalInput = Input.GetAxis("Vertical");
            _isBraking = Input.GetKey(KeyCode.Space) || _verticalInput < -0.1f;

            if (Input.GetKeyDown(KeyCode.R) && Input.GetKey(KeyCode.LeftControl))
            {
                ResetVehiclePosition();
            }
        }

        private void ApplySteering()
        {
            float speedFactor = Mathf.Clamp01(_currentSpeed / 10f);
            float targetSteer = _horizontalInput * maxSteerAngle * steeringSensitivity * speedFactor;
            _steerAngle = Mathf.Lerp(_steerAngle, targetSteer, Time.fixedDeltaTime * 5f);

            Quaternion targetRotation = transform.rotation * Quaternion.Euler(0, _steerAngle * Time.fixedDeltaTime * 10f, 0);
            _rb.MoveRotation(Quaternion.Slerp(_rb.rotation, targetRotation, Time.fixedDeltaTime * 2f));
        }

        private void ApplyAcceleration()
        {
            if (_verticalInput > 0.1f && !_isBraking)
            {
                if (_currentSpeed < maxSpeed)
                {
                    Vector3 force = transform.forward * _verticalInput * acceleration * _rb.mass;
                    _rb.AddForce(force, ForceMode.Force);
                    Throttle = Mathf.Clamp01(_verticalInput);
                }
                else
                {
                    Throttle = 0f;
                }
                Brake = 0f;
            }
            else if (_verticalInput <= 0.1f)
            {
                Throttle = 0f;
            }
        }

        private void ApplyBraking()
        {
            if (_isBraking || _verticalInput < -0.1f)
            {
                float brakeAmount = _isBraking ? 1f : Mathf.Abs(_verticalInput);
                Vector3 brakeForce = -_rb.velocity.normalized * brakeForce * _rb.mass * brakeAmount;
                _rb.AddForce(brakeForce, ForceMode.Force);
                Brake = brakeAmount;
                if (!_isBraking)
                {
                    Throttle = 0f;
                }
            }
            else
            {
                Brake = 0f;
            }
        }

        private void ApplyDownForce()
        {
            _rb.AddForce(Vector3.down * downForce * _rb.mass);
        }

        private void ResetVehiclePosition()
        {
            Vector3 upPosition = transform.position + Vector3.up * 2f;
            _rb.velocity = Vector3.zero;
            _rb.angularVelocity = Vector3.zero;
            transform.position = upPosition;
            transform.rotation = Quaternion.Euler(0, transform.rotation.eulerAngles.y, 0);
            SimulationManager.Instance.Log("Vehicle position reset");
        }

        public void SetSpeed(float speed)
        {
            if (_rb != null)
            {
                _rb.velocity = transform.forward * speed;
            }
        }

        public void SetPositionRotation(Vector3 pos, Quaternion rot)
        {
            if (_rb != null)
            {
                _rb.MovePosition(pos);
                _rb.MoveRotation(rot);
            }
            else
            {
                transform.position = pos;
                transform.rotation = rot;
            }
        }
    }
}
