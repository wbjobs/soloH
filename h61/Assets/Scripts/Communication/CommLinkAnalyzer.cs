using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;
using LanderSim.Terrain;

namespace LanderSim.Communication
{
    [Serializable]
    public class RelaySatellite
    {
        public string name;
        public Vector3d position;
        public Vector3d velocity;
        public double orbitalPeriod;
        public double orbitalRadius;
        public double inclination;
        public double rightAscension;
        public double meanAnomaly;
        public double transmitPower;
        public double antennaGain;
        public double frequency;
        public double minimumElevationAngle;

        private double currentTime;

        public RelaySatellite(string name, double orbitalRadius, double inclination,
                              double rightAscension, double meanAnomaly,
                              double transmitPower = 100.0, double antennaGain = 30.0,
                              double frequency = 8.4e9, double minElevation = 10.0)
        {
            this.name = name;
            this.orbitalRadius = orbitalRadius;
            this.inclination = inclination;
            this.rightAscension = rightAscension;
            this.meanAnomaly = meanAnomaly;
            this.transmitPower = transmitPower;
            this.antennaGain = antennaGain;
            this.frequency = frequency;
            this.minimumElevationAngle = minElevation;

            double gravitationalParameter = 4.2828e13;
            orbitalPeriod = 2 * Math.PI * Math.Sqrt(Math.Pow(orbitalRadius, 3) / gravitationalParameter);

            currentTime = 0;
            UpdatePosition(0);
        }

        public void UpdatePosition(double time)
        {
            currentTime = time;

            double meanMotion = 2 * Math.PI / orbitalPeriod;
            double currentMeanAnomaly = meanAnomaly + meanMotion * time;
            currentMeanAnomaly = currentMeanAnomaly % (2 * Math.PI);

            double eccentricAnomaly = SolveKeplerEquation(currentMeanAnomaly);
            double trueAnomaly = 2 * Math.Atan2(
                Math.Sqrt(1.0 + 0.0) * Math.Sin(eccentricAnomaly / 2),
                Math.Cos(eccentricAnomaly / 2)
            );

            double radius = orbitalRadius * (1 - 0.0 * Math.Cos(eccentricAnomaly));

            double xOrbit = radius * Math.Cos(trueAnomaly);
            double yOrbit = radius * Math.Sin(trueAnomaly);

            double i = inclination * Math.PI / 180.0;
            double raan = rightAscension * Math.PI / 180.0;

            double x = xOrbit * Math.Cos(raan) - yOrbit * Math.Cos(i) * Math.Sin(raan);
            double y = xOrbit * Math.Sin(raan) + yOrbit * Math.Cos(i) * Math.Cos(raan);
            double z = yOrbit * Math.Sin(i);

            position = new Vector3d(x, z, y);

            double theta_dot = meanMotion * Math.Pow(orbitalRadius / radius, 2);
            double vxOrbit = -radius * theta_dot * Math.Sin(trueAnomaly);
            double vyOrbit = radius * theta_dot * Math.Cos(trueAnomaly);

            double vx = vxOrbit * Math.Cos(raan) - vyOrbit * Math.Cos(i) * Math.Sin(raan);
            double vy = vxOrbit * Math.Sin(raan) + vyOrbit * Math.Cos(i) * Math.Cos(raan);
            double vz = vyOrbit * Math.Sin(i);

            velocity = new Vector3d(vx, vz, vy);
        }

        private double SolveKeplerEquation(double meanAnomaly)
        {
            double E = meanAnomaly;
            for (int i = 0; i < 100; i++)
            {
                double dE = (meanAnomaly - (E - 0.0 * Math.Sin(E))) / (1 - 0.0 * Math.Cos(E));
                E += dE;
                if (Math.Abs(dE) < 1e-10) break;
            }
            return E;
        }

        public double GetElevationAngle(Vector3d groundPoint)
        {
            Vector3d toSat = position - groundPoint;
            Vector3d zenith = groundPoint.normalized;

            double elevation = 90.0 - Vector3d.Angle(toSat, zenith) * 180.0 / Math.PI;
            return elevation;
        }

        public double GetAzimuthAngle(Vector3d groundPoint)
        {
            Vector3d toSat = position - groundPoint;
            Vector3d east = Vector3d.Cross(Vector3d.up, groundPoint.normalized).normalized;
            Vector3d north = Vector3d.Cross(groundPoint.normalized, east).normalized;

            double az = Math.Atan2(
                Vector3d.Dot(toSat, east),
                Vector3d.Dot(toSat, north)
            ) * 180.0 / Math.PI;

            if (az < 0) az += 360.0;
            return az;
        }

