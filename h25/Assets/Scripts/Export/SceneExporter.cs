using System;
using System.IO;
using UnityEngine;

namespace CitySimulator
{
    public class SceneExporter : MonoBehaviour
    {
        public static SceneExporter Instance { get; private set; }

        [SerializeField] private string exportDirectory = "Exports";

        public event Action<string> OnSceneExported;
        public event Action<string> OnExportError;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        public SceneDescription GenerateSceneDescription()
        {
            if (SceneGenerator.Instance == null)
            {
                OnExportError?.Invoke("Scene generator not available");
                return null;
            }

            var gen = SceneGenerator.Instance;
            var sim = SimulationManager.Instance;

            var description = new SceneDescription
            {
                version = "1.0",
                generatedAt = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"),
                parameters = sim != null ? sim.CurrentParameters : new SceneParameters(),
                roads = new System.Collections.Generic.List<RoadSegmentData>(gen.Roads),
                lanes = new System.Collections.Generic.List<LaneData>(gen.Lanes),
                buildings = new System.Collections.Generic.List<BuildingData>(gen.Buildings),
                trafficSigns = new System.Collections.Generic.List<TrafficSignData>(gen.TrafficSigns),
                trafficLights = new System.Collections.Generic.List<TrafficLightData>(gen.TrafficLights),
                vehicles = new System.Collections.Generic.List<VehicleData>(VehicleGenerator.Instance.VehicleDataList),
                pedestrians = new System.Collections.Generic.List<PedestrianData>(PedestrianGenerator.Instance.PedestrianDataList),
                weather = sim != null ? sim.CurrentParameters.weather : WeatherType.Clear,
                worldBoundsMin = new Vector3Data(gen.WorldBounds.min),
                worldBoundsMax = new Vector3Data(gen.WorldBounds.max)
            };

            return description;
        }

        public string ExportSceneToJson(SceneDescription description)
        {
            try
            {
                string json = JsonUtility.ToJson(description, true);
                return json;
            }
            catch (Exception e)
            {
                OnExportError?.Invoke($"Failed to serialize scene: {e.Message}");
                return null;
            }
        }

        public bool ExportSceneToFile(string filePath = null)
        {
            var description = GenerateSceneDescription();
            if (description == null) return false;

            string json = ExportSceneToJson(description);
            if (string.IsNullOrEmpty(json)) return false;

            if (string.IsNullOrEmpty(filePath))
            {
                string timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
                string directory = Path.Combine(Application.dataPath, "..", exportDirectory);
                Directory.CreateDirectory(directory);
                filePath = Path.Combine(directory, $"scene_{timestamp}.json");
            }

            try
            {
                File.WriteAllText(filePath, json);
                OnSceneExported?.Invoke(filePath);
                SimulationManager.Instance.Log($"Scene exported to: {filePath}");
                return true;
            }
            catch (Exception e)
            {
                OnExportError?.Invoke($"Failed to save file: {e.Message}");
                SimulationManager.Instance.Log($"Export failed: {e.Message}");
                return false;
            }
        }

        public SceneDescription LoadSceneFromJson(string json)
        {
            try
            {
                var description = JsonUtility.FromJson<SceneDescription>(json);
                SimulationManager.Instance.Log($"Scene loaded. Roads: {description.roads.Count}, Buildings: {description.buildings.Count}");
                return description;
            }
            catch (Exception e)
            {
                OnExportError?.Invoke($"Failed to parse JSON: {e.Message}");
                return null;
            }
        }

        public SceneDescription LoadSceneFromFile(string filePath)
        {
            try
            {
                string json = File.ReadAllText(filePath);
                return LoadSceneFromJson(json);
            }
            catch (Exception e)
            {
                OnExportError?.Invoke($"Failed to read file: {e.Message}");
                return null;
            }
        }

        public string ExportForCARLA(SceneDescription description)
        {
            var carlaData = new
            {
                version = "1.0",
                map_name = $"city_sim_map",
                open_drive = ConvertToOpenDrive(description),
                actors = ConvertToCARLAActors(description)
            };
            return JsonUtility.ToJson(carlaData, true);
        }

        private string ConvertToOpenDrive(SceneDescription description)
        {
            return "<OpenDRIVE>" +
                   "<header revMajor=\"1\" revMinor=\"4\" name=\"CitySimMap\"/>" +
                   "<road id=\"0\" length=\"" + description.parameters.roadLength + "\">" +
                   "<planView>" +
                   "<geometry s=\"0\" x=\"0\" y=\"0\" hdg=\"0\" length=\"" + description.parameters.roadLength + "\">" +
                   "<line/>" +
                   "</geometry>" +
                   "</planView>" +
                   "<lanes>" +
                   "<laneSection s=\"0\">" +
                   "<left>" +
                   $"<lane id=\"" + description.parameters.lanesPerDirection + "\" type=\"driving\" level=\"false\">" +
                   "<width sOffset=\"0\" a=\"" + description.parameters.laneWidth + "\"/>" +
                   "</lane>" +
                   "</left>" +
                   "<center>" +
                   "<lane id=\"0\" type=\"none\"/>" +
                   "</center>" +
                   "<right>" +
                   $"<lane id=\"-" + description.parameters.lanesPerDirection + "\" type=\"driving\" level=\"false\">" +
                   "<width sOffset=\"0\" a=\"" + description.parameters.laneWidth + "\"/>" +
                   "</lane>" +
                   "</right>" +
                   "</laneSection>" +
                   "</lanes>" +
                   "</road>" +
                   "</OpenDRIVE>";
        }

        private object ConvertToCARLAActors(SceneDescription description)
        {
            var actors = new System.Collections.Generic.List<object>();

            foreach (var vehicle in description.vehicles)
            {
                actors.Add(new
                {
                    type = "vehicle." + vehicle.vehicleType.ToString().ToLower(),
                    id = vehicle.id,
                    transform = new
                    {
                        location = new { x = vehicle.position.x, y = vehicle.position.y, z = vehicle.position.z },
                        rotation = new { pitch = vehicle.rotation.x, yaw = vehicle.rotation.y, roll = vehicle.rotation.z }
                    }
                });
            }

            foreach (var pedestrian in description.pedestrians)
            {
                actors.Add(new
                {
                    type = "walker.pedestrian.0001",
                    id = pedestrian.id,
                    transform = new
                    {
                        location = new { x = pedestrian.position.x, y = pedestrian.position.y, z = pedestrian.position.z },
                        rotation = new { pitch = pedestrian.rotation.x, yaw = pedestrian.rotation.y, roll = pedestrian.rotation.z }
                    }
                });
            }

            return actors.ToArray();
        }

        public void SetExportDirectory(string directory)
        {
            exportDirectory = directory;
        }
    }
}
