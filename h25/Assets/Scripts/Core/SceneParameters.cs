using System;
using UnityEngine;

namespace CitySimulator
{
    [Serializable]
    public class SceneParameters
    {
        [Header("Road Settings")]
        [Range(2, 8)] public int lanesPerDirection = 2;
        [Range(0f, 1f)] public float curvature = 0f;
        [Range(50f, 500f)] public float roadLength = 200f;
        [Range(3f, 5f)] public float laneWidth = 3.5f;

        [Header("Traffic Settings")]
        [Range(0.1f, 5f)] public float vehicleDensity = 1f;
        [Range(5f, 60f)] public float trafficLightPeriod = 30f;
        [Range(0, 50)] public int pedestrianCount = 10;

        [Header("Environment Settings")]
        public WeatherType weather = WeatherType.Clear;
        [Range(0, 100)] public int buildingDensity = 50;

        [Header("Vehicle Settings")]
        [Range(10f, 30f)] public float maxSpeed = 20f;
        [Range(1f, 5f)] public float safetyDistance = 2f;

        public SceneParameters Clone()
        {
            return (SceneParameters)MemberwiseClone();
        }
    }
}