        public double GetDopplerShift(Vector3d groundPoint, Vector3d groundVelocity)
        {
            Vector3d toSat = position - groundPoint;
            double range = toSat.magnitude;
            Vector3d lineOfSight = toSat / range;

            double relativeVelocity = Vector3d.Dot(velocity - groundVelocity, lineOfSight);
            double dopplerShift = -frequency * relativeVelocity / 299792458.0;

            return dopplerShift;
        }

        public double GetPathLoss(Vector3d groundPoint)
        {
            double range = (position - groundPoint).magnitude;
            double wavelength = 299792458.0 / frequency;

            double freeSpacePathLoss = 20 * Math.Log10(4 * Math.PI * range / wavelength);

            return freeSpacePathLoss;
        }

        public double GetReceivedPower(Vector3d groundPoint, double groundAntennaGain = 20.0)
        {
            double pathLoss = GetPathLoss(groundPoint);
            double receivedPower = transmitPower + antennaGain + groundAntennaGain - pathLoss;

            return receivedPower;
        }

        public bool HasLineOfSight(Vector3d groundPoint, TerrainData terrainData)
        {
            double elevation = GetElevationAngle(groundPoint);
            if (elevation < minimumElevationAngle) return false;

            Vector3d toSat = position - groundPoint;
            double distance = toSat.magnitude;
            Vector3d direction = toSat / distance;

            double stepSize = 500.0;
            int steps = (int)(distance / stepSize);

            for (int i = 1; i < steps; i++)
            {
                Vector3d point = groundPoint + direction * stepSize * i;
                double terrainHeight = 0;

                if (terrainData != null)
                {
                    if (terrainData.IsInBounds((float)point.x, (float)point.z))
                    {
                        terrainHeight = terrainData.GetHeight((float)point.x, (float)point.z);
                    }
                }

                if (point.y < terrainHeight + 1.0)
                {
                    return false;
                }
            }

            return true;
        }
    }

    [Serializable]
    public class LinkBudget
    {
        public double receivedPower;
        public double pathLoss;
        public double carrierToNoiseRatio;
        public double dataRate;
        public double bitErrorRate;
        public double margin;
        public double fadeMargin;
        public double totalLoss;
        public double eirp;
        public double noiseFloor;
        public double signalToNoiseRatio;
        public double energyPerBit;

        public override string ToString()
        {
            return $"P_rx={receivedPower:F1} dBm, C/N={carrierToNoiseRatio:F1} dB, " +
                   $"Data Rate={dataRate:F0} bps, BER={bitErrorRate:E2}, Margin={margin:F1} dB";
        }
    }

    [Serializable]
    public class CommunicationEvent
    {
        public double startTime;
        public double endTime;
        public double duration;
        public RelaySatellite satellite;
        public double maxElevation;
        public double avgElevation;
        public double minRange;
        public double maxRange;
        public double avgDataRate;
        public double totalDataTransferred;

        public override string ToString()
        {
            return $"{satellite.name}: {startTime:F0}-{endTime:F0}s, " +
                   $"Max El={maxElevation:F1}°, Duration={duration:F0}s";
        }
    }

    public class CommLinkAnalyzer
    {
        public List<RelaySatellite> satellites = new List<RelaySatellite>();
        public TerrainData terrainData;

        [Header("Ground Terminal")]
        public double groundAntennaGain = 20.0;
        public double groundNoiseTemperature = 300.0;
        public double systemNoiseFigure = 3.0;
        public double operatingBandwidth = 1.0e6;
        public double minEbN0 = 6.0;

        [Header("Atmospheric Loss")]
        public double atmosphericLossAtZenith = 0.5;
        public double cloudLoss = 2.0;
        public double scintillationLoss = 1.0;

        [Header("Margin Settings")]
        public double requiredLinkMargin = 3.0;

        private double currentTime;
        private List<CommunicationEvent> communicationEvents = new List<CommunicationEvent>();
        private CommunicationEvent currentEvent;
        private bool wasInContact;

        public List<CommunicationEvent> CommunicationEvents => communicationEvents;

        public CommLinkAnalyzer(TerrainData terrainData = null)
        {
            this.terrainData = terrainData;
            InitializeSatelliteConstellation();
        }

