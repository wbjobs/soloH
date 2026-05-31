using UnityEngine;
using FlowVisualization.Core;
using FlowVisualization.Data;
using FlowVisualization.Particles;
using FlowVisualization.Integration;
using System.Diagnostics;

namespace FlowVisualization.Tests
{
    public class BugFixValidation : MonoBehaviour
    {
        [Header("Test Settings")]
        public bool RunTestsOnStart = true;
        public bool StressTestMemory = true;
        public int StressTestIterations = 1000;
        public int ParticlesPerIteration = 100;

        [Header("Results")]
        public bool BoundaryIndexTestPassed;
        public bool StreaklineStriplineTestPassed;
        public bool MemoryFragmentationTestPassed;
        public string DetailedResults;

        private TimeVaryingField _testField;
        private ParticlePool _testPool;

        private void Start()
        {
            if (RunTestsOnStart)
            {
                RunAllTests();
            }
        }

        public void RunAllTests()
        {
            Stopwatch stopwatch = new Stopwatch();
            stopwatch.Start();

            DetailedResults = "=== Bug Fix Validation Results ===\n\n";

            GenerateTestField();

            DetailedResults += "Test 1: Time Varying Field Boundary Index\n";
            BoundaryIndexTestPassed = TestBoundaryIndex();
            DetailedResults += $"  Result: {(BoundaryIndexTestPassed ? "PASS ✓" : "FAIL ✗")}\n\n";

            DetailedResults += "Test 2: Streakline vs Stripline Distinction\n";
            StreaklineStriplineTestPassed = TestStreaklineStripline();
            DetailedResults += $"  Result: {(StreaklineStriplineTestPassed ? "PASS ✓" : "FAIL ✗")}\n\n";

            if (StressTestMemory)
            {
                DetailedResults += "Test 3: Memory Fragmentation Prevention\n";
                MemoryFragmentationTestPassed = TestMemoryFragmentation();
                DetailedResults += $"  Result: {(MemoryFragmentationTestPassed ? "PASS ✓" : "FAIL ✗")}\n\n";
            }

            stopwatch.Stop();
            DetailedResults += $"Total test time: {stopwatch.ElapsedMilliseconds}ms\n";
            DetailedResults += $"All tests passed: {(AllTestsPassed() ? "YES ✓" : "NO ✗")}";

            UnityEngine.Debug.Log(DetailedResults);
        }

        private void GenerateTestField()
        {
            SyntheticFieldGenerator generator = new SyntheticFieldGenerator(
                dimX: 16,
                dimY: 16,
                dimZ: 16,
                timeSteps: 128,
                timeStepDuration: 0.05f
            );
            _testField = generator.Generate();
            _testPool = new ParticlePool(1000, 100000, 256);
        }

        public bool TestBoundaryIndex()
        {
            bool passed = true;

            try
            {
                float minTime = _testField.MinTime;
                float maxTime = _testField.MaxTime;
                float step = (maxTime - minTime) / 10f;

                UnityEngine.Debug.Log($"Testing time range: [{minTime}, {maxTime}] with step {step}");

                for (float t = minTime - 1.0f; t <= maxTime + 1.0f; t += step * 0.1f)
                {
                    Vector3Field field = _testField.GetFieldAtTime(t);
                    
                    if (field.DimX == 0 || field.DimY == 0 || field.DimZ == 0)
                    {
                        UnityEngine.Debug.LogError($"Field has zero dimensions at time {t}");
                        passed = false;
                    }

                    Vector3 testPos = new Vector3(0.5f, 0.5f, 0.5f);
                    Vector3 vel = _testField.GetVelocityAtTime(testPos, t, IntegrationDirection.Forward);
                    
                    if (float.IsNaN(vel.x) || float.IsNaN(vel.y) || float.IsNaN(vel.z))
                    {
                        UnityEngine.Debug.LogError($"NaN velocity at time {t}");
                        passed = false;
                    }
                }

                for (int i = 0; i < _testField.TimeStepCount; i++)
                {
                    float exactTime = _testField[i].TimeValue;
                    Vector3Field field = _testField.GetFieldAtTime(exactTime);
                    if (field == null || field.Velocity == null)
                    {
                        UnityEngine.Debug.LogError($"Null field at exact time step {i}");
                        passed = false;
                    }
                }

                Vector3Field singleStep = new Vector3Field(8, 8, 8);
                TimeVaryingField singleStepField = new TimeVaryingField(1);
                singleStepField.AddTimeStep(singleStep);
                
                Vector3Field result = singleStepField.GetFieldAtTime(0f);
                if (result.DimX != 8)
                {
                    UnityEngine.Debug.LogError("Single time step field failed");
                    passed = false;
                }
            }
            catch (System.IndexOutOfRangeException e)
            {
                UnityEngine.Debug.LogError($"Index out of range: {e.Message}");
                passed = false;
            }
            catch (System.Exception e)
            {
                UnityEngine.Debug.LogError($"Unexpected exception: {e.Message}");
                passed = false;
            }

            return passed;
        }

