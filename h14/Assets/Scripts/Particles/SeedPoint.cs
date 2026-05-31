using System.Collections.Generic;
using UnityEngine;
using FlowVisualization.Core;
using FlowVisualization.Integration;

namespace FlowVisualization.Particles
{
    public enum LineType
    {
        Pathline,
        Streakline,
        Stripline
    }

    public class SeedPoint
    {
        public Vector3 Position;
        public LineType LineType;
        public Color Color;
        public bool IsActive;
        public int ID;

        private readonly List<Particle> _particles;
        private readonly ParticlePool _particlePool;
        private readonly TimeVaryingField _field;
        private readonly AdaptiveRK45 _integrator;
        private float _lastReleaseTime;
        private int _particleIdCounter;
        private readonly int _maxParticlesPerSeed;
        private readonly float _releaseInterval;
        private float _striplineReleaseTime;
        private bool _striplineReleased;
        private readonly ScalarFieldType _colorField;

        public IReadOnlyList<Particle> Particles => _particles;
        public int ActiveParticleCount
        {
            get
            {
                int count = 0;
                for (int i = 0; i < _particles.Count; i++)
                {
                    if (_particles[i].Data.IsAlive) count++;
                }
                return count;
            }
        }

        public SeedPoint(
            int id,
            Vector3 position,
            LineType lineType,
            TimeVaryingField field,
            ParticlePool particlePool,
            int maxParticlesPerSeed = 200,
            float releaseInterval = 0.02f,
            ScalarFieldType colorField = ScalarFieldType.VelocityMagnitude)
        {
            ID = id;
            Position = position;
            LineType = lineType;
            Color = Color.white;
            IsActive = true;
            _field = field;
            _particlePool = particlePool;
            _integrator = new AdaptiveRK45(field);
            _maxParticlesPerSeed = maxParticlesPerSeed;
            _releaseInterval = releaseInterval;
            _colorField = colorField;
            _particles = new List<Particle>(_maxParticlesPerSeed);
            _lastReleaseTime = -1f;
            _striplineReleased = false;
        }

        public void Update(float simulationTime, float deltaTime, IntegrationDirection direction)
        {
            if (!IsActive) return;

            switch (LineType)
            {
                case LineType.Pathline:
                    UpdatePathline(simulationTime, deltaTime, direction);
                    break;
                case LineType.Streakline:
                    UpdateStreakline(simulationTime, deltaTime, direction);
                    break;
                case LineType.Stripline:
                    UpdateStripline(simulationTime, deltaTime, direction);
                    break;
            }

            for (int i = _particles.Count - 1; i >= 0; i--)
            {
                if (!_particles[i].Data.IsAlive && _particles[i].Trail.Count == 0)
                {
                    if (_particlePool != null)
                    {
                        _particlePool.Release(_particles[i]);
                    }
                    _particles.RemoveAt(i);
                }
            }
        }

        private void UpdatePathline(float simulationTime, float deltaTime, IntegrationDirection direction)
        {
            if (_particles.Count == 0)
            {
                SpawnParticle(Position, simulationTime);
            }

            UpdateAllParticles(deltaTime, direction);
        }

        private void UpdateStreakline(float simulationTime, float deltaTime, IntegrationDirection direction)
        {
            if (_lastReleaseTime < 0 || simulationTime - _lastReleaseTime >= _releaseInterval)
            {
                if (_particles.Count < _maxParticlesPerSeed)
                {
                    SpawnParticle(Position, simulationTime);
                }
                _lastReleaseTime = simulationTime;
            }

            UpdateAllParticles(deltaTime, direction);
        }

        private void UpdateStripline(float simulationTime, float deltaTime, IntegrationDirection direction)
        {
            if (!_striplineReleased)
            {
                _striplineReleaseTime = simulationTime;
                _striplineReleased = true;

                int numParticles = Mathf.Min(_maxParticlesPerSeed, 100);
                Vector3 lineDir = Vector3.right * 0.2f;
                
                for (int i = 0; i < numParticles; i++)
                {
                    float t = i / (float)(numParticles - 1);
                    Vector3 offsetPosition = Position + lineDir * (t - 0.5f);
                    Vector3Field field = _field.GetFieldAtTime(simulationTime);
                    if (field.IsInsideBounds(offsetPosition))
                    {
                        SpawnParticle(offsetPosition, simulationTime);
                    }
                }
            }

            UpdateAllParticles(deltaTime, direction);
        }

        private void SpawnParticle(Vector3 position, float time)
        {
            Particle particle;
            if (_particlePool != null)
            {
                particle = _particlePool.Get(_particleIdCounter++, position, time);
                if (particle == null) return;
            }
            else
            {
                particle = new Particle(
                    _particleIdCounter++,
                    position,
                    time,
                    256
                );
            }
            _particles.Add(particle);
        }

        public void CleanupDeadParticles(ParticlePool pool)
        {
            if (pool == null) return;

            for (int i = _particles.Count - 1; i >= 0; i--)
            {
                if (!_particles[i].Data.IsAlive)
                {
                    pool.Release(_particles[i]);
                    _particles.RemoveAt(i);
                }
            }
        }

        private void UpdateAllParticles(float deltaTime, IntegrationDirection direction)
        {
            for (int i = 0; i < _particles.Count; i++)
            {
                _particles[i].Update(deltaTime, _field, direction, _colorField);
            }
        }