        private void InitializeSatelliteConstellation()
        {
            double marsRadius = 3389500.0;
            double relayOrbitAltitude = 400000.0;
            double relayOrbitRadius = marsRadius + relayOrbitAltitude;

            satellites.Add(new RelaySatellite(
                "Mars Reconnaissance Orbiter",
                relayOrbitRadius,
                93.0,
                0.0,
                0.0,
                100.0,
                35.0,
                8.4e9,
                10.0
            ));

            satellites.Add(new RelaySatellite(
                "Mars Odyssey",
                relayOrbitRadius,
                93.0,
                120.0,
                Math.PI * 2.0 / 3.0,
                80.0,
                32.0,
                7.2e9,
                10.0
            ));

            satellites.Add(new RelaySatellite(
                "Mars Express",
                relayOrbitRadius,
                87.0,
                240.0,
                Math.PI * 4.0 / 3.0,
                60.0,
                30.0,
                2.1e9,
                10.0
            ));
        }

        public void Update(double time, Vector3d landerPosition, Vector3d landerVelocity)
        {
            currentTime = time;

            foreach (var sat in satellites)
            {
                sat.UpdatePosition(time);
            }

            CheckContactEvents(landerPosition, landerVelocity);
        }

        private void CheckContactEvents(Vector3d landerPosition, Vector3d landerVelocity)
        {
            bool inContact = false;
            RelaySatellite bestSatellite = null;
            double bestElevation = -999;

            foreach (var sat in satellites)
            {
                if (sat.HasLineOfSight(landerPosition, terrainData))
                {
                    double elevation = sat.GetElevationAngle(landerPosition);
                    if (elevation > bestElevation)
                    {
                        bestElevation = elevation;
                        bestSatellite = sat;
                        inContact = true;
                    }
                }
            }

            if (inContact && !wasInContact)
            {
                currentEvent = new CommunicationEvent
                {
                    startTime = currentTime,
                    satellite = bestSatellite,
                    maxElevation = bestElevation,
                    avgElevation = bestElevation,
                    minRange = (bestSatellite.position - landerPosition).magnitude,
                    maxRange = (bestSatellite.position - landerPosition).magnitude
                };
            }
            else if (inContact && wasInContact)
            {
                if (currentEvent != null)
                {
                    double elevation = bestSatellite.GetElevationAngle(landerPosition);
                    double range = (bestSatellite.position - landerPosition).magnitude;

                    currentEvent.maxElevation = Math.Max(currentEvent.maxElevation, elevation);
                    currentEvent.avgElevation = (currentEvent.avgElevation *
                        (currentTime - currentEvent.startTime) + elevation) /
                        (currentTime - currentEvent.startTime + 1);
                    currentEvent.minRange = Math.Min(currentEvent.minRange, range);
                    currentEvent.maxRange = Math.Max(currentEvent.maxRange, range);

                    LinkBudget budget = CalculateLinkBudget(bestSatellite, landerPosition, landerVelocity);
                    currentEvent.avgDataRate = (currentEvent.avgDataRate *
                        (currentTime - currentEvent.startTime) + budget.dataRate) /
                        (currentTime - currentEvent.startTime + 1);
                }
            }
            else if (!inContact && wasInContact)
            {
                if (currentEvent != null)
                {
                    currentEvent.endTime = currentTime;
                    currentEvent.duration = currentEvent.endTime - currentEvent.startTime;
                    currentEvent.totalDataTransferred = currentEvent.avgDataRate * currentEvent.duration;
                    communicationEvents.Add(currentEvent);
                    currentEvent = null;
                }
            }

            wasInContact = inContact;
        }

        public LinkBudget CalculateLinkBudget(RelaySatellite sat, Vector3d groundPoint,
                                              Vector3d groundVelocity)
        {
            LinkBudget budget = new LinkBudget();

            double elevation = sat.GetElevationAngle(groundPoint);
            double zenithAngle = 90.0 - elevation;

            budget.eirp = sat.transmitPower + sat.antennaGain;

            budget.pathLoss = sat.GetPathLoss(groundPoint);

            double slantRangeFactor = 1.0 / Math.Cos(zenithAngle * Math.PI / 180.0);
            double atmosphericLoss = atmosphericLossAtZenith * slantRangeFactor;
            double totalAtmosphericLoss = atmosphericLoss + cloudLoss + scintillationLoss;
            budget.totalLoss = budget.pathLoss + totalAtmosphericLoss;

            budget.receivedPower = budget.eirp + groundAntennaGain - budget.totalLoss;

            double boltzmannConstant = 1.38e-23;
            double kT = 10 * Math.Log10(boltzmannConstant * groundNoiseTemperature * 1000);
            budget.noiseFloor = kT + 10 * Math.Log10(operatingBandwidth) + systemNoiseFigure;

            budget.carrierToNoiseRatio = budget.receivedPower - budget.noiseFloor;

            double dataRate = Math.Pow(10, (budget.carrierToNoiseRatio - minEbN0) / 10.0);
            budget.dataRate = Math.Max(0, dataRate);

            budget.energyPerBit = budget.carrierToNoiseRatio - 10 * Math.Log10(budget.dataRate / operatingBandwidth);

            budget.bitErrorRate = CalculateBER(budget.energyPerBit);

            budget.margin = budget.carrierToNoiseRatio - minEbN0
                            - 10 * Math.Log10(budget.dataRate / operatingBandwidth);

            budget.fadeMargin = budget.margin - requiredLinkMargin;

            return budget;
        }

