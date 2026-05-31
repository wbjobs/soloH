using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;
using LanderSim.Terrain;

namespace LanderSim.RiskAssessment
{
    [Serializable]
    public class RiskWeights
    {
        public double slopeWeight = 0.4;
        public double roughnessWeight = 0.3;
        public double shadowWeight = 0.15;
        public double obstacleDistanceWeight = 0.15;

        public double maxAcceptableSlope = 15.0;
        public double maxAcceptableRoughness = 0.5;
        public double minAcceptableClearance = 5.0;
        public double maxAcceptableRisk = 0.5;

        public override string ToString()
        {
            return $"Slope:{slopeWeight:F2} Rough:{roughnessWeight:F2} " +
                   $"Shadow:{shadowWeight:F2} Obstacle:{obstacleDistanceWeight:F2}";
        }
    }

    [Serializable]
    public class RiskMap
    {
        public int resolutionX;
        public int resolutionZ;
        public double[,] slopeRisk;
        public double[,] roughnessRisk;
        public double[,] shadowRisk;
        public double[,] obstacleRisk;
        public double[,] totalRisk;

        public LandingSite[,] landingSites;

        public RiskMap(int resX, int resZ)
        {
            resolutionX = resX;
            resolutionZ = resZ;
            slopeRisk = new double[resX, resZ];
            roughnessRisk = new double[resX, resZ];
            shadowRisk = new double[resX, resZ];
            obstacleRisk = new double[resX, resZ];
            totalRisk = new double[resX, resZ];
            landingSites = new LandingSite[resX, resZ];
        }

        public double GetTotalRisk(int x, int z)
        {
            if (x < 0 || x >= resolutionX || z < 0 || z >= resolutionZ) return 1.0;
            return totalRisk[x, z];
        }

        public Color GetRiskColor(int x, int z)
        {
            double risk = GetTotalRisk(x, z);
            return GetRiskColor(risk);
        }

        public static Color GetRiskColor(double risk)
        {
            risk = Math.Max(0, Math.Min(1.0, risk));

            if (risk < 0.25)
            {
                return Color.Lerp(Color.green, Color.yellow, (float)(risk / 0.25));
            }
            else if (risk < 0.5)
            {
                return Color.Lerp(Color.yellow, new Color(1, 0.5f, 0),
                    (float)((risk - 0.25) / 0.25));
            }
            else if (risk < 0.75)
            {
                return Color.Lerp(new Color(1, 0.5f, 0), Color.red,
                    (float)((risk - 0.5) / 0.25));
            }
            else
            {
                return Color.Lerp(Color.red, Color.magenta,
                    (float)((risk - 0.75) / 0.25));
            }
        }

        public List<LandingSite> GetSafeLandingSites(RiskWeights weights, double minSeparation = 10.0)
        {
            List<LandingSite> candidates = new List<LandingSite>();

            for (int x = 0; x < resolutionX; x++)
            {
                for (int z = 0; z < resolutionZ; z++)
                {
                    if (totalRisk[x, z] <= weights.maxAcceptableRisk)
                    {
                        LandingSite site = landingSites[x, z];
                        if (site.totalRisk <= weights.maxAcceptableRisk)
                        {
                            bool tooClose = false;
                            foreach (var existing in candidates)
                            {
                                if (Vector3d.Distance(site.position, existing.position) < minSeparation)
                                {
                                    tooClose = true;
                                    break;
                                }
                            }

                            if (!tooClose)
                            {
                                candidates.Add(site);
                            }
                        }
                    }
                }
            }

            candidates.Sort((a, b) => a.totalRisk.CompareTo(b.totalRisk));
            return candidates;
        }

        public List<LandingSite> GetBestLandingSites(int count, RiskWeights weights)
        {
            List<LandingSite> allSites = new List<LandingSite>();

            for (int x = 0; x < resolutionX; x++)
            {
                for (int z = 0; z < resolutionZ; z++)
                {
                    if (landingSites[x, z].totalRisk > 0)
                    {
                        allSites.Add(landingSites[x, z]);
                    }
                }
            }

            allSites.Sort((a, b) => a.totalRisk.CompareTo(b.totalRisk));

            int returnCount = Math.Min(count, allSites.Count);
            return allSites.GetRange(0, returnCount);
        }
    }

