using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class SimulationManager : MonoBehaviour
    {
        public static SimulationManager Instance { get; private set; }

        public SceneParameters CurrentParameters { get; private set; }
        public SimulationState State { get; private set; } = SimulationState.Stopped;

        public event Action<SimulationState> OnStateChanged;
        public event Action<SceneParameters> OnParametersChanged;
        public event Action<string> OnLog;

        [SerializeField] private SceneParameters defaultParameters = new SceneParameters();

        private float _simulationTime;
        private bool _isPaused;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            DontDestroyOnLoad(gameObject);
            CurrentParameters = defaultParameters.Clone();
        }

        private void Update()
        {
            if (State == SimulationState.Playing)
            {
                _simulationTime += Time.deltaTime;
            }
        }

        public void SetParameters(SceneParameters parameters)
        {
            CurrentParameters = parameters.Clone();
            OnParametersChanged?.Invoke(CurrentParameters);
            Log("Parameters updated");
        }

        public void GenerateScene()
        {
            if (State != SimulationState.Stopped)
            {
                ClearScene();
            }
            SetState(SimulationState.Playing);
            _simulationTime = 0;
            Log("Scene generation started...");
            SceneGenerator.Instance.Generate(CurrentParameters);
            Log("Scene generation completed");
        }

        public void ClearScene()
        {
            SetState(SimulationState.Stopped);
            _simulationTime = 0;
            SceneGenerator.Instance.Clear();
            Log("Scene cleared");
        }

        public void Play()
        {
            if (State == SimulationState.Paused || State == SimulationState.Stopped)
            {
                SetState(SimulationState.Playing);
                Time.timeScale = 1f;
                Log("Simulation resumed");
            }
        }

        public void Pause()
        {
            if (State == SimulationState.Playing)
            {
                SetState(SimulationState.Paused);
                Time.timeScale = 0f;
                Log("Simulation paused");
            }
        }

        public void TogglePause()
        {
            if (State == SimulationState.Playing)
                Pause();
            else if (State == SimulationState.Paused)
                Play();
        }

        public void StartReplay()
        {
            SetState(SimulationState.Replaying);
            Log("Replay started");
        }

        public void StopReplay()
        {
            SetState(SimulationState.Stopped);
            Log("Replay stopped");
        }

        private void SetState(SimulationState newState)
        {
            if (State != newState)
            {
                State = newState;
                OnStateChanged?.Invoke(State);
            }
        }

        public float GetSimulationTime()
        {
            return _simulationTime;
        }

        public void Log(string message)
        {
            OnLog?.Invoke($"[{DateTime.Now:HH:mm:ss}] {message}");
            Debug.Log(message);
        }
    }
}
