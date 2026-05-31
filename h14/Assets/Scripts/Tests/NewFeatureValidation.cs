using System;
using System.Collections.Generic;
using System.Diagnostics;
using UnityEngine;
using FlowVisualization.Core;
using FlowVisualization.Data;
using FlowVisualization.Particles;
using FlowVisualization.Analysis;
using FlowVisualization.Compute;
using FlowVisualization.PIV;

namespace FlowVisualization.Tests
{
    public class NewFeatureValidation : MonoBehaviour
    {
        public bool RunTestsOnStart = false;
        public int TestGridSize = 16;
        public int TestParticleCount = 1000;
        public int PIVVectorCount = 1000;

        private TimeVaryingField _testField;
        private LyapunovCalculator _lyapunovCalculator;
        private GPUParticleSystem _gpuSystem;
        private PIVReader _pivReader;
        private PIVCrossCorrelation _pivCorrelation;
        private PIVVectorFieldReconstructor _pivReconstructor;

        private struct TestResult
        {
            public string TestName;
            public bool Passed;
            public string Message;
            public double DurationMs;
        }

        private List<TestResult> _results = new List<TestResult>();

        private void Start()
        {
            if (RunTestsOnStart)
            {
                RunAllTests();
            }
        }

        public void RunAllTests()
        {
            UnityEngine.Debug.Log("========== NEW FEATURE VALIDATION TESTS ==========");
            _results.Clear();

            SetupTestEnvironment();

            RunTest("Lyapunov Calculator Initialization", TestLyapunovInitialization);
            RunTest("FTLE Forward Computation", TestFTLEForward);
            RunTest("FTLE Backward Computation", TestFTLEBackward);
            RunTest("LCS Attracting/Repelling Extraction", TestLCSExtraction);
            RunTest("Stretching/Compression Field", TestStretchingCompression);
            
            RunTest("GPU Compute Shader Support", TestGPUSupport);
            RunTest("GPU Particle Integration", TestGPUParticleIntegration);
            RunTest("GPU FTLE Computation", TestGPUFTLE);
            RunTest("GPU Batch Processing", TestGPUBatchProcessing);
            
            RunTest("PIV Reader Format Detection", TestPIVFormatDetection);
            RunTest("PIV Synthetic Data Generation", TestPIVSyntheticData);
            RunTest("PIV Cross Correlation", TestPIVCrossCorrelation);
            RunTest("PIV Field Reconstruction IDW", TestPIVReconstructionIDW);
            RunTest("PIV Field Reconstruction RBF", TestPIVReconstructionRBF);
            RunTest("PIV Outlier Removal", TestPIVOutlierRemoval);
            RunTest("PIV Pressure Reconstruction", TestPIVPressure);

            PrintTestSummary();
        }

        private void SetupTestEnvironment()
        {
            Stopwatch sw = Stopwatch.StartNew();
            
            SyntheticFieldGenerator generator = new SyntheticFieldGenerator();
            List<Vector3Field> fields = new List<Vector3Field>();
            
            for (int t = 0; t < 10; t++)
            {
                fields.Add(generator.GenerateDoubleGyre(TestGridSize, TestGridSize, TestGridSize, t * 0.1f, 1.0f));
            }
            
            _testField = new TimeVaryingField(fields, 0.1f);
            _lyapunovCalculator = new LyapunovCalculator(_testField, new AdaptiveRK45());
            _gpuSystem = GetComponent<GPUParticleSystem>();
            _pivReader = new PIVReader();
            _pivCorrelation = new PIVCrossCorrelation();
            _pivReconstructor = new PIVVectorFieldReconstructor();

            sw.Stop();
            UnityEngine.Debug.Log($"Test environment setup completed in {sw.Elapsed.TotalMilliseconds:F2}ms");
        }

        private void RunTest(string name, Func<bool> test)
        {
            Stopwatch sw = Stopwatch.StartNew();
            bool passed = false;
            string message = "";

            try
            {
                passed = test();
                message = passed ? "Test passed successfully" : "Test failed";
            }
            catch (Exception e)
            {
                passed = false;
                message = $"Exception: {e.Message}";
                UnityEngine.Debug.LogError($"Test '{name}' exception: {e}");
            }

            sw.Stop();

            _results.Add(new TestResult
            {
                TestName = name,
                Passed = passed,
                Message = message,
                DurationMs = sw.Elapsed.TotalMilliseconds
            });

            UnityEngine.Debug.Log($"{(passed ? "[PASS]" : "[FAIL]")} {name}: {message} ({sw.Elapsed.TotalMilliseconds:F2}ms)");
        }

