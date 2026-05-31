using UnityEngine;

namespace CitySimulator
{
    public class CollisionDetector : MonoBehaviour
    {
        public string VehicleId { get; set; }

        private Rigidbody _rb;

        private void Awake()
        {
            _rb = GetComponent<Rigidbody>();
        }

        private void OnCollisionEnter(Collision collision)
        {
            if (SimulationManager.Instance == null) return;
            if (SimulationManager.Instance.State != SimulationState.Playing) return;

            var otherVehicle = collision.collider.GetComponent<CollisionDetector>();
            string otherId = otherVehicle != null ? otherVehicle.VehicleId : collision.collider.name;

            foreach (ContactPoint contact in collision.contacts)
            {
                var collisionEvent = new CollisionEvent
                {
                    timestamp = SimulationManager.Instance.GetSimulationTime(),
                    objectAId = VehicleId,
                    objectBId = otherId,
                    position = new Vector3Data(contact.point),
                    normal = new Vector3Data(contact.normal),
                    relativeVelocity = collision.relativeVelocity.magnitude
                };

                TrajectoryRecorder.Instance?.RecordCollision(collisionEvent);

                string msg = $"Collision: {VehicleId} <-> {otherId} | Speed: {collision.relativeVelocity.magnitude:F1} m/s";
                SimulationManager.Instance.Log(msg);
                break;
            }
        }
    }
}
