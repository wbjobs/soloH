using System.Collections.Generic;
using UnityEngine;

namespace FlowVisualization.Core
{
    public class TimeVaryingField
    {
        private readonly List<Vector3Field> _timeSteps;
        public int TimeStepCount => _timeSteps.Count;
        public float MinTime { get; private set; }
        public float MaxTime { get; private set; }
        public float TimeStepDuration { get; private set; }

        public Vector3Field this[int index] => _timeSteps[index];

        public TimeVaryingField(int expectedTimeSteps = 128)
        {
            _timeSteps = new List<Vector3Field>(expectedTimeSteps);
        }

        public void AddTimeStep(Vector3Field field)
        {
            _timeSteps.Add(field);
            if (_timeSteps.Count == 1)
            {
                MinTime = field.TimeValue;
                TimeStepDuration = field.TimeStep;
            }
            MaxTime = field.TimeValue;
        }

        public Vector3Field GetFieldAtTime(float time)
        {
            if (_timeSteps.Count == 0) return default;
            if (_timeSteps.Count == 1) return _timeSteps[0];
            
            float normalizedTime = Mathf.Clamp(time, MinTime, MaxTime);
            
            if (normalizedTime >= MaxTime - 1e-6f)
            {
                return _timeSteps[_timeSteps.Count - 1];
            }
            if (normalizedTime <= MinTime + 1e-6f)
            {
                return _timeSteps[0];
            }

            float exactIndex = (normalizedTime - MinTime) / TimeStepDuration;
            int index0 = Mathf.FloorToInt(exactIndex);
            
            if (index0 < 0) index0 = 0;
            if (index0 >= _timeSteps.Count - 1) index0 = _timeSteps.Count - 2;
            
            int index1 = index0 + 1;
            float t = exactIndex - index0;

            return InterpolateFields(_timeSteps[index0], _timeSteps[index1], t);
        }

        public Vector3 GetVelocityAtTime(Vector3 position, float time, IntegrationDirection direction)
        {
            Vector3Field field = GetFieldAtTime(time);
            Vector3 velocity = field.GetVelocity(position);
            return direction == IntegrationDirection.Backward ? -velocity : velocity;
        }

        public float GetScalarAtTime(Vector3 position, float time, ScalarFieldType type)
        {
            Vector3Field field = GetFieldAtTime(time);
            return field.GetScalarValue(position, type);
        }

        private Vector3Field InterpolateFields(Vector3Field f0, Vector3Field f1, float t)
        {
            Vector3Field result = new Vector3Field(f0.DimX, f0.DimY, f0.DimZ)
            {
                MinBounds = f0.MinBounds,
                MaxBounds = f0.MaxBounds,
                CellSize = f0.CellSize,
                TimeStep = f0.TimeStep,
                TimeValue = Mathf.Lerp(f0.TimeValue, f1.TimeValue, t)
            };

            for (int x = 0; x < f0.DimX; x++)
            {
                for (int y = 0; y < f0.DimY; y++)
                {
                    for (int z = 0; z < f0.DimZ; z++)
                    {
                        result.Velocity[x, y, z] = Vector3.Lerp(f0.Velocity[x, y, z], f1.Velocity[x, y, z], t);
                        result.Pressure[x, y, z] = Mathf.Lerp(f0.Pressure[x, y, z], f1.Pressure[x, y, z], t);
                        result.Vorticity[x, y, z] = Vector3.Lerp(f0.Vorticity[x, y, z], f1.Vorticity[x, y, z], t);
                        result.VorticityMagnitude[x, y, z] = Mathf.Lerp(f0.VorticityMagnitude[x, y, z], f1.VorticityMagnitude[x, y, z], t);
                        result.LyapunovExponent[x, y, z] = Mathf.Lerp(f0.LyapunovExponent[x, y, z], f1.LyapunovExponent[x, y, z], t);
                        result.FTLE[x, y, z] = Mathf.Lerp(f0.FTLE[x, y, z], f1.FTLE[x, y, z], t);
                        result.Stretching[x, y, z] = Mathf.Lerp(f0.Stretching[x, y, z], f1.Stretching[x, y, z], t);
                        result.Compression[x, y, z] = Mathf.Lerp(f0.Compression[x, y, z], f1.Compression[x, y, z], t);
                    }
                }
            }

            return result;
        }

        public bool IsValidTime(float time)
        {
            return time >= MinTime && time <= MaxTime;
        }
    }
}
