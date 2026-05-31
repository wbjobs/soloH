using System;
using System.Collections.Generic;
using System.Diagnostics;
using UnityEngine;
using FlowVisualization.Core;
using FlowVisualization.Particles;

namespace FlowVisualization.Compute
{
    public class GPUParticleSystem : MonoBehaviour
    {
        [Header("Compute Shader")]
        public ComputeShader ParticleIntegrationShader;
        public int MaxParticles = 100000;
        public int TrailLength = 256;
        public int FTLEGridSize = 32;
        public bool UseBatchIntegration = true;

        [Header("Integration Settings")]
        public float MinStepSize = 1e-4f;
        public float MaxStepSize = 1e-1f;
        public float Tolerance = 1e-5f;

        [Header("Performance")]
        public bool UseGPU = true;
        public bool AsyncReadback = true;

        private struct GPUParticle
        {
            public Vector3 position;
            public Vector3 velocity;
            public float time;
            public float scalarValue;
            public int isAlive;
            public int id;
            public float stepSize;
            public float padding;
        }

        private struct FieldData
        {
            public Vector3 velocity;
            public float pressure;
            public float vorticity;
            public float lyapunov;
            public float ftle;
            public float stretching;
            public float compression;
            public float padding1;
        }

        private struct FTLEParticle
        {
            public Vector3 basePos;
            public Vector3 offsetX;
            public Vector3 offsetY;
            public Vector3 offsetZ;
            public float startTime;
            public float integrationTime;
            public int isActive;
            public int padding;
        }

        private ComputeBuffer _particlesBuffer;
        private ComputeBuffer _fieldBuffer0;
        private ComputeBuffer _fieldBuffer1;
        private ComputeBuffer _trailPositionsBuffer;
        private ComputeBuffer _trailTimesBuffer;
        private ComputeBuffer _trailScalarsBuffer;
        private ComputeBuffer _trailCountsBuffer;
        private ComputeBuffer _ftleFieldBuffer;
        private ComputeBuffer _ftleParticlesBuffer;

        private int _integrateKernel;
        private int _integrateBatchKernel;
        private int _resetKernel;
        private int _computeFTLEKernel;
        private bool _initialized;
        private TimeVaryingField _field;

        private GPUParticle[] _cpuParticles;
        private Vector3[] _trailPositions;
        private float[] _trailTimes;
        private float[] _trailScalars;
        private int[] _trailCounts;
        private float[] _ftleField;

        private int _currentTimeStep0 = -1;
        private int _currentTimeStep1 = -1;
        private float _currentTimeInterpolation = 0f;

        private Stopwatch _performanceTimer;
        public float AverageFramesPerSecond { get; private set; }
        public float AverageParticlesPerSecond { get; private set; }
        private float _frameCount;
        private float _totalParticlesProcessed;

        public int ActiveParticles { get; private set; }
        public bool IsInitialized => _initialized;
        public float[] FTLEField => _ftleField;

        public event Action OnParticlesUpdated;
        public event Action<float> OnFTLEComputed;

        private void Awake()
        {
            _performanceTimer = new Stopwatch();
        }

        private void OnDisable()
        {
            ReleaseBuffers();
        }

        public void Initialize(TimeVaryingField field)
        {
            _field = field;
            
            if (ParticleIntegrationShader == null)
            {
                UnityEngine.Debug.LogError("ParticleIntegrationShader is not assigned!");
                UseGPU = false;
                return;
            }

            if (!SystemInfo.supportsComputeShaders)
            {
                UnityEngine.Debug.LogWarning("Compute shaders are not supported on this system. Falling back to CPU.");
                UseGPU = false;
                return;
            }

            CreateBuffers();
            UploadFieldData(0);
            UploadFieldData(1);

            _integrateKernel = ParticleIntegrationShader.FindKernel("IntegrateParticles");
            _integrateBatchKernel = ParticleIntegrationShader.FindKernel("IntegrateParticlesBatch");
            _resetKernel = ParticleIntegrationShader.FindKernel("ResetParticles");
            _computeFTLEKernel = ParticleIntegrationShader.FindKernel("ComputeFTLEGrid");

            _cpuParticles = new GPUParticle[MaxParticles];
            _trailPositions = new Vector3[MaxParticles * TrailLength];
            _trailTimes = new float[MaxParticles * TrailLength];
            _trailScalars = new float[MaxParticles * TrailLength];
            _trailCounts = new int[MaxParticles];
            _ftleField = new float[FTLEGridSize * FTLEGridSize * FTLEGridSize];

            _initialized = true;
            _performanceTimer.Start();
        }