        public void Reset(float simulationTime)
        {
            if (_particlePool != null)
            {
                for (int i = 0; i < _particles.Count; i++)
                {
                    _particlePool.Release(_particles[i]);
                }
            }
            _particles.Clear();
            _lastReleaseTime = -1f;
            _striplineReleased = false;
            _particleIdCounter = 0;
        }

        public void Clear()
        {
            if (_particlePool != null)
            {
                for (int i = 0; i < _particles.Count; i++)
                {
                    _particlePool.Release(_particles[i]);
                }
            }
            _particles.Clear();
        }

        public List<List<Vector3>> GetAllLineTrails()
        {
            List<List<Vector3>> allTrails = new List<List<Vector3>>(_particles.Count);

            if (LineType == LineType.Pathline)
            {
                if (_particles.Count > 0 && _particles[0].Trail.Count > 0)
                {
                    List<Vector3> trail = new List<Vector3>(_particles[0].Trail.Count);
                    _particles[0].Trail.CopyPositionsTo(trail);
                    allTrails.Add(trail);
                }
            }
            else if (LineType == LineType.Streakline)
            {
                List<Vector3> streakPoints = new List<Vector3>(_particles.Count);
                for (int i = 0; i < _particles.Count; i++)
                {
                    if (_particles[i].Data.IsAlive)
                    {
                        streakPoints.Add(_particles[i].Data.Position);
                    }
                    else if (_particles[i].Trail.Count > 0)
                    {
                        int lastIdx = _particles[i].Trail.Count - 1;
                        streakPoints.Add(_particles[i].Trail.GetPosition(lastIdx));
                    }
                }
                if (streakPoints.Count > 1)
                {
                    allTrails.Add(streakPoints);
                }
            }
            else if (LineType == LineType.Stripline)
            {
                for (int i = 0; i < _particles.Count; i++)
                {
                    if (_particles[i].Trail.Count > 1)
                    {
                        List<Vector3> trail = new List<Vector3>(_particles[i].Trail.Count);
                        _particles[i].Trail.CopyPositionsTo(trail);
                        allTrails.Add(trail);
                    }
                    else if (_particles[i].Data.IsAlive && _particles[i].Trail.Count == 1)
                    {
                        List<Vector3> trail = new List<Vector3>(2);
                        _particles[i].Trail.CopyPositionsTo(trail);
                        trail.Add(_particles[i].Data.Position);
                        allTrails.Add(trail);
                    }
                }
            }

            return allTrails;
        }

        public List<List<float>> GetAllLineScalars()
        {
            List<List<float>> allScalars = new List<List<float>>(_particles.Count);

            if (LineType == LineType.Pathline)
            {
                if (_particles.Count > 0 && _particles[0].Trail.Count > 0)
                {
                    List<float> scalars = new List<float>(_particles[0].Trail.Count);
                    _particles[0].Trail.CopyScalarsTo(scalars);
                    allScalars.Add(scalars);
                }
            }
            else if (LineType == LineType.Streakline)
            {
                List<float> streakScalars = new List<float>(_particles.Count);
                for (int i = 0; i < _particles.Count; i++)
                {
                    streakScalars.Add(_particles[i].Data.ScalarValue);
                }
                if (streakScalars.Count > 1)
                {
                    allScalars.Add(streakScalars);
                }
            }
            else if (LineType == LineType.Stripline)
            {
                for (int i = 0; i < _particles.Count; i++)
                {
                    if (_particles[i].Trail.Count > 1)
                    {
                        List<float> scalars = new List<float>(_particles[i].Trail.Count);
                        _particles[i].Trail.CopyScalarsTo(scalars);
                        allScalars.Add(scalars);
                    }
                    else if (_particles[i].Data.IsAlive && _particles[i].Trail.Count == 1)
                    {
                        List<float> scalars = new List<float>(2);
                        _particles[i].Trail.CopyScalarsTo(scalars);
                        scalars.Add(_particles[i].Data.ScalarValue);
                        allScalars.Add(scalars);
                    }
                }
            }

            return allScalars;
        }

        public List<Vector3> GetLinePoints()
        {
            List<Vector3> points = new List<Vector3>();

            if (LineType == LineType.Pathline)
            {
                if (_particles.Count > 0 && _particles[0].Trail.Count > 0)
                {
                    points.AddRange(_particles[0].Trail.Positions);
                }
            }
            else if (LineType == LineType.Streakline)
            {
                for (int i = 0; i < _particles.Count; i++)
                {
                    if (_particles[i].Data.IsAlive)
                    {
                        points.Add(_particles[i].Data.Position);
                    }
                    else if (_particles[i].Trail.Count > 0)
                    {
                        int lastIdx = _particles[i].Trail.Count - 1;
                        points.Add(_particles[i].Trail.Positions[lastIdx]);
                    }
                }
            }
            else if (LineType == LineType.Stripline)
            {
                for (int i = 0; i < _particles.Count; i++)
                {
                    if (_particles[i].Trail.Count > 0)
                    {
                        int lastIdx = _particles[i].Trail.Count - 1;
                        points.Add(_particles[i].Trail.Positions[lastIdx]);
                    }
                }
            }

            return points;
        }
    }
}