        private bool TestLyapunovInitialization()
        {
            if (_lyapunovCalculator == null) return false;
            if (_lyapunovCalculator.Field == null) return false;
            
            _lyapunovCalculator.PerturbationSize = 1e-3f;
            _lyapunovCalculator.IntegrationTime = 1.0f;
            
            return _lyapunovCalculator.FTLEForward != null &&
                   _lyapunovCalculator.FTLEBackward != null &&
                   _lyapunovCalculator.LCSAttracting != null &&
                   _lyapunovCalculator.LCSRepelling != null;
        }

        private bool TestFTLEForward()
        {
            _lyapunovCalculator.ComputeFTLE(0.0f, IntegrationDirection.Forward, _lyapunovCalculator.FTLEForward);
            
            float[,,] ftle = _lyapunovCalculator.FTLEForward;
            if (ftle == null) return false;

            int nonZeroCount = 0;
            float maxVal = 0;
            float minVal = float.MaxValue;
            
            for (int z = 0; z < TestGridSize; z++)
                for (int y = 0; y < TestGridSize; y++)
                    for (int x = 0; x < TestGridSize; x++)
                    {
                        float val = ftle[x, y, z];
                        if (val > 0) nonZeroCount++;
                        maxVal = Mathf.Max(maxVal, val);
                        minVal = Mathf.Min(minVal, val);
                        if (float.IsNaN(val) || float.IsInfinity(val)) return false;
                    }

            UnityEngine.Debug.Log($"  FTLE Forward: {nonZeroCount} non-zero values, range=[{minVal:E2}, {maxVal:E2}]");
            return nonZeroCount > TestGridSize * TestGridSize * TestGridSize * 0.5;
        }

        private bool TestFTLEBackward()
        {
            _lyapunovCalculator.ComputeFTLE(0.0f, IntegrationDirection.Backward, _lyapunovCalculator.FTLEBackward);
            
            float[,,] ftle = _lyapunovCalculator.FTLEBackward;
            if (ftle == null) return false;

            int nonZeroCount = 0;
            for (int z = 0; z < TestGridSize; z++)
                for (int y = 0; y < TestGridSize; y++)
                    for (int x = 0; x < TestGridSize; x++)
                    {
                        float val = ftle[x, y, z];
                        if (val > 0) nonZeroCount++;
                        if (float.IsNaN(val) || float.IsInfinity(val)) return false;
                    }

            return nonZeroCount > TestGridSize * TestGridSize * TestGridSize * 0.5;
        }

        private bool TestLCSExtraction()
        {
            _lyapunovCalculator.ComputeLCS();
            
            float[,,] attracting = _lyapunovCalculator.LCSAttracting;
            float[,,] repelling = _lyapunovCalculator.LCSRepelling;
            
            if (attracting == null || repelling == null) return false;

            int attractCount = 0, repelCount = 0;
            for (int z = 0; z < TestGridSize; z++)
                for (int y = 0; y < TestGridSize; y++)
                    for (int x = 0; x < TestGridSize; x++)
                    {
                        if (attracting[x, y, z] > 0.1f) attractCount++;
                        if (repelling[x, y, z] > 0.1f) repelCount++;
                    }

            UnityEngine.Debug.Log($"  LCS: {attractCount} attracting points, {repelCount} repelling points");
            return attractCount > 0 && repelCount > 0;
        }

        private bool TestStretchingCompression()
        {
            _lyapunovCalculator.ComputeStretchingCompression(0.0f);
            
            float[,,] stretching = _lyapunovCalculator.StretchingField;
            float[,,] compression = _lyapunovCalculator.CompressionField;
            
            if (stretching == null || compression == null) return false;

            for (int z = 0; z < TestGridSize; z++)
                for (int y = 0; y < TestGridSize; y++)
                    for (int x = 0; x < TestGridSize; x++)
                    {
                        if (stretching[x, y, z] < 0 || compression[x, y, z] < 0) return false;
                        if (float.IsNaN(stretching[x, y, z]) || float.IsNaN(compression[x, y, z])) return false;
                    }

            return true;
        }

        private bool TestGPUSupport()
        {
            return SystemInfo.supportsComputeShaders;
        }

