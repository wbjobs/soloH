using System;
using System.Diagnostics;
using System.Threading.Tasks;
using UnityEngine;
using SoleFrictionSim.Data;
using SoleFrictionSim.Geometry;

namespace SoleFrictionSim.Core
{
    public class BEMSolver
    {
        private readonly StlImporter _stlImporter = new StlImporter();
        private readonly PatternGenerator _patternGenerator = new PatternGenerator();

        public async Task<ContactResult> SolveAsync(
            Mesh contactSurface,
            RubberMaterial material,
            GroundSurface ground,
            SimulationParams parameters,
            IProgress<float> progress = null)
        {
            return await Task.Run(() =>
            {
                var stopwatch = Stopwatch.StartNew();
                int n = parameters.bemResolution;

                float[,] heightField;
                if (contactSurface != null)
                {
                    heightField = _stlImporter.ExtractContactHeightField(contactSurface, n);
                }
                else
                {
                    var config = new PatternConfig
                    {
                        soleWidth = 10f,
                        soleLength = 28f,
                        meshResolution = n
                    };
                    heightField = _patternGenerator.GetHeightField(config, n);
                }

                progress?.Report(0.1f);

                float[,] gap = InitializeGap(heightField, n);
                float[,] pressure = new float[n, n];
                float[,] displacement = new float[n, n];

                float effectiveModulus = material.GetEffectiveModulus();
                float cellSize = 0.3f / n;

                float[,] influenceMatrix = PrecomputeInfluenceMatrix(n, cellSize, effectiveModulus);

                progress?.Report(0.2f);

                int iterations = 0;
                float residual = float.MaxValue;
                float targetLoad = parameters.normalLoad;

                float[,] residualVec = new float[n, n];
                float[,] searchDir = new float[n, n];
                float[,] prevResidual = new float[n, n];

                while (iterations < parameters.maxIterations && residual > parameters.tolerance)
                {
                    ComputeDisplacement(pressure, influenceMatrix, displacement, n);

                    float totalLoad = CalculateTotalLoad(pressure, cellSize);
                    float loadScale = totalLoad > 0 ? targetLoad / totalLoad : 1f;

                    for (int i = 0; i < n; i++)
                    {
                        for (int j = 0; j < n; j++)
                        {
                            pressure[i, j] *= loadScale;
                            displacement[i, j] *= loadScale;
                        }
                    }

                    ComputeResidual(gap, displacement, pressure, residualVec, n);
                    residual = CalculateResidualNorm(residualVec, n);

                    if (iterations == 0)
                    {
                        CopyArray(residualVec, searchDir, n);
                    }
                    else
                    {
                        float beta = CalculateBeta(residualVec, prevResidual, n);
                        UpdateSearchDirection(residualVec, searchDir, beta, n);
                    }

                    float alpha = CalculateStepSize(pressure, searchDir, gap, influenceMatrix, n, cellSize, targetLoad);
                    UpdatePressure(pressure, searchDir, alpha, n);

                    CopyArray(residualVec, prevResidual, n);

                    iterations++;

                    if (iterations % 10 == 0)
                    {
                        progress?.Report(0.2f + 0.6f * (float)iterations / parameters.maxIterations);
                    }
                }

                progress?.Report(0.8f);

                float[,] waterFilm = null;
                if (parameters.includeHydrodynamics)
                {
                    waterFilm = ComputeWaterFilmDistribution(pressure, ground, n);
                }

                var result = new ContactResult
                {
                    contactPressure = pressure,
                    waterFilmThickness = waterFilm,
                    iterations = iterations,
                    residualError = residual,
                    computeTime = (float)stopwatch.Elapsed.TotalSeconds
                };

                result.CalculateStatistics();

                progress?.Report(1.0f);

                return result;
            });
        }

