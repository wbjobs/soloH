using System;
using System.Collections.Generic;
using UnityEngine;
using GaitSimulation.Core;
using GaitSimulation.Gait;
using GaitSimulation.Exoskeleton;
using GaitSimulation.Battery;
using GaitSimulation.Optimization;
using GaitSimulation.Simulation;

namespace GaitSimulation.Tests
{
    public class SimulationTester : MonoBehaviour
    {
        [Header("Test Settings")]
        public bool runTestsOnStart = true;
        public bool enableLogging = true;
        public float testDuration = 5f;

        [Header("Test Scenarios")]
        public TestScenario[] testScenarios;

        private List<TestResult> _testResults = new List<TestResult>();
        private bool _isRunningTests = false;

        [Serializable]
        public class TestScenario
        {
            public string name = "Test Scenario";
            public float gaitCycleDuration = 1.2f;
            public float bodyMass = 70f;
            public float slopeAngle = 0f;
            public bool useDynamicProgramming = true;
            public float duration = 5f;
        }

        [Serializable]
        public class TestResult
        {
            public string scenarioName;
            public bool passed;
            public float duration;
            public float averageGeneratorPower;
            public float averageMotorPower;
            public float netEnergy;
            public float initialSOC;
            public float finalSOC;
            public float socChange;
            public string errorMessage;
            public List<string> warnings = new List<string>();

            public string GetSummary()
            {
                return $"Scenario: {scenarioName}\n" +
                       $"  Passed: {passed}\n" +
                       $"  Duration: {duration:F2}s\n" +
                       $"  Avg Gen Power: {averageGeneratorPower:F2}W\n" +
                       $"  Avg Mot Power: {averageMotorPower:F2}W\n" +
                       $"  Net Energy: {netEnergy:F2}J\n" +
                       $"  SOC Change: {socChange * 100:F2}%\n" +
                       $"  Initial SOC: {initialSOC * 100:F1}%\n" +
                       $"  Final SOC: {finalSOC * 100:F1}%\n" +
                       (passed ? "" : $"  Error: {errorMessage}\n") +
                       (warnings.Count > 0 ? $"  Warnings: {warnings.Count}\n" : "");
            }
        }

        private void Start()
        {
            if (testScenarios == null || testScenarios.Length == 0)
            {
                InitializeDefaultScenarios();
            }

            if (runTestsOnStart)
            {
                RunAllTests();
            }
        }

        private void InitializeDefaultScenarios()
        {
            testScenarios = new TestScenario[]
            {
                new TestScenario
                {
                    name = "Level Ground - Normal Walking",
                    gaitCycleDuration = 1.2f,
                    bodyMass = 70f,
                    slopeAngle = 0f,
                    useDynamicProgramming = true,
                    duration = testDuration
                },
                new TestScenario
                {
                    name = "Uphill - 5° Incline",
                    gaitCycleDuration = 1.4f,
                    bodyMass = 70f,
                    slopeAngle = 5f,
                    useDynamicProgramming = true,
                    duration = testDuration
                },
                new TestScenario
                {
                    name = "Downhill - 5° Decline",
                    gaitCycleDuration = 1.1f,
                    bodyMass = 70f,
                    slopeAngle = -5f,
                    useDynamicProgramming = true,
                    duration = testDuration
                },
                new TestScenario
                {
                    name = "Light Weight - 50kg",
                    gaitCycleDuration = 1.0f,
                    bodyMass = 50f,
                    slopeAngle = 0f,
                    useDynamicProgramming = true,
                    duration = testDuration
                },
                new TestScenario
                {
                    name = "Heavy Weight - 100kg",
                    gaitCycleDuration = 1.3f,
                    bodyMass = 100f,
                    slopeAngle = 0f,
                    useDynamicProgramming = true,
                    duration = testDuration
                },
                new TestScenario
                {
                    name = "No Optimization - Baseline",
                    gaitCycleDuration = 1.2f,
                    bodyMass = 70f,
                    slopeAngle = 0f,
                    useDynamicProgramming = false,
                    duration = testDuration
                }
            };

            if (enableLogging)
            {
                Debug.Log($"Initialized {testScenarios.Length} default test scenarios.");
            }
        }

