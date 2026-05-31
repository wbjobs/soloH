using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace CitySimulator
{
    public class TrajectoryRecorder : MonoBehaviour
    {
        public static TrajectoryRecorder Instance { get; private set; }

        [SerializeField] private float recordInterval = 0.1f;

        public RecordingData CurrentRecording { get; private set; }
        public List<CollisionEvent> Collisions { get; private set; } = new List<CollisionEvent>();
        public bool IsRecording { get; private set; }

        private float _lastRecordTime;
        private Transform _targetVehicle;
        private string _sceneId;

        public event Action<TrajectoryPoint> OnTrajectoryPointRecorded;
        public event Action<CollisionEvent> OnCollisionRecorded;
        public event Action<RecordingData> OnRecordingSaved;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        private void Update()
        {
            if (!IsRecording) return;
            if (SimulationManager.Instance == null) return;
            if (SimulationManager.Instance.State != SimulationState.Playing) return;

            if (Time.time - _lastRecordTime >= recordInterval)
            {
                RecordTrajectoryPoint();
                _lastRecordTime = Time.time;
            }
        }

        public void StartRecording(Transform targetVehicle, string sceneId)
        {
            if (targetVehicle == null) return;

            _targetVehicle = targetVehicle;
            _sceneId = sceneId;
            IsRecording = true;
            _lastRecordTime = 0;

            CurrentRecording = new RecordingData
            {
                sceneId = sceneId,
                recordedVehicleId = targetVehicle.name,
                trajectory = new List<TrajectoryPoint>(),
                collisions = new List<CollisionEvent>()
            };

            Collisions.Clear();
            SimulationManager.Instance.Log($"Started recording: {targetVehicle.name}");
        }

        public void StopRecording()
        {
            if (!IsRecording) return;

            IsRecording = false;
            if (CurrentRecording != null)
            {
                CurrentRecording.duration = SimulationManager.Instance.GetSimulationTime();
                CurrentRecording.collisions = new List<CollisionEvent>(Collisions);
            }
            SimulationManager.Instance.Log($"Recording stopped. Duration: {CurrentRecording?.duration:F1}s, Points: {CurrentRecording?.trajectory.Count}");
        }

        private void RecordTrajectoryPoint()
        {
            if (_targetVehicle == null || CurrentRecording == null) return;

            float speed = 0f;
            float steering = 0f;
            float throttle = 0f;
            float brake = 0f;

            var playerControl = _targetVehicle.GetComponent<PlayerVehicleController>();
            var aiControl = _targetVehicle.GetComponent<VehicleAIController>();

            if (playerControl != null && playerControl.enabled)
            {
                speed = playerControl.CurrentSpeed;
                steering = playerControl.SteeringAngle;
                throttle = playerControl.Throttle;
                brake = playerControl.Brake;
            }
            else if (aiControl != null)
            {
                speed = aiControl.CurrentSpeed;
                steering = aiControl.SteeringAngle;
                throttle = aiControl.Throttle;
                brake = aiControl.Brake;
            }

            var point = new TrajectoryPoint
            {
                timestamp = SimulationManager.Instance.GetSimulationTime(),
                position = new Vector3Data(_targetVehicle.position),
                rotation = new Vector3Data(_targetVehicle.rotation.eulerAngles),
                speed = speed,
                steeringAngle = steering,
                throttle = throttle,
                brake = brake
            };

            CurrentRecording.trajectory.Add(point);
            OnTrajectoryPointRecorded?.Invoke(point);
        }

        public void RecordCollision(CollisionEvent collisionEvent)
        {
            if (!IsRecording || CurrentRecording == null) return;

            lock (Collisions)
            {
                Collisions.Add(collisionEvent);
            }
            OnCollisionRecorded?.Invoke(collisionEvent);
        }

        public void SaveRecording(string filePath)
        {
            if (CurrentRecording == null)
            {
                SimulationManager.Instance.Log("No recording to save");
                return;
            }

            try
            {
                CurrentRecording.duration = SimulationManager.Instance.GetSimulationTime();
                string json = JsonUtility.ToJson(CurrentRecording, true);
                File.WriteAllText(filePath, json);
                OnRecordingSaved?.Invoke(CurrentRecording);
                SimulationManager.Instance.Log($"Recording saved to: {filePath}");
            }
            catch (Exception e)
            {
                SimulationManager.Instance.Log($"Failed to save recording: {e.Message}");
            }
        }

        public RecordingData LoadRecording(string filePath)
        {
            try
            {
                string json = File.ReadAllText(filePath);
                var data = JsonUtility.FromJson<RecordingData>(json);
                SimulationManager.Instance.Log($"Recording loaded: {data.recordedVehicleId}, Duration: {data.duration:F1}s");
                return data;
            }
            catch (Exception e)
            {
                SimulationManager.Instance.Log($"Failed to load recording: {e.Message}");
                return null;
            }
        }

        public RecordingData GetCurrentRecording()
        {
            if (CurrentRecording == null) return null;
            var copy = new RecordingData
            {
                sceneId = CurrentRecording.sceneId,
                duration = CurrentRecording.duration,
                recordedVehicleId = CurrentRecording.recordedVehicleId,
                trajectory = new List<TrajectoryPoint>(CurrentRecording.trajectory),
                collisions = new List<CollisionEvent>(CurrentRecording.collisions)
            };
            return copy;
        }

        public string GenerateRecordingFilename()
        {
            string timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            return $"recording_{timestamp}.json";
        }
    }
}