        private void CreateBuffers()
        {
            int particleStride = System.Runtime.InteropServices.Marshal.SizeOf(typeof(GPUParticle));
            int fieldStride = System.Runtime.InteropServices.Marshal.SizeOf(typeof(FieldData));
            int ftleParticleStride = System.Runtime.InteropServices.Marshal.SizeOf(typeof(FTLEParticle));
            int fieldSize = _field[0].DimX * _field[0].DimY * _field[0].DimZ;

            _particlesBuffer = new ComputeBuffer(MaxParticles, particleStride, ComputeBufferType.Structured);
            _fieldBuffer0 = new ComputeBuffer(fieldSize, fieldStride, ComputeBufferType.Structured);
            _fieldBuffer1 = new ComputeBuffer(fieldSize, fieldStride, ComputeBufferType.Structured);
            _trailPositionsBuffer = new ComputeBuffer(MaxParticles * TrailLength, sizeof(float) * 3, ComputeBufferType.Structured);
            _trailTimesBuffer = new ComputeBuffer(MaxParticles * TrailLength, sizeof(float), ComputeBufferType.Structured);
            _trailScalarsBuffer = new ComputeBuffer(MaxParticles * TrailLength, sizeof(float), ComputeBufferType.Structured);
            _trailCountsBuffer = new ComputeBuffer(MaxParticles, sizeof(int), ComputeBufferType.Structured);
            _ftleFieldBuffer = new ComputeBuffer(FTLEGridSize * FTLEGridSize * FTLEGridSize, sizeof(float), ComputeBufferType.Structured);
            _ftleParticlesBuffer = new ComputeBuffer(FTLEGridSize * FTLEGridSize * FTLEGridSize, ftleParticleStride, ComputeBufferType.Structured);
        }

        private void ReleaseBuffers()
        {
            if (_particlesBuffer != null) { _particlesBuffer.Release(); _particlesBuffer = null; }
            if (_fieldBuffer0 != null) { _fieldBuffer0.Release(); _fieldBuffer0 = null; }
            if (_fieldBuffer1 != null) { _fieldBuffer1.Release(); _fieldBuffer1 = null; }
            if (_trailPositionsBuffer != null) { _trailPositionsBuffer.Release(); _trailPositionsBuffer = null; }
            if (_trailTimesBuffer != null) { _trailTimesBuffer.Release(); _trailTimesBuffer = null; }
            if (_trailScalarsBuffer != null) { _trailScalarsBuffer.Release(); _trailScalarsBuffer = null; }
            if (_trailCountsBuffer != null) { _trailCountsBuffer.Release(); _trailCountsBuffer = null; }
            if (_ftleFieldBuffer != null) { _ftleFieldBuffer.Release(); _ftleFieldBuffer = null; }
            if (_ftleParticlesBuffer != null) { _ftleParticlesBuffer.Release(); _ftleParticlesBuffer = null; }

            _initialized = false;
        }