        private double CalculateBER(double ebN0)
        {
            double ebN0Linear = Math.Pow(10, ebN0 / 10.0);

            if (ebN0Linear <= 0) return 0.5;

            double ber = 0.5 * Math.Erfc(Math.Sqrt(ebN0Linear));

            return Math.Max(1e-15, Math.Min(0.5, ber));
        }

        public List<RelaySatellite> GetVisibleSatellites(Vector3d groundPoint)
        {
            List<RelaySatellite> visible = new List<RelaySatellite>();

            foreach (var sat in satellites)
            {
                if (sat.HasLineOfSight(groundPoint, terrainData))
                {
                    visible.Add(sat);
                }
            }

            return visible;
        }

        public RelaySatellite GetBestSatellite(Vector3d groundPoint)
        {
            RelaySatellite best = null;
            double bestElevation = -999;

            foreach (var sat in satellites)
            {
                if (sat.HasLineOfSight(groundPoint, terrainData))
                {
                    double elevation = sat.GetElevationAngle(groundPoint);
                    if (elevation > bestElevation)
                    {
                        bestElevation = elevation;
                        best = sat;
                    }
                }
            }

            return best;
        }

        public double GetCoveragePercentage(Vector3d groundPoint, double simulationTime = 86400.0)
        {
            int visibleTimeSteps = 0;
            int totalTimeSteps = 1000;
            double dt = simulationTime / totalTimeSteps;

            for (int i = 0; i < totalTimeSteps; i++)
            {
                double time = i * dt;

                foreach (var sat in satellites)
                {
                    sat.UpdatePosition(time);
                }

                foreach (var sat in satellites)
                {
                    if (sat.HasLineOfSight(groundPoint, terrainData))
                    {
                        visibleTimeSteps++;
                        break;
                    }
                }
            }

            return (double)visibleTimeSteps / totalTimeSteps * 100.0;
        }

        public double[,] GenerateCoverageMap(double[,] heightMap, double simTime = 86400.0)
        {
            int width = heightMap.GetLength(0);
            int height = heightMap.GetLength(1);
            double[,] coverageMap = new double[width, height];

            for (int x = 0; x < width; x += 4)
            {
                for (int z = 0; z < height; z += 4)
                {
                    Vector3d point = new Vector3d(x * 10, heightMap[x, z], z * 10);
                    double coverage = GetCoveragePercentage(point, simTime);

                    for (int dx = 0; dx < 4 && x + dx < width; dx++)
                    {
                        for (int dz = 0; dz < 4 && z + dz < height; dz++)
                        {
                            coverageMap[x + dx, z + dz] = coverage;
                        }
                    }
                }
            }

            return coverageMap;
        }

        public double GetNextContactTime(Vector3d groundPoint, double currentTime,
                                          out double contactDuration,
                                          out double maxElevation)
        {
            contactDuration = 0;
            maxElevation = 0;

            double searchTime = currentTime;
            double maxSearchTime = currentTime + 86400.0;
            double timeStep = 30.0;

            while (searchTime < maxSearchTime)
            {
                bool foundContact = false;
                double contactStart = 0;
                double contactEnd = 0;
                double contactMaxElev = 0;

                foreach (var sat in satellites)
                {
                    sat.UpdatePosition(searchTime);

                    if (sat.HasLineOfSight(groundPoint, terrainData))
                    {
                        contactStart = searchTime;

                        double fineTime = searchTime;
                        double fineStep = 5.0;
                        while (fineTime < searchTime + 7200.0)
                        {
                            sat.UpdatePosition(fineTime);
                            double elev = sat.GetElevationAngle(groundPoint);

                            if (!sat.HasLineOfSight(groundPoint, terrainData))
                            {
                                contactEnd = fineTime;
                                break;
                            }

                            if (elev > contactMaxElev)
                            {
                                contactMaxElev = elev;
                            }

                            fineTime += fineStep;
                        }

                        if (contactEnd == 0) contactEnd = fineTime;

                        foundContact = true;
                        contactDuration = contactEnd - contactStart;
                        maxElevation = contactMaxElev;
                        break;
                    }
                }

                if (foundContact)
                {
                    return contactStart - currentTime;
                }

                searchTime += timeStep;
            }

            return -1;
        }

