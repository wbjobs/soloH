using System;
using UnityEngine;
using LanderSim.Core;

namespace LanderSim.Physics
{
    [Serializable]
    public class FuelConsumptionModel
    {
        public double thrustSpecificImpulse = 300.0;
        public double g0 = 9.81;
        public double maxThrust = 15000.0;
        public double minThrottle = 0.1;
        public double idleFuelConsumption = 0.5;

        private double prevFuelFlowRate = 0;
        private double prevIsp = 0;
        private double prevAltitude = 0;
        private double prevVelocity = 0;

        public double CalculateFuelFlowRate(double throttle, Vector3d thrustDirection,
                                           double altitude, double velocity,
                                           double gravity = 1.62, int integrationOrder = 2)
        {
            throttle = Math.Max(minThrottle, Math.Min(1.0, throttle));

            if (throttle < 0.01) return idleFuelConsumption;

            double thrust = throttle * maxThrust;

            double effectiveIsp = CalculateIspAtAltitude(altitude);

            double gravityLossFactor = CalculateGravityLossFactor(
                thrustDirection, throttle, gravity, effectiveIsp);

            double ve = effectiveIsp * g0;
            double idealFuelFlowRate = thrust / ve;

            double correctedFuelFlowRate = idealFuelFlowRate * gravityLossFactor;

            double dynamicPressure = 0.5 * 0.02 * velocity * velocity;
            double dragFactor = 1.0 + dynamicPressure * 0.0001;

            double angleOfAttack = Math.Acos(Vector3d.Dot(
                thrustDirection.normalized, Vector3d.up));
            double aoaFactor = 1.0 + Math.Abs(angleOfAttack) * 0.1;

            double instantaneousFuelFlow = correctedFuelFlowRate * dragFactor * aoaFactor + idleFuelConsumption;

            if (integrationOrder >= 2 && prevFuelFlowRate > 0)
            {
                instantaneousFuelFlow = ApplyTrapezoidalIntegration(
                    instantaneousFuelFlow, prevFuelFlowRate, altitude, prevAltitude,
                    velocity, prevVelocity, effectiveIsp, prevIsp);
            }

            prevFuelFlowRate = instantaneousFuelFlow;
            prevIsp = effectiveIsp;
            prevAltitude = altitude;
            prevVelocity = velocity;

            return instantaneousFuelFlow;
        }

        public double CalculateIspAtAltitude(double altitude)
        {
            double ispVariation = 1.0 - 0.0008 * altitude / 1000.0
                                  - 0.0002 * altitude * altitude / (1000.0 * 1000.0);
            double effectiveIsp = thrustSpecificImpulse * ispVariation;
            return Math.Max(150, Math.Min(thrustSpecificImpulse, effectiveIsp));
        }

        public double CalculateGravityLossFactor(Vector3d thrustDirection, double throttle,
                                                 double gravity, double currentIsp)
        {
            if (throttle < minThrottle) return 1.0;

            double thrustToWeightRatio = (throttle * maxThrust) / (gravity * 800.0);

            double cosTheta = Vector3d.Dot(thrustDirection.normalized, Vector3d.up);
            cosTheta = Math.Max(-1.0, Math.Min(1.0, cosTheta));

            double gravityLoss = 0;

            if (cosTheta > 0.01)
            {
                gravityLoss = gravity / (thrustToWeightRatio * cosTheta * currentIsp * g0);
            }
            else
            {
                gravityLoss = gravity / (thrustToWeightRatio * 0.01 * currentIsp * g0);
            }

            gravityLoss = Math.Max(0, Math.Min(0.5, gravityLoss));

            double gravityLossFactor = 1.0 + gravityLoss * 2.5;

            return gravityLossFactor;
        }

