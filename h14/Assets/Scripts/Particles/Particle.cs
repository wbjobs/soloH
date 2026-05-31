using System.Collections.Generic;
using UnityEngine;
using FlowVisualization.Core;
using FlowVisualization.Integration;

namespace FlowVisualization.Particles
{
    public struct ParticleData
    {
        public Vector3 Position;
        public Vector3 Velocity;
        public float Time;
        public float ScalarValue;
        public bool IsAlive;
        public int ID;
    }

    public class ParticleTrail
    {
        private CircularBuffer<Vector3> _positions;
        private CircularBuffer<float> _times;
        private CircularBuffer<float> _scalarValues;
        private readonly int _maxLength;

        public int Count => _positions.Count;
        public int Capacity => _maxLength;

        public ParticleTrail(int maxLength = 1024)
        {
            _maxLength = maxLength;
            _positions = new CircularBuffer<Vector3>(maxLength);
            _times = new CircularBuffer<float>(maxLength);
            _scalarValues = new CircularBuffer<float>(maxLength);
        }

        public void AddPoint(Vector3 position, float time, float scalarValue)
        {
            _positions.Add(position);
            _times.Add(time);
            _scalarValues.Add(scalarValue);
        }

        public Vector3 GetPosition(int index)
        {
            return _positions[index];
        }

        public float GetTime(int index)
        {
            return _times[index];
        }

        public float GetScalar(int index)
        {
            return _scalarValues[index];
        }

        public Vector3[] GetPositionsArray()
        {
            return _positions.ToArray();
        }

        public float[] GetTimesArray()
        {
            return _times.ToArray();
        }

        public float[] GetScalarsArray()
        {
            return _scalarValues.ToArray();
        }

        public void CopyPositionsTo(List<Vector3> list)
        {
            list.Clear();
            if (list.Capacity < _positions.Count)
            {
                list.Capacity = _positions.Count;
            }
            for (int i = 0; i < _positions.Count; i++)
            {
                list.Add(_positions[i]);
            }
        }

        public void CopyScalarsTo(List<float> list)
        {
            list.Clear();
            if (list.Capacity < _scalarValues.Count)
            {
                list.Capacity = _scalarValues.Count;
            }
            for (int i = 0; i < _scalarValues.Count; i++)
            {
                list.Add(_scalarValues[i]);
            }
        }

        public void Clear()
        {
            _positions.Clear();
            _times.Clear();
            _scalarValues.Clear();
        }

        public IReadOnlyList<Vector3> Positions
        {
            get
            {
                Vector3[] arr = new Vector3[_positions.Count];
                _positions.CopyTo(arr, 0);
                return arr;
            }
        }

        public IReadOnlyList<float> Times
        {
            get
            {
                float[] arr = new float[_times.Count];
                _times.CopyTo(arr, 0);
                return arr;
            }
        }

        public IReadOnlyList<float> ScalarValues
        {
            get
            {
                float[] arr = new float[_scalarValues.Count];
                _scalarValues.CopyTo(arr, 0);
                return arr;
            }
        }
    }

    public class Particle
    {
        public ParticleData Data;
        public ParticleTrail Trail;
        public AdaptiveRK45 Integrator;
        public float CurrentStepSize;

        public Particle(int id, Vector3 initialPosition, float initialTime, int trailLength = 512)
        {
            Data = new ParticleData
            {
                ID = id,
                Position = initialPosition,
                Time = initialTime,
                Velocity = Vector3.zero,
                ScalarValue = 0f,
                IsAlive = true
            };
            Trail = new ParticleTrail(trailLength);
            CurrentStepSize = 0.01f;
        }

        public void Update(float deltaTime, TimeVaryingField field, IntegrationDirection direction, ScalarFieldType colorField)
        {
            if (!Data.IsAlive) return;

            if (Integrator == null)
            {
                Integrator = new AdaptiveRK45(field);
            }

            float remainingTime = deltaTime;
            float localDt = CurrentStepSize;
            float dirSign = direction == IntegrationDirection.Forward ? 1.0f : -1.0f;

            while (remainingTime > 1e-6f && Data.IsAlive)
            {
                float stepDt = Mathf.Min(localDt, remainingTime);
                float error;

                Vector3 newPos = Integrator.IntegrateSingleStep(
                    Data.Position,
                    Data.Time,
                    ref localDt,
                    direction,
                    out error
                );

                Data.Time += stepDt * dirSign;
                Data.Position = newPos;
                Data.Velocity = field.GetVelocityAtTime(Data.Position, Data.Time, direction);
                Data.ScalarValue = field.GetScalarAtTime(Data.Position, Data.Time, colorField);

                Vector3Field currentField = field.GetFieldAtTime(Data.Time);
                if (!currentField.IsInsideBounds(Data.Position) || !field.IsValidTime(Data.Time))
                {
                    Data.IsAlive = false;
                    break;
                }

                Trail.AddPoint(Data.Position, Data.Time, Data.ScalarValue);
                remainingTime -= stepDt;
            }

            CurrentStepSize = localDt;
        }

        public void Reset(Vector3 newPosition, float newTime)
        {
            Data.Position = newPosition;
            Data.Time = newTime;
            Data.IsAlive = true;
            Data.Velocity = Vector3.zero;
            Data.ScalarValue = 0f;
            Trail.Clear();
        }
    }
}
