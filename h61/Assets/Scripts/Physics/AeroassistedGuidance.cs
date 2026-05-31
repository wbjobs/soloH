using System;
using System.Collections.Generic;
using UnityEngine;
using LanderSim.Core;

namespace LanderSim.Physics
{
    [Serializable]
    public class AtmosphericModel
    {
        public double scaleHeight = 11.1;
        public double surfacePressure = 610.0;
        public double surfaceTemperature = 210.0;
        public double molarMass = 0.04334;
        public double gasConstant = 8.314;
        public double adiabaticIndex = 1.3;

        public double GetDensity(double altitude)
        {
            double temperature = surfaceTemperature - 0.0015 * altitude * 1000.0;
            temperature = Math.Max(100.0, temperature);

            double pressure = surfacePressure * Math.Exp(
                -9.81 * molarMass * altitude * 1000.0 / (gasConstant * surfaceTemperature));

            double density = pressure * molarMass / (gasConstant * temperature);

            return density;
        }

        public double GetSpeedOfSound(double altitude)
        {
            double temperature = surfaceTemperature - 0.0015 * altitude * 1000.0;
            temperature = Math.Max(100.0, temperature);
            return Math.Sqrt(adiabaticIndex * gasConstant * temperature / molarMass);
        }

        public double GetMachNumber(double velocity, double altitude)
        {
            return velocity / GetSpeedOfSound(altitude);
        }
    }

    [Serializable]
    public class AerodynamicCoefficients
    {
        public double C_L_alpha = 3.5;
        public double C_D0 = 0.05;
        public double C_D_induced = 0.03;
        public double C_m_alpha = -0.5;
        public double C_m_q = -1.0;
        public double maxLiftCoeff = 1.2;
        public double maxDragCoeff = 1.5;

        public double GetLiftCoeff(double angleOfAttack, double machNumber)
        {
            double aoaRad = angleOfAttack * Math.PI / 180.0;
            double C_L = C_L_alpha * aoaRad;

            double machFactor = 1.0;
            if (machNumber > 1.0)
            {
                machFactor = 1.0 / Math.Sqrt(machNumber * machNumber - 1.0);
            }
            else if (machNumber > 0.8)
            {
                machFactor = 1.0 / Math.Sqrt(1.0 - 0.8 * 0.8);
            }

            C_L *= machFactor;
            return Math.Max(-maxLiftCoeff, Math.Min(maxLiftCoeff, C_L));
        }

        public double GetDragCoeff(double angleOfAttack, double machNumber, double liftCoeff)
        {
            double aoaRad = angleOfAttack * Math.PI / 180.0;
            double C_D = C_D0 + C_D_induced * liftCoeff * liftCoeff;

            double waveDrag = 0;
            if (machNumber > 1.0)
            {
                waveDrag = 0.1 * (machNumber - 1.0);
            }
            else if (machNumber > 0.8)
            {
                waveDrag = 0.2 * Math.Pow((machNumber - 0.8) / 0.2, 2.0);
            }

            C_D += waveDrag;
            return Math.Min(maxDragCoeff, C_D);
        }

        public double GetPitchingMomentCoeff(double angleOfAttack, double pitchRate,
                                           double machNumber, double meanChord, double velocity)
        {
            double aoaRad = angleOfAttack * Math.PI / 180.0;
            double C_m = C_m_alpha * aoaRad;

            double q = pitchRate * meanChord / (2.0 * Math.Max(1.0, velocity));
            C_m += C_m_q * q;

            return C_m;
        }
    }

    public enum EntryPhase
    {
        Cruise,
        EntryInterface,
        Hypersonic,
        Supersonic,
        Transonic,
        Subsonic,
        ParachuteDeployment,
        TerminalDescent,
        PoweredDescent
    }

    public class AeroassistedGuidance
    {
        public AtmosphericModel atmosphere = new AtmosphericModel();
        public AerodynamicCoefficients aerodynamics = new AerodynamicCoefficients();

        [Header("Vehicle Properties")]
        public double referenceArea = 15.0;
        public double meanAerodynamicChord = 3.0;
        public double liftToDragRatio = 3.5;
        public double maxBankAngle = 75.0;
        public double maxAngleOfAttack = 20.0;

