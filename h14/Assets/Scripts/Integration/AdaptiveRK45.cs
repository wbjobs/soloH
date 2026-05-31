using System;
using UnityEngine;
using FlowVisualization.Core;

namespace FlowVisualization.Integration
{
    public class AdaptiveRK45
    {
        private readonly TimeVaryingField _field;
        public float MinStepSize { get; set; } = 1e-4f;
        public float MaxStepSize { get; set; } = 1e-1f;
        public float Tolerance { get; set; } = 1e-5f;
        public int MaxIterations { get; set; } = 1000;

        private const float SafetyFactor = 0.9f;
        private const float MinScale = 0.2f;
        private const float MaxScale = 10.0f;

        private static readonly float[] A =
        {
            0.0f,
            1.0f / 4.0f,
            3.0f / 8.0f,
            12.0f / 13.0f,
            1.0f,
            1.0f / 2.0f
        };

        private static readonly float[][] B =
        {
            new float[] { 1.0f / 4.0f },
            new float[] { 3.0f / 32.0f, 9.0f / 32.0f },
            new float[] { 1932.0f / 2197.0f, -7200.0f / 2197.0f, 7296.0f / 2197.0f },
            new float[] { 439.0f / 216.0f, -8.0f, 3680.0f / 513.0f, -845.0f / 4104.0f },
            new float[] { -8.0f / 27.0f, 2.0f, -3544.0f / 2565.0f, 1859.0f / 4104.0f, -11.0f / 40.0f }
        };

        private static readonly float[] C4 =
        {
            25.0f / 216.0f,
            0.0f,
            1408.0f / 2565.0f,
            2197.0f / 4104.0f,
            -1.0f / 5.0f,
            0.0f
        };

        private static readonly float[] C5 =
        {
            16.0f / 135.0f,
            0.0f,
            6656.0f / 12825.0f,
            28561.0f / 56430.0f,
            -9.0f / 50.0f,
            2.0f / 55.0f
        };

        public AdaptiveRK45(TimeVaryingField field)
        {
            _field = field;
        }

        public struct IntegrationResult
        {
            public Vector3 FinalPosition;
            public float FinalTime;
            public int StepsTaken;
            public bool ExitedBoundary;
            public bool MaxIterationsReached;
            public float TotalError;
        }

        public struct StepResult
        {
            public Vector3 Position;
            public float Time;
            public Vector3 Velocity;
            public float Error;
        }

        public IntegrationResult Integrate(
            Vector3 initialPosition,
            float initialTime,
            float integrationTime,
            IntegrationDirection direction,
            System.Collections.Generic.List<StepResult> trajectory = null)
        {
            Vector3 currentPos = initialPosition;
            float currentTime = initialTime;
            float remainingTime = Math.Abs(integrationTime);
            int stepsTaken = 0;
            bool exitedBoundary = false;
            bool maxIterReached = false;
            float totalError = 0f;
            float stepSize = Mathf.Clamp(remainingTime * 0.1f, MinStepSize, MaxStepSize);
            float dirSign = direction == IntegrationDirection.Forward ? 1.0f : -1.0f;

            if (trajectory != null)
            {
                trajectory.Capacity = Math.Max(trajectory.Capacity, (int)(integrationTime / MinStepSize) + 2);
                trajectory.Add(new StepResult
                {
                    Position = currentPos,
                    Time = currentTime,
                    Velocity = _field.GetVelocityAtTime(currentPos, currentTime, direction),
                    Error = 0f
                });
            }

            while (remainingTime > 1e-10f && stepsTaken < MaxIterations)
            {
                if (!_field.GetFieldAtTime(currentTime).IsInsideBounds(currentPos))
                {
                    exitedBoundary = true;
                    break;
                }

                if (stepSize > remainingTime)
                {
                    stepSize = remainingTime;
                }

                Vector3 newPos4, newPos5;
                float stepError;
                Vector3[] k = ComputeRKStages(currentPos, currentTime, stepSize * dirSign, direction);
                
                newPos4 = currentPos;
                newPos5 = currentPos;
                
                for (int i = 0; i < 6; i++)
                {
                    newPos4 += C4[i] * k[i] * stepSize * dirSign;
                    newPos5 += C5[i] * k[i] * stepSize * dirSign;
                }

                stepError = Vector3.Distance(newPos4, newPos5);
                totalError += stepError;

                if (stepError <= Tolerance || stepSize <= MinStepSize + 1e-12f)
                {
                    currentPos = newPos5;
                    currentTime += stepSize * dirSign;
                    remainingTime -= stepSize;
                    stepsTaken++;

                    if (trajectory != null)
                    {
                        trajectory.Add(new StepResult
                        {
                            Position = currentPos,
                            Time = currentTime,
                            Velocity = _field.GetVelocityAtTime(currentPos, currentTime, direction),
                            Error = stepError
                        });
                    }
                }

                if (stepError > 0)
                {
                    float scale = SafetyFactor * Mathf.Pow(Tolerance / stepError, 0.2f);
                    scale = Mathf.Clamp(scale, MinScale, MaxScale);
                    stepSize *= scale;
                }
                else
                {
                    stepSize *= 1.5f;
                }

                stepSize = Mathf.Clamp(stepSize, MinStepSize, MaxStepSize);

                if (!_field.IsValidTime(currentTime))
                {
                    exitedBoundary = true;
                    break;
                }
            }

            if (stepsTaken >= MaxIterations)
            {
                maxIterReached = true;
            }

            return new IntegrationResult
            {
                FinalPosition = currentPos,
                FinalTime = currentTime,
                StepsTaken = stepsTaken,
                ExitedBoundary = exitedBoundary,
                MaxIterationsReached = maxIterReached,
                TotalError = totalError
            };
        }

        private Vector3[] ComputeRKStages(Vector3 pos, float time, float dt, IntegrationDirection direction)
        {
            Vector3[] k = new Vector3[6];
            
            k[0] = _field.GetVelocityAtTime(pos, time, direction);

            for (int stage = 1; stage < 6; stage++)
            {
                Vector3 stagePos = pos;
                for (int j = 0; j < stage; j++)
                {
                    stagePos += B[stage - 1][j] * k[j] * dt;
                }
                float stageTime = time + A[stage] * dt;
                k[stage] = _field.GetVelocityAtTime(stagePos, stageTime, direction);
            }

            return k;
        }

        public Vector3 IntegrateSingleStep(
            Vector3 pos,
            float time,
            ref float dt,
            IntegrationDirection direction,
            out float error)
        {
            float dirSign = direction == IntegrationDirection.Forward ? 1.0f : -1.0f;
            float stepSize = dt;

            Vector3[] k = ComputeRKStages(pos, time, stepSize * dirSign, direction);

            Vector3 newPos4 = pos;
            Vector3 newPos5 = pos;

            for (int i = 0; i < 6; i++)
            {
                newPos4 += C4[i] * k[i] * stepSize * dirSign;
                newPos5 += C5[i] * k[i] * stepSize * dirSign;
            }

            error = Vector3.Distance(newPos4, newPos5);

            if (error > 0)
            {
                float scale = SafetyFactor * Mathf.Pow(Tolerance / error, 0.2f);
                scale = Mathf.Clamp(scale, MinScale, MaxScale);
                dt = Mathf.Clamp(stepSize * scale, MinStepSize, MaxStepSize);
            }
            else
            {
                dt = Mathf.Clamp(stepSize * 1.5f, MinStepSize, MaxStepSize);
            }

            return newPos5;
        }
    }
}
