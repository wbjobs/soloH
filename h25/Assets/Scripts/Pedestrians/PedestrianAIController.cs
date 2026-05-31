using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class PedestrianAIController : MonoBehaviour
    {
        [SerializeField] private float walkingSpeed = 1.2f;
        [SerializeField] private float rotationSpeed = 3f;

        private List<Vector3> _path;
        private int _currentWaypoint;
        private Rigidbody _rb;
        private Color _skinColor;
        private Color _clothingColor;
        private Animator _animator;

        public float WalkingSpeed => walkingSpeed;

        public void Initialize(List<Vector3> path, float speed, Color skinColor, Color clothingColor)
        {
            _path = path;
            walkingSpeed = speed;
            _skinColor = skinColor;
            _clothingColor = clothingColor;
            _currentWaypoint = 0;
            _rb = GetComponent<Rigidbody>();
        }

        private void Update()
        {
            if (SimulationManager.Instance == null) return;
            if (SimulationManager.Instance.State != SimulationState.Playing) return;
            if (_path == null || _path.Count < 2) return;

            UpdateWalking();
        }

        private void UpdateWalking()
        {
            if (_currentWaypoint >= _path.Count - 1)
            {
                _currentWaypoint = 0;
                _path.Reverse();
            }

            Vector3 targetPos = _path[_currentWaypoint + 1];
            targetPos.y = transform.position.y;

            Vector3 toTarget = targetPos - transform.position;
            float distance = toTarget.magnitude;

            if (distance < 0.5f)
            {
                _currentWaypoint++;
                return;
            }

            Vector3 desiredDir = toTarget.normalized;
            Quaternion targetRot = Quaternion.LookRotation(desiredDir);

            transform.rotation = Quaternion.Slerp(transform.rotation, targetRot, rotationSpeed * Time.deltaTime);

            Vector3 moveDir = transform.forward * walkingSpeed;
            _rb.MovePosition(_rb.position + moveDir * Time.deltaTime);
        }
    }
}
