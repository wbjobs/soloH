using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;
using FlowVisualization.Core;
using FlowVisualization.Analysis;
using FlowVisualization.Compute;

namespace FlowVisualization.Rendering
{
    public class LCSFieldRenderer : MonoBehaviour
    {
        [Header("LCS Settings")]
        public bool ShowLCS = true;
        public float IntegrationTime = 2.0f;
        public float PerturbationSize = 1e-3f;
        [Range(0.0f, 1.0f)]
        public float Threshold = 0.3f;
        [Range(4, 64)]
        public int RenderGridSize = 32;
        public bool ShowAttracting = true;
        public bool ShowRepelling = true;
        public bool ShowStretching = false;
        public bool ShowCompression = false;

        [Header("Rendering")]
        public Material PointMaterial;
        public float PointSize = 0.01f;
        public float Alpha = 0.8f;
        public bool UseGPUComputation = true;

        [Header("References")]
        public LyapunovCalculator LyapunovCalculator;
        public GPUParticleSystem GPUParticleSystem;
        public ColorMapManager ColorMapManager;

        private ComputeBuffer _pointBuffer;
        private ComputeBuffer _colorBuffer;
        private ComputeBuffer _argsBuffer;

        private Vector3[] _positions;
        private Color[] _colors;
        private int[] _args;
        private int _activePointCount;

        private float[,,] _ftleForward;
        private float[,,] _ftleBackward;
        private float[,,] _lcsAttracting;
        private float[,,] _lcsRepelling;
        private float[,,] _stretching;
        private float[,,] _compression;

        private bool _dataDirty;
        private float _lastComputationTime = -1;
        private const float ComputationInterval = 0.1f;

        public event Action OnLCSUpdated;

        private void OnDisable()
        {
            ReleaseBuffers();
        }

        private void Update()
        {
            if (!ShowLCS || LyapunovCalculator == null) return;

            float simTime = LyapunovCalculator.Field?.MinTime ?? 0;
            if (Time.time - _lastComputationTime > ComputationInterval)
            {
                _lastComputationTime = Time.time;
                UpdateLCSData(simTime);
            }

            if (_dataDirty)
            {
                UpdatePointData();
                _dataDirty = false;
            }

            if (_activePointCount > 0 && PointMaterial != null)
            {
                RenderPoints();
            }
        }

        public void UpdateLCSData(float time)
        {
            if (LyapunovCalculator == null || LyapunovCalculator.Field == null) return;

            try
            {
                if (UseGPUComputation && GPUParticleSystem != null && GPUParticleSystem.IsInitialized)
                {
                    float[] gpuFTLE = GPUParticleSystem.ComputeFTLEField(
                        time,
                        IntegrationTime,
                        IntegrationDirection.Forward,
                        PerturbationSize
                    );

                    if (gpuFTLE != null)
                    {
                        UpdateFieldFromGPU(gpuFTLE, ref _ftleForward);
                        _lcsRepelling = (float[,,])_ftleForward.Clone();

                        gpuFTLE = GPUParticleSystem.ComputeFTLEField(
                            time,
                            IntegrationTime,
                            IntegrationDirection.Backward,
                            PerturbationSize
                        );

                        if (gpuFTLE != null)
                        {
                            UpdateFieldFromGPU(gpuFTLE, ref _ftleBackward);
                            _lcsAttracting = (float[,,])_ftleBackward.Clone();
                        }
                    }
                }
                else
                {
                    LyapunovCalculator.ComputeAll(time);
                    
                    _ftleForward = LyapunovCalculator.FTLEForward;
                    _ftleBackward = LyapunovCalculator.FTLEBackward;
                    _lcsAttracting = LyapunovCalculator.LCSAttracting;
                    _lcsRepelling = LyapunovCalculator.LCSRepelling;
                    _stretching = LyapunovCalculator.StretchingField;
                    _compression = LyapunovCalculator.CompressionField;
                }

                _dataDirty = true;
                OnLCSUpdated?.Invoke();
            }
            catch (Exception e)
            {
                UnityEngine.Debug.LogError($"LCS computation error: {e.Message}");
            }
        }

        private void UpdateFieldFromGPU(float[] gpuData, ref float[,,] field)
        {
            int size = RenderGridSize;
            if (field == null || field.GetLength(0) != size)
            {
                field = new float[size, size, size];
            }

            Parallel.For(0, size, z =>
            {
                for (int y = 0; y < size; y++)
                {
                    for (int x = 0; x < size; x++)
                    {
                        int idx = (z * size + y) * size + x;
                        if (idx < gpuData.Length)
                        {
                            field[x, y, z] = gpuData[idx];
                        }
                    }
                }
            });
        }

