using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class ReplaySystem : MonoBehaviour
    {
        public static ReplaySystem Instance { get; private set; }

        [SerializeField] private float replaySpeed = 1f;

        public bool IsReplaying { get; private set; }
        public RecordingData CurrentReplayData { get; private set; }
        public float CurrentReplayTime { get; private set; }

        private GameObject _replayVehicle;
        private Coroutine _replayCoroutine;

        public event Action<float> OnReplayProgress;
        public event Action OnReplayStarted;
        public event Action OnReplayPaused;
        public event Action OnReplayStopped;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        public bool LoadAndPlay(RecordingData recordingData)
        {
            if (recordingData == null || recordingData.trajectory == null || recordingData.trajectory.Count == 0)
            {
                SimulationManager.Instance.Log("Invalid recording data");
                return false;
            }

            StopReplay();

            CurrentReplayData = recordingData;
            CreateReplayVehicle(recordingData);

            SimulationManager.Instance.StartReplay();
            IsReplaying = true;
            _replayCoroutine = StartCoroutine(ReplayCoroutine());
            OnReplayStarted?.Invoke();
            SimulationManager.Instance.Log($"Replay started: {recordingData.recordedVehicleId}");

            return true;
        }

        private void CreateReplayVehicle(RecordingData recordingData)
        {
            if (_replayVehicle != null)
            {
                Destroy(_replayVehicle);
            }

            var startPoint = recordingData.trajectory[0];
            _replayVehicle = new GameObject("ReplayVehicle");
            _replayVehicle.transform.position = startPoint.position.ToVector3();
            _replayVehicle.transform.rotation = Quaternion.Euler(startPoint.rotation.ToVector3());

            GameObject body = GameObject.CreatePrimitive(PrimitiveType.Cube);
            body.transform.SetParent(_replayVehicle.transform);
            body.transform.localPosition = new Vector3(0, 0.5f, 0);
            body.transform.localScale = new Vector3(1.8f, 1f, 4.5f);
            var bodyMat = new Material(Shader.Find("Standard"));
            bodyMat.color = new Color(0f, 0.8f, 1f, 0.7f);
            bodyMat.SetFloat("_Mode", 3);
            bodyMat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            bodyMat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            bodyMat.SetInt("_ZWrite", 0);
            bodyMat.DisableKeyword("_ALPHATEST_ON");
            bodyMat.EnableKeyword("_ALPHABLEND_ON");
            bodyMat.DisableKeyword("_ALPHAPREMULTIPLY_ON");
            bodyMat.renderQueue = 3000;
            body.GetComponent<MeshRenderer>().material = bodyMat;
            Destroy(body.GetComponent<BoxCollider>());

            _replayVehicle.AddComponent<BoxCollider>().center = new Vector3(0, 0.5f, 0);
            _replayVehicle.GetComponent<BoxCollider>().size = new Vector3(1.8f, 1f, 4.5f);

            if (CameraSystem.Instance != null)
            {
                CameraSystem.Instance.SetTarget(_replayVehicle.transform);
            }
        }

        private IEnumerator ReplayCoroutine()
        {
            CurrentReplayTime = 0f;
            int currentIndex = 0;
            var trajectory = CurrentReplayData.trajectory;

            while (currentIndex < trajectory.Count - 1)
            {
                while (SimulationManager.Instance.State == SimulationState.Paused)
                {
                    yield return null;
                }

                if (SimulationManager.Instance.State != SimulationState.Replaying)
                {
                    yield break;
                }

                float timeStep = Time.deltaTime * replaySpeed;
                CurrentReplayTime += timeStep;

                while (currentIndex < trajectory.Count - 1 &&
                       trajectory[currentIndex + 1].timestamp <= CurrentReplayTime)
                {
                    currentIndex++;
                }

                if (currentIndex >= trajectory.Count - 1)
                {
                    SetVehiclePose(trajectory[trajectory.Count - 1]);
                    break;
                }

                var point1 = trajectory[currentIndex];
                var point2 = trajectory[currentIndex + 1];
                float t = Mathf.InverseLerp(point1.timestamp, point2.timestamp, CurrentReplayTime);

                Vector3 pos = Vector3.Lerp(point1.position.ToVector3(), point2.position.ToVector3(), t);
                Quaternion rot = Quaternion.Slerp(
                    Quaternion.Euler(point1.rotation.ToVector3()),
                    Quaternion.Euler(point2.rotation.ToVector3()),
                    t);

                _replayVehicle.transform.position = pos;
                _replayVehicle.transform.rotation = rot;

                float progress = (float)currentIndex / (trajectory.Count - 1);
                OnReplayProgress?.Invoke(progress);

                yield return null;
            }

            SimulationManager.Instance.Log("Replay completed");
            OnReplayStopped?.Invoke();
            IsReplaying = false;
            SimulationManager.Instance.StopReplay();
        }

        private void SetVehiclePose(TrajectoryPoint point)
        {
            _replayVehicle.transform.position = point.position.ToVector3();
            _replayVehicle.transform.rotation = Quaternion.Euler(point.rotation.ToVector3());
        }

        public void PauseReplay()
        {
            if (IsReplaying)
            {
                SimulationManager.Instance.Pause();
                OnReplayPaused?.Invoke();
            }
        }

        public void ResumeReplay()
        {
            if (IsReplaying && SimulationManager.Instance.State == SimulationState.Paused)
            {
                SimulationManager.Instance.Play();
            }
        }

        public void StopReplay()
        {
            if (_replayCoroutine != null)
            {
                StopCoroutine(_replayCoroutine);
                _replayCoroutine = null;
            }

            if (_replayVehicle != null)
            {
                Destroy(_replayVehicle);
                _replayVehicle = null;
            }

            IsReplaying = false;
            CurrentReplayData = null;
            CurrentReplayTime = 0f;

            if (SimulationManager.Instance != null && SimulationManager.Instance.State == SimulationState.Replaying)
            {
                SimulationManager.Instance.StopReplay();
            }

            OnReplayStopped?.Invoke();
        }

        public void SetReplaySpeed(float speed)
        {
            replaySpeed = Mathf.Clamp(speed, 0.1f, 5f);
        }

        public void JumpToTime(float time)
        {
            if (CurrentReplayData == null) return;

            CurrentReplayTime = Mathf.Clamp(time, 0, CurrentReplayData.duration);

            for (int i = 0; i < CurrentReplayData.trajectory.Count - 1; i++)
            {
                if (CurrentReplayData.trajectory[i].timestamp <= CurrentReplayTime &&
                    CurrentReplayData.trajectory[i + 1].timestamp >= CurrentReplayTime)
                {
                    var point1 = CurrentReplayData.trajectory[i];
                    var point2 = CurrentReplayData.trajectory[i + 1];
                    float t = Mathf.InverseLerp(point1.timestamp, point2.timestamp, CurrentReplayTime);

                    Vector3 pos = Vector3.Lerp(point1.position.ToVector3(), point2.position.ToVector3(), t);
                    Quaternion rot = Quaternion.Slerp(
                        Quaternion.Euler(point1.rotation.ToVector3()),
                        Quaternion.Euler(point2.rotation.ToVector3()),
                        t);

                    _replayVehicle.transform.position = pos;
                    _replayVehicle.transform.rotation = rot;
                    break;
                }
            }
        }
    }
}