        private void UploadFieldData(int bufferIndex, int timeStep = 0)
        {
            Vector3Field field = _field[timeStep];
            FieldData[] fieldData = new FieldData[field.DimX * field.DimY * field.DimZ];

            int idx = 0;
            for (int z = 0; z < field.DimZ; z++)
            {
                for (int y = 0; y < field.DimY; y++)
                {
                    for (int x = 0; x < field.DimX; x++)
                    {
                        fieldData[idx] = new FieldData
                        {
                            velocity = field.Velocity[x, y, z],
                            pressure = field.Pressure[x, y, z],
                            vorticity = field.VorticityMagnitude[x, y, z],
                            lyapunov = field.LyapunovExponent[x, y, z],
                            ftle = field.FTLE[x, y, z],
                            stretching = field.Stretching[x, y, z],
                            compression = field.Compression[x, y, z]
                        };
                        idx++;
                    }
                }
            }

            if (bufferIndex == 0)
            {
                _fieldBuffer0.SetData(fieldData);
                _currentTimeStep0 = timeStep;
            }
            else
            {
                _fieldBuffer1.SetData(fieldData);
                _currentTimeStep1 = timeStep;
            }
        }

        private void UpdateTimeInterpolatedField(float simulationTime)
        {
            float normalizedTime = Mathf.Clamp(
                (simulationTime - _field.MinTime) / _field.TimeStepDuration,
                0,
                _field.TimeStepCount - 1
            );

            int t0 = Mathf.FloorToInt(normalizedTime);
            int t1 = Mathf.Min(t0 + 1, _field.TimeStepCount - 1);
            float t = normalizedTime - t0;

            if (t0 != _currentTimeStep0)
                UploadFieldData(0, t0);
            if (t1 != _currentTimeStep1)
                UploadFieldData(1, t1);

            _currentTimeInterpolation = t;
        }

        public void SpawnParticle(Vector3 position, float time)
        {
            if (!_initialized || ActiveParticles >= MaxParticles) return;

            _cpuParticles[ActiveParticles] = new GPUParticle
            {
                position = position,
                velocity = Vector3.zero,
                time = time,
                scalarValue = 0f,
                isAlive = 1,
                id = ActiveParticles,
                stepSize = 0.01f,
                padding = 0f
            };

            _trailCounts[ActiveParticles] = 0;
            ActiveParticles++;
        }

