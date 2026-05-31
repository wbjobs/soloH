using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;
using FlowVisualization.Core;

namespace FlowVisualization.PIV
{
    public enum ReconstructionMethod
    {
        InverseDistance,
        RBF,
        Kriging,
        BiharmonicSpline
    }

    public class PIVVectorFieldReconstructor
    {
        public ReconstructionMethod Method = ReconstructionMethod.InverseDistance;
        public int TargetGridSizeX = 64;
        public int TargetGridSizeY = 64;
        public int TargetGridSizeZ = 1;
        public float SmoothingParameter = 1.0f;
        public int NearestNeighbors = 8;
        public float OutlierThreshold = 3.0f;
        public bool RemoveOutliers = true;
        public bool FillHoles = true;

        private struct WeightedPoint
        {
            public Vector3 Position;
            public Vector3 Velocity;
            public float Weight;
            public float Distance;
        }

        public Vector3Field ReconstructField(PIVData pivData)
        {
            if (pivData == null || pivData.Vectors.Count == 0)
                throw new ArgumentException("Invalid PIV data");

            List<PIVVector> validVectors = new List<PIVVector>(pivData.Vectors.Count);
            
            if (RemoveOutliers)
            {
                validVectors = RemoveOutlierVectors(pivData.Vectors);
            }
            else
            {
                foreach (var v in pivData.Vectors)
                    if (v.IsValid) validVectors.Add(v);
            }

            if (validVectors.Count == 0)
                throw new InvalidOperationException("No valid vectors available for reconstruction");

            int dimX = TargetGridSizeX;
            int dimY = TargetGridSizeY;
            int dimZ = Math.Max(1, TargetGridSizeZ);

            Vector3Field field = new Vector3Field(dimX, dimY, dimZ);
            
            Vector3 minBounds = pivData.MinBounds;
            Vector3 maxBounds = pivData.MaxBounds;
            
            if (dimZ > 1)
            {
                float depth = Mathf.Max((maxBounds.x - minBounds.x), (maxBounds.y - minBounds.y)) * 0.3f;
                minBounds.z = -depth / 2;
                maxBounds.z = depth / 2;
            }

            field.MinBounds = minBounds;
            field.MaxBounds = maxBounds;
            field.CellSize = new Vector3(
                (maxBounds.x - minBounds.x) / (dimX - 1),
                (maxBounds.y - minBounds.y) / (dimY - 1),
                dimZ > 1 ? (maxBounds.z - minBounds.z) / (dimZ - 1) : 1f
            );
            field.TimeStep = pivData.DeltaT;
            field.TimeValue = (float)pivData.Timestamp;

            Vector3[] points = new Vector3[validVectors.Count];
            Vector3[] velocities = new Vector3[validVectors.Count];
            float[] weights = new float[validVectors.Count];

            for (int i = 0; i < validVectors.Count; i++)
            {
                points[i] = validVectors[i].Position;
                velocities[i] = validVectors[i].Velocity;
                weights[i] = validVectors[i].Correlation * validVectors[i].SNR;
            }

            Parallel.For(0, dimZ, z =>
            {
                for (int y = 0; y < dimY; y++)
                {
                    for (int x = 0; x < dimX; x++)
                    {
                        Vector3 pos = field.IndexToWorld(x, y, z);
                        Vector3 vel;

                        switch (Method)
                        {
                            case ReconstructionMethod.RBF:
                                vel = InterpolateRBF(pos, points, velocities, weights);
                                break;
                            case ReconstructionMethod.Kriging:
                                vel = InterpolateKriging(pos, points, velocities);
                                break;
                            case ReconstructionMethod.BiharmonicSpline:
                                vel = InterpolateBiharmonic(pos, points, velocities);
                                break;
                            default:
                                vel = InterpolateIDW(pos, points, velocities, weights);
                                break;
                        }

                        field.Velocity[x, y, z] = vel;
                    }
                }
            });

            field.ComputeDerivedQuantities();

            if (FillHoles)
            {
                FillInvalidRegions(field);
            }

            ComputePressureField(field);

            ComputeLyapunovQuantities(field);

            return field;
        }

