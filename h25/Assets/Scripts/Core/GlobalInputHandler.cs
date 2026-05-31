using UnityEngine;

namespace CitySimulator
{
    public class GlobalInputHandler : MonoBehaviour
    {
        public static GlobalInputHandler Instance { get; private set; }

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }

        private void Update()
        {
            if (Input.GetKeyDown(KeyCode.F1))
            {
                CameraSystem.Instance?.SetCameraMode(CameraMode.TopDown);
            }
            else if (Input.GetKeyDown(KeyCode.F2))
            {
                CameraSystem.Instance?.SetCameraMode(CameraMode.Follow);
            }
            else if (Input.GetKeyDown(KeyCode.F3))
            {
                CameraSystem.Instance?.SetCameraMode(CameraMode.FirstPerson);
            }

            if (Input.GetKeyDown(KeyCode.Tab))
            {
                CameraSystem.Instance?.CycleCameraMode();
            }

            if (Input.GetKeyDown(KeyCode.Escape))
            {
                if (VehicleGenerator.Instance != null)
                {
                    VehicleGenerator.Instance.TogglePlayerControl(false);
                }
            }

            if (Input.GetKeyDown(KeyCode.Space))
            {
                if (SimulationManager.Instance != null &&
                    (SimulationManager.Instance.State == SimulationState.Playing ||
                     SimulationManager.Instance.State == SimulationState.Paused))
                {
                    SimulationManager.Instance.TogglePause();
                }
            }
        }
    }
}