        public double CalculateTotalGravityLoss(double flightTime, double avgThrottle,
                                                double avgAltitude, double gravity)
        {
            double avgIsp = CalculateIspAtAltitude(avgAltitude);
            double thrustToWeightRatio = (avgThrottle * maxThrust) / (gravity * 800.0);

            if (thrustToWeightRatio <= 1.0) return double.PositiveInfinity;

            double gravityLossDeltaV = gravity * flightTime * (1.0 - 1.0 / thrustToWeightRatio);

            double requiredFuel = CalculateRequiredFuel(gravityLossDeltaV, 500.0);

            return requiredFuel;
        }

        private double ApplyTrapezoidalIntegration(double currentFlow, double prevFlow,
                                                    double currentAlt, double prevAlt,
                                                    double currentVel, double prevVel,
                                                    double currentIsp, double prevIsp)
        {
            double avgFlow = (currentFlow + prevFlow) * 0.5;

            double altCorrection = 1.0 + (currentAlt - prevAlt) * 0.0001;
            double velCorrection = 1.0 + Math.Abs(currentVel - prevVel) * 0.001;
            double ispCorrection = 2.0 / (currentIsp + prevIsp) * thrustSpecificImpulse;

            altCorrection = Math.Max(0.9, Math.Min(1.1, altCorrection));
            velCorrection = Math.Max(0.95, Math.Min(1.05, velCorrection));
            ispCorrection = Math.Max(0.95, Math.Min(1.05, ispCorrection));

            return avgFlow * altCorrection * velCorrection * ispCorrection;
        }

        public double IntegrateFuelConsumptionRK4(Func<double, double> flowRateFunction,
                                                  double startTime, double endTime,
                                                  int numSteps = 100)
        {
            double dt = (endTime - startTime) / numSteps;
            double totalFuel = 0;
            double t = startTime;

            for (int i = 0; i < numSteps; i++)
            {
                double k1 = flowRateFunction(t);
                double k2 = flowRateFunction(t + dt * 0.5);
                double k3 = flowRateFunction(t + dt * 0.5);
                double k4 = flowRateFunction(t + dt);

                totalFuel += (k1 + 2 * k2 + 2 * k3 + k4) * dt / 6.0;
                t += dt;
            }

            return totalFuel;
        }

        public void ResetIntegrationHistory()
        {
            prevFuelFlowRate = 0;
            prevIsp = 0;
            prevAltitude = 0;
            prevVelocity = 0;
        }

        public double CalculateDeltaV(double initialMass, double finalMass)
        {
            if (finalMass <= 0 || initialMass <= finalMass) return 0;
            return thrustSpecificImpulse * g0 * Math.Log(initialMass / finalMass);
        }

        public double CalculateRequiredFuel(double deltaV, double dryMass)
        {
            double massRatio = Math.Exp(deltaV / (thrustSpecificImpulse * g0));
            return dryMass * (massRatio - 1);
        }

