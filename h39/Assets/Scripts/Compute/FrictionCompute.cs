using UnityEngine;
using UnityEngine.Rendering;
using System;
using System.Threading.Tasks;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.Compute
{
    public class FrictionCompute : IDisposable
    {
        private readonly ComputeShader _shader;

        private ComputeBuffer _pressureBuffer;
        private ComputeBuffer _waterFilmBuffer;
        private ComputeBuffer _frictionResultsBuffer;
        private RenderTexture _heatmapTexture;

        private int _kernelFriction;
        private int _kernelWaterFilm;
        private int _kernelHeatmap;

        private int _resolution = 64;
        private int _velocityCount = 50;
        private float _minVelocity = 0.001f;
        private float _maxVelocity = 10f;
        private bool _disposed = false;

        public RenderTexture HeatmapTexture => _heatmapTexture;

        public FrictionCompute(ComputeShader shader)
        {
            _shader = shader;
            _kernelFriction = shader.FindKernel("CalculateFrictionPoints");
            _kernelWaterFilm = shader.FindKernel("CalculateWaterFilm");
            _kernelHeatmap = shader.FindKernel("GenerateHeatmap");
        }

        public void Initialize(int resolution, int velocityCount)
        {
            ReleaseBuffers();

            _resolution = resolution;
            _velocityCount = velocityCount;
            int totalCells = resolution * resolution;

            _pressureBuffer = new ComputeBuffer(totalCells, sizeof(float));
            _waterFilmBuffer = new ComputeBuffer(totalCells, sizeof(float));
            _frictionResultsBuffer = new ComputeBuffer(velocityCount, 4 * sizeof(float));

            _heatmapTexture = new RenderTexture(resolution, resolution, 0, RenderTextureFormat.ARGB32)
            {
                enableRandomWrite = true,
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp
            };
            _heatmapTexture.Create();

            _shader.SetBuffer(_kernelFriction, "contactPressure", _pressureBuffer);
            _shader.SetBuffer(_kernelFriction, "frictionResults", _frictionResultsBuffer);

            _shader.SetBuffer(_kernelWaterFilm, "contactPressure", _pressureBuffer);
            _shader.SetBuffer(_kernelWaterFilm, "waterFilmThickness", _waterFilmBuffer);

            _shader.SetBuffer(_kernelHeatmap, "contactPressure", _pressureBuffer);
            _shader.SetTexture(_kernelHeatmap, "heatmapTexture", _heatmapTexture);
        }

        public void SetMaterialParams(RubberMaterial material)
        {
            _shader.SetFloat("material_elasticModulus", material.elasticModulus);
            _shader.SetFloat("material_poissonRatio", material.poissonRatio);
            _shader.SetFloat("material_hurstExponent", material.hurstExponent);
            _shader.SetFloat("material_rmsRoughness", material.rmsRoughness);
            _shader.SetFloat("material_correlationLength", material.correlationLength);
            _shader.SetFloat("material_lossFactor", material.lossFactor);
            _shader.SetFloat("material_shoreHardness", material.shoreHardness);
            _shader.SetFloat("minimumLengthScale", material.minimumLengthScale);
        }

        public void SetGroundParams(GroundSurface ground)
        {
            _shader.SetInt("ground_groundType", (int)ground.groundType);
            _shader.SetFloat("ground_roughness", ground.roughness);
            _shader.SetFloat("ground_hardness", ground.hardness);
            _shader.SetFloat("ground_waterFilmThickness", ground.waterFilmThickness);
            _shader.SetFloat("ground_fluidViscosity", ground.fluidViscosity);
            _shader.SetFloat("ground_hurstExponent", ground.hurstExponent);
            _shader.SetFloat("groundCorrelationLength", ground.correlationLength);
            _shader.SetFloat("groundMinLengthScale", ground.minimumLengthScale);
            _shader.SetFloat("groundHurst", ground.hurstExponent);
        }

        public void SetSimulationParams(float averagePressure, float contactAreaRatio,
            int velocityCount, float minVelocity, float maxVelocity)
        {
            SetSimulationParams(averagePressure, contactAreaRatio, velocityCount,
                minVelocity, maxVelocity, new SimulationParams());
        }

        public void SetSimulationParams(float averagePressure, float contactAreaRatio,
            int velocityCount, float minVelocity, float maxVelocity, SimulationParams simParams)
        {
            _velocityCount = velocityCount;
            _minVelocity = minVelocity;
            _maxVelocity = maxVelocity;

            _shader.SetFloat("averagePressure", averagePressure);
            _shader.SetFloat("contactAreaRatio", contactAreaRatio);
            _shader.SetInt("velocityCount", velocityCount);
            _shader.SetFloat("minVelocity", minVelocity);
            _shader.SetFloat("maxVelocity", maxVelocity);
            _shader.SetFloat("staticFrictionMultiplier", simParams.staticFrictionMultiplier);
            _shader.SetFloat("transitionVelocity", simParams.transitionVelocity);
            _shader.SetFloat("transitionSharpness", simParams.transitionSharpness);
            _shader.SetInt("enableStickSlip", simParams.enableStickSlip ? 1 : 0);
        }

        public void SetPressureData(float[,] pressure)
        {
            int n = pressure.GetLength(0);
            int m = pressure.GetLength(1);
            float[] flat = new float[n * m];

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < m; j++)
                {
                    flat[i * m + j] = pressure[i, j];
                }
            }

            _pressureBuffer.SetData(flat);
        }

        public async Task<float[]> CalculateFrictionCurveAsync()
        {
            return await Task.Run(() =>
            {
                int threadGroups = Mathf.CeilToInt((float)_velocityCount / 64f);
                _shader.Dispatch(_kernelFriction, threadGroups, 1, 1);

                float[] results = new float[_velocityCount * 4];
                _frictionResultsBuffer.GetData(results);

                float[] frictionCoeffs = new float[_velocityCount];
                for (int i = 0; i < _velocityCount; i++)
                {
                    frictionCoeffs[i] = results[i * 4 + 1];
                }

                return frictionCoeffs;
            });
        }

        public async Task<float[]> CalculateFrictionCurveAsync(float[] velocities)
        {
            return await CalculateFrictionCurveAsync();
        }

        public async Task<float[,]> CalculateWaterFilmAsync()
        {
            return await Task.Run(() =>
            {
                int threadGroups = Mathf.CeilToInt((float)_resolution / 8f);
                _shader.Dispatch(_kernelWaterFilm, threadGroups, threadGroups, 1);

                float[] flat = new float[_resolution * _resolution];
                _waterFilmBuffer.GetData(flat);

                float[,] result = new float[_resolution, _resolution];
                for (int i = 0; i < _resolution; i++)
                {
                    for (int j = 0; j < _resolution; j++)
                    {
                        result[i, j] = flat[i * _resolution + j];
                    }
                }

                return result;
            });
        }

        public void GenerateHeatmap()
        {
            int threadGroups = Mathf.CeilToInt((float)_resolution / 8f);
            _shader.Dispatch(_kernelHeatmap, threadGroups, threadGroups, 1);
        }

        public Texture2D GetHeatmapTexture2D()
        {
            RenderTexture.active = _heatmapTexture;
            Texture2D tex = new Texture2D(_resolution, _resolution, TextureFormat.ARGB32, false);
            tex.ReadPixels(new Rect(0, 0, _resolution, _resolution), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            return tex;
        }

        public float[] GetVelocities(float minVelocity, float maxVelocity, int count)
        {
            float[] velocities = new float[count];
            float logMin = Mathf.Log10(minVelocity);
            float logMax = Mathf.Log10(maxVelocity);

            for (int i = 0; i < count; i++)
            {
                float t = (float)i / (count - 1);
                float logV = logMin + t * (logMax - logMin);
                velocities[i] = Mathf.Pow(10f, logV);
            }

            return velocities;
        }

        private void ReleaseBuffers()
        {
            _pressureBuffer?.Release();
            _waterFilmBuffer?.Release();
            _frictionResultsBuffer?.Release();

            if (_heatmapTexture != null)
            {
                _heatmapTexture.Release();
                UnityEngine.Object.Destroy(_heatmapTexture);
            }

            _pressureBuffer = null;
            _waterFilmBuffer = null;
            _frictionResultsBuffer = null;
            _heatmapTexture = null;
        }

        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }

        protected virtual void Dispose(bool disposing)
        {
            if (_disposed) return;

            if (disposing)
            {
                ReleaseBuffers();
            }

            _disposed = true;
        }

        ~FrictionCompute()
        {
            Dispose(false);
        }
    }
}