        private float[,] InitializeGap(float[,] heightField, int n)
        {
            float[,] gap = new float[n, n];
            float maxHeight = float.MinValue;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    if (heightField[i, j] > maxHeight)
                    {
                        maxHeight = heightField[i, j];
                    }
                }
            }

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    gap[i, j] = maxHeight - heightField[i, j];
                }
            }

            return gap;
        }

        private float[,] PrecomputeInfluenceMatrix(int n, float cellSize, float effectiveModulus)
        {
            int totalSize = n * n;
            float[,] matrix = new float[totalSize, totalSize];

            float factor = 1f / (Mathf.PI * effectiveModulus);

            Parallel.For(0, totalSize, i =>
            {
                int xi = i / n;
                int yi = i % n;

                for (int j = 0; j < totalSize; j++)
                {
                    int xj = j / n;
                    int yj = j % n;

                    float dx = (xi - xj) * cellSize;
                    float dy = (yi - yj) * cellSize;
                    float r = Mathf.Sqrt(dx * dx + dy * dy);

                    if (r < cellSize * 0.5f)
                    {
                        matrix[i, j] = factor * (2f / cellSize) * (Mathf.Log(2f / (1f + Mathf.Sqrt(2f))) + 1f);
                    }
                    else
                    {
                        matrix[i, j] = factor / r;
                    }
                }
            });

            return matrix;
        }

        private void ComputeDisplacement(float[,] pressure, float[,] influenceMatrix, float[,] displacement, int n)
        {
            int totalSize = n * n;

            Parallel.For(0, n, i =>
            {
                for (int j = 0; j < n; j++)
                {
                    int idx = i * n + j;
                    float sum = 0f;

                    for (int k = 0; k < n; k++)
                    {
                        for (int l = 0; l < n; l++)
                        {
                            int jdx = k * n + l;
                            sum += influenceMatrix[idx, jdx] * pressure[k, l];
                        }
                    }

                    displacement[i, j] = sum;
                }
            });
        }

        private float CalculateTotalLoad(float[,] pressure, float cellSize)
        {
            float total = 0f;
            int n = pressure.GetLength(0);

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    total += pressure[i, j] * cellSize * cellSize;
                }
            }

            return total;
        }

        private void ComputeResidual(float[,] gap, float[,] displacement, float[,] pressure, float[,] residual, int n)
        {
            const float epsilon = 1e-8f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float g = gap[i, j] - displacement[i, j];

                    if (pressure[i, j] > epsilon)
                    {
                        residual[i, j] = g;
                    }
                    else if (g > epsilon)
                    {
                        residual[i, j] = -pressure[i, j];
                    }
                    else
                    {
                        residual[i, j] = Mathf.Min(pressure[i, j], g);
                    }
                }
            }
        }

        private float CalculateResidualNorm(float[,] residual, int n)
        {
            float sum = 0f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    sum += residual[i, j] * residual[i, j];
                }
            }

            return Mathf.Sqrt(sum);
        }

        private float CalculateBeta(float[,] residual, float[,] prevResidual, int n)
        {
            float num = 0f;
            float den = 0f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    num += residual[i, j] * (residual[i, j] - prevResidual[i, j]);
                    den += prevResidual[i, j] * prevResidual[i, j];
                }
            }

            return den > 0 ? Mathf.Max(0, num / den) : 0f;
        }

        private void UpdateSearchDirection(float[,] residual, float[,] searchDir, float beta, int n)
        {
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    searchDir[i, j] = residual[i, j] + beta * searchDir[i, j];
                }
            }
        }

        private float CalculateStepSize(float[,] pressure, float[,] searchDir, float[,] gap,
            float[,] influenceMatrix, int n, float cellSize, float targetLoad)
        {
            float alphaMax = float.MaxValue;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    if (searchDir[i, j] < 0)
                    {
                        float a = -pressure[i, j] / searchDir[i, j];
                        if (a > 0 && a < alphaMax)
                        {
                            alphaMax = a;
                        }
                    }
                }
            }

            if (alphaMax == float.MaxValue) alphaMax = 1f;

            float alpha1 = 0f;
            float alpha2 = alphaMax;
            int iterations = 0;

            while (iterations < 20 && alpha2 - alpha1 > 1e-6f)
            {
                float alpha = 0.5f * (alpha1 + alpha2);
                float[,] testPressure = new float[n, n];
                float[,] testDisplacement = new float[n, n];

                for (int i = 0; i < n; i++)
                {
                    for (int j = 0; j < n; j++)
                    {
                        testPressure[i, j] = Mathf.Max(0, pressure[i, j] + alpha * searchDir[i, j]);
                    }
                }

                ComputeDisplacement(testPressure, influenceMatrix, testDisplacement, n);

                float totalLoad = CalculateTotalLoad(testPressure, cellSize);

                if (totalLoad < targetLoad)
                {
                    alpha1 = alpha;
                }
                else
                {
                    alpha2 = alpha;
                }

                iterations++;
            }

            return 0.5f * (alpha1 + alpha2);
        }

        private void UpdatePressure(float[,] pressure, float[,] searchDir, float alpha, int n)
        {
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    pressure[i, j] = Mathf.Max(0, pressure[i, j] + alpha * searchDir[i, j]);
                }
            }
        }

        private void CopyArray(float[,] source, float[,] dest, int n)
        {
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    dest[i, j] = source[i, j];
                }
            }
        }

        private float[,] ComputeWaterFilmDistribution(float[,] pressure, GroundSurface ground, int n)
        {
            float[,] waterFilm = new float[n, n];
            float baseFilm = ground.waterFilmThickness * 1e-6f;

            float maxPressure = 0f;
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    if (pressure[i, j] > maxPressure) maxPressure = pressure[i, j];
                }
            }

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float pNorm = maxPressure > 0 ? pressure[i, j] / maxPressure : 0f;
                    float squeezeFactor = Mathf.Exp(-pNorm * 2f);
                    waterFilm[i, j] = baseFilm * squeezeFactor;
                }
            }

            return waterFilm;
        }

        public float[,] FastFourierTransform(float[,] data, bool inverse = false)
        {
            int n = data.GetLength(0);
            int m = data.GetLength(1);

            System.Numerics.Complex[,] complex = new System.Numerics.Complex[n, m];

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < m; j++)
                {
                    complex[i, j] = new System.Numerics.Complex(data[i, j], 0);
                }
            }

            for (int i = 0; i < n; i++)
            {
                var row = new System.Numerics.Complex[m];
                for (int j = 0; j < m; j++) row[j] = complex[i, j];
                FFT1D(row, inverse);
                for (int j = 0; j < m; j++) complex[i, j] = row[j];
            }

            for (int j = 0; j < m; j++)
            {
                var col = new System.Numerics.Complex[n];
                for (int i = 0; i < n; i++) col[i] = complex[i, j];
                FFT1D(col, inverse);
                for (int i = 0; i < n; i++) complex[i, j] = col[i];
            }

            float[,] result = new float[n, m];
            float scale = inverse ? 1f / (n * m) : 1f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < m; j++)
                {
                    result[i, j] = (float)complex[i, j].Real * scale;
                }
            }

            return result;
        }

        private void FFT1D(System.Numerics.Complex[] data, bool inverse)
        {
            int n = data.Length;
            if (n <= 1) return;

            var even = new System.Numerics.Complex[n / 2];
            var odd = new System.Numerics.Complex[n / 2];

            for (int i = 0; i < n / 2; i++)
            {
                even[i] = data[2 * i];
                odd[i] = data[2 * i + 1];
            }

            FFT1D(even, inverse);
            FFT1D(odd, inverse);

            double angle = (inverse ? 2 : -2) * Math.PI / n;

            for (int i = 0; i < n / 2; i++)
            {
                var t = System.Numerics.Complex.FromPolarCoordinates(1, angle * i) * odd[i];
                data[i] = even[i] + t;
                data[i + n / 2] = even[i] - t;
            }
        }
    }
}