        public bool TestStreaklineStripline()
        {
            bool passed = true;

            try
            {
                Vector3 seedPos = new Vector3(0.5f, 0.5f, 0.5f);

                SeedPoint streakline = new SeedPoint(
                    0,
                    seedPos,
                    LineType.Streakline,
                    _testField,
                    _testPool,
                    maxParticlesPerSeed: 50,
                    releaseInterval: 0.1f
                );

                SeedPoint stripline = new SeedPoint(
                    1,
                    seedPos,
                    LineType.Stripline,
                    _testField,
                    _testPool,
                    maxParticlesPerSeed: 50
                );

                float simTime = 0f;
                float dt = 0.1f;
                for (int i = 0; i < 50; i++)
                {
                    streakline.Update(simTime, dt, IntegrationDirection.Forward);
                    stripline.Update(simTime, dt, IntegrationDirection.Forward);
                    simTime += dt;
                }

                var streakTrails = streakline.GetAllLineTrails();
                var stripTrails = stripline.GetAllLineTrails();

                DetailedResults += $"  Streakline trails: {streakTrails.Count} (expected ~1)\n";
                DetailedResults += $"  Stripline trails: {stripTrails.Count} (expected ~50)\n";

                if (streakTrails.Count > 5)
                {
                    UnityEngine.Debug.LogError($"Streakline has too many trails: {streakTrails.Count}, should be ~1");
                    passed = false;
                }

                if (stripTrails.Count < 10)
                {
                    UnityEngine.Debug.LogError($"Stripline has too few trails: {stripTrails.Count}, should be ~50");
                    passed = false;
                }

                if (stripTrails.Count > 0 && stripTrails[0].Count < 2)
                {
                    UnityEngine.Debug.LogError("Stripline trails too short, should have multiple points per trail");
                    passed = false;
                }

                if (streakTrails.Count > 0)
                {
                    int streakPoints = streakTrails[0].Count;
                    DetailedResults += $"  Streakline points: {streakPoints} (one continuous line)\n";
                    
                    if (stripTrails.Count > 0)
                    {
                        int stripPoints = stripTrails[0].Count;
                        DetailedResults += $"  First stripline trail points: {stripPoints} (individual particle path)\n";
                    }
                }

                streakline.Clear();
                stripline.Clear();
            }
            catch (System.Exception e)
            {
                UnityEngine.Debug.LogError($"Streakline/Stripline test failed: {e.Message}");
                passed = false;
            }

            return passed;
        }