        [Header("Guidance Parameters")]
        public double entryInterfaceAltitude = 125.0;
        public double parachuteDeploymentAltitude = 10.0;
        public double targetLandingEllipseMajor = 20.0;
        public double targetLandingEllipseMinor = 10.0;

        [Header("Thermal Constraints")]
        public double maxHeatFlux = 100.0;
        public double maxStagnationPressure = 10000.0;
        public double maxDeceleration = 15.0;

        [Header("Bank Angle Control")]
        public double bankAngleDeadband = 5.0;
        public double bankAngleRateLimit = 10.0;

        private EntryPhase currentPhase = EntryPhase.Cruise;
        private double currentBankAngle = 0;
        private double currentAngleOfAttack = 15.0;
        private double referenceRange = 0;
        private double predictedRange = 0;
        private Vector3d downrangeDirection;

        private List<AeroTrajectoryPoint> aeroTrajectory = new List<AeroTrajectoryPoint>();

        public EntryPhase CurrentPhase => currentPhase;
        public double CurrentBankAngle => currentBankAngle;
        public double CurrentAngleOfAttack => currentAngleOfAttack;
        public List<AeroTrajectoryPoint> AeroTrajectory => aeroTrajectory;

        public void InitializeEntry(Vector3d entryPosition, Vector3d entryVelocity)
        {
            currentPhase = EntryPhase.EntryInterface;
            downrangeDirection = new Vector3d(entryVelocity.x, 0, entryVelocity.z).normalized;
            referenceRange = 0;
            aeroTrajectory.Clear();
            currentBankAngle = 0;
            currentAngleOfAttack = 15.0;
        }

        public AeroTrajectoryPoint UpdateAeroGuidance(LanderState state, Vector3d targetPosition, double dt)
        {
            UpdateEntryPhase(state);

            double altitude = state.position.y / 1000.0;
            double velocity = state.velocity.magnitude;
            double machNumber = atmosphere.GetMachNumber(velocity, altitude);
            double density = atmosphere.GetDensity(altitude);

            double angleOfAttack = CalculateOptimalAOA(state, machNumber);
            double bankAngle = CalculateBankAngle(state, targetPosition, machNumber);

            Vector3d liftForce, dragForce;
            Vector3d moments;
            CalculateAerodynamicForces(state, angleOfAttack, bankAngle, machNumber, density,
                                        out liftForce, out dragForce, out moments);

            double heatFlux = CalculateStagnationHeatFlux(velocity, density);
            double deceleration = (liftForce + dragForce).magnitude / state.mass / 9.81;
            double stagnationPressure = 0.5 * density * velocity * velocity;

            CheckThermalConstraints(heatFlux, deceleration, stagnationPressure, ref bankAngle);

            double rangeError = CalculateRangeError(state, targetPosition);

            currentAngleOfAttack = angleOfAttack;
            currentBankAngle = bankAngle;

            AeroTrajectoryPoint point = new AeroTrajectoryPoint
            {
                time = state.time,
                position = state.position,
                velocity = state.velocity,
                machNumber = machNumber,
                dynamicPressure = 0.5 * density * velocity * velocity,
                heatFlux = heatFlux,
                deceleration = deceleration,
                angleOfAttack = angleOfAttack,
                bankAngle = bankAngle,
                liftForce = liftForce,
                dragForce = dragForce,
                rangeError = rangeError,
                phase = currentPhase
            };

            aeroTrajectory.Add(point);

            return point;
        }

        private void UpdateEntryPhase(LanderState state)
        {
            double altitude = state.position.y / 1000.0;
            double velocity = state.velocity.magnitude;
            double machNumber = atmosphere.GetMachNumber(velocity, altitude);

            if (altitude > entryInterfaceAltitude)
            {
                currentPhase = EntryPhase.Cruise;
            }
            else if (altitude > 90.0)
            {
                currentPhase = EntryPhase.EntryInterface;
            }
            else if (machNumber > 5.0)
            {
                currentPhase = EntryPhase.Hypersonic;
            }
            else if (machNumber > 1.2)
            {
                currentPhase = EntryPhase.Supersonic;
            }
            else if (machNumber > 0.8)
            {
                currentPhase = EntryPhase.Transonic;
            }
            else if (altitude > parachuteDeploymentAltitude)
            {
                currentPhase = EntryPhase.Subsonic;
            }
            else if (altitude > 2.0)
            {
                currentPhase = EntryPhase.ParachuteDeployment;
            }
            else
            {
                currentPhase = EntryPhase.TerminalDescent;
            }
        }