        private bool TestGPUParticleIntegration()
        {
            if (_gpuSystem == null || !_gpuSystem.IsInitialized)
            {
                GameObject gpuObj = new GameObject("GPUSystem");
                _gpuSystem = gpuObj.AddComponent<GPUParticleSystem>();
                _gpuSystem.ParticleIntegrationShader = Resources.Load<ComputeShader>("ParticleIntegration");
                _gpuSystem.MaxParticles = TestParticleCount;
                _gpuSystem.Initialize(_testField);
            }

            if (!_gpuSystem.IsInitialized) return false;

            Stopwatch sw = Stopwatch.StartNew();
            
            for (int i = 0; i < TestParticleCount; i++)
            {
                _gpuSystem.SpawnParticle(
                    new Vector3(
                        UnityEngine.Random.Range(0f, 1f),
                        UnityEngine.Random.Range(0f, 1f),
                        UnityEngine.Random.Range(0f, 1f)
                    ),
                    0.0f
                );
            }

            _gpuSystem.UpdateParticles(0.1f, 0.0f, IntegrationDirection.Forward, ScalarFieldType.VelocityMagnitude);
            
            sw.Stop();
            
            int active = _gpuSystem.ActiveParticles;
            double particlesPerSec = TestParticleCount / (sw.Elapsed.TotalMilliseconds / 1000.0);
            
            UnityEngine.Debug.Log($"  GPU: {TestParticleCount} particles in {sw.Elapsed.TotalMilliseconds:F2}ms = {particlesPerSec:F0} particles/sec");

            return active > 0 && sw.Elapsed.TotalMilliseconds < 1000;
        }

        private bool TestGPUFTLE()
        {
            if (_gpuSystem == null || !_gpuSystem.IsInitialized) return false;

            Stopwatch sw = Stopwatch.StartNew();
            float[] ftle = _gpuSystem.ComputeFTLEField(0.0f, 1.0f, IntegrationDirection.Forward, 1e-3f);
            sw.Stop();

            if (ftle == null || ftle.Length == 0) return false;

            int nonZero = 0;
            foreach (float f in ftle)
                if (f > 0) nonZero++;

            UnityEngine.Debug.Log($"  GPU FTLE: {ftle.Length} points in {sw.Elapsed.TotalMilliseconds:F2}ms, {nonZero} non-zero");
            
            return nonZero > ftle.Length * 0.1;
        }

        private bool TestGPUBatchProcessing()
        {
            if (_gpuSystem == null || !_gpuSystem.IsInitialized) return false;

            _gpuSystem.ResetParticles();
            _gpuSystem.UseBatchIntegration = false;
            
            Stopwatch sw1 = Stopwatch.StartNew();
            for (int i = 0; i < TestParticleCount; i++)
                _gpuSystem.SpawnParticle(new Vector3(0.5f, 0.5f, 0.5f), 0.0f);
            _gpuSystem.UpdateParticles(0.1f, 0.0f, IntegrationDirection.Forward, ScalarFieldType.VelocityMagnitude);
            sw1.Stop();

            _gpuSystem.ResetParticles();
            _gpuSystem.UseBatchIntegration = true;
            
            Stopwatch sw2 = Stopwatch.StartNew();
            for (int i = 0; i < TestParticleCount; i++)
                _gpuSystem.SpawnParticle(new Vector3(0.5f, 0.5f, 0.5f), 0.0f);
            _gpuSystem.UpdateParticles(0.1f, 0.0f, IntegrationDirection.Forward, ScalarFieldType.VelocityMagnitude);
            sw2.Stop();

            double improvement = sw1.Elapsed.TotalMilliseconds / Math.Max(sw2.Elapsed.TotalMilliseconds, 1);
            UnityEngine.Debug.Log($"  Batch: normal={sw1.Elapsed.TotalMilliseconds:F2}ms, batch={sw2.Elapsed.TotalMilliseconds:F2}ms, {improvement:F2}x faster");

            return sw2.Elapsed.TotalMilliseconds <= sw1.Elapsed.TotalMilliseconds * 1.1;
        }

        private bool TestPIVFormatDetection()
        {
            PIVFormat format1 = _pivReader.DetectFormat("test.vc7");
            PIVFormat format2 = _pivReader.DetectFormat("test.dat");
            PIVFormat format3 = _pivReader.DetectFormat("test.csv");
            PIVFormat format4 = _pivReader.DetectFormat("test.tec");
            PIVFormat format5 = _pivReader.DetectFormat("test.tif");

            return format1 == PIVFormat.VC7 &&
                   format2 == PIVFormat.DAT &&
                   format3 == PIVFormat.CSV &&
                   format4 == PIVFormat.TECPLOT &&
                   format5 == PIVFormat.ImagePair;
        }