        public double EstimateFuelForTrajectory(List<TrajectoryPoint> trajectory,
                                                double gravity = 1.62, int integrationOrder = 2)
        {
            if (trajectory == null || trajectory.Count < 2) return 0;

            ResetIntegrationHistory();
            double totalFuel = 0;

            for (int i = 1; i < trajectory.Count; i++)
            {
                double dt = trajectory[i].time - trajectory[i - 1].time;
                double avgThrottle = (trajectory[i].throttle + trajectory[i - 1].throttle) / 2;

                double velocity1 = trajectory[i - 1].velocity.magnitude;
                double velocity2 = trajectory[i].velocity.magnitude;
                double avgVelocity = (velocity1 + velocity2) * 0.5;

                double altitude1 = trajectory[i - 1].position.y;
                double altitude2 = trajectory[i].position.y;
                double avgAltitude = (altitude1 + altitude2) * 0.5;

                Vector3d thrustDir1 = trajectory[i - 1].attitude * Vector3d.up;
                Vector3d thrustDir2 = trajectory[i].attitude * Vector3d.up;

                double fuelRate1 = CalculateFuelFlowRate(
                    avgThrottle, thrustDir1, altitude1, velocity1, gravity, 1);
                double fuelRate2 = CalculateFuelFlowRate(
                    avgThrottle, thrustDir2, altitude2, velocity2, gravity, 1);

                if (integrationOrder >= 2)
                {
                    double avgFuelRate = (fuelRate1 + fuelRate2) * 0.5;

                    double dAltitude = altitude2 - altitude1;
                    double dVelocity = velocity2 - velocity1;

                    double altCorrection = 1.0 + dAltitude * 0.0001;
                    double velCorrection = 1.0 + Math.Abs(dVelocity) * 0.001;

                    altCorrection = Math.Max(0.95, Math.Min(1.05, altCorrection));
                    velCorrection = Math.Max(0.98, Math.Min(1.02, velCorrection));

                    totalFuel += avgFuelRate * dt * altCorrection * velCorrection;
                }
                else
                {
                    totalFuel += fuelRate2 * dt;
                }
            }

            double totalFlightTime = trajectory[trajectory.Count - 1].time - trajectory[0].time;
            double avgThrottleTotal = 0;
            foreach (var point in trajectory)
            {
                avgThrottleTotal += point.throttle;
            }
            avgThrottleTotal /= trajectory.Count;

            double avgAltitudeTotal = 0;
            foreach (var point in trajectory)
            {
                avgAltitudeTotal += point.position.y;
            }
            avgAltitudeTotal /= trajectory.Count;

            double gravityLossFuel = CalculateTotalGravityLoss(
                totalFlightTime, avgThrottleTotal, avgAltitudeTotal, gravity);

            if (gravityLossFuel < double.PositiveInfinity)
            {
                totalFuel += gravityLossFuel * 0.1;
            }

            return totalFuel;
        }

        public double GetMaximumDeltaV(double initialMass, double fuelMass)
        {
            return CalculateDeltaV(initialMass, initialMass - fuelMass);
        }

        public double GetRemainingBurnTime(double fuelMass, double throttle,
                                          double altitude, double velocity)
        {
            Vector3d thrustDir = Vector3d.up;
            double fuelRate = CalculateFuelFlowRate(throttle, thrustDir, altitude, velocity);
            return fuelRate > 0 ? fuelMass / fuelRate : double.PositiveInfinity;
        }
    }

    [Serializable]
    public class AttitudeController
    {
        public double maxAngularRate = 30.0;
        public double maxAngularAcceleration = 15.0;
        public double controlGain = 2.0;
        public double dampingGain = 1.0;

        public Quaterniond targetAttitude;
        public Vector3d targetAngularVelocity;

        public AttitudeController()
        {
            targetAttitude = Quaterniond.identity;
            targetAngularVelocity = Vector3d.zero;
        }

        public Vector3d CalculateTorque(LanderState state, double dt)
        {
            Quaterniond attitudeError = targetAttitude *
                Quaterniond.Conjugate(state.attitude);

            Vector3d errorAxis;
            double errorAngle;
            GetAxisAngle(attitudeError, out errorAxis, out errorAngle);

            if (errorAngle > Math.PI)
            {
                errorAngle = 2 * Math.PI - errorAngle;
                errorAxis = -errorAxis;
            }

            Vector3d angularError = errorAxis * errorAngle;
            Vector3d angularVelError = targetAngularVelocity - state.angularVelocity;

            Vector3d torque = controlGain * angularError + dampingGain * angularVelError;

            torque = ClampTorque(torque, state.angularVelocity, dt);

            return torque;
        }

        private void GetAxisAngle(Quaterniond q, out Vector3d axis, out double angle)
        {
            double w = q.w;
            double s = Math.Sqrt(1 - w * w);

            if (s < 1e-8)
            {
                axis = new Vector3d(1, 0, 0);
                angle = 0;
            }
            else
            {
                axis = new Vector3d(q.x / s, q.y / s, q.z / s);
                angle = 2 * Math.Acos(w);
            }
        }

        private Vector3d ClampTorque(Vector3d torque, Vector3d currentAngVel, double dt)
        {
            double maxTorque = maxAngularAcceleration * 100.0;

            Vector3d predictedAngVel = currentAngVel + torque / 100.0 * dt;
            double predMag = predictedAngVel.magnitude;

            if (predMag > maxAngularRate)
            {
                double scale = maxAngularRate / predMag;
                torque = torque * scale;
            }

            double torMag = torque.magnitude;
            if (torMag > maxTorque)
            {
                torque = torque * (maxTorque / torMag);
            }

            return torque;
        }

