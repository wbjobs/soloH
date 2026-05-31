using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class UIController : MonoBehaviour
    {
        [SerializeField] private bool showUI = true;
        [SerializeField] private int uiWidth = 350;

        private SceneParameters _parameters;
        private Vector2 _scrollPos;
        private Vector2 _logScrollPos;
        private List<string> _logs = new List<string>();
        private bool _showControls = true;
        private bool _showRecording = false;
        private bool _showExport = false;
        private bool _showCornerCases = false;
        private bool _showAdvanced = false;
        private bool _playerControlEngaged = false;
        private string _statusMessage = "";

        private Texture2D _panelBackground;
        private GUIStyle _panelStyle;
        private GUIStyle _headerStyle;
        private GUIStyle _buttonStyle;
        private GUIStyle _sliderStyle;

        private void Start()
        {
            _parameters = new SceneParameters();
            InitializeStyles();

            if (SimulationManager.Instance != null)
            {
                SimulationManager.Instance.OnLog += AddLog;
                SimulationManager.Instance.OnStateChanged += OnStateChanged;
            }
        }

        private void InitializeStyles()
        {
            _panelBackground = new Texture2D(1, 1);
            _panelBackground.SetPixel(0, 0, new Color(0, 0, 0, 0.85f));
            _panelBackground.Apply();

            _panelStyle = new GUIStyle();
            _panelStyle.normal.background = _panelBackground;
            _panelStyle.padding = new RectOffset(15, 15, 15, 15);

            _headerStyle = new GUIStyle(GUI.skin.label);
            _headerStyle.fontSize = 16;
            _headerStyle.fontStyle = FontStyle.Bold;
            _headerStyle.normal.textColor = Color.white;

            _buttonStyle = new GUIStyle(GUI.skin.button);
            _buttonStyle.fontSize = 12;
            _buttonStyle.fixedHeight = 28;
            _buttonStyle.normal.textColor = Color.white;

            _sliderStyle = new GUIStyle(GUI.skin.horizontalSlider);
            _sliderStyle.fixedHeight = 20;
        }

        private void Update()
        {
            if (Input.GetKeyDown(KeyCode.H))
            {
                showUI = !showUI;
            }

            if (Input.GetKeyDown(KeyCode.Space) && SimulationManager.Instance != null)
            {
                if (SimulationManager.Instance.State == SimulationState.Playing ||
                    SimulationManager.Instance.State == SimulationState.Paused)
                {
                    SimulationManager.Instance.TogglePause();
                }
            }

            if (Input.GetKeyDown(KeyCode.E) && !_playerControlEngaged)
            {
                EngagePlayerControl();
            }
            else if (Input.GetKeyDown(KeyCode.Escape) && _playerControlEngaged)
            {
                DisengagePlayerControl();
            }

            if (Input.GetKeyDown(KeyCode.R) && !Input.GetKey(KeyCode.LeftControl))
            {
                if (TrajectoryRecorder.Instance != null && !TrajectoryRecorder.Instance.IsRecording)
                {
                    StartRecording();
                }
                else if (TrajectoryRecorder.Instance != null && TrajectoryRecorder.Instance.IsRecording)
                {
                    StopRecording();
                }
            }
        }

        private void OnGUI()
        {
            if (!showUI) return;

            DrawMainPanel();
            DrawStatusBar();
            DrawLogPanel();
        }

        private void DrawMainPanel()
        {
            GUILayout.BeginArea(new Rect(10, 10, uiWidth, Screen.height - 120), _panelStyle);
            _scrollPos = GUILayout.BeginScrollView(_scrollPos, false, false);

            GUILayout.Label("City Traffic Simulator", _headerStyle);
            GUILayout.Space(10);

            _showControls = GUILayout.Toggle(_showControls, "Scene Controls", _buttonStyle);
            if (_showControls)
            {
                DrawSceneControls();
            }

            GUILayout.Space(5);
            _showRecording = GUILayout.Toggle(_showRecording, "Recording & Replay", _buttonStyle);
            if (_showRecording)
            {
                DrawRecordingControls();
            }

            GUILayout.Space(5);
            _showExport = GUILayout.Toggle(_showExport, "Export", _buttonStyle);
            if (_showExport)
            {
                DrawExportControls();
            }

            GUILayout.Space(5);
            _showCornerCases = GUILayout.Toggle(_showCornerCases, "Corner Cases", _buttonStyle);
            if (_showCornerCases)
            {
                DrawCornerCaseControls();
            }

            GUILayout.Space(5);
            _showAdvanced = GUILayout.Toggle(_showAdvanced, "Advanced AI", _buttonStyle);
            if (_showAdvanced)
            {
                DrawAdvancedControls();
            }

            GUILayout.Space(10);
            DrawShortcuts();

            GUILayout.EndScrollView();
            GUILayout.EndArea();
        }

        private void DrawSceneControls()
        {
            GUILayout.BeginVertical(GUI.skin.box);
            GUILayout.Label("Road Settings", _headerStyle);

            GUILayout.Label($"Lanes per direction: {_parameters.lanesPerDirection}");
            _parameters.lanesPerDirection = (int)GUILayout.HorizontalSlider(_parameters.lanesPerDirection, 2, 8);

            GUILayout.Label($"Curvature: {_parameters.curvature:F2}");
            _parameters.curvature = GUILayout.HorizontalSlider(_parameters.curvature, 0f, 1f);

            GUILayout.Label($"Road Length: {_parameters.roadLength:F0}");
            _parameters.roadLength = GUILayout.HorizontalSlider(_parameters.roadLength, 50f, 500f);

            GUILayout.Label($"Lane Width: {_parameters.laneWidth:F1}");
            _parameters.laneWidth = GUILayout.HorizontalSlider(_parameters.laneWidth, 3f, 5f);

            GUILayout.Space(10);
            GUILayout.Label("Traffic Settings", _headerStyle);

            GUILayout.Label($"Vehicle Density: {_parameters.vehicleDensity:F2}");
            _parameters.vehicleDensity = GUILayout.HorizontalSlider(_parameters.vehicleDensity, 0.1f, 5f);

            GUILayout.Label($"Traffic Light Period: {_parameters.trafficLightPeriod:F1}s");
            _parameters.trafficLightPeriod = GUILayout.HorizontalSlider(_parameters.trafficLightPeriod, 5f, 60f);

            GUILayout.Label($"Pedestrians: {_parameters.pedestrianCount}");
            _parameters.pedestrianCount = (int)GUILayout.HorizontalSlider(_parameters.pedestrianCount, 0, 50);

            GUILayout.Space(10);
            GUILayout.Label("Environment Settings", _headerStyle);

            GUILayout.Label("Weather:");
            string[] weatherNames = Enum.GetNames(typeof(WeatherType));
            int weatherIndex = Array.IndexOf(weatherNames, _parameters.weather.ToString());
            weatherIndex = GUILayout.Toolbar(weatherIndex, weatherNames);
            _parameters.weather = (WeatherType)Enum.Parse(typeof(WeatherType), weatherNames[weatherIndex]);

            GUILayout.Label($"Building Density: {_parameters.buildingDensity}%");
            _parameters.buildingDensity = (int)GUILayout.HorizontalSlider(_parameters.buildingDensity, 0, 100);

            GUILayout.Space(10);
            GUILayout.Label("Vehicle Settings", _headerStyle);

            GUILayout.Label($"Max Speed: {_parameters.maxSpeed:F1} m/s");
            _parameters.maxSpeed = GUILayout.HorizontalSlider(_parameters.maxSpeed, 10f, 30f);

            GUILayout.Label($"Safety Distance: {_parameters.safetyDistance:F1}m");
            _parameters.safetyDistance = GUILayout.HorizontalSlider(_parameters.safetyDistance, 1f, 5f);

            GUILayout.Space(10);
            if (GUILayout.Button("Generate Scene", _buttonStyle))
            {
                GenerateScene();
            }

            if (GUILayout.Button("Clear Scene", _buttonStyle))
            {
                ClearScene();
            }

            if (SimulationManager.Instance != null &&
                (SimulationManager.Instance.State == SimulationState.Playing ||
                 SimulationManager.Instance.State == SimulationState.Paused))
            {
                string pauseButton = SimulationManager.Instance.State == SimulationState.Paused ? "Resume" : "Pause";
                if (GUILayout.Button(pauseButton, _buttonStyle))
                {
                    SimulationManager.Instance.TogglePause();
                }
            }

            GUILayout.Space(5);
            if (GUILayout.Button(_playerControlEngaged ? "Release Control (ESC)" : "Take Control (E)", _buttonStyle))
            {
                if (_playerControlEngaged)
                    DisengagePlayerControl();
                else
                    EngagePlayerControl();
            }

            GUILayout.EndVertical();
        }

        private void DrawRecordingControls()
        {
            GUILayout.BeginVertical(GUI.skin.box);
            GUILayout.Label("Recording", _headerStyle);

            if (TrajectoryRecorder.Instance != null)
            {
                if (!TrajectoryRecorder.Instance.IsRecording)
                {
                    if (GUILayout.Button("Start Recording (R)", _buttonStyle))
                    {
                        StartRecording();
                    }
                }
                else
                {
                    GUI.color = Color.red;
                    if (GUILayout.Button("Stop Recording (R)", _buttonStyle))
                    {
                        StopRecording();
                    }
                    GUI.color = Color.white;

                    var recording = TrajectoryRecorder.Instance.CurrentRecording;
                    if (recording != null)
                    {
                        GUILayout.Label($"Points: {recording.trajectory.Count}");
                        GUILayout.Label($"Time: {SimulationManager.Instance.GetSimulationTime():F1}s");
                    }
                }

                if (TrajectoryRecorder.Instance.CurrentRecording != null && !TrajectoryRecorder.Instance.IsRecording)
                {
                    if (GUILayout.Button("Save Recording", _buttonStyle))
                    {
                        SaveRecording();
                    }
                }

                if (GUILayout.Button("Load Recording", _buttonStyle))
                {
                    LoadRecording();
                }
            }

            GUILayout.Space(10);
            GUILayout.Label("Replay", _headerStyle);

            if (ReplaySystem.Instance != null)
            {
                if (!ReplaySystem.Instance.IsReplaying)
                {
                    if (GUILayout.Button("Play Last Recording", _buttonStyle))
                    {
                        PlayLastRecording();
                    }
                }
                else
                {
                    if (GUILayout.Button("Stop Replay", _buttonStyle))
                    {
                        ReplaySystem.Instance.StopReplay();
                    }

                    GUILayout.Label($"Progress: {ReplaySystem.Instance.CurrentReplayTime:F1}s / {ReplaySystem.Instance.CurrentReplayData.duration:F1}s");
                }
            }

            GUILayout.EndVertical();
        }

        private void DrawExportControls()
        {
            GUILayout.BeginVertical(GUI.skin.box);
            GUILayout.Label("Scene Export", _headerStyle);

            if (SceneExporter.Instance != null)
            {
                if (GUILayout.Button("Export Scene JSON", _buttonStyle))
                {
                    ExportScene();
                }

                if (GUILayout.Button("Export for CARLA", _buttonStyle))
                {
                    ExportForCARLA();
                }
            }

            GUILayout.EndVertical();
        }

        private void DrawShortcuts()
        {
            GUILayout.BeginVertical(GUI.skin.box);
            GUILayout.Label("Keyboard Shortcuts", _headerStyle);
            GUILayout.Label("F1/F2/F3: Camera modes");
            GUILayout.Label("Tab: Cycle camera");
            GUILayout.Label("E: Take/Release control");
            GUILayout.Label("WASD: Drive");
            GUILayout.Label("Space: Brake/Pause");
            GUILayout.Label("R: Record/Stop");
            GUILayout.Label("Ctrl+R: Reset vehicle");
            GUILayout.Label("H: Toggle UI");
            GUILayout.Label("ESC: Release control");
            GUILayout.EndVertical();
        }

        private void DrawStatusBar()
        {
            GUILayout.BeginArea(new Rect(10, Screen.height - 100, Screen.width - 20, 25), _panelStyle);
            GUILayout.BeginHorizontal();

            string stateText = SimulationManager.Instance != null ?
                $"State: {SimulationManager.Instance.State}" : "State: N/A";
            GUILayout.Label(stateText, _headerStyle);

            string timeText = SimulationManager.Instance != null ?
                $"Time: {SimulationManager.Instance.GetSimulationTime():F1}s" : "Time: 0s";
            GUILayout.Label(timeText, _headerStyle, GUILayout.Width(120));

            if (SimulationManager.Instance != null && SimulationManager.Instance.State == SimulationState.Playing)
            {
                var playerVehicle = VehicleGenerator.Instance?.PlayerVehicle;
                if (playerVehicle != null)
                {
                    var ai = playerVehicle.GetComponent<VehicleAIController>();
                    var player = playerVehicle.GetComponent<PlayerVehicleController>();
                    float speed = ai != null && ai.enabled ? ai.CurrentSpeed :
                                  player != null && player.enabled ? player.CurrentSpeed : 0;
                    GUILayout.Label($"Speed: {speed * 3.6f:F0} km/h", _headerStyle, GUILayout.Width(150));
                }
            }

            if (CameraSystem.Instance != null)
            {
                GUILayout.Label($"Camera: {CameraSystem.Instance.CurrentMode}", _headerStyle, GUILayout.Width(150));
            }

            if (TrajectoryRecorder.Instance != null && TrajectoryRecorder.Instance.IsRecording)
            {
                GUI.color = Color.red;
                GUILayout.Label("● RECORDING", _headerStyle);
                GUI.color = Color.white;
            }

            if (_playerControlEngaged)
            {
                GUI.color = Color.green;
                GUILayout.Label("● DRIVING", _headerStyle);
                GUI.color = Color.white;
            }

            GUILayout.EndHorizontal();
            GUILayout.EndArea();
        }

        private void DrawLogPanel()
        {
            float logHeight = 60;
            GUILayout.BeginArea(new Rect(10, Screen.height - 75, Screen.width - 20, logHeight), _panelStyle);

            _logScrollPos = GUILayout.BeginScrollView(_logScrollPos, false, true);
            for (int i = Mathf.Max(0, _logs.Count - 20); i < _logs.Count; i++)
            {
                GUILayout.Label(_logs[i]);
            }
            GUILayout.EndScrollView();

            GUILayout.EndArea();
        }

        private void GenerateScene()
        {
            if (SimulationManager.Instance == null) return;

            _statusMessage = "Generating scene...";
            SimulationManager.Instance.SetParameters(_parameters);
            SimulationManager.Instance.GenerateScene();
            _playerControlEngaged = false;

            if (CameraSystem.Instance != null)
            {
                CameraSystem.Instance.ResetCamera();
            }
        }

        private void ClearScene()
        {
            if (SimulationManager.Instance == null) return;

            _playerControlEngaged = false;
            SimulationManager.Instance.ClearScene();
        }

        private void EngagePlayerControl()
        {
            if (VehicleGenerator.Instance == null) return;

            VehicleGenerator.Instance.TogglePlayerControl(true);
            _playerControlEngaged = true;
        }

        private void DisengagePlayerControl()
        {
            if (VehicleGenerator.Instance == null) return;

            VehicleGenerator.Instance.TogglePlayerControl(false);
            _playerControlEngaged = false;
        }

        private void StartRecording()
        {
            if (TrajectoryRecorder.Instance == null || VehicleGenerator.Instance == null) return;

            var target = VehicleGenerator.Instance.PlayerVehicle;
            if (target == null) return;

            TrajectoryRecorder.Instance.StartRecording(target.transform, "scene_" + DateTime.Now.Ticks);
        }

        private void StopRecording()
        {
            if (TrajectoryRecorder.Instance == null) return;
            TrajectoryRecorder.Instance.StopRecording();
        }

        private void SaveRecording()
        {
            if (TrajectoryRecorder.Instance == null) return;

            string filename = TrajectoryRecorder.Instance.GenerateRecordingFilename();
            string path = System.IO.Path.Combine(Application.dataPath, "..", "Recordings");
            System.IO.Directory.CreateDirectory(path);
            string fullPath = System.IO.Path.Combine(path, filename);
            TrajectoryRecorder.Instance.SaveRecording(fullPath);
        }

        private void LoadRecording()
        {
            if (TrajectoryRecorder.Instance == null) return;

            string path = System.IO.Path.Combine(Application.dataPath, "..", "Recordings");
            System.IO.Directory.CreateDirectory(path);
            string[] files = System.IO.Directory.GetFiles(path, "*.json");
            if (files.Length > 0)
            {
                var recording = TrajectoryRecorder.Instance.LoadRecording(files[files.Length - 1]);
                if (recording != null && ReplaySystem.Instance != null)
                {
                    ReplaySystem.Instance.LoadAndPlay(recording);
                }
            }
        }

        private void PlayLastRecording()
        {
            if (TrajectoryRecorder.Instance == null || ReplaySystem.Instance == null) return;

            var recording = TrajectoryRecorder.Instance.GetCurrentRecording();
            if (recording != null && recording.trajectory.Count > 0)
            {
                ReplaySystem.Instance.LoadAndPlay(recording);
            }
        }

        private void ExportScene()
        {
            if (SceneExporter.Instance == null) return;
            SceneExporter.Instance.ExportSceneToFile();
        }

        private void ExportForCARLA()
        {
            if (SceneExporter.Instance == null) return;

            var description = SceneExporter.Instance.GenerateSceneDescription();
            if (description != null)
            {
                string carlaJson = SceneExporter.Instance.ExportForCARLA(description);
                string timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
                string directory = System.IO.Path.Combine(Application.dataPath, "..", "Exports");
                System.IO.Directory.CreateDirectory(directory);
                string filePath = System.IO.Path.Combine(directory, $"carla_scene_{timestamp}.json");
                System.IO.File.WriteAllText(filePath, carlaJson);
                SimulationManager.Instance.Log($"CARLA scene exported to: {filePath}");
            }
        }

        private void AddLog(string message)
        {
            _logs.Add(message);
            _logScrollPos.y = float.MaxValue;
            if (_logs.Count > 100)
            {
                _logs.RemoveRange(0, _logs.Count - 100);
            }
        }

        private void OnStateChanged(SimulationState state)
        {
            _statusMessage = $"State changed to: {state}";
        }

        private void DrawCornerCaseControls()
        {
            GUILayout.BeginVertical(GUI.skin.box);
            GUILayout.Label("Corner Case Generation", _headerStyle);

            if (CornerCaseGenerator.Instance != null)
            {
                var config = CornerCaseGenerator.Instance.GetConfig();

                GUILayout.Label($"Event Probability: {config.eventProbability:F2}");
                config.eventProbability = GUILayout.HorizontalSlider(config.eventProbability, 0f, 1f);

                GUILayout.Label($"Min Interval: {config.minInterval:F0}s");
                config.minInterval = GUILayout.HorizontalSlider(config.minInterval, 5f, 60f);

                GUILayout.Label($"Max Interval: {config.maxInterval:F0}s");
                config.maxInterval = GUILayout.HorizontalSlider(config.maxInterval, 10f, 120f);

                GUILayout.Label($"Max Concurrent: {config.maxConcurrentEvents}");
                config.maxConcurrentEvents = (int)GUILayout.HorizontalSlider(config.maxConcurrentEvents, 1, 5);

                GUILayout.Space(8);
                GUILayout.Label("Enabled Events:", _headerStyle);

                string[] caseNames = Enum.GetNames(typeof(CornerCaseType));
                for (int i = 0; i < caseNames.Length; i++)
                {
                    if (caseNames[i] == "None") continue;
                    CornerCaseType caseType = (CornerCaseType)Enum.Parse(typeof(CornerCaseType), caseNames[i]);
                    bool isEnabled = config.enabledCases.Contains(caseType);
                    bool newEnabled = GUILayout.Toggle(isEnabled, caseNames[i]);
                    if (newEnabled != isEnabled)
                    {
                        if (newEnabled)
                            config.enabledCases.Add(caseType);
                        else
                            config.enabledCases.Remove(caseType);
                    }
                }

                GUILayout.Space(8);
                float nextTime = CornerCaseGenerator.Instance.GetTimeUntilNextEvent();
                GUILayout.Label($"Next event in: {nextTime:F1}s");

                var activeEvents = CornerCaseGenerator.Instance.GetActiveEvents();
                GUILayout.Label($"Active events: {activeEvents.Count}");
                foreach (var ev in activeEvents)
                {
                    float timeLeft = (ev.triggerTime + ev.duration) - Time.time;
                    GUILayout.Label($"  {ev.caseType}: {timeLeft:F1}s");
                }

                GUILayout.Space(8);
                if (GUILayout.Button("Trigger Random Event", _buttonStyle))
                {
                    CornerCaseGenerator.Instance.TriggerRandomEvent();
                }

                if (GUILayout.Button("Clear All Events", _buttonStyle))
                {
                    CornerCaseGenerator.Instance.ClearAllEvents();
                }

                CornerCaseGenerator.Instance.SetConfig(config);
            }
            else
            {
                GUILayout.Label("CornerCaseGenerator not available");
            }

            GUILayout.EndVertical();
        }

        private void DrawAdvancedControls()
        {
            GUILayout.BeginVertical(GUI.skin.box);
            GUILayout.Label("Advanced AI Settings", _headerStyle);

            if (CollaborativeLaneChangeManager.Instance != null)
            {
                GUILayout.Space(5);
                GUILayout.Label("Lane Change Manager", _headerStyle);

                var mergeGames = CollaborativeLaneChangeManager.Instance.GetActiveMergeGames();
                GUILayout.Label($"Active merges: {mergeGames.Count}");

                if (GUILayout.Button("Toggle Cooperative Merging", _buttonStyle))
                {
                    var field = CollaborativeLaneChangeManager.Instance.GetType().GetField("enableCooperativeMerging",
                        System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                    bool current = (bool)field.GetValue(CollaborativeLaneChangeManager.Instance);
                    field.SetValue(CollaborativeLaneChangeManager.Instance, !current);
                }

                if (GUILayout.Button("Toggle Game Theory", _buttonStyle))
                {
                    var field = CollaborativeLaneChangeManager.Instance.GetType().GetField("enableGameTheory",
                        System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                    bool current = (bool)field.GetValue(CollaborativeLaneChangeManager.Instance);
                    field.SetValue(CollaborativeLaneChangeManager.Instance, !current);
                }
            }

            if (ILDriverModel.Instance != null)
            {
                GUILayout.Space(8);
                GUILayout.Label("Imitation Learning", _headerStyle);
                GUILayout.Label("Driver Style Distribution:");

                string[] styleNames = Enum.GetNames(typeof(DrivingStyle));
                foreach (var style in styleNames)
                {
                    GUILayout.Label($"  - {style}");
                }

                GUILayout.Space(5);
                GUILayout.Label("Driving styles randomly assigned to vehicles");
                GUILayout.Label("70% of vehicles use imitation learning");
            }

            GUILayout.EndVertical();
        }

        private void OnDestroy()
        {
            if (SimulationManager.Instance != null)
            {
                SimulationManager.Instance.OnLog -= AddLog;
                SimulationManager.Instance.OnStateChanged -= OnStateChanged;
            }
        }
    }
}
