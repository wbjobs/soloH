using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;
using FlowVisualization.Core;
using FlowVisualization.Data;
using FlowVisualization.Rendering;

namespace FlowVisualization.Particles
{
    public class ParticleSystemManager : MonoBehaviour
    {
        [Header("Data Settings")]
        public string NetCDFFilePath = "";
        public bool UseSyntheticData = true;
        public int SyntheticResolution = 32;
        public int SyntheticTimeSteps = 128;

        [Header("Simulation Settings")]
        public float SimulationSpeed = 1.0f;
        public IntegrationDirection Direction = IntegrationDirection.Forward;
        public float SimulationTime { get; private set; }
        public bool IsPaused = false;

        [Header("Color Mapping")]
        public ScalarFieldType ColorField = ScalarFieldType.VelocityMagnitude;
        public Gradient ColorGradient;
        public float ColorMinValue = 0f;
        public float ColorMaxValue = 5f;
        public bool AutoRange = true;

        [Header("Particle Settings")]
        public int MaxParticlesPerSeed = 200;
        public float ParticleReleaseInterval = 0.02f;
        public int TrailLength = 256;

        [Header("Performance")]
        public int TargetParticlesPerSecond = 100000;
        public bool UseParallelProcessing = true;

        public TimeVaryingField Field { get; private set; }
        public IReadOnlyList<SeedPoint> SeedPoints => _seedPoints;
        public int TotalActiveParticles { get; private set; }
        public int ParticlesProcessedPerSecond { get; private set; }
        public ParticlePool ParticlePool { get; private set; }

        private readonly List<SeedPoint> _seedPoints = new List<SeedPoint>(32);
        private int _seedPointIdCounter;
        private bool _dataLoaded;
        private float _fpsTimer;
        private int _particlesProcessedThisSecond;
        private LineRendererManager _lineRenderer;
        private ParticleRenderer _particleRenderer;
        private float _memoryCleanupTimer;
        private const float MemoryCleanupInterval = 30f;

        public event Action OnDataLoaded;
        public event Action<int> OnSeedPointAdded;
        public event Action<int> OnSeedPointRemoved;

        private void Awake()
        {
            InitializeColorGradient();
        }

        private async void Start()
        {
            _lineRenderer = GetComponent<LineRendererManager>() ?? gameObject.AddComponent<LineRendererManager>();
            _particleRenderer = GetComponent<ParticleRenderer>() ?? gameObject.AddComponent<ParticleRenderer>();

            ParticlePool = new ParticlePool(
                initialCapacity: 2000,
                maxCapacity: 100000,
                trailLength: TrailLength
            );

            await LoadData();
        }

        private void Update()
        {
            if (!_dataLoaded || IsPaused) return;

            float deltaTime = Time.deltaTime * SimulationSpeed;
            SimulationTime += deltaTime;

            if (UseParallelProcessing && _seedPoints.Count > 5)
            {
                UpdateSeedsParallel(deltaTime);
            }
            else
            {
                UpdateSeedsSequential(deltaTime);
            }

            _fpsTimer += Time.deltaTime;
            if (_fpsTimer >= 1f)
            {
                ParticlesProcessedPerSecond = _particlesProcessedThisSecond;
                _particlesProcessedThisSecond = 0;
                _fpsTimer = 0f;
            }

            _memoryCleanupTimer += Time.deltaTime;
            if (_memoryCleanupTimer >= MemoryCleanupInterval)
            {
                PerformMemoryCleanup();
                _memoryCleanupTimer = 0f;
            }

            TotalActiveParticles = 0;
            foreach (var seed in _seedPoints)
            {
                TotalActiveParticles += seed.ActiveParticleCount;
            }

            _lineRenderer?.UpdateRendering(_seedPoints, this);
            _particleRenderer?.UpdateRendering(_seedPoints, this);
        }

        private void PerformMemoryCleanup()
        {
            ParticlePool?.TrimExcess();
            
            foreach (var seed in _seedPoints)
            {
                seed.CleanupDeadParticles(ParticlePool);
            }

            System.GC.Collect(System.GC.MaxGeneration, System.GCCollectionMode.Optimized, false);
        }

        private async Task LoadData()
        {
            try
            {
                if (UseSyntheticData)
                {
                    await Task.Run(() =>
                    {
                        SyntheticFieldGenerator generator = new SyntheticFieldGenerator(
                            SyntheticResolution,
                            SyntheticResolution,
                            SyntheticResolution,
                            SyntheticTimeSteps
                        );
                        Field = generator.Generate();
                    });
                }
                else
                {
                    if (string.IsNullOrEmpty(NetCDFFilePath))
                    {
                        Debug.LogError("NetCDF file path not specified!");
                        UseSyntheticData = true;
                        await LoadData();
                        return;
                    }

                    INetcdfReader reader = new NetCDFReader();
                    Field = await reader.LoadAsync(NetCDFFilePath);
                }

                _dataLoaded = true;
                OnDataLoaded?.Invoke();

                if (AutoRange)
                {
                    ComputeAutoRange();
                }

                Debug.Log($"Data loaded: {Field.TimeStepCount} time steps, " +
                          $"{Field[0].DimX}x{Field[0].DimY}x{Field[0].DimZ} resolution");
            }
            catch (Exception e)
            {
                Debug.LogError($"Failed to load data: {e.Message}");
            }
        }