    public class RiskEvaluator
    {
        private TerrainData terrainData;
        private TerrainGenerator terrainGenerator;
        private RiskWeights weights;

        public Vector3d sunDirection = new Vector3d(0.5, 0.8, 0.3).normalized;
        public int shadowKernelSize = 5;

        [Header("Sun Position Settings")]
        public bool useDynamicSunPosition = true;
        public double latitude = 25.0;
        public double solarDeclination = 23.5;
        public int numSunAngles = 8;
        public double startTimeOfDay = 6.0;
        public double endTimeOfDay = 18.0;

        private List<Vector3d> sunDirections;
        private List<double> sunWeights;

        public RiskEvaluator(TerrainData terrainData,
                            TerrainGenerator terrainGenerator = null,
                            RiskWeights weights = null)
        {
            this.terrainData = terrainData;
            this.terrainGenerator = terrainGenerator;
            this.weights = weights ?? new RiskWeights();
            CalculateSunDirections();
        }

        public void CalculateSunDirections()
        {
            sunDirections = new List<Vector3d>();
            sunWeights = new List<double>();

            if (!useDynamicSunPosition || numSunAngles <= 1)
            {
                sunDirections.Add(sunDirection.normalized);
                sunWeights.Add(1.0);
                return;
            }

            double timeStep = (endTimeOfDay - startTimeOfDay) / (numSunAngles - 1);
            double totalWeight = 0;

            for (int i = 0; i < numSunAngles; i++)
            {
                double hour = startTimeOfDay + i * timeStep;
                Vector3d sunDir = CalculateSunPosition(hour);
                double weight = CalculateSunWeight(hour);

                sunDirections.Add(sunDir);
                sunWeights.Add(weight);
                totalWeight += weight;
            }

            for (int i = 0; i < sunWeights.Count; i++)
            {
                sunWeights[i] /= totalWeight;
            }
        }

        public Vector3d CalculateSunPosition(double hourOfDay)
        {
            double hourAngle = (hourOfDay - 12.0) * 15.0 * Math.PI / 180.0;
            double latRad = latitude * Math.PI / 180.0;
            double decRad = solarDeclination * Math.PI / 180.0;

            double sinAltitude = Math.Sin(latRad) * Math.Sin(decRad) +
                                 Math.Cos(latRad) * Math.Cos(decRad) * Math.Cos(hourAngle);
            sinAltitude = Math.Max(-1.0, Math.Min(1.0, sinAltitude));
            double altitude = Math.Asin(sinAltitude);

            if (altitude <= 0)
            {
                return new Vector3d(0, 0.01, 1).normalized;
            }

            double cosAzimuth = (Math.Sin(decRad) - Math.Sin(latRad) * sinAltitude) /
                               (Math.Cos(latRad) * Math.Cos(altitude));
            cosAzimuth = Math.Max(-1.0, Math.Min(1.0, cosAzimuth));
            double azimuth = Math.Acos(cosAzimuth);

            if (hourAngle > 0)
            {
                azimuth = 2 * Math.PI - azimuth;
            }

            double x = Math.Cos(altitude) * Math.Sin(azimuth);
            double y = Math.Sin(altitude);
            double z = Math.Cos(altitude) * Math.Cos(azimuth);

            return new Vector3d(x, y, z).normalized;
        }

        public double CalculateSunWeight(double hourOfDay)
        {
            double hourAngle = (hourOfDay - 12.0) * 15.0 * Math.PI / 180.0;
            double latRad = latitude * Math.PI / 180.0;
            double decRad = solarDeclination * Math.PI / 180.0;

            double sinAltitude = Math.Sin(latRad) * Math.Sin(decRad) +
                                 Math.Cos(latRad) * Math.Cos(decRad) * Math.Cos(hourAngle);
            sinAltitude = Math.Max(0.0, Math.Min(1.0, sinAltitude));

            double weight = sinAltitude;
            weight = Math.Pow(weight, 0.5);

            return Math.Max(0.01, weight);
        }

        public void SetWeights(RiskWeights newWeights)
        {
            weights = newWeights;
        }

