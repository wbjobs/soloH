using UnityEngine;
using UnityEngine.Rendering;
using System.Threading.Tasks;
using System;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.Compute
{
    public class BEMCompute : IDisposable
    {
        private readonly ComputeShader _shader;
        private int _resolution;
        private float _cellSize;

        private ComputeBuffer _cellsBuffer;
        private ComputeBuffer _influenceMatrixBuffer;
        private ComputeBuffer _searchDirBuffer;
        private ComputeBuffer _tempBuffer;

        private int _kernelPrecompute;
        private int _kernelDisplacement;
        private int _kernelResidual;
        private int _kernelPressureUpdate;

        private bool _disposed = false;

        public BEMCompute(ComputeShader shader)
        {
            _shader = shader;
            _kernelPrecompute = shader.FindKernel("PrecomputeInfluenceRow");
            _kernelDisplacement = shader.FindKernel("ComputeDisplacement");
            _kernelResidual = shader.FindKernel("ComputeResidual");
            _kernelPressureUpdate = shader.FindKernel("ApplyPressureUpdate");
        }

        public void Initialize(int resolution, float cellSize, float effectiveModulus, float targetLoad, float tolerance)
        {
            ReleaseBuffers();

            _resolution = resolution;
            _cellSize = cellSize;
            int totalCells = resolution * resolution;

            _cellsBuffer = new ComputeBuffer(totalCells, 6 * sizeof(float));
            _influenceMatrixBuffer = new ComputeBuffer(totalCells * totalCells, sizeof(float));
            _searchDirBuffer = new ComputeBuffer(totalCells, sizeof(float));
            _tempBuffer = new ComputeBuffer(totalCells, sizeof(float));

            _shader.SetInt("resolution", resolution);
            _shader.SetFloat("cellSize", cellSize);
            _shader.SetFloat("effectiveModulus", effectiveModulus);
            _shader.SetFloat("targetLoad", targetLoad);
            _shader.SetFloat("tolerance", tolerance);

            _shader.SetBuffer(_kernelPrecompute, "influenceMatrix", _influenceMatrixBuffer);
            _shader.SetBuffer(_kernelPrecompute, "cells", _cellsBuffer);

            _shader.SetBuffer(_kernelDisplacement, "cells", _cellsBuffer);
            _shader.SetBuffer(_kernelDisplacement, "influenceMatrix", _influenceMatrixBuffer);

            _shader.SetBuffer(_kernelResidual, "cells", _cellsBuffer);
            _shader.SetBuffer(_kernelResidual, "tempBuffer", _tempBuffer);

            _shader.SetBuffer(_kernelPressureUpdate, "cells", _cellsBuffer);
            _shader.SetBuffer(_kernelPressureUpdate, "searchDir", _searchDirBuffer);
            _shader.SetBuffer(_kernelPressureUpdate, "tempBuffer", _tempBuffer);
        }

        public async Task PrecomputeInfluenceMatrixAsync()
        {
            await Task.Run(() =>
            {
                int threadGroups = Mathf.CeilToInt((float)(_resolution * _resolution) / 64f);
                _shader.Dispatch(_kernelPrecompute, threadGroups, 1, 1);
            });
        }

        public void ComputeDisplacement()
        {
            int threadGroups = Mathf.CeilToInt((float)(_resolution * _resolution) / 64f);
            _shader.Dispatch(_kernelDisplacement, threadGroups, 1, 1);
        }

        public float ComputeResidual()
        {
            int threadGroups = Mathf.CeilToInt((float)(_resolution * _resolution) / 64f);
            _shader.Dispatch(_kernelResidual, threadGroups, 1, 1);

            float[] residuals = new float[_resolution * _resolution];
            _tempBuffer.GetData(residuals);

            float sum = 0f;
            for (int i = 0; i < residuals.Length; i++)
            {
                sum += residuals[i];
            }

            return Mathf.Sqrt(sum);
        }

        public void SetCellsData(float[] pressures, float[] gaps)
        {
            int total = _resolution * _resolution;
            float[] cellData = new float[total * 6];

            for (int i = 0; i < total; i++)
            {
                int xi = i / _resolution;
                int yi = i % _resolution;
                cellData[i * 6] = (xi + 0.5f) * _cellSize;
                cellData[i * 6 + 1] = (yi + 0.5f) * _cellSize;
                cellData[i * 6 + 2] = pressures[i];
                cellData[i * 6 + 3] = 0f;
                cellData[i * 6 + 4] = gaps[i];
                cellData[i * 6 + 5] = 0f;
            }

            _cellsBuffer.SetData(cellData);
        }

        public void GetPressures(float[] pressures)
        {
            float[] cellData = new float[_resolution * _resolution * 6];
            _cellsBuffer.GetData(cellData);

            for (int i = 0; i < _resolution * _resolution; i++)
            {
                pressures[i] = cellData[i * 6 + 2];
            }
        }

        public void SetSearchDirection(float[] direction)
        {
            _searchDirBuffer.SetData(direction);
        }

        public void ApplyPressureUpdate(float alpha)
        {
            float[] alphaData = new float[1] { alpha };
            _tempBuffer.SetData(alphaData);

            int threadGroups = Mathf.CeilToInt((float)(_resolution * _resolution) / 64f);
            _shader.Dispatch(_kernelPressureUpdate, threadGroups, 1, 1);
        }

        private void ReleaseBuffers()
        {
            _cellsBuffer?.Release();
            _influenceMatrixBuffer?.Release();
            _searchDirBuffer?.Release();
            _tempBuffer?.Release();

            _cellsBuffer = null;
            _influenceMatrixBuffer = null;
            _searchDirBuffer = null;
            _tempBuffer = null;
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

        ~BEMCompute()
        {
            Dispose(false);
        }
    }
}