        public bool IsAttitudeValid(Quaterniond attitude)
        {
            Vector3d euler = attitude.eulerAngles;
            double pitch = Math.Abs(euler.y);
            double roll = Math.Abs(euler.x);

            return pitch < 45.0 && roll < 45.0;
        }

        public bool IsAttitudeSafeForLanding(Quaterniond attitude)
        {
            Vector3d thrustDir = attitude * Vector3d.up;
            double angle = Math.Acos(Vector3d.Dot(thrustDir, Vector3d.up)) * 180.0 / Math.PI;
            return angle < 15.0;
        }

        public double GetAttitudePenalty(Quaterniond attitude)
        {
            Vector3d euler = attitude.eulerAngles;
            double pitch = Math.Abs(euler.y);
            double roll = Math.Abs(euler.x);

            double penalty = 0;
            if (pitch > 30.0) penalty += (pitch - 30.0) * 0.1;
            if (roll > 30.0) penalty += (roll - 30.0) * 0.1;

            return penalty;
        }
    }

    public class LanderDynamics
    {
        public double gravity = 1.62;
        public double momentOfInertia = 100.0;
        public double dragCoefficient = 0.5;
        public double referenceArea = 10.0;
        public double atmosphericDensity = 0.02;

        private FuelConsumptionModel fuelModel;
        private AttitudeController attitudeController;

        public LanderDynamics(FuelConsumptionModel fuelModel,
                             AttitudeController attitudeController)
        {
            this.fuelModel = fuelModel;
            this.attitudeController = attitudeController;
        }