        private PIVData GenerateSyntheticPIVData(int count)
        {
            PIVData data = new PIVData
            {
                Format = PIVFormat.DAT,
                DeltaT = 0.01f,
                PixelSize = 1e-5f,
                Magnification = 1.0f,
                GridSizeX = (int)Math.Sqrt(count),
                GridSizeY = (int)Math.Sqrt(count),
                GridSizeZ = 1,
                MinBounds = Vector3.zero,
                MaxBounds = Vector3.one
            };

            for (int y = 0; y < data.GridSizeY; y++)
            {
                for (int x = 0; x < data.GridSizeX; x++)
                {
                    float px = (float)x / data.GridSizeX;
                    float py = (float)y / data.GridSizeY;
                    
                    float vx = Mathf.Sin(px * Mathf.PI * 2) * Mathf.Cos(py * Mathf.PI * 2);
                    float vy = -Mathf.Cos(px * Mathf.PI * 2) * Mathf.Sin(py * Mathf.PI * 2);
                    
                    data.Vectors.Add(new PIVVector
                    {
                        Position = new Vector3(px, py, 0),
                        Velocity = new Vector3(vx, vy, 0),
                        Correlation = 0.9f,
                        SNR = 3.0f,
                        IsValid = true
                    });
                }
            }

            return data;
        }

        private bool TestPIVSyntheticData()
        {
            PIVData data = GenerateSyntheticPIVData(PIVVectorCount);
            
            if (data.Vectors.Count != PIVVectorCount) return false;
            if (data.GridSizeX * data.GridSizeY != PIVVectorCount) return false;

            float maxV = 0;
            foreach (var v in data.Vectors)
            {
                maxV = Mathf.Max(maxV, v.Velocity.magnitude);
                if (float.IsNaN(v.Velocity.x) || float.IsNaN(v.Velocity.y)) return false;
            }

            return maxV > 0 && maxV < 2.0f;
        }

        private bool TestPIVCrossCorrelation()
        {
            int size = 64;
            Texture2D img1 = new Texture2D(size, size);
            Texture2D img2 = new Texture2D(size, size);

            Color[] pixels1 = new Color[size * size];
            Color[] pixels2 = new Color[size * size];

            float displacement = 3.0f;
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float v1 = Mathf.Sin(x * 0.3f) * Mathf.Cos(y * 0.2f) * 0.5f + 0.5f;
                    float v2 = Mathf.Sin((x + displacement) * 0.3f) * Mathf.Cos(y * 0.2f) * 0.5f + 0.5f;
                    
                    pixels1[y * size + x] = new Color(v1, v1, v1);
                    pixels2[y * size + x] = new Color(v2, v2, v2);
                }
            }

            img1.SetPixels(pixels1);
            img2.SetPixels(pixels2);
            img1.Apply();
            img2.Apply();

            _pivCorrelation.InterrogationWindowSize = 16;
            _pivCorrelation.SearchWindowSize = 32;
            _pivCorrelation.NumPasses = 1;

            Stopwatch sw = Stopwatch.StartNew();
            PIVData data = _pivCorrelation.ProcessImagePair(img1, img2, 0.01f, 1e-5f);
            sw.Stop();

            UnityEngine.Debug.Log($"  PIV Correlation: {data.Vectors.Count} vectors in {sw.Elapsed.TotalMilliseconds:F2}ms");

            float avgDisp = 0;
            foreach (var v in data.Vectors)
                avgDisp += Mathf.Abs(v.Velocity.x * 0.01f / 1e-5f - displacement);
            
            avgDisp /= data.Vectors.Count;

            Destroy(img1);
            Destroy(img2);