        public bool TestMemoryFragmentation()
        {
            bool passed = true;

            try
            {
                long initialMemory = System.GC.GetTotalMemory(true);
                int initialPoolActive = _testPool.ActiveCount;
                int initialPoolTotal = _testPool.TotalAllocated;

                DetailedResults += $"  Initial memory: {initialMemory / 1024 / 1024}MB\n";
                DetailedResults += $"  Initial pool: active={initialPoolActive}, total={initialPoolTotal}\n";

                Stopwatch iterationTimer = new Stopwatch();
                iterationTimer.Start();

                for (int iter = 0; iter < StressTestIterations; iter++)
                {
                    SeedPoint testSeed = new SeedPoint(
                        iter,
                        new Vector3(0.5f, 0.5f, 0.5f),
                        LineType.Streakline,
                        _testField,
                        _testPool,
                        maxParticlesPerSeed: ParticlesPerIteration,
                        releaseInterval: 0.001f
                    );

                    float simTime = 0f;
                    for (int t = 0; t < 50; t++)
                    {
                        testSeed.Update(simTime, 0.01f, IntegrationDirection.Forward);
                        simTime += 0.01f;
                    }

                    testSeed.Clear();
                }

                iterationTimer.Stop();

                long finalMemory = System.GC.GetTotalMemory(true);
                int finalPoolActive = _testPool.ActiveCount;
                int finalPoolTotal = _testPool.TotalAllocated;
                int finalPoolAvailable = _testPool.AvailableCount;

                DetailedResults += $"  Final memory: {finalMemory / 1024 / 1024}MB\n";
                DetailedResults += $"  Final pool: active={finalPoolActive}, total={finalPoolTotal}, available={finalPoolAvailable}\n";
                DetailedResults += $"  Iteration time: {iterationTimer.ElapsedMilliseconds}ms\n";

                if (finalPoolActive != 0)
                {
                    UnityEngine.Debug.LogError($"Pool should have 0 active particles after clear, but has {finalPoolActive}");
                    passed = false;
                }

                float memoryGrowth = (float)(finalMemory - initialMemory) / initialMemory;
                DetailedResults += $"  Memory growth: {memoryGrowth * 100:F2}%\n";

                if (memoryGrowth > 0.5f)
                {
                    UnityEngine.Debug.LogWarning($"Memory grew by {memoryGrowth * 100:F1}%, check for leaks");
                }

                if (finalPoolTotal > initialPoolTotal * 2)
                {
                    UnityEngine.Debug.LogWarning($"Pool size doubled ({initialPoolTotal} -> {finalPoolTotal}), may indicate inefficiency");
                }

                long memoryPerParticle = (finalMemory - initialMemory) / (StressTestIterations * ParticlesPerIteration);
                DetailedResults += $"  Memory per particle: {memoryPerParticle} bytes\n";

                _testPool.TrimExcess();
                _testPool.ReleaseAll();
            }
            catch (System.OutOfMemoryException e)
            {
                UnityEngine.Debug.LogError($"Out of memory during stress test: {e.Message}");
                passed = false;
            }
            catch (System.Exception e)
            {
                UnityEngine.Debug.LogError($"Memory test failed: {e.Message}");
                passed = false;
            }

            return passed;
        }

        public bool AllTestsPassed()
        {
            bool result = BoundaryIndexTestPassed && StreaklineStriplineTestPassed;
            if (StressTestMemory)
            {
                result = result && MemoryFragmentationTestPassed;
            }
            return result;
        }

        private void OnGUI()
        {
            if (string.IsNullOrEmpty(DetailedResults)) return;

            GUI.Box(new Rect(10, 250, 400, 350), "Bug Fix Validation Results");
            
            int y = 275;
            string[] lines = DetailedResults.Split('\n');
            for (int i = 0; i < lines.Length && y < 580; i++)
            {
                string line = lines[i];
                
                if (line.Contains("✓"))
                {
                    GUI.color = Color.green;
                }
                else if (line.Contains("✗"))
                {
                    GUI.color = Color.red;
                }
                else
                {
                    GUI.color = Color.white;
                }
                
                GUI.Label(new Rect(20, y, 380, 20), line);
                y += 18;
            }

            GUI.color = Color.white;

            if (AllTestsPassed())
            {
                GUI.color = Color.green;
                GUI.Label(new Rect(10, 590, 400, 25), "✓ ALL BUG FIXES VERIFIED SUCCESSFULLY");
            }
            else
            {
                GUI.color = Color.red;
                GUI.Label(new Rect(10, 590, 400, 25), "✗ SOME TESTS FAILED - CHECK LOGS");
            }
            GUI.color = Color.white;
        }
    }
}