        public void UpdateState(LanderState state, double dt)
        {
            if (state.isLanded || state.isCrashed) return;

            Vector3d thrustDir = state.attitude * Vector3d.up;
            double thrust = state.throttle * fuelModel.maxThrust;
            Vector3d thrustForce = thrustDir * thrust;

            Vector3d gravityForce = Vector3d.down * gravity * state.mass;

            double velocity = state.velocity.magnitude;
            Vector3d dragForce = -state.velocity.normalized *
                (0.5 * atmosphericDensity * velocity * velocity *
                 dragCoefficient * referenceArea);

            Vector3d totalForce = thrustForce + gravityForce + dragForce;
            Vector3d acceleration = totalForce / state.mass;

            Vector3d torque = attitudeController.CalculateTorque(state, dt);
            Vector3d angularAcceleration = torque / momentOfInertia;

            Vector3d prevVelocity = state.velocity;
            Vector3d prevPosition = state.position;
            double prevFuelMass = state.fuelMass;
            double prevMass = state.mass;

            if (dt > 0.01)
            {
                int subSteps = Math.Max(1, (int)(dt / 0.01));
                double subDt = dt / subSteps;

                for (int step = 0; step < subSteps; step++)
                {
                    double t = (double)step / subSteps;
                    double interpThrottle = state.throttle;

                    Vector3d interpThrustDir = thrustDir;
                    double interpThrust = interpThrottle * fuelModel.maxThrust;
                    Vector3d interpThrustForce = interpThrustDir * interpThrust;

                    double curMass = prevMass - (prevMass - (state.dryMass + Math.Max(0, prevFuelMass -
                        fuelModel.CalculateFuelFlowRate(interpThrottle, interpThrustDir,
                            prevPosition.y, prevVelocity.magnitude, gravity, 1) * dt * t)));
                    curMass = Math.Max(state.dryMass, curMass);

                    Vector3d curGravityForce = Vector3d.down * gravity * curMass;

                    double curVelocityMag = (prevVelocity + acceleration * subDt * step).magnitude;
                    Vector3d curDragForce = -(prevVelocity + acceleration * subDt * step).normalized *
                        (0.5 * atmosphericDensity * curVelocityMag * curVelocityMag *
                         dragCoefficient * referenceArea);

                    Vector3d curTotalForce = interpThrustForce + curGravityForce + curDragForce;
                    Vector3d curAcceleration = curTotalForce / curMass;

                    state.velocity += curAcceleration * subDt;
                    state.position += state.velocity * subDt;

                    Vector3d curTorque = attitudeController.CalculateTorque(state, subDt);
                    Vector3d curAngularAccel = curTorque / momentOfInertia;
                    state.angularVelocity += curAngularAccel * subDt;

                    Vector3d angularVel = state.angularVelocity;
                    double angle = angularVel.magnitude * subDt;
                    if (angle > 1e-8)
                    {
                        Vector3d axis = angularVel.normalized;
                        double halfAngle = angle * 0.5;
                        Quaterniond deltaQ = new Quaterniond(
                            axis.x * Math.Sin(halfAngle),
                            axis.y * Math.Sin(halfAngle),
                            axis.z * Math.Sin(halfAngle),
                            Math.Cos(halfAngle)
                        );
                        state.attitude = (deltaQ * state.attitude).normalized;
                    }

                    double altitude = state.position.y;
                    double fuelRate = fuelModel.CalculateFuelFlowRate(
                        interpThrottle, interpThrustDir, altitude,
                        state.velocity.magnitude, gravity, 2);
                    double fuelUsed = fuelRate * subDt;

                    state.fuelMass = Math.Max(0, state.fuelMass - fuelUsed);
                    state.mass = state.dryMass + state.fuelMass;
                }
            }
            else
            {
                state.velocity += acceleration * dt;
                state.position += state.velocity * dt;

                Vector3d angularVel = state.angularVelocity;
                double angle = angularVel.magnitude * dt;
                if (angle > 1e-8)
                {
                    Vector3d axis = angularVel.normalized;
                    double halfAngle = angle * 0.5;
                    Quaterniond deltaQ = new Quaterniond(
                        axis.x * Math.Sin(halfAngle),
                        axis.y * Math.Sin(halfAngle),
                        axis.z * Math.Sin(halfAngle),
                        Math.Cos(halfAngle)
                    );
                    state.attitude = (deltaQ * state.attitude).normalized;
                }

                double altitude = state.position.y;
                double fuelRate = fuelModel.CalculateFuelFlowRate(
                    state.throttle, thrustDir, altitude, velocity, gravity, 2);
                double fuelUsed = fuelRate * dt;

                state.fuelMass = Math.Max(0, state.fuelMass - fuelUsed);
                state.mass = state.dryMass + state.fuelMass;
            }

            state.angularVelocity += angularAcceleration * dt;

            if (state.fuelMass <= 0)
            {
                state.throttle = 0;
            }
        }

        public bool CheckLanding(LanderState state, double terrainHeight)
        {
            double heightAboveTerrain = state.position.y - terrainHeight;
            double verticalSpeed = state.velocity.y;

            if (heightAboveTerrain < 0.5 && verticalSpeed < -5.0)
            {
                state.isCrashed = true;
                return false;
            }

            if (heightAboveTerrain < 0.1 && Math.Abs(verticalSpeed) < 2.0)
            {
                Vector3d thrustDir = state.attitude * Vector3d.up;
                double attitudeAngle = Math.Acos(Vector3d.Dot(thrustDir, Vector3d.up))
                    * 180.0 / Math.PI;

                if (attitudeAngle < 20.0 && state.velocity.magnitude < 3.0)
                {
                    state.isLanded = true;
                    state.velocity = Vector3d.zero;
                    state.angularVelocity = Vector3d.zero;
                    state.throttle = 0;
                    return true;
                }
            }

            return false;
        }

        public TrajectoryPoint CreateTrajectoryPoint(LanderState state, double time)
        {
            return new TrajectoryPoint(
                state.position,
                state.velocity,
                state.attitude,
                state.mass,
                state.fuelMass,
                time,
                state.throttle,
                0
            );
        }
    }
}