        public RiskWeights GetWeights()
        {
            return weights;
        }

        public RiskMap EvaluateRisk()
        {
            if (terrainData == null) return null;

            RiskMap riskMap = new RiskMap(terrainData.resolutionX, terrainData.resolutionZ);

            EvaluateSlopeRisk(riskMap);
            EvaluateRoughnessRisk(riskMap);
            EvaluateShadowRisk(riskMap);
            EvaluateObstacleRisk(riskMap);
            CombineRisks(riskMap);
            GenerateLandingSites(riskMap);

            return riskMap;
        }

        private void EvaluateSlopeRisk(RiskMap riskMap)
        {
            for (int x = 0; x < terrainData.resolutionX; x++)
            {
                for (int z = 0; z < terrainData.resolutionZ; z++)
                {
                    double slope = terrainData.GetSlope(x, z);
                    riskMap.slopeRisk[x, z] = NormalizeRisk(slope, weights.maxAcceptableSlope);
                }
            }
        }

        private void EvaluateRoughnessRisk(RiskMap riskMap)
        {
            for (int x = 0; x < terrainData.resolutionX; x++)
            {
                for (int z = 0; z < terrainData.resolutionZ; z++)
                {
                    double roughness = terrainData.GetRoughness(x, z);
                    riskMap.roughnessRisk[x, z] =
                        NormalizeRisk(roughness, weights.maxAcceptableRoughness);
                }
            }
        }

        private void EvaluateShadowRisk(RiskMap riskMap)
        {
            if (sunDirections == null || sunDirections.Count == 0)
            {
                CalculateSunDirections();
            }

            double[,] shadowMap = new double[terrainData.resolutionX, terrainData.resolutionZ];

            for (int x = 0; x < terrainData.resolutionX; x++)
            {
                for (int z = 0; z < terrainData.resolutionZ; z++)
                {
                    Vector3d pos = terrainData.GetWorldPosition(x, z);
                    shadowMap[x, z] = CalculateWeightedShadowFactor(pos);
                }
            }

            for (int x = 0; x < terrainData.resolutionX; x++)
            {
                for (int z = 0; z < terrainData.resolutionZ; z++)
                {
                    double avgShadow = 0;
                    int count = 0;

                    for (int dx = -shadowKernelSize / 2; dx <= shadowKernelSize / 2; dx++)
                    {
                        for (int dz = -shadowKernelSize / 2; dz <= shadowKernelSize / 2; dz++)
                        {
                            int xi = x + dx;
                            int zi = z + dz;
                            if (xi >= 0 && xi < terrainData.resolutionX &&
                                zi >= 0 && zi < terrainData.resolutionZ)
                            {
                                avgShadow += shadowMap[xi, zi];
                                count++;
                            }
                        }
                    }

                    avgShadow = count > 0 ? avgShadow / count : 0;

                    double temporalVariation = CalculateTemporalShadowVariation(x, z);
                    double combinedShadow = avgShadow * 0.7 + temporalVariation * 0.3;

                    riskMap.shadowRisk[x, z] = 1.0 - combinedShadow;
                }
            }
        }

        private double CalculateWeightedShadowFactor(Vector3d position)
        {
            if (sunDirections == null || sunDirections.Count == 0)
            {
                return CalculateShadowFactor(position, sunDirection);
            }

            double weightedShadow = 0;

            for (int i = 0; i < sunDirections.Count; i++)
            {
                double shadow = CalculateShadowFactor(position, sunDirections[i]);
                weightedShadow += shadow * sunWeights[i];
            }

            return weightedShadow;
        }

