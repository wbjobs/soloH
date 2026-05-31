using System;
using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    [Serializable]
    public class Vector3Data
    {
        public float x;
        public float y;
        public float z;

        public Vector3Data() { }

        public Vector3Data(Vector3 v)
        {
            x = v.x;
            y = v.y;
            z = v.z;
        }

        public Vector3 ToVector3()
        {
            return new Vector3(x, y, z);
        }
    }

    [Serializable]
    public class RoadSegmentData
    {
        public string id;
        public Vector3Data startPoint;
        public Vector3Data endPoint;
        public Vector3Data centerPoint;
        public int lanesPerDirection;
        public float laneWidth;
        public RoadType roadType;
        public float curvature;
        public List<Vector3Data> centerLinePoints;
    }

    [Serializable]
    public class LaneData
    {
        public string id;
        public string roadId;
        public int laneIndex;
        public LaneDirection direction;
        public List<Vector3Data> waypoints;
    }

    [Serializable]
    public class BuildingData
    {
        public string id;
        public Vector3Data position;
        public Vector3Data scale;
        public float rotation;
        public int floors;
    }

    [Serializable]
    public class TrafficSignData
    {
        public string id;
        public SignType signType;
        public Vector3Data position;
        public float rotation;
        public string value;
    }

    [Serializable]
    public class TrafficLightData
    {
        public string id;
        public Vector3Data position;
        public Vector3Data rotation;
        public string controlledRoadId;
        public float redDuration;
        public float yellowDuration;
        public float greenDuration;
    }

    [Serializable]
    public class VehicleData
    {
        public string id;
        public VehicleType vehicleType;
        public Vector3Data position;
        public Vector3Data rotation;
        public Vector3Data scale;
        public float maxSpeed;
        public float currentSpeed;
        public string currentLaneId;
        public ColorData color;
    }

    [Serializable]
    public class PedestrianData
    {
        public string id;
        public Vector3Data position;
        public Vector3Data rotation;
        public float walkingSpeed;
        public List<Vector3Data> path;
    }

    [Serializable]
    public class ColorData
    {
        public float r;
        public float g;
        public float b;
        public float a;

        public ColorData() { }

        public ColorData(Color c)
        {
            r = c.r;
            g = c.g;
            b = c.b;
            a = c.a;
        }

        public Color ToColor()
        {
            return new Color(r, g, b, a);
        }
    }

    [Serializable]
    public class TrajectoryPoint
    {
        public float timestamp;
        public Vector3Data position;
        public Vector3Data rotation;
        public float speed;
        public float steeringAngle;
        public float throttle;
        public float brake;
    }

    [Serializable]
    public class CollisionEvent
    {
        public float timestamp;
        public string objectAId;
        public string objectBId;
        public Vector3Data position;
        public Vector3Data normal;
        public float relativeVelocity;
    }

    [Serializable]
    public class SceneDescription
    {
        public string version;
        public string generatedAt;
        public SceneParameters parameters;
        public List<RoadSegmentData> roads;
        public List<LaneData> lanes;
        public List<BuildingData> buildings;
        public List<TrafficSignData> trafficSigns;
        public List<TrafficLightData> trafficLights;
        public List<VehicleData> vehicles;
        public List<PedestrianData> pedestrians;
        public WeatherType weather;
        public Vector3Data worldBoundsMin;
        public Vector3Data worldBoundsMax;
    }

    [Serializable]
    public class RecordingData
    {
        public string sceneId;
        public float duration;
        public string recordedVehicleId;
        public List<TrajectoryPoint> trajectory;
        public List<CollisionEvent> collisions;
    }
}