        public void RunAllTests()
        {
            if (_isRunningTests)
            {
                Debug.LogWarning("Tests are already running.");
                return;
            }

            StartCoroutine(RunAllTestsCoroutine());
        }

        private System.Collections.IEnumerator RunAllTestsCoroutine()
        {
            _isRunningTests = true;
            _testResults.Clear();

            if (enableLogging)
            {
                Debug.Log("=== Starting Simulation Test Suite ===");
                Debug.Log($"Running {testScenarios.Length} test scenarios...");
            }

            for (int i = 0; i < testScenarios.Length; i++)
            {
                var scenario = testScenarios[i];

                if (enableLogging)
                {
                    Debug.Log($"\n--- Running Test {i + 1}/{testScenarios.Length}: {scenario.name} ---");
                }

                var result = RunSingleTest(scenario);
                _testResults.Add(result);

                if (enableLogging)
                {
                    Debug.Log(result.GetSummary());
                }

                yield return new WaitForSeconds(0.5f);
            }

            _isRunningTests = false;

            if (enableLogging)
            {
                Debug.Log("\n=== Test Suite Complete ===");
                PrintTestSummary();
            }
        }

        public TestResult RunSingleTest(TestScenario scenario)
        {
            var result = new TestResult
            {
                scenarioName = scenario.name,
                passed = true,
                duration = scenario.duration
            };

            try
            {
                var simConfig = new SimulationConfig
                {
                    gaitCycleDuration = scenario.gaitCycleDuration,
                    bodyMass = scenario.bodyMass,
                    slopeAngle = scenario.slopeAngle,
                    simulationFrequency = 100f
                };

                var exoConfig = new ExoskeletonConfig();
                var batteryState = new BatteryState();
                var gaitModel = new GaitModel(simConfig);
                var exoskeletonController = new ExoskeletonController(exoConfig, simConfig);
                var bms = new BatteryManagementSystem(batteryState);
                var ioManager = new InputOutputManager(simConfig);

                DynamicPlanner dynamicPlanner = null;
                if (scenario.useDynamicProgramming)
                {
                    dynamicPlanner = new DynamicPlanner(simConfig, exoConfig, batteryState);
                    dynamicPlanner.ComputeOptimalPolicy(30, 10);
                }

                ioManager.SetInputParameters(scenario.gaitCycleDuration, scenario.bodyMass, scenario.slopeAngle);

                result.initialSOC = batteryState.currentSOC;

                float dt = 1f / simConfig.simulationFrequency;
                float time = 0f;

                while (time < scenario.duration)
                {
                    gaitModel.Update(time, dt);

                    Dictionary<(Side, JointType), ExoskeletonMode> modeOverrides = null;
                    if (scenario.useDynamicProgramming && dynamicPlanner != null && dynamicPlanner.PolicyComputed)
                    {
                        modeOverrides = dynamicPlanner.GetFullModeOverride(time, batteryState.currentSOC);
                    }

                    exoskeletonController.Update(time, dt, gaitModel.JointStates, modeOverrides);

                    var (motorPower, generatorPower) = exoskeletonController.GetTotalPowers(gaitModel.JointStates);
                    float netPower = motorPower - generatorPower;

                    bms.Update(netPower, dt);

                    ioManager.Update(time, dt, gaitModel, exoskeletonController, bms);

                    ValidateSimulationState(time, gaitModel, exoskeletonController, bms, result);

                    time += dt;
                }

                ioManager.FinalizeSimulation();
                var simResult = ioManager.Result;

                result.averageGeneratorPower = simResult.totalGeneratorPower;
                result.averageMotorPower = simResult.totalMotorPower;
                result.netEnergy = simResult.netEnergyConsumption;
                result.finalSOC = simResult.finalSOC;
                result.socChange = result.finalSOC - result.initialSOC;

                ValidateTestResult(result, scenario);
            }
            catch (Exception e)
            {
                result.passed = false;
                result.errorMessage = e.Message;

                if (enableLogging)
                {
                    Debug.LogError($"Test failed with exception: {e}");
                }
            }

            return result;
        }