        private double CalculateOptimalAOA(LanderState state, double machNumber)
        {
            double optimalAOA = 0;

            if (machNumber > 8.0)
            {
                optimalAOA = 16.0;
            }
            else if (machNumber > 5.0)
            {
                optimalAOA = 14.0;
            }
            else if (machNumber > 2.0)
            {
                optimalAOA = 12.0;
            }
            else if (machNumber > 1.0)
            {
                optimalAOA = 10.0;
            }
            else
            {
                optimalAOA = 8.0;
            }

            optimalAOA = Math.Max(0, Math.Min(maxAngleOfAttack, optimalAOA));

            double targetAOA = optimalAOA;
            double rate = 5.0;
            double delta = targetAOA - currentAngleOfAttack;
            double maxDelta = rate * Time.deltaTime;

            return currentAngleOfAttack + Math.Max(-maxDelta, Math.Min(maxDelta, delta));
        }

        private double CalculateBankAngle(LanderState state, Vector3d targetPosition, double machNumber)
        {
            Vector3d horizontalPos = new Vector3d(state.position.x, 0, state.position.z);
            Vector3d targetHorizontal = new Vector3d(targetPosition.x, 0, targetPosition.z);
            Vector3d toTarget = targetHorizontal - horizontalPos;

            double downrangeDistance = Vector3d.Dot(toTarget, downrangeDirection);
            double crossrangeDistance = Vector3d.Dot(toTarget, Vector3d.Cross(Vector3d.up, downrangeDirection));

            double targetBankAngle = 0;

            if (Math.Abs(crossrangeDistance) > bankAngleDeadband)
            {
                targetBankAngle = Math.Sign(crossrangeDistance) * Math.Min(
                    maxBankAngle,
                    Math.Abs(crossrangeDistance) * 2.0 + 10.0
                );
            }

            if (downrangeDistance < 0)
            {
                targetBankAngle = Math.Sign(targetBankAngle) * Math.Min(
                    Math.Abs(targetBankAngle) + 10.0,
                    maxBankAngle
                );
            }

            if (machNumber < 5.0)
            {
                targetBankAngle *= 0.5;
            }
            if (machNumber < 2.0)
            {
                targetBankAngle *= 0.3;
            }

            double rate = bankAngleRateLimit * Time.deltaTime;
            double delta = targetBankAngle - currentBankAngle;

            return currentBankAngle + Math.Max(-rate, Math.Min(rate, delta));
        }

        private void CalculateAerodynamicForces(LanderState state, double angleOfAttack,
                                                double bankAngle, double machNumber, double density,
                                                out Vector3d liftForce, out Vector3d dragForce,
                                                out Vector3d moments)
        {
            double velocity = state.velocity.magnitude;
            double dynamicPressure = 0.5 * density * velocity * velocity;

            double C_L = aerodynamics.GetLiftCoeff(angleOfAttack, machNumber);
            double C_D = aerodynamics.GetDragCoeff(angleOfAttack, machNumber, C_L);

            Vector3d velocityDir = state.velocity.normalized;

            Vector3d up = Vector3d.up;
            Vector3d liftNormal = Vector3d.Cross(velocityDir, up).normalized;
            if (liftNormal.sqrMagnitude < 1e-6)
            {
                liftNormal = Vector3d.right;
            }

            double bankRad = bankAngle * Math.PI / 180.0;
            Vector3d liftDirection = Vector3d.Cross(velocityDir,
                Vector3d.Cross(up, velocityDir).normalized).normalized;
            liftDirection = Quaterniond.FromAngleAxis(bankRad, velocityDir) * liftDirection;

            double aoaRad = angleOfAttack * Math.PI / 180.0;
            liftDirection = (liftDirection + velocityDir * Math.Tan(aoaRad)).normalized;

            liftForce = liftDirection * C_L * dynamicPressure * referenceArea;
            dragForce = -velocityDir * C_D * dynamicPressure * referenceArea;

            double pitchRate = state.angularVelocity.y;
            double C_m = aerodynamics.GetPitchingMomentCoeff(
                angleOfAttack, pitchRate, machNumber, meanAerodynamicChord, velocity);

            double momentMagnitude = C_m * dynamicPressure * referenceArea * meanAerodynamicChord;
            moments = new Vector3d(momentMagnitude, 0, 0);

            if (double.IsNaN(liftForce.x) || double.IsNaN(liftForce.y) || double.IsNaN(liftForce.z))
            {
                liftForce = Vector3d.zero;
            }
            if (double.IsNaN(dragForce.x) || double.IsNaN(dragForce.y) || double.IsNaN(dragForce.z))
            {
                dragForce = Vector3d.zero;
            }
        }