        public List<Vector3Field> ReconstructTimeSequence(List<PIVData> timeSeries)
        {
            if (timeSeries == null || timeSeries.Count == 0)
                throw new ArgumentException("Invalid time series data");

            List<Vector3Field> fields = new List<Vector3Field>(timeSeries.Count);

            foreach (var pivData in timeSeries)
            {
                fields.Add(ReconstructField(pivData));
            }

            return fields;
        }

        private List<PIVVector> RemoveOutlierVectors(List<PIVVector> vectors)
        {
            int n = vectors.Count;
            Vector3[] velocities = new Vector3[n];
            for (int i = 0; i < n; i++)
                velocities[i] = vectors[i].Velocity;

            Vector3 mean = Vector3.zero;
            foreach (var v in velocities) mean += v;
            mean /= n;

            Vector3 variance = Vector3.zero;
            foreach (var v in velocities)
            {
                Vector3 d = v - mean;
                variance += new Vector3(d.x * d.x, d.y * d.y, d.z * d.z);
            }
            variance /= n;

            Vector3 std = new Vector3(Mathf.Sqrt(variance.x), Mathf.Sqrt(variance.y), Mathf.Sqrt(variance.z));

            List<PIVVector> valid = new List<PIVVector>(n);
            for (int i = 0; i < n; i++)
            {
                Vector3 dev = velocities[i] - mean;
                float zScore = Mathf.Max(
                    Mathf.Abs(dev.x) / Mathf.Max(std.x, 1e-6f),
                    Mathf.Max(Mathf.Abs(dev.y) / Mathf.Max(std.y, 1e-6f),
                              Mathf.Abs(dev.z) / Mathf.Max(std.z, 1e-6f))
                );

                if (zScore < OutlierThreshold && vectors[i].IsValid)
                {
                    valid.Add(vectors[i]);
                }
            }

            return valid;
        }

        private Vector3 InterpolateIDW(Vector3 pos, Vector3[] points, Vector3[] values, float[] weights)
        {
            float totalWeight = 0;
            Vector3 result = Vector3.zero;
            float power = 2.0f;

            for (int i = 0; i < points.Length; i++)
            {
                float dist = Vector3.Distance(pos, points[i]);
                if (dist < 1e-6f) return values[i];

                float w = weights[i] / Mathf.Pow(dist, power);
                result += values[i] * w;
                totalWeight += w;
            }

            return totalWeight > 0 ? result / totalWeight : Vector3.zero;
        }

        private Vector3 InterpolateRBF(Vector3 pos, Vector3[] points, Vector3[] values, float[] weights)
        {
            float totalWeight = 0;
            Vector3 result = Vector3.zero;
            float eps = 1.0f / (SmoothingParameter * SmoothingParameter);

            for (int i = 0; i < points.Length; i++)
            {
                float dist = Vector3.Distance(pos, points[i]);
                float rbf = Mathf.Exp(-eps * dist * dist);
                float w = weights[i] * rbf;
                
                result += values[i] * w;
                totalWeight += w;
            }

            return totalWeight > 0 ? result / totalWeight : Vector3.zero;
        }

        private Vector3 InterpolateKriging(Vector3 pos, Vector3[] points, Vector3[] values)
        {
            List<WeightedPoint> neighbors = FindNearestNeighbors(pos, points, values, NearestNeighbors);
            
            if (neighbors.Count == 0) return Vector3.zero;
            if (neighbors.Count == 1) return neighbors[0].Velocity;

            int n = neighbors.Count;
            float[,] K = new float[n + 1, n + 1];
            float[] k = new float[n + 1];

            float range = neighbors[neighbors.Count - 1].Distance * 2;
            float nugget = 0.01f;
            float sill = 1.0f;

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float d = Vector3.Distance(neighbors[i].Position, neighbors[j].Position);
                    K[i, j] = GaussianVariogram(d, range, nugget, sill);
                }
                K[i, n] = 1;
                K[n, i] = 1;
            }
            K[n, n] = 0;

            for (int i = 0; i < n; i++)
            {
                float d = Vector3.Distance(pos, neighbors[i].Position);
                k[i] = GaussianVariogram(d, range, nugget, sill);
            }
            k[n] = 1;

            float[] lambda = SolveLinearSystem(K, k);

            Vector3 result = Vector3.zero;
            for (int i = 0; i < n; i++)
            {
                result += neighbors[i].Velocity * lambda[i];
            }