            return data.Vectors.Count > 0 && avgDisp < 2.0f;
        }

        private bool TestPIVReconstructionIDW()
        {
            PIVData pivData = GenerateSyntheticPIVData(PIVVectorCount);
            
            _pivReconstructor.Method = ReconstructionMethod.InverseDistance;
            _pivReconstructor.TargetGridSizeX = TestGridSize;
            _pivReconstructor.TargetGridSizeY = TestGridSize;
            _pivReconstructor.TargetGridSizeZ = 1;

            Stopwatch sw = Stopwatch.StartNew();
            Vector3Field field = _pivReconstructor.ReconstructField(pivData);
            sw.Stop();

            UnityEngine.Debug.Log($"  PIV IDW Reconstruction: {sw.Elapsed.TotalMilliseconds:F2}ms");

            return ValidateReconstructedField(field, TestGridSize, TestGridSize, 1);
        }

        private bool TestPIVReconstructionRBF()
        {
            PIVData pivData = GenerateSyntheticPIVData(Math.Min(400, PIVVectorCount));
            
            _pivReconstructor.Method = ReconstructionMethod.RBF;
            _pivReconstructor.SmoothingParameter = 0.5f;
            _pivReconstructor.TargetGridSizeX = TestGridSize;
            _pivReconstructor.TargetGridSizeY = TestGridSize;
            _pivReconstructor.TargetGridSizeZ = 1;

            Stopwatch sw = Stopwatch.StartNew();
            Vector3Field field = _pivReconstructor.ReconstructField(pivData);
            sw.Stop();

            UnityEngine.Debug.Log($"  PIV RBF Reconstruction: {sw.Elapsed.TotalMilliseconds:F2}ms");

            return ValidateReconstructedField(field, TestGridSize, TestGridSize, 1);
        }

        private bool TestPIVOutlierRemoval()
        {
            PIVData pivData = GenerateSyntheticPIVData(PIVVectorCount);
            
            for (int i = 0; i < 100; i++)
            {
                int idx = UnityEngine.Random.Range(0, pivData.Vectors.Count);
                PIVVector v = pivData.Vectors[idx];
                v.Velocity = new Vector3(1000f, 1000f, 0);
                pivData.Vectors[idx] = v;
            }

            _pivReconstructor.RemoveOutliers = true;
            _pivReconstructor.OutlierThreshold = 3.0f;
            
            Vector3Field field = _pivReconstructor.ReconstructField(pivData);

            float maxV = 0;
            for (int z = 0; z < field.DimZ; z++)
                for (int y = 0; y < field.DimY; y++)
                    for (int x = 0; x < field.DimX; x++)
                        maxV = Mathf.Max(maxV, field.Velocity[x, y, z].magnitude);

            return maxV < 100f;
        }

        private bool TestPIVPressure()
        {
            PIVData pivData = GenerateSyntheticPIVData(PIVVectorCount);
            Vector3Field field = _pivReconstructor.ReconstructField(pivData);

            if (field.Pressure == null) return false;

            float meanP = 0;
            int count = 0;
            for (int z = 0; z < field.DimZ; z++)
                for (int y = 0; y < field.DimY; y++)
                    for (int x = 0; x < field.DimX; x++)
                    {
                        float p = field.Pressure[x, y, z];
                        if (float.IsNaN(p) || float.IsInfinity(p)) return false;
                        meanP += p;
                        count++;
                    }

            meanP /= count;
            return !float.IsNaN(meanP);
        }

        private bool ValidateReconstructedField(Vector3Field field, int dimX, int dimY, int dimZ)
        {
            if (field == null) return false;
            if (field.DimX != dimX || field.DimY != dimY || field.DimZ != dimZ) return false;
            if (field.Velocity == null) return false;

            int validCount = 0;
            for (int z = 0; z < dimZ; z++)
                for (int y = 0; y < dimY; y++)
                    for (int x = 0; x < dimX; x++)
                    {
                        Vector3 v = field.Velocity[x, y, z];
                        if (!float.IsNaN(v.x) && !float.IsNaN(v.y) && !float.IsNaN(v.z) &&
                            !float.IsInfinity(v.x) && !float.IsInfinity(v.y) && !float.IsInfinity(v.z))
                            validCount++;
                    }

            return validCount == dimX * dimY * dimZ;
        }

        private void PrintTestSummary()
        {
            int passed = 0, failed = 0;
            double totalTime = 0;

            UnityEngine.Debug.Log("\n========== TEST SUMMARY ==========");
            foreach (var result in _results)
            {
                if (result.Passed) passed++;
                else failed++;
                totalTime += result.DurationMs;
            }

            UnityEngine.Debug.Log($"Passed: {passed}/{_results.Count}");
            UnityEngine.Debug.Log($"Failed: {failed}/{_results.Count}");
            UnityEngine.Debug.Log($"Total time: {totalTime:F2}ms");
            UnityEngine.Debug.Log($"Success rate: {(100.0 * passed / _results.Count):F1}%");
            UnityEngine.Debug.Log("==================================\n");
        }
    }
}