        private double CalculateStagnationHeatFlux(double velocity, double density)
        {
            if (velocity < 100.0) return 0;

            double heatFlux = 1.8e-8 * Math.Sqrt(density) * Math.Pow(velocity, 3.05);
            return heatFlux;
        }

        private double CalculateRangeError(LanderState state, Vector3d targetPosition)
        {
            double currentEnergy = 0.5 * state.velocity.sqrMagnitude + 9.81 * state.position.y;

            double totalDrag = 0;
            double dt = 0.1;
            double simTime = 0;
            double predictedRange = 0;

            LanderState simState = state.Clone();

            while (simState.position.y > 0 && simTime < 300.0)
            {
                double alt = simState.position.y / 1000.0;
                double vel = simState.velocity.magnitude;
                double mach = atmosphere.GetMachNumber(vel, alt);
                double rho = atmosphere.GetDensity(alt);
                double q = 0.5 * rho * vel * vel;

                double C_D = aerodynamics.GetDragCoeff(15.0, mach, 0.5);
                double drag = C_D * q * referenceArea;

                Vector3d dragForce = -simState.velocity.normalized * drag;
                Vector3d gravity = Vector3d.down * 9.81 * simState.mass;
                Vector3d accel = (dragForce + gravity) / simState.mass;

                simState.velocity += accel * dt;
                simState.position += simState.velocity * dt;

                predictedRange += simState.velocity.x * dt + simState.velocity.z * dt;
                simTime += dt;
            }

            double actualRange = Math.Sqrt(
                Math.Pow(targetPosition.x - state.position.x, 2) +
                Math.Pow(targetPosition.z - state.position.z, 2)
            );

            return predictedRange - actualRange;
        }

        private void CheckThermalConstraints(double heatFlux, double deceleration,
                                             double stagnationPressure, ref double bankAngle)
        {
            if (heatFlux > maxHeatFlux * 0.9)
            {
                bankAngle *= 0.5;
                Debug.LogWarning($"Heat flux limit approached: {heatFlux:F1} W/cm²");
            }

            if (deceleration > maxDeceleration * 0.9)
            {
                bankAngle = Math.Sign(bankAngle) * Math.Max(0, Math.Abs(bankAngle) - 10.0);
                Debug.LogWarning($"Deceleration limit approached: {deceleration:F1} g");
            }

            if (stagnationPressure > maxStagnationPressure * 0.9)
            {
                bankAngle = 0;
                Debug.LogWarning($"Stagnation pressure limit approached: {stagnationPressure:F0} Pa");
            }
        }

        public Vector3d GetTotalAerodynamicForce()
        {
            if (aeroTrajectory.Count == 0) return Vector3d.zero;
            AeroTrajectoryPoint last = aeroTrajectory[aeroTrajectory.Count - 1];
            return last.liftForce + last.dragForce;
        }

        public bool IsPhaseComplete(EntryPhase phase)
        {
            return currentPhase > phase;
        }

        public double GetRangeToTarget(LanderState state, Vector3d target)
        {
            return Math.Sqrt(
                Math.Pow(target.x - state.position.x, 2) +
                Math.Pow(target.z - state.position.z, 2)
            );
        }
    }

    [Serializable]
    public class AeroTrajectoryPoint
    {
        public double time;
        public Vector3d position;
        public Vector3d velocity;
        public double machNumber;
        public double dynamicPressure;
        public double heatFlux;
        public double deceleration;
        public double angleOfAttack;
        public double bankAngle;
        public Vector3d liftForce;
        public Vector3d dragForce;
        public double rangeError;
        public EntryPhase phase;
    }
}