        private void InitializeColorGradient()
        {
            ColorGradient = new Gradient();
            GradientColorKey[] colorKeys = new GradientColorKey[6];
            colorKeys[0] = new GradientColorKey(new Color(0.0f, 0.0f, 0.5f), 0.0f);
            colorKeys[1] = new GradientColorKey(new Color(0.0f, 0.2f, 0.8f), 0.2f);
            colorKeys[2] = new GradientColorKey(new Color(0.0f, 0.8f, 0.8f), 0.4f);
            colorKeys[3] = new GradientColorKey(new Color(0.2f, 0.8f, 0.2f), 0.6f);
            colorKeys[4] = new GradientColorKey(new Color(0.8f, 0.8f, 0.0f), 0.8f);
            colorKeys[5] = new GradientColorKey(new Color(1.0f, 0.0f, 0.0f), 1.0f);

            GradientAlphaKey[] alphaKeys = new GradientAlphaKey[2];
            alphaKeys[0] = new GradientAlphaKey(1.0f, 0.0f);
            alphaKeys[1] = new GradientAlphaKey(1.0f, 1.0f);

            ColorGradient.SetKeys(colorKeys, alphaKeys);
        }

        private void ComputeAutoRange()
        {
            float min = float.MaxValue;
            float max = float.MinValue;

            Vector3Field f0 = Field[0];
            for (int x = 0; x < f0.DimX; x++)
            {
                for (int y = 0; y < f0.DimY; y++)
                {
                    for (int z = 0; z < f0.DimZ; z++)
                    {
                        float val = ColorField switch
                        {
                            ScalarFieldType.VelocityMagnitude => f0.Velocity[x, y, z].magnitude,
                            ScalarFieldType.Vorticity => f0.VorticityMagnitude[x, y, z],
                            ScalarFieldType.Pressure => f0.Pressure[x, y, z],
                            _ => 0f
                        };
                        min = Mathf.Min(min, val);
                        max = Mathf.Max(max, val);
                    }
                }
            }

            ColorMinValue = min * 0.9f;
            ColorMaxValue = max * 1.1f;
        }

        private void UpdateSeedsSequential(float deltaTime)
        {
            foreach (var seed in _seedPoints)
            {
                seed.Update(SimulationTime, deltaTime, Direction);
                _particlesProcessedThisSecond += seed.ActiveParticleCount;
            }
        }

        private void UpdateSeedsParallel(float deltaTime)
        {
            int processedCount = 0;
            Parallel.ForEach(_seedPoints, seed =>
            {
                seed.Update(SimulationTime, deltaTime, Direction);
                System.Threading.Interlocked.Add(ref processedCount, seed.ActiveParticleCount);
            });
            _particlesProcessedThisSecond += processedCount;
        }

        public SeedPoint AddSeedPoint(Vector3 position, LineType lineType)
        {
            SeedPoint seed = new SeedPoint(
                _seedPointIdCounter++,
                position,
                lineType,
                Field,
                ParticlePool,
                MaxParticlesPerSeed,
                ParticleReleaseInterval,
                ColorField
            );

            _seedPoints.Add(seed);
            OnSeedPointAdded?.Invoke(seed.ID);
            return seed;
        }

        public void RemoveSeedPoint(int seedId)
        {
            int index = _seedPoints.FindIndex(s => s.ID == seedId);
            if (index >= 0)
            {
                _seedPoints[index].Clear();
                _seedPoints.RemoveAt(index);
                OnSeedPointRemoved?.Invoke(seedId);
                ParticlePool?.TrimExcess();
            }
        }

        public void ClearAllSeedPoints()
        {
            foreach (var seed in _seedPoints)
            {
                seed.Clear();
            }
            _seedPoints.Clear();
            ParticlePool?.TrimExcess();
        }

        public void ResetSimulation()
        {
            SimulationTime = Field != null ? Field.MinTime : 0f;
            foreach (var seed in _seedPoints)
            {
                seed.Reset(SimulationTime);
            }
            ParticlePool?.TrimExcess();
        }

        public void TogglePause()
        {
            IsPaused = !IsPaused;
        }

        public void SetIntegrationDirection(IntegrationDirection direction)
        {
            Direction = direction;
        }

        public Color GetColorForScalar(float scalarValue)
        {
            float normalized = Mathf.Clamp01((scalarValue - ColorMinValue) / (ColorMaxValue - ColorMinValue));
            return ColorGradient.Evaluate(normalized);
        }

        public void UpdateColorField(ScalarFieldType newField)
        {
            ColorField = newField;
            if (AutoRange)
            {
                ComputeAutoRange();
            }
        }
    }
}