        private double CalculateShadowFactor(Vector3d position, Vector3d sunDir)
        {
            if (sunDir.y <= 0.01)
            {
                return 0.1;
            }

            double stepSize = 2.0;
            double maxDistance = 100.0;
            Vector3d step = sunDir * stepSize;
            Vector3d current = position + Vector3d.up * 0.5;

            double maxHeightDiff = 0;
            bool isInShadow = false;
            double shadowStartDist = double.MaxValue;

            for (double dist = stepSize; dist < maxDistance; dist += stepSize)
            {
                current += step;

                if (!terrainData.IsInBounds((float)current.x, (float)current.z))
                {
                    break;
                }

                double terrainHeight = terrainData.GetHeight((float)current.x, (float)current.z);
                double heightDiff = current.y - terrainHeight;

                if (heightDiff < maxHeightDiff)
                {
                    maxHeightDiff = heightDiff;
                }

                if (heightDiff < 0 && !isInShadow)
                {
                    isInShadow = true;
                    shadowStartDist = dist;
                }
            }

            if (isInShadow)
            {
                double shadowDepth = Math.Max(0, -maxHeightDiff);
                double shadowFactor = 0.3 + 0.3 * Math.Exp(-shadowDepth / 10.0);
                shadowFactor += 0.2 * Math.Exp(-shadowStartDist / 50.0);
                return Math.Min(0.9, shadowFactor);
            }

            return 1.0;
        }

        private double CalculateTemporalShadowVariation(int x, int z)
        {
            if (sunDirections == null || sunDirections.Count <= 1)
            {
                return 1.0;
            }

            Vector3d pos = terrainData.GetWorldPosition(x, z);
            double minShadow = double.MaxValue;
            double maxShadow = double.MinValue;

            for (int i = 0; i < sunDirections.Count; i++)
            {
                double shadow = CalculateShadowFactor(pos, sunDirections[i]);
                minShadow = Math.Min(minShadow, shadow);
                maxShadow = Math.Max(maxShadow, shadow);
            }

            double variation = maxShadow - minShadow;
            double normalizedVariation = 1.0 - (variation * 0.8);

            return Math.Max(0.2, Math.Min(1.0, normalizedVariation));
        }

        public double[,] GetShadowDurationMap()
        {
            if (sunDirections == null || sunDirections.Count == 0)
            {
                CalculateSunDirections();
            }

            double[,] durationMap = new double[terrainData.resolutionX, terrainData.resolutionZ];

            for (int x = 0; x < terrainData.resolutionX; x++)
            {
                for (int z = 0; z < terrainData.resolutionZ; z++)
                {
                    Vector3d pos = terrainData.GetWorldPosition(x, z);
                    double sunlitHours = 0;
                    double totalWeight = 0;

                    for (int i = 0; i < sunDirections.Count; i++)
                    {
                        double shadow = CalculateShadowFactor(pos, sunDirections[i]);
                        if (shadow > 0.5)
                        {
                            sunlitHours += sunWeights[i] * (endTimeOfDay - startTimeOfDay);
                        }
                        totalWeight += sunWeights[i];
                    }

                    durationMap[x, z] = sunlitHours;
                }
            }

            return durationMap;
        }

        public Vector3d GetSunDirectionAtTime(double hourOfDay)
        {
            return CalculateSunPosition(hourOfDay);
        }

        public List<Vector3d> GetSunDirections()
        {
            return new List<Vector3d>(sunDirections);
        }

        private void EvaluateObstacleRisk(RiskMap riskMap)
        {
            double[,] distanceMap = new double[terrainData.resolutionX, terrainData.resolutionZ];

            for (int x = 0; x < terrainData.resolutionX; x++)
            {
                for (int z = 0; z < terrainData.resolutionZ; z++)
                {
                    distanceMap[x, z] = double.MaxValue;
                }
            }

            if (terrainGenerator != null && terrainGenerator.Rocks != null)
            {
                foreach (var rock in terrainGenerator.Rocks)
                {
                    Vector3 rockCenter = rock.center;
                    Vector3 rockSize = rock.size;

                    int minX = Math.Max(0, (int)((rockCenter.x - rockSize.x * 2 -
                        terrainData.origin.x) / terrainData.cellSize));
                    int maxX = Math.Min(terrainData.resolutionX - 1,
                        (int)((rockCenter.x + rockSize.x * 2 - terrainData.origin.x) /
                        terrainData.cellSize));
                    int minZ = Math.Max(0, (int)((rockCenter.z - rockSize.z * 2 -
                        terrainData.origin.z) / terrainData.cellSize));
                    int maxZ = Math.Min(terrainData.resolutionZ - 1,
                        (int)((rockCenter.z + rockSize.z * 2 - terrainData.origin.z) /
                        terrainData.cellSize));

                    for (int x = minX; x <= maxX; x++)
                    {
                        for (int z = minZ; z <= maxZ; z++)
                        {
                            Vector3d worldPos = terrainData.GetWorldPosition(x, z);
                            double dist = Vector3d.Distance(
                                Vector3d.FromVector3(rockCenter), worldPos);
                            dist = Math.Max(0, dist - Math.Max(rockSize.x, rockSize.z));

                            if (dist < distanceMap[x, z])
                            {
                                distanceMap[x, z] = dist;
                            }
                        }
                    }
                }
            }

            for (int x = 0; x < terrainData.resolutionX; x++)
            {
                for (int z = 0; z < terrainData.resolutionZ; z++)
                {
                    double distance = distanceMap[x, z];
                    if (distance == double.MaxValue)
                    {
                        riskMap.obstacleRisk[x, z] = 0;
                    }
                    else
                    {
                        riskMap.obstacleRisk[x, z] =
                            1.0 - NormalizeRisk(distance, weights.minAcceptableClearance);
                    }
                }
            }
        }