            return result;
        }

        private Vector3 InterpolateBiharmonic(Vector3 pos, Vector3[] points, Vector3[] values)
        {
            List<WeightedPoint> neighbors = FindNearestNeighbors(pos, points, values, Math.Min(15, points.Length));
            
            if (neighbors.Count < 4) return InterpolateIDW(pos, points, values, new float[points.Length]);

            int n = neighbors.Count;
            float[,] A = new float[n + 4, n + 4];
            float[] bx = new float[n + 4];
            float[] by = new float[n + 4];
            float[] bz = new float[n + 4];

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float r = Vector3.Distance(neighbors[i].Position, neighbors[j].Position);
                    A[i, j] = r > 0 ? r * r * Mathf.Log(r) : 0;
                }
                
                A[i, n] = 1;
                A[i, n + 1] = neighbors[i].Position.x;
                A[i, n + 2] = neighbors[i].Position.y;
                A[i, n + 3] = neighbors[i].Position.z;
                
                A[n, i] = 1;
                A[n + 1, i] = neighbors[i].Position.x;
                A[n + 2, i] = neighbors[i].Position.y;
                A[n + 3, i] = neighbors[i].Position.z;

                bx[i] = neighbors[i].Velocity.x;
                by[i] = neighbors[i].Velocity.y;
                bz[i] = neighbors[i].Velocity.z;
            }

            float[] wx = SolveLinearSystem(A, bx);
            float[] wy = SolveLinearSystem(A, by);
            float[] wz = SolveLinearSystem(A, bz);

            float vx = wx[n] + wx[n + 1] * pos.x + wx[n + 2] * pos.y + wx[n + 3] * pos.z;
            float vy = wy[n] + wy[n + 1] * pos.x + wy[n + 2] * pos.y + wy[n + 3] * pos.z;
            float vz = wz[n] + wz[n + 1] * pos.x + wz[n + 2] * pos.y + wz[n + 3] * pos.z;

            for (int i = 0; i < n; i++)
            {
                float r = Vector3.Distance(pos, neighbors[i].Position);
                float phi = r > 0 ? r * r * Mathf.Log(r) : 0;
                vx += wx[i] * phi;
                vy += wy[i] * phi;
                vz += wz[i] * phi;
            }

            return new Vector3(vx, vy, vz);
        }

        private float GaussianVariogram(float h, float range, float nugget, float sill)
        {
            if (h == 0) return nugget;
            return nugget + sill * (1 - Mathf.Exp(-h * h / (range * range)));
        }

        private List<WeightedPoint> FindNearestNeighbors(Vector3 pos, Vector3[] points, Vector3[] values, int k)
        {
            SortedList<float, int> nearest = new SortedList<float, int>();

            for (int i = 0; i < points.Length; i++)
            {
                float dist = Vector3.Distance(pos, points[i]);
                
                if (nearest.Count < k)
                {
                    nearest.Add(dist, i);
                }
                else if (dist < nearest.Keys[nearest.Count - 1])
                {
                    nearest.RemoveAt(nearest.Count - 1);
                    nearest.Add(dist, i);
                }
            }

            List<WeightedPoint> result = new List<WeightedPoint>(nearest.Count);
            for (int i = 0; i < nearest.Count; i++)
            {
                int idx = nearest.Values[i];
                result.Add(new WeightedPoint
                {
                    Position = points[idx],
                    Velocity = values[idx],
                    Distance = nearest.Keys[i],
                    Weight = 1.0f / Mathf.Max(nearest.Keys[i], 1e-6f)
                });
            }

            return result;
        }

        private float[] SolveLinearSystem(float[,] A, float[] b)
        {
            int n = b.Length;
            float[,] augmented = new float[n, n + 1];

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                    augmented[i, j] = A[i, j];
                augmented[i, n] = b[i];
            }

            for (int col = 0; col < n; col++)
            {
                int pivotRow = col;
                float maxVal = Mathf.Abs(augmented[col, col]);
                for (int row = col + 1; row < n; row++)
                {
                    if (Mathf.Abs(augmented[row, col]) > maxVal)
                    {
                        maxVal = Mathf.Abs(augmented[row, col]);
                        pivotRow = row;
                    }
                }

                if (pivotRow != col)
                {
                    for (int j = 0; j <= n; j++)
                    {
                        float temp = augmented[col, j];
                        augmented[col, j] = augmented[pivotRow, j];
                        augmented[pivotRow, j] = temp;
                    }
                }

                float pivot = augmented[col, col];
                if (Mathf.Abs(pivot) < 1e-10f) continue;

                for (int j = col; j <= n; j++)
                    augmented[col, j] /= pivot;

                for (int row = 0; row < n; row++)
                {
                    if (row != col && Mathf.Abs(augmented[row, col]) > 1e-10f)
                    {
                        float factor = augmented[row, col];
                        for (int j = col; j <= n; j++)
                        {
                            augmented[row, j] -= factor * augmented[col, j];
                        }
                    }
                }
            }

            float[] result = new float[n];
            for (int i = 0; i < n; i++)
                result[i] = augmented[i, n];

            return result;
        }

        private void FillInvalidRegions(Vector3Field field)
        {
            int dimX = field.DimX;
            int dimY = field.DimY;
            int dimZ = field.DimZ;

            float[,] validMask = new float[dimX, dimY];
            
            for (int z = 0; z < dimZ; z++)
            {
                for (int y = 0; y < dimY; y++)
                {
                    for (int x = 0; x < dimX; x++)
                    {
                        validMask[x, y] = float.IsNaN(field.Velocity[x, y, z].x) || 
                                         field.Velocity[x, y, z].sqrMagnitude > 1e10 ? 0 : 1;
                    }
                }

                for (int pass = 0; pass < 5; pass++)
                {
                    for (int y = 1; y < dimY - 1; y++)
                    {
                        for (int x = 1; x < dimX - 1; x++)
                        {
                            if (validMask[x, y] == 0)
                            {
                                Vector3 sumVel = Vector3.zero;
                                int count = 0;

                                for (int dy = -1; dy <= 1; dy++)
                                {
                                    for (int dx = -1; dx <= 1; dx++)
                                    {
                                        if (validMask[x + dx, y + dy] > 0)
                                        {
                                            sumVel += field.Velocity[x + dx, y + dy, z];
                                            count++;
                                        }
                                    }
                                }

                                if (count > 0)
                                {
                                    field.Velocity[x, y, z] = sumVel / count;
                                    validMask[x, y] = 0.5f;
                                }
                            }
                        }
                    }
                }
            }
        }

        private void ComputePressureField(Vector3Field field)
        {
            int dimX = field.DimX;
            int dimY = field.DimY;
            int dimZ = field.DimZ;
            float dx = field.CellSize.x;
            float dy = field.CellSize.y;
            float dz = field.CellSize.z;

            float[,] vorticity2D = new float[dimX, dimY];

            for (int z = 0; z < dimZ; z++)
            {
                for (int y = 1; y < dimY - 1; y++)
                {
                    for (int x = 1; x < dimX - 1; x++)
                    {
                        float dudy = (field.Velocity[x, y + 1, z].y - field.Velocity[x, y - 1, z].y) / (2 * dy);
                        float dvdx = (field.Velocity[x + 1, y, z].x - field.Velocity[x - 1, y, z].x) / (2 * dx);
                        vorticity2D[x, y] = dvdx - dudy;
                    }
                }
            }

            float[,] rhs = new float[dimX, dimY];
            
            for (int y = 1; y < dimY - 1; y++)
            {
                for (int x = 1; x < dimX - 1; x++)
                {
                    float dudx = (field.Velocity[x + 1, y, 0].x - field.Velocity[x - 1, y, 0].x) / (2 * dx);
                    float dudy = (field.Velocity[x, y + 1, 0].x - field.Velocity[x, y - 1, 0].x) / (2 * dy);
                    float dvdx = (field.Velocity[x + 1, y, 0].y - field.Velocity[x - 1, y, 0].y) / (2 * dx);
                    float dvdy = (field.Velocity[x, y + 1, 0].y - field.Velocity[x, y - 1, 0].y) / (2 * dy);

                    rhs[x, y] = -2 * (dudx * dvdy - dudy * dvdx);
                }
            }

            float[,] pressure = SolvePoisson(rhs, dx, dy);

            for (int z = 0; z < dimZ; z++)
            {
                for (int y = 0; y < dimY; y++)
                {
                    for (int x = 0; x < dimX; x++)
                    {
                        field.Pressure[x, y, z] = pressure[x, y];
                    }
                }
            }
        }

        private float[,] SolvePoisson(float[,] rhs, float dx, float dy)
        {
            int nx = rhs.GetLength(0);
            int ny = rhs.GetLength(1);
            float[,] solution = new float[nx, ny];
            float[,] newSol = new float[nx, ny];

            float dx2 = dx * dx;
            float dy2 = dy * dy;
            float diag = -2 * (1 / dx2 + 1 / dy2);

            for (int iter = 0; iter < 1000; iter++)
            {
                float maxError = 0;

                for (int y = 1; y < ny - 1; y++)
                {
                    for (int x = 1; x < nx - 1; x++)
                    {
                        float laplacian =
                            (solution[x + 1, y] - 2 * solution[x, y] + solution[x - 1, y]) / dx2 +
                            (solution[x, y + 1] - 2 * solution[x, y] + solution[x, y - 1]) / dy2;

                        float residual = rhs[x, y] - laplacian;
                        newSol[x, y] = solution[x, y] + residual / diag * 0.5f;
                        maxError = Mathf.Max(maxError, Mathf.Abs(residual));
                    }
                }

                for (int y = 0; y < ny; y++)
                {
                    for (int x = 0; x < nx; x++)
                    {
                        solution[x, y] = newSol[x, y];
                    }
                }

                for (int x = 0; x < nx; x++)
                {
                    solution[x, 0] = solution[x, 1];
                    solution[x, ny - 1] = solution[x, ny - 2];
                }
                for (int y = 0; y < ny; y++)
                {
                    solution[0, y] = solution[1, y];
                    solution[nx - 1, y] = solution[nx - 2, y];
                }

                if (maxError < 1e-6f) break;
            }

            return solution;
        }

        private void ComputeLyapunovQuantities(Vector3Field field)
        {
            int dimX = field.DimX;
            int dimY = field.DimY;
            int dimZ = field.DimZ;
            float dx = field.CellSize.x;
            float dy = field.CellSize.y;
            float dz = field.CellSize.z;

            Parallel.For(0, dimZ, z =>
            {
                for (int y = 1; y < dimY - 1; y++)
                {
                    for (int x = 1; x < dimX - 1; x++)
                    {
                        Vector3 v = field.Velocity[x, y, z];
                        Vector3 v_xp = field.Velocity[Math.Min(x + 1, dimX - 1), y, z];
                        Vector3 v_xm = field.Velocity[Math.Max(x - 1, 0), y, z];
                        Vector3 v_yp = field.Velocity[x, Math.Min(y + 1, dimY - 1), z];
                        Vector3 v_ym = field.Velocity[x, Math.Max(y - 1, 0), z];

                        float dudx = (v_xp.x - v_xm.x) / (2 * dx);
                        float dudy = (v_yp.x - v_ym.x) / (2 * dy);
                        float dvdx = (v_xp.y - v_xm.y) / (2 * dx);
                        float dvdy = (v_yp.y - v_ym.y) / (2 * dy);

                        float[,] S = new float[2, 2];
                        S[0, 0] = dudx;
                        S[0, 1] = 0.5f * (dudy + dvdx);
                        S[1, 0] = 0.5f * (dudy + dvdx);
                        S[1, 1] = dvdy;

                        float trace = S[0, 0] + S[1, 1];
                        float det = S[0, 0] * S[1, 1] - S[0, 1] * S[1, 0];
                        float sqrtDisc = Mathf.Sqrt(Mathf.Max(trace * trace / 4 - det, 0));

                        float lambda1 = trace / 2 + sqrtDisc;
                        float lambda2 = trace / 2 - sqrtDisc;

                        float maxStretch = Mathf.Max(lambda1, lambda2);
                        float maxCompress = Mathf.Min(lambda1, lambda2);

                        field.Stretching[x, y, z] = Mathf.Max(maxStretch, 0);
                        field.Compression[x, y, z] = Mathf.Max(-maxCompress, 0);
                        field.LyapunovExponent[x, y, z] = maxStretch;
                        field.FTLE[x, y, z] = maxStretch;
                    }
                }
            });
        }
    }
}