        public void UpdateParticles(float deltaTime, float simulationTime, IntegrationDirection direction, ScalarFieldType colorField)
        {
            if (!_initialized || !UseGPU || ActiveParticles == 0) return;

            _performanceTimer.Stop();
            float elapsedMs = (float)_performanceTimer.Elapsed.TotalMilliseconds;
            _performanceTimer.Reset();
            _performanceTimer.Start();

            _frameCount++;
            _totalParticlesProcessed += ActiveParticles;

            if (_frameCount >= 60)
            {
                AverageFramesPerSecond = 1000.0f / (elapsedMs / _frameCount);
                AverageParticlesPerSecond = _totalParticlesProcessed / (elapsedMs / 1000.0f);
                _frameCount = 0;
                _totalParticlesProcessed = 0;
            }

            _particlesBuffer.SetData(_cpuParticles, 0, 0, ActiveParticles);
            _trailCountsBuffer.SetData(_trailCounts, 0, 0, ActiveParticles);

            UpdateTimeInterpolatedField(simulationTime);

            int kernel = UseBatchIntegration ? _integrateBatchKernel : _integrateKernel;

            ParticleIntegrationShader.SetBuffer(kernel, "Particles", _particlesBuffer);
            ParticleIntegrationShader.SetBuffer(kernel, "FieldVolume0", _fieldBuffer0);
            ParticleIntegrationShader.SetBuffer(kernel, "FieldVolume1", _fieldBuffer1);
            ParticleIntegrationShader.SetBuffer(kernel, "TrailPositions", _trailPositionsBuffer);
            ParticleIntegrationShader.SetBuffer(kernel, "TrailTimes", _trailTimesBuffer);
            ParticleIntegrationShader.SetBuffer(kernel, "TrailScalars", _trailScalarsBuffer);
            ParticleIntegrationShader.SetBuffer(kernel, "TrailCounts", _trailCountsBuffer);

            ParticleIntegrationShader.SetInts("FieldDimensions", _field[0].DimX, _field[0].DimY, _field[0].DimZ);
            ParticleIntegrationShader.SetVector("FieldMinBounds", new Vector4(_field[0].MinBounds.x, _field[0].MinBounds.y, _field[0].MinBounds.z, 0));
            ParticleIntegrationShader.SetVector("FieldCellSize", new Vector4(_field[0].CellSize.x, _field[0].CellSize.y, _field[0].CellSize.z, 0));
            ParticleIntegrationShader.SetFloat("TimeStepDuration", _field.TimeStepDuration);
            ParticleIntegrationShader.SetFloat("DeltaTime", deltaTime);
            ParticleIntegrationShader.SetFloat("SimulationTime", simulationTime);
            ParticleIntegrationShader.SetFloat("TimeInterpolation", _currentTimeInterpolation);
            ParticleIntegrationShader.SetInt("IntegrationDirection", (int)direction);
            ParticleIntegrationShader.SetInt("ColorFieldType", (int)colorField);
            ParticleIntegrationShader.SetFloat("MinStepSize", MinStepSize);
            ParticleIntegrationShader.SetFloat("MaxStepSize", MaxStepSize);
            ParticleIntegrationShader.SetFloat("Tolerance", Tolerance);
            ParticleIntegrationShader.SetInt("MaxTrailLength", TrailLength);

            int particlesPerThread = UseBatchIntegration ? 4 : 1;
            int threadGroups = Mathf.CeilToInt(ActiveParticles / (float)(THREADS_PER_GROUP * particlesPerThread));
            ParticleIntegrationShader.Dispatch(kernel, threadGroups, 1, 1);

            if (AsyncReadback)
            {
                AsyncGPUReadback.Request(_particlesBuffer, OnParticlesReadback);
                AsyncGPUReadback.Request(_trailCountsBuffer, OnTrailCountsReadback);
            }
            else
            {
                _particlesBuffer.GetData(_cpuParticles, 0, 0, ActiveParticles);
                _trailCountsBuffer.GetData(_trailCounts, 0, 0, ActiveParticles);
                _trailPositionsBuffer.GetData(_trailPositions);
                _trailTimesBuffer.GetData(_trailTimes);
                _trailScalarsBuffer.GetData(_trailScalars);

                OnParticlesUpdated?.Invoke();
            }
        }

        private void OnParticlesReadback(AsyncGPUReadbackRequest request)
        {
            if (request.hasError)
            {
                UnityEngine.Debug.LogError("GPU particle readback error");
                return;
            }

            request.GetData<GPUParticle>().CopyTo(_cpuParticles, 0, ActiveParticles);
        }

        private void OnTrailCountsReadback(AsyncGPUReadbackRequest request)
        {
            if (request.hasError)
            {
                UnityEngine.Debug.LogError("GPU trail counts readback error");
                return;
            }

            request.GetData<int>().CopyTo(_trailCounts, 0, ActiveParticles);

            _trailPositionsBuffer.GetData(_trailPositions);
            _trailTimesBuffer.GetData(_trailTimes);
            _trailScalarsBuffer.GetData(_trailScalars);

            OnParticlesUpdated?.Invoke();
        }

