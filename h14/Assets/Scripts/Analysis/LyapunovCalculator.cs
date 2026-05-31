using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;
using FlowVisualization.Core;
using FlowVisualization.Integration;
using FlowVisualization.Particles;

namespace FlowVisualization.Analysis
{
    public class LyapunovCalculator
    {
        private readonly TimeVaryingField _field;
        private readonly AdaptiveRK45 _integrator;
        private readonly int _gridX, _gridY, _gridZ;
        private readonly float _integrationTime;
        private readonly float _perturbationSize;

        public float[,,] FTLEForward { get; private set; }
        public float[,,] FTLEBackward { get; private set; }
        public float[,,] LCSAttracting { get; private set; }
        public float[,,] LCSRepelling { get; private set; }
        public float[,,] StretchingField { get; private set; }
        public float[,,] CompressionField { get; private set; }
        
        public float FTLEThreshold { get; set; } = 0.5f;
        public bool UseParallelProcessing { get; set; } = true;

        public LyapunovCalculator(
            TimeVaryingField field,
            float integrationTime = 2.0f,
            float perturbationSize = 1e-4f)
        {
            _field = field;
            _integrator = new AdaptiveRK45(field);
            _gridX = field[0].DimX;
            _gridY = field[0].DimY;
            _gridZ = field[0].DimZ;
            _integrationTime = integrationTime;
            _perturbationSize = perturbationSize;

            FTLEForward = new float[_gridX, _gridY, _gridZ];
            FTLEBackward = new float[_gridX, _gridY, _gridZ];
            LCSAttracting = new float[_gridX, _gridY, _gridZ];
            LCSRepelling = new float[_gridX, _gridY, _gridZ];
            StretchingField = new float[_gridX, _gridY, _gridZ];
            CompressionField = new float[_gridX, _gridY, _gridZ];
        }

        public void ComputeAll(float startTime)
        {
            ComputeFTLE(startTime, IntegrationDirection.Forward, FTLEForward);
            ComputeFTLE(startTime, IntegrationDirection.Backward, FTLEBackward);
            ComputeLCS();
            ComputeStretchingCompression(startTime);
            UpdateFieldData(startTime);
        }

        public void ComputeFTLE(
            float startTime,
            IntegrationDirection direction,
            float[,,] result)
        {
            Vector3Field baseField = _field[0];
            Vector3 offsetX = new Vector3(_perturbationSize, 0, 0);
            Vector3 offsetY = new Vector3(0, _perturbationSize, 0);
            Vector3 offsetZ = new Vector3(0, 0, _perturbationSize);

            float sign = direction == IntegrationDirection.Forward ? 1f : -1f;
            float absT = Math.Abs(_integrationTime);
            float inv2Eps = 1f / (2f * _perturbationSize);
            float invT = 1f / absT;

            Action<int> computeLine = (int x) =>
            {
                for (int y = 0; y < _gridY; y++)
                {
                    for (int z = 0; z < _gridZ; z++)
                    {
                        Vector3 basePos = new Vector3(
                            baseField.MinBounds.x + x * baseField.CellSize.x,
                            baseField.MinBounds.y + y * baseField.CellSize.y,
                            baseField.MinBounds.z + z * baseField.CellSize.z
                        );

                        if (!baseField.IsInsideBounds(basePos))
                        {
                            result[x, y, z] = 0f;
                            continue;
                        }

                        Vector3 finalBase = IntegrateParticle(basePos, startTime, _integrationTime, direction);
                        Vector3 finalX = IntegrateParticle(basePos + offsetX, startTime, _integrationTime, direction);
                        Vector3 finalY = IntegrateParticle(basePos + offsetY, startTime, _integrationTime, direction);
                        Vector3 finalZ = IntegrateParticle(basePos + offsetZ, startTime, _integrationTime, direction);

                        Vector3 dx = (finalX - finalBase) * inv2Eps;
                        Vector3 dy = (finalY - finalBase) * inv2Eps;
                        Vector3 dz = (finalZ - finalBase) * inv2Eps;

                        float[,] cauchyGreen = new float[3, 3];
                        cauchyGreen[0, 0] = dx.x * dx.x + dx.y * dx.y + dx.z * dx.z;
                        cauchyGreen[0, 1] = dx.x * dy.x + dx.y * dy.y + dx.z * dy.z;
                        cauchyGreen[0, 2] = dx.x * dz.x + dx.y * dz.y + dx.z * dz.z;
                        cauchyGreen[1, 0] = cauchyGreen[0, 1];
                        cauchyGreen[1, 1] = dy.x * dy.x + dy.y * dy.y + dy.z * dy.z;
                        cauchyGreen[1, 2] = dy.x * dz.x + dy.y * dz.y + dy.z * dz.z;
                        cauchyGreen[2, 0] = cauchyGreen[0, 2];
                        cauchyGreen[2, 1] = cauchyGreen[1, 2];
                        cauchyGreen[2, 2] = dz.x * dz.x + dz.y * dz.y + dz.z * dz.z;

                        float[] eigenvalues = ComputeEigenvalues(cauchyGreen);
                        float maxLambda = Mathf.Max(Mathf.Max(eigenvalues[0], eigenvalues[1]), eigenvalues[2]);

                        if (maxLambda > 1f)
                        {
                            result[x, y, z] = 0.5f * invT * Mathf.Log(maxLambda);
                        }
                        else
                        {
                            result[x, y, z] = 0f;
                        }
                    }
                }
            };

            if (UseParallelProcessing)
            {
                Parallel.For(0, _gridX, computeLine);
            }
            else
            {
                for (int x = 0; x < _gridX; x++)
                {
                    computeLine(x);
                }
            }
        }