        public List<CommunicationEvent> PredictContacts(Vector3d groundPoint,
                                                        double predictionDuration = 86400.0)
        {
            List<CommunicationEvent> predictions = new List<CommunicationEvent>();

            double timeStep = 10.0;
            double currentSimTime = 0;

            while (currentSimTime < predictionDuration)
            {
                foreach (var sat in satellites)
                {
                    sat.UpdatePosition(currentSimTime);
                }

                foreach (var sat in satellites)
                {
                    if (sat.HasLineOfSight(groundPoint, terrainData))
                    {
                        double startTime = currentSimTime;
                        double endTime = currentSimTime;
                        double maxElev = sat.GetElevationAngle(groundPoint);

                        double fineTime = currentSimTime;
                        double fineStep = 5.0;
                        double totalRange = 0;
                        int rangeSamples = 0;

                        while (fineTime < currentSimTime + 7200.0)
                        {
                            sat.UpdatePosition(fineTime);
                            if (!sat.HasLineOfSight(groundPoint, terrainData))
                            {
                                endTime = fineTime;
                                break;
                            }

                            double elev = sat.GetElevationAngle(groundPoint);
                            if (elev > maxElev) maxElev = elev;
                            totalRange += (sat.position - groundPoint).magnitude;
                            rangeSamples++;

                            fineTime += fineStep;
                            endTime = fineTime;
                        }

                        if (endTime - startTime > 60.0)
                        {
                            LinkBudget budget = CalculateLinkBudget(sat, groundPoint, Vector3d.zero);
                            predictions.Add(new CommunicationEvent
                            {
                                startTime = startTime,
                                endTime = endTime,
                                duration = endTime - startTime,
                                satellite = sat,
                                maxElevation = maxElev,
                                avgElevation = maxElev * 0.7,
                                minRange = totalRange / rangeSamples * 0.8,
                                maxRange = totalRange / rangeSamples * 1.2,
                                avgDataRate = budget.dataRate,
                                totalDataTransferred = budget.dataRate * (endTime - startTime)
                            });
                        }

                        currentSimTime = endTime + 300;
                        break;
                    }
                }

                currentSimTime += timeStep;
            }

            return predictions;
        }

        public string GetStatusReport(Vector3d groundPoint)
        {
            var visible = GetVisibleSatellites(groundPoint);
            var bestSat = GetBestSatellite(groundPoint);

            string report = $"=== Communication Status ===\n";
            report += $"Time: {currentTime:F1}s\n";
            report += $"Visible Satellites: {visible.Count}/3\n\n";

            foreach (var sat in satellites)
            {
                double elevation = sat.GetElevationAngle(groundPoint);
                double azimuth = sat.GetAzimuthAngle(groundPoint);
                double range = (sat.position - groundPoint).magnitude / 1000.0;
                bool los = sat.HasLineOfSight(groundPoint, terrainData);

                report += $"{sat.name}:\n";
                report += $"  Elevation: {elevation:F1}°\n";
                report += $"  Azimuth: {azimuth:F1}°\n";
                report += $"  Range: {range:F0} km\n";
                report += $"  Line of Sight: {(los ? "YES" : "NO")}\n";

                if (los)
                {
                    LinkBudget budget = CalculateLinkBudget(sat, groundPoint, Vector3d.zero);
                    report += $"  Data Rate: {budget.dataRate / 1000:F1} kbps\n";
                    report += $"  Margin: {budget.margin:F1} dB\n\n";
                }
                else
                {
                    report += "\n";
                }
            }

            if (communicationEvents.Count > 0)
            {
                report += $"\n=== Last Contact ===\n";
                var lastEvent = communicationEvents[communicationEvents.Count - 1];
                report += $"{lastEvent.ToString()}\n";
                report += $"Data Transferred: {lastEvent.totalDataTransferred / 1e6:F2} MB\n";
            }

            return report;
        }
    }
}