        public float[] ComputeFTLEField(float startTime, float integrationTime, IntegrationDirection direction, float perturbationSize = 1e-3f)
        {
            if (!_initialized) return null;

            UpdateTimeInterpolatedField(startTime);

            ParticleIntegrationShader.SetBuffer(_computeFTLEKernel, "FieldVolume0", _fieldBuffer0);
            ParticleIntegrationShader.SetBuffer(_computeFTLEKernel, "FieldVolume1", _fieldBuffer1);
            ParticleIntegrationShader.SetBuffer(_computeFTLEKernel, "FTLEField", _ftleFieldBuffer);

            ParticleIntegrationShader.SetInts("FieldDimensions", _field[0].DimX, _field[0].DimY, _field[0].DimZ);
            ParticleIntegrationShader.SetVector("FieldMinBounds", new Vector4(_field[0].MinBounds.x, _field[0].MinBounds.y, _field[0].MinBounds.z, 0));
            ParticleIntegrationShader.SetVector("FieldCellSize", new Vector4(_field[0].CellSize.x, _field[0].CellSize.y, _field[0].CellSize.z, 0));
            ParticleIntegrationShader.SetFloat("TimeStepDuration", _field.TimeStepDuration);
            ParticleIntegrationShader.SetFloat("SimulationTime", startTime);
            ParticleIntegrationShader.SetFloat("TimeInterpolation", _currentTimeInterpolation);
            ParticleIntegrationShader.SetInt("IntegrationDirection", (int)direction);
            ParticleIntegrationShader.SetInt("FieldGridSize", FTLEGridSize);
            ParticleIntegrationShader.SetFloat("IntegrationTime", integrationTime);
            ParticleIntegrationShader.SetFloat("PerturbationSize", perturbationSize);

            int totalGridPoints = FTLEGridSize * FTLEGridSize * FTLEGridSize;
            int threadGroups = Mathf.CeilToInt(totalGridPoints / 128f);
            ParticleIntegrationShader.Dispatch(_computeFTLEKernel, threadGroups, 1, 1);

            _ftleFieldBuffer.GetData(_ftleField);

            OnFTLEComputed?.Invoke(integrationTime);

            return _ftleField;
        }

        public void ResetParticles()
        {
            if (!_initialized) return;

            ParticleIntegrationShader.SetBuffer(_resetKernel, "Particles", _particlesBuffer);
            ParticleIntegrationShader.SetBuffer(_resetKernel, "TrailCounts", _trailCountsBuffer);
            int threadGroups = Mathf.CeilToInt(MaxParticles / 128f);
            ParticleIntegrationShader.Dispatch(_resetKernel, threadGroups, 1, 1);

            ActiveParticles = 0;
            Array.Clear(_cpuParticles, 0, _cpuParticles.Length);
            Array.Clear(_trailCounts, 0, _trailCounts.Length);
        }

        public GPUParticle GetParticle(int index)
        {
            if (index < 0 || index >= ActiveParticles) return default;
            return _cpuParticles[index];
        }

        public Vector3[] GetParticleTrail(int particleIndex, out int trailLength)
        {
            trailLength = 0;
            if (particleIndex < 0 || particleIndex >= ActiveParticles) return null;

            trailLength = _trailCounts[particleIndex];
            if (trailLength == 0) return null;

            Vector3[] trail = new Vector3[trailLength];
            int startIdx = particleIndex * TrailLength;
            Array.Copy(_trailPositions, startIdx, trail, 0, trailLength);
            return trail;
        }

        public float[] GetTrailScalars(int particleIndex, out int trailLength)
        {
            trailLength = 0;
            if (particleIndex < 0 || particleIndex >= ActiveParticles) return null;

            trailLength = _trailCounts[particleIndex];
            if (trailLength == 0) return null;

            float[] scalars = new float[trailLength];
            int startIdx = particleIndex * TrailLength;
            Array.Copy(_trailScalars, startIdx, scalars, 0, trailLength);
            return scalars;
        }

        public void SyncWithSeeds(List<SeedPoint> seedPoints, float simulationTime)
        {
            if (!_initialized) return;

            ResetParticles();

            foreach (var seed in seedPoints)
            {
                if (!seed.IsActive) continue;

                switch (seed.LineType)
                {
                    case LineType.Pathline:
                        SpawnParticle(seed.Position, simulationTime);
                        break;
                    case LineType.Streakline:
                        foreach (var particle in seed.Particles)
                        {
                            if (particle.Data.IsAlive)
                            {
                                SpawnParticle(particle.Data.Position, particle.Data.Time);
                            }
                        }
                        break;
                    case LineType.Stripline:
                        foreach (var particle in seed.Particles)
                        {
                            if (particle.Data.IsAlive)
                            {
                                SpawnParticle(particle.Data.Position, particle.Data.Time);
                            }
                        }
                        break;
                }
            }
        }

        private const int THREADS_PER_GROUP = 128;
    }
}