        private void CombineRisks(RiskMap riskMap)
        {
            double totalWeight = weights.slopeWeight + weights.roughnessWeight +
                                weights.shadowWeight + weights.obstacleDistanceWeight;

            for (int x = 0; x < terrainData.resolutionX; x++)
            {
                for (int z = 0; z < terrainData.resolutionZ; z++)
                {
                    double combined =
                        weights.slopeWeight * riskMap.slopeRisk[x, z] +
                        weights.roughnessWeight * riskMap.roughnessRisk[x, z] +
                        weights.shadowWeight * riskMap.shadowRisk[x, z] +
                        weights.obstacleDistanceWeight * riskMap.obstacleRisk[x, z];

                    riskMap.totalRisk[x, z] = combined / totalWeight;
                }
            }
        }

        private void GenerateLandingSites(RiskMap riskMap)
        {
            for (int x = 0; x < terrainData.resolutionX; x++)
            {
                for (int z = 0; z < terrainData.resolutionZ; z++)
                {
                    Vector3d pos = terrainData.GetWorldPosition(x, z);
                    Vector3d normal = terrainData.GetNormal(x, z);
                    double slope = terrainData.GetSlope(x, z);
                    double roughness = terrainData.GetRoughness(x, z);
                    double shadow = 1.0 - riskMap.shadowRisk[x, z];
                    double totalRisk = riskMap.totalRisk[x, z];

                    riskMap.landingSites[x, z] = new LandingSite(
                        pos, normal, slope, roughness, shadow, totalRisk
                    );
                }
            }
        }

        private double NormalizeRisk(double value, double threshold)
        {
            if (value <= 0) return 0;
            if (value >= threshold * 2) return 1.0;

            double normalized = value / threshold;
            return normalized * normalized / (1 + normalized * normalized);
        }

        public double EvaluateTrajectoryRisk(List<Vector3d> path)
        {
            if (path == null || path.Count < 2) return 0;

            double totalRisk = 0;

            for (int i = 0; i < path.Count; i++)
            {
                Vector3d pos = path[i];
                double terrainHeight = terrainData.GetHeight((float)pos.x, (float)pos.z);
                double clearance = pos.y - terrainHeight;

                double terrainRisk = 0;
                if (clearance < 10.0)
                {
                    int x = (int)((pos.x - terrainData.origin.x) / terrainData.cellSize);
                    int z = (int)((pos.z - terrainData.origin.z) / terrainData.cellSize);
                    x = Math.Max(0, Math.Min(terrainData.resolutionX - 1, x));
                    z = Math.Max(0, Math.Min(terrainData.resolutionZ - 1, z));

                    double slope = terrainData.GetSlope(x, z);
                    double roughness = terrainData.GetRoughness(x, z);

                    terrainRisk = (slope / 45.0 + roughness) * 0.5;
                }

                double altitudeRisk = clearance < 5.0 ? (5.0 - clearance) * 0.1 : 0;
                double pointRisk = Math.Max(terrainRisk, altitudeRisk);

                totalRisk += pointRisk;
            }

            return totalRisk / path.Count;
        }
    }
}
