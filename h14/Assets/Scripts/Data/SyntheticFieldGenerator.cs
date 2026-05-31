using UnityEngine;
using System.Threading.Tasks;
using FlowVisualization.Core;

namespace FlowVisualization.Data
{
    public class SyntheticFieldGenerator
    {
        private readonly int _dimX;
        private readonly int _dimY;
        private readonly int _dimZ;
        private readonly int _timeSteps;
        private readonly Vector3 _minBounds;
        private readonly Vector3 _maxBounds;
        private readonly float _timeStepDuration;

        public SyntheticFieldGenerator(
            int dimX = 32,
            int dimY = 32,
            int dimZ = 32,
            int timeSteps = 128,
            float timeStepDuration = 0.05f)
        {
            _dimX = dimX;
            _dimY = dimY;
            _dimZ = dimZ;
            _timeSteps = timeSteps;
            _timeStepDuration = timeStepDuration;
            _minBounds = Vector3.zero;
            _maxBounds = Vector3.one;
        }

        public TimeVaryingField Generate()
        {
            TimeVaryingField tvf = new TimeVaryingField(_timeSteps);

            Vector3 cellSize = new Vector3(
                (_maxBounds.x - _minBounds.x) / (_dimX - 1),
                (_maxBounds.y - _minBounds.y) / (_dimY - 1),
                (_maxBounds.z - _minBounds.z) / (_dimZ - 1)
            );

            Parallel.For(0, _timeSteps, t =>
            {
                Vector3Field field = new Vector3Field(_dimX, _dimY, _dimZ)
                {
                    MinBounds = _minBounds,
                    MaxBounds = _maxBounds,
                    CellSize = cellSize,
                    TimeStep = _timeStepDuration,
                    TimeValue = t * _timeStepDuration
                };

                float time = t * _timeStepDuration;

                for (int x = 0; x < _dimX; x++)
                {
                    for (int y = 0; y < _dimY; y++)
                    {
                        for (int z = 0; z < _dimZ; z++)
                        {
                            Vector3 worldPos = new Vector3(
                                _minBounds.x + x * cellSize.x,
                                _minBounds.y + y * cellSize.y,
                                _minBounds.z + z * cellSize.z
                            );

                            field.Velocity[x, y, z] = GenerateVelocity(worldPos, time);
                            field.Pressure[x, y, z] = GeneratePressure(worldPos, time);
                        }
                    }
                }

                field.ComputeVorticity();
                tvf.AddTimeStep(field);
            });

            return tvf;
        }

        private Vector3 GenerateVelocity(Vector3 pos, float time)
        {
            float x = pos.x * Mathf.PI * 2f;
            float y = pos.y * Mathf.PI * 2f;
            float z = pos.z * Mathf.PI * 2f;

            float t = time * 0.5f;

            float vx = Mathf.Sin(x + t) * Mathf.Cos(y) * Mathf.Cos(z);
            float vy = Mathf.Cos(x) * Mathf.Sin(y + t * 0.7f) * Mathf.Cos(z);
            float vz = Mathf.Cos(x) * Mathf.Cos(y) * Mathf.Sin(z + t * 1.3f);

            Vector3 vortex = GenerateVortex(pos, time);
            Vector3 shear = GenerateShearFlow(pos, time);

            return (new Vector3(vx, vy, vz) * 0.5f + vortex * 0.3f + shear * 0.2f) * 2.0f;
        }

        private Vector3 GenerateVortex(Vector3 pos, float time)
        {
            Vector3 center = new Vector3(0.5f, 0.5f, 0.5f);
            Vector3 offset = pos - center;
            float r = offset.magnitude;
            
            if (r < 0.01f) return Vector3.zero;

            float omega = 8.0f * Mathf.Exp(-r * r * 8.0f) * (1.0f + 0.3f * Mathf.Sin(time * 2.0f));
            
            Vector3 tangential = Vector3.Cross(Vector3.up, offset).normalized;
            Vector3 axial = Vector3.up * Mathf.Exp(-r * r * 4.0f) * Mathf.Sin(time * 0.5f);

            return tangential * omega * r + axial * 0.5f;
        }

        private Vector3 GenerateShearFlow(Vector3 pos, float time)
        {
            float shearStrength = 1.5f + 0.5f * Mathf.Sin(time);
            return new Vector3(
                shearStrength * pos.y * (1f - pos.y),
                0f,
                shearStrength * 0.3f * Mathf.Sin(pos.y * Mathf.PI * 2f + time)
            );
        }

        private float GeneratePressure(Vector3 pos, float time)
        {
            float x = pos.x * Mathf.PI * 2f;
            float y = pos.y * Mathf.PI * 2f;
            float z = pos.z * Mathf.PI * 2f;

            float t = time * 0.3f;

            float p = 0.5f
                      + 0.3f * Mathf.Sin(x + t) * Mathf.Cos(y)
                      + 0.2f * Mathf.Cos(z * 1.5f - t * 0.7f)
                      + 0.15f * Mathf.Sin((x + y + z) * 0.5f + t * 1.3f);

            Vector3 center = new Vector3(0.5f, 0.5f, 0.5f);
            float r = (pos - center).magnitude;
            p -= 0.4f * Mathf.Exp(-r * r * 6.0f) * (1.0f + 0.3f * Mathf.Sin(time * 2.5f));

            return p;
        }
    }
}