        private Vector3 IntegrateParticle(
            Vector3 initialPos,
            float startTime,
            float integrationTime,
            IntegrationDirection direction)
        {
            var result = _integrator.Integrate(
                initialPos,
                startTime,
                integrationTime,
                direction
            );
            return result.FinalPosition;
        }

        private float[] ComputeEigenvalues(float[,] matrix)
        {
            float a = matrix[0, 0];
            float b = matrix[0, 1];
            float c = matrix[0, 2];
            float d = matrix[1, 0];
            float e = matrix[1, 1];
            float f = matrix[1, 2];
            float g = matrix[2, 0];
            float h = matrix[2, 1];
            float i = matrix[2, 2];

            float p1 = b * b + c * c + f * f;
            
            if (p1 == 0)
            {
                return new float[] { a, e, i };
            }

            float q = (a + e + i) / 3f;
            float p2 = (a - q) * (a - q) + (e - q) * (e - q) + (i - q) * (i - q) + 2f * p1;
            float p = Mathf.Sqrt(p2 / 6f);
            float invP = 1f / p;

            float det = (a - q) * ((e - q) * (i - q) - f * f) -
                       b * (d * (i - q) - f * c) +
                       c * (d * h - (e - q) * c);

            float r = det * invP * invP * invP * 0.5f;
            r = Mathf.Clamp(r, -1f, 1f);

            float phi = (float)Math.Acos(r) / 3f;
            float twoPi3 = 2f * Mathf.PI / 3f;

            float[] eigenvalues = new float[3];
            eigenvalues[0] = q + 2f * p * Mathf.Cos(phi);
            eigenvalues[1] = q + 2f * p * Mathf.Cos(phi + twoPi3);
            eigenvalues[2] = q + 2f * p * Mathf.Cos(phi + 2f * twoPi3);

            Array.Sort(eigenvalues);
            Array.Reverse(eigenvalues);

            for (int j = 0; j < 3; j++)
            {
                if (eigenvalues[j] < 0) eigenvalues[j] = 0;
            }

            return eigenvalues;
        }

        public void ComputeLCS()
        {
            Parallel.For(0, _gridX, x =>
            {
                for (int y = 0; y < _gridY; y++)
                {
                    for (int z = 0; z < _gridZ; z++)
                    {
                        float fwd = FTLEForward[x, y, z];
                        float bwd = FTLEBackward[x, y, z];

                        LCSRepelling[x, y, z] = fwd > FTLEThreshold ? fwd : 0f;
                        LCSAttracting[x, y, z] = bwd > FTLEThreshold ? bwd : 0f;
                    }
                }
            });
        }

        public void ComputeStretchingCompression(float startTime)
        {
            Vector3Field baseField = _field[0];
            float invDt = 1f / _field.TimeStepDuration;

            Parallel.For(0, _gridX, x =>
            {
                for (int y = 0; y < _gridY; y++)
                {
                    for (int z = 0; z < _gridZ; z++)
                    {
                        Vector3 pos = new Vector3(
                            baseField.MinBounds.x + x * baseField.CellSize.x,
                            baseField.MinBounds.y + y * baseField.CellSize.y,
                            baseField.MinBounds.z + z * baseField.CellSize.z
                        );

                        if (!baseField.IsInsideBounds(pos)) continue;

                        Vector3 vel = baseField.GetVelocity(pos);
                        
                        Vector3 gradVx = ComputeGradient(pos, startTime, 0);
                        Vector3 gradVy = ComputeGradient(pos, startTime, 1);
                        Vector3 gradVz = ComputeGradient(pos, startTime, 2);

                        float[,] velocityGradient = new float[3, 3];
                        velocityGradient[0, 0] = gradVx.x;
                        velocityGradient[0, 1] = gradVy.x;
                        velocityGradient[0, 2] = gradVz.x;
                        velocityGradient[1, 0] = gradVx.y;
                        velocityGradient[1, 1] = gradVy.y;
                        velocityGradient[1, 2] = gradVz.y;
                        velocityGradient[2, 0] = gradVx.z;
                        velocityGradient[2, 1] = gradVy.z;
                        velocityGradient[2, 2] = gradVz.z;

                        float[,] strainRate = new float[3, 3];
                        for (int i = 0; i < 3; i++)
                        {
                            for (int j = 0; j < 3; j++)
                            {
                                strainRate[i, j] = 0.5f * (velocityGradient[i, j] + velocityGradient[j, i]);
                            }
                        }

                        float[] eigenvals = ComputeEigenvalues(strainRate);
                        
                        float stretching = 0f;
                        float compression = 0f;
                        for (int k = 0; k < 3; k++)
                        {
                            if (eigenvals[k] > 0) stretching += eigenvals[k];
                            else compression += eigenvals[k];
                        }

                        StretchingField[x, y, z] = stretching;
                        CompressionField[x, y, z] = Mathf.Abs(compression);
                    }
                }
            });
        }