        private void UpdatePointData()
        {
            if (_ftleForward == null) return;

            int size = _ftleForward.GetLength(0);
            int totalPoints = size * size * size;

            if (_positions == null || _positions.Length != totalPoints)
            {
                _positions = new Vector3[totalPoints];
                _colors = new Color[totalPoints];
            }

            Vector3 minBounds = LyapunovCalculator.Field[0].MinBounds;
            Vector3 maxBounds = LyapunovCalculator.Field[0].MaxBounds;
            Vector3 cellSize = new Vector3(
                (maxBounds.x - minBounds.x) / (size - 1),
                (maxBounds.y - minBounds.y) / (size - 1),
                (maxBounds.z - minBounds.z) / (size - 1)
            );

            float maxFTLE = 0.01f;
            for (int z = 0; z < size; z++)
            {
                for (int y = 0; y < size; y++)
                {
                    for (int x = 0; x < size; x++)
                    {
                        if (_ftleForward != null) maxFTLE = Mathf.Max(maxFTLE, _ftleForward[x, y, z]);
                        if (_ftleBackward != null) maxFTLE = Mathf.Max(maxFTLE, _ftleBackward[x, y, z]);
                    }
                }
            }

            _activePointCount = 0;

            Parallel.For(0, size, z =>
            {
                for (int y = 0; y < size; y++)
                {
                    for (int x = 0; x < size; x++)
                    {
                        int idx = (z * size + y) * size + x;

                        Vector3 pos = new Vector3(
                            minBounds.x + x * cellSize.x,
                            minBounds.y + y * cellSize.y,
                            minBounds.z + z * cellSize.z
                        );

                        float ftleForward = _ftleForward != null ? _ftleForward[x, y, z] : 0;
                        float ftleBackward = _ftleBackward != null ? _ftleBackward[x, y, z] : 0;
                        float stretching = _stretching != null ? _stretching[x, y, z] : 0;
                        float compression = _compression != null ? _compression[x, y, z] : 0;

                        float value = 0;
                        Color color = Color.clear;
                        bool showPoint = false;

                        if (ShowRepelling && ftleForward > Threshold * maxFTLE)
                        {
                            value = ftleForward / maxFTLE;
                            color = GetColorForField(value, ScalarFieldType.FTLE);
                            showPoint = true;
                        }
                        else if (ShowAttracting && ftleBackward > Threshold * maxFTLE)
                        {
                            value = ftleBackward / maxFTLE;
                            color = GetColorForField(value, ScalarFieldType.LyapunovExponent);
                            color = Color.Lerp(Color.blue, Color.cyan, value);
                            showPoint = true;
                        }
                        else if (ShowStretching && stretching > 0.1f)
                        {
                            value = Mathf.Min(stretching, 1.0f);
                            color = Color.Lerp(Color.yellow, Color.red, value);
                            showPoint = true;
                        }
                        else if (ShowCompression && compression > 0.1f)
                        {
                            value = Mathf.Min(compression, 1.0f);
                            color = Color.Lerp(Color.green, Color.blue, value);
                            showPoint = true;
                        }

                        if (showPoint)
                        {
                            _positions[_activePointCount] = pos;
                            color.a = Alpha;
                            _colors[_activePointCount] = color;
                            _activePointCount++;
                        }
                    }
                }
            });

            if (_activePointCount > 0)
            {
                UpdateBuffers();
            }
        }

        private Color GetColorForField(float value, ScalarFieldType type)
        {
            if (ColorMapManager != null)
            {
                return ColorMapManager.GetColor(value, type);
            }
            return Color.Lerp(Color.blue, Color.red, value);
        }

        private void UpdateBuffers()
        {
            if (_pointBuffer != null) _pointBuffer.Release();
            if (_colorBuffer != null) _colorBuffer.Release();
            if (_argsBuffer != null) _argsBuffer.Release();

            _pointBuffer = new ComputeBuffer(_activePointCount, sizeof(float) * 3, ComputeBufferType.Structured);
            _colorBuffer = new ComputeBuffer(_activePointCount, sizeof(float) * 4, ComputeBufferType.Structured);
            _argsBuffer = new ComputeBuffer(1, sizeof(uint) * 5, ComputeBufferType.IndirectArguments);

            _pointBuffer.SetData(_positions, 0, 0, _activePointCount);
            _colorBuffer.SetData(_colors, 0, 0, _activePointCount);

            _args = new int[] { 0, _activePointCount, 0, 0, 0 };
            _argsBuffer.SetData(_args);
        }

        private void ReleaseBuffers()
        {
            if (_pointBuffer != null) { _pointBuffer.Release(); _pointBuffer = null; }
            if (_colorBuffer != null) { _colorBuffer.Release(); _colorBuffer = null; }
            if (_argsBuffer != null) { _argsBuffer.Release(); _argsBuffer = null; }
        }

        private void RenderPoints()
        {
            if (_pointBuffer == null || _colorBuffer == null || PointMaterial == null) return;

            PointMaterial.SetBuffer("positions", _pointBuffer);
            PointMaterial.SetBuffer("colors", _colorBuffer);
            PointMaterial.SetFloat("pointSize", PointSize);
            PointMaterial.SetPass(0);

            Graphics.DrawProceduralIndirectNow(MeshTopology.Points, _argsBuffer);
        }

        public void SetThreshold(float threshold)
        {
            Threshold = threshold;
            _dataDirty = true;
        }

        public void SetIntegrationTime(float time)
        {
            IntegrationTime = Mathf.Max(0.1f, time);
            _lastComputationTime = -1;
        }

        public void ToggleLCS(bool show)
        {
            ShowLCS = show;
            if (show)
            {
                _dataDirty = true;
                _lastComputationTime = -1;
            }
        }

        public void ToggleAttracting(bool show)
        {
            ShowAttracting = show;
            _dataDirty = true;
        }

        public void ToggleRepelling(bool show)
        {
            ShowRepelling = show;
            _dataDirty = true;
        }

        public float[,,] FTLEForward => _ftleForward;
        public float[,,] FTLEBackward => _ftleBackward;
        public float[,,] LCSAttracting => _lcsAttracting;
        public float[,,] LCSRepelling => _lcsRepelling;
    }
}