        private void ValidateSimulationState(float time, GaitModel gaitModel,
            ExoskeletonController exoskeletonController, BatteryManagementSystem bms,
            TestResult result)
        {
            if (bms.Battery.currentSOC < 0f || bms.Battery.currentSOC > 1f)
            {
                result.warnings.Add($"SOC out of bounds at time {time:F2}s: {bms.Battery.currentSOC:F4}");
            }

            foreach (var kvp in gaitModel.JointStates)
            {
                var joint = kvp.Value;
                if (float.IsNaN(joint.angle) || float.IsInfinity(joint.angle))
                {
                    result.warnings.Add($"Invalid angle at {kvp.Key.Item1} {kvp.Key.Item2} at time {time:F2}s");
                }
                if (float.IsNaN(joint.mechanicalPower) || float.IsInfinity(joint.mechanicalPower))
                {
                    result.warnings.Add($"Invalid power at {kvp.Key.Item1} {kvp.Key.Item2} at time {time:F2}s");
                }
            }
        }

        private void ValidateTestResult(TestResult result, TestScenario scenario)
        {
            if (result.averageGeneratorPower < 0)
            {
                result.warnings.Add("Average generator power is negative.");
            }

            if (result.averageMotorPower < 0)
            {
                result.warnings.Add("Average motor power is negative.");
            }

            if (result.finalSOC < 0.05f)
            {
                result.warnings.Add("Battery nearly depleted at end of test.");
            }

            if (result.finalSOC > 0.95f)
            {
                result.warnings.Add("Battery nearly full at end of test.");
            }

            if (result.warnings.Count > 5)
            {
                result.passed = false;
                result.errorMessage = $"Too many warnings ({result.warnings.Count}).";
            }
        }

        public void PrintTestSummary()
        {
            int passed = 0;
            int failed = 0;
            float totalNetEnergy = 0f;
            float avgSOCChange = 0f;

            foreach (var result in _testResults)
            {
                if (result.passed) passed++;
                else failed++;

                totalNetEnergy += result.netEnergy;
                avgSOCChange += result.socChange;
            }

            avgSOCChange /= _testResults.Count;

            string summary = $"\n=== Test Summary ===\n" +
                           $"Total Tests: {_testResults.Count}\n" +
                           $"Passed: {passed}\n" +
                           $"Failed: {failed}\n" +
                           $"Success Rate: {(float)passed / _testResults.Count * 100:F1}%\n" +
                           $"\nAverage Metrics:\n" +
                           $"  Avg Net Energy: {totalNetEnergy / _testResults.Count:F2}J\n" +
                           $"  Avg SOC Change: {avgSOCChange * 100:F2}%\n";

            if (failed > 0)
            {
                summary += "\nFailed Tests:\n";
                foreach (var result in _testResults)
                {
                    if (!result.passed)
                    {
                        summary += $"  - {result.scenarioName}: {result.errorMessage}\n";
                    }
                }
            }

            Debug.Log(summary);
        }

        public List<TestResult> GetTestResults()
        {
            return _testResults;
        }

        public string GetComparisonReport()
        {
            if (_testResults.Count < 2)
            {
                return "Not enough results for comparison.";
            }

            string report = "\n=== Scenario Comparison Report ===\n\n";

            var baseline = _testResults.Find(r => r.scenarioName.Contains("Baseline") || r.scenarioName.Contains("No Optimization"));

            foreach (var result in _testResults)
            {
                report += $"--- {result.scenarioName} ---\n";
                report += $"  {'Status',-10}: {(result.passed ? "PASS" : "FAIL")}\n";
                report += $"  {'Gen Power',-10}: {result.averageGeneratorPower:F2} W\n";
                report += $"  {'Mot Power',-10}: {result.averageMotorPower:F2} W\n";
                report += $"  {'Net Energy',-10}: {result.netEnergy:F2} J\n";
                report += $"  {'SOC Δ',-10}: {result.socChange * 100:F2} %\n";

                if (baseline != null && result != baseline)
                {
                    float energyDiff = result.netEnergy - baseline.netEnergy;
                    float socDiff = result.socChange - baseline.socChange;

                    report += $"\n  vs Baseline:\n";
                    report += $"    {'Energy Diff',-10}: {energyDiff:F2} J ({(energyDiff / baseline.netEnergy) * 100:F1}%)\n";
                    report += $"    {'SOC Diff',-10}: {socDiff * 100:F2} %\n";
                }

                report += "\n";
            }

            var optimized = _testResults.Find(r => r.scenarioName == "Level Ground - Normal Walking");
            var nonOptimized = _testResults.Find(r => r.scenarioName == "No Optimization - Baseline");

            if (optimized != null && nonOptimized != null)
            {
                report += "\n=== Dynamic Programming Optimization Impact ===\n";
                float energySaving = nonOptimized.netEnergy - optimized.netEnergy;
                float savingPercent = (energySaving / nonOptimized.netEnergy) * 100f;

                report += $"Energy with DP: {optimized.netEnergy:F2} J\n";
                report += $"Energy without DP: {nonOptimized.netEnergy:F2} J\n";
                report += $"Energy Saved: {energySaving:F2} J ({savingPercent:F1}%)\n";

                float socImprovement = optimized.socChange - nonOptimized.socChange;
                report += $"SOC Improvement: {socImprovement * 100:F2}%\n";
            }

            return report;
        }