        private Vector3 ComputeGradient(Vector3 pos, float time, int component)
        {
            float dx = _field[0].CellSize.x;
            float dy = _field[0].CellSize.y;
            float dz = _field[0].CellSize.z;

            Vector3 px = new Vector3(pos.x + dx, pos.y, pos.z);
            Vector3 mx = new Vector3(pos.x - dx, pos.y, pos.z);
            Vector3 py = new Vector3(pos.x, pos.y + dy, pos.z);
            Vector3 my = new Vector3(pos.x, pos.y - dy, pos.z);
            Vector3 pz = new Vector3(pos.x, pos.y, pos.z + dz);
            Vector3 mz = new Vector3(pos.x, pos.y, pos.z - dz);

            Vector3 vpx = _field.GetVelocityAtTime(px, time, IntegrationDirection.Forward);
            Vector3 vmx = _field.GetVelocityAtTime(mx, time, IntegrationDirection.Forward);
            Vector3 vpy = _field.GetVelocityAtTime(py, time, IntegrationDirection.Forward);
            Vector3 vmy = _field.GetVelocityAtTime(my, time, IntegrationDirection.Forward);
            Vector3 vpz = _field.GetVelocityAtTime(pz, time, IntegrationDirection.Forward);
            Vector3 vmz = _field.GetVelocityAtTime(mz, time, IntegrationDirection.Forward);

            float[] vals = new float[6];
            vals[0] = component == 0 ? vpx.x : component == 1 ? vpx.y : vpx.z;
            vals[1] = component == 0 ? vmx.x : component == 1 ? vmx.y : vmx.z;
            vals[2] = component == 0 ? vpy.x : component == 1 ? vpy.y : vpy.z;
            vals[3] = component == 0 ? vmy.x : component == 1 ? vmy.y : vmy.z;
            vals[4] = component == 0 ? vpz.x : component == 1 ? vpz.y : vpz.z;
            vals[5] = component == 0 ? vmz.x : component == 1 ? vmz.y : vmz.z;

            float inv2dx = 1f / (2f * dx);
            float inv2dy = 1f / (2f * dy);
            float inv2dz = 1f / (2f * dz);

            return new Vector3(
                (vals[0] - vals[1]) * inv2dx,
                (vals[2] - vals[3]) * inv2dy,
                (vals[4] - vals[5]) * inv2dz
            );
        }

        public void UpdateFieldData(float startTime)
        {
            int timeStep = Mathf.Clamp(
                Mathf.FloorToInt((startTime - _field.MinTime) / _field.TimeStepDuration),
                0,
                _field.TimeStepCount - 1
            );

            Vector3Field field = _field[timeStep];

            for (int x = 0; x < _gridX; x++)
            {
                for (int y = 0; y < _gridY; y++)
                {
                    for (int z = 0; z < _gridZ; z++)
                    {
                        field.LyapunovExponent[x, y, z] = Mathf.Max(FTLEForward[x, y, z], FTLEBackward[x, y, z]);
                        field.FTLE[x, y, z] = FTLEForward[x, y, z];
                        field.Stretching[x, y, z] = StretchingField[x, y, z];
                        field.Compression[x, y, z] = CompressionField[x, y, z];
                    }
                }
            }
        }

        public float[] ComputeHistogram(float[,,] field, int binCount = 50)
        {
            float min = float.MaxValue, max = float.MinValue;
            for (int x = 0; x < _gridX; x++)
                for (int y = 0; y < _gridY; y++)
                    for (int z = 0; z < _gridZ; z++)
                    {
                        min = Mathf.Min(min, field[x, y, z]);
                        max = Mathf.Max(max, field[x, y, z]);
                    }

            float[] histogram = new float[binCount];
            float binWidth = (max - min) / binCount;

            for (int x = 0; x < _gridX; x++)
                for (int y = 0; y < _gridY; y++)
                    for (int z = 0; z < _gridZ; z++)
                    {
                        int bin = Mathf.Clamp((int)((field[x, y, z] - min) / binWidth), 0, binCount - 1);
                        histogram[bin]++;
                    }

            return histogram;
        }
    }
}