        public void ExportResultsToCSV(string filePath)
        {
            try
            {
                string csv = "Scenario,Passed,Duration,AvgGenPower,AvgMotorPower,NetEnergy,InitialSOC,FinalSOC,SOCChange\n";

                foreach (var result in _testResults)
                {
                    csv += $"{result.scenarioName},{result.passed},{result.duration:F2}," +
                           $"{result.averageGeneratorPower:F4},{result.averageMotorPower:F4}," +
                           $"{result.netEnergy:F4},{result.initialSOC:F4},{result.finalSOC:F4}," +
                           $"{result.socChange:F4}\n";
                }

                System.IO.File.WriteAllText(filePath, csv);
                Debug.Log($"Results exported to {filePath}");
            }
            catch (Exception e)
            {
                Debug.LogError($"Failed to export results: {e.Message}");
            }
        }

        private void OnGUI()
        {
            if (_testResults == null || _testResults.Count == 0) return;

            float panelX = 20f;
            float panelY = 20f;
            float panelW = 350f;
            float panelH = 30f + _testResults.Count * 25f;

            GUI.Box(new Rect(panelX, panelY, panelW, panelH), "Test Results");

            GUIStyle headerStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 11,
                fontStyle = FontStyle.Bold,
                normal = { textColor = Color.white }
            };

            GUIStyle resultStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 10,
                normal = { textColor = Color.white }
            };

            GUI.Label(new Rect(panelX + 10f, panelY + 10f, 180f, 20f), "Scenario", headerStyle);
            GUI.Label(new Rect(panelX + 190f, panelY + 10f, 50f, 20f), "Status", headerStyle);
            GUI.Label(new Rect(panelX + 240f, panelY + 10f, 60f, 20f), "Net (J)", headerStyle);
            GUI.Label(new Rect(panelX + 300f, panelY + 10f, 40f, 20f), "ΔSOC%", headerStyle);

            for (int i = 0; i < _testResults.Count; i++)
            {
                var result = _testResults[i];
                float y = panelY + 30f + i * 25f;

                GUI.color = result.passed ? Color.white : Color.gray;
                GUI.Label(new Rect(panelX + 10f, y, 180f, 20f), result.scenarioName, resultStyle);
                GUI.color = result.passed ? Color.green : Color.red;
                GUI.Label(new Rect(panelX + 190f, y, 50f, 20f), result.passed ? "PASS" : "FAIL", resultStyle);
                GUI.color = Color.white;
                GUI.Label(new Rect(panelX + 240f, y, 60f, 20f), result.netEnergy.ToString("F0"), resultStyle);
                GUI.Label(new Rect(panelX + 300f, y, 40f, 20f), (result.socChange * 100).ToString("F1"), resultStyle);
            }

            GUI.color = Color.white;

            if (GUI.Button(new Rect(panelX, panelY + panelH + 10f, 150f, 30f), "Export Results"))
            {
                string path = Application.dataPath + "/test_results.csv";
                ExportResultsToCSV(path);
            }

            if (GUI.Button(new Rect(panelX + 160f, panelY + panelH + 10f, 150f, 30f), "Show Comparison"))
            {
                Debug.Log(GetComparisonReport());
            }

            if (GUI.Button(new Rect(panelX + 310f, panelY + panelH + 10f, 40f, 30f), "↻"))
            {
                RunAllTests();
            }
        }
    }
}
