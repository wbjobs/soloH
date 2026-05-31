#if UNITY_EDITOR || UNITY_STANDALONE
#else
using System;
using System.Collections.Generic;
using GaitSimulation.Core;
using GaitSimulation.Gait;
using GaitSimulation.Exoskeleton;
using GaitSimulation.Battery;
using GaitSimulation.Optimization;
using GaitSimulation.Simulation;
using GaitSimulation.Safety;
using GaitSimulation.Learning;

namespace GaitSimulation.Tests
{
    class CoreLogicValidator
    {
        static void Main(string[] args)
        {
            Console.WriteLine("=== Gait Simulation Core Logic Validation ===\n");

            TestGaitModel();
            Console.WriteLine();

            TestMassDistributionFix();
            Console.WriteLine();

            TestTorqueSmoothingFix();
            Console.WriteLine();

            TestSlopeAdaptationFix();
            Console.WriteLine();

            TestExoskeletonController();
            Console.WriteLine();

            TestBatteryManagement();
            Console.WriteLine();

            TestDynamicProgramming();
            Console.WriteLine();

            TestFatigueModel();
            Console.WriteLine();

            TestGaitLearning();
            Console.WriteLine();

            TestFallDetection();
            Console.WriteLine();

            TestFullSimulationWithNewFeatures();

            Console.WriteLine("\n=== All Tests Completed ===");
            Console.ReadKey();
        }

        static void TestGaitModel()
        {
            Console.WriteLine("--- Testing Gait Model ---");

            var config = new SimulationConfig
            {
                gaitCycleDuration = 1.2f,
                bodyMass = 70f,
                slopeAngle = 0f
            };

            var gaitModel = new GaitModel(config);

            Console.WriteLine($"Testing gait trajectory generation for 2 cycles...");

            int validPoints = 0;
            int totalPoints = 120;
            float dt = 0.02f;

            for (int i = 0; i < totalPoints; i++)
            {
                float time = i * dt;
                gaitModel.Update(time, dt);

                var leftKnee = gaitModel.GetJointState(Side.Left, JointType.Knee);
                var rightAnkle = gaitModel.GetJointState(Side.Right, JointType.Ankle);

                if (!float.IsNaN(leftKnee.angle) && !float.IsInfinity(leftKnee.angle) &&
                    !float.IsNaN(rightAnkle.mechanicalPower) && !float.IsInfinity(rightAnkle.mechanicalPower))
                {
                    validPoints++;
                }

                if (i % 20 == 0)
                {
                    Console.WriteLine($"  t={time:F2}s | L Knee: {leftKnee.angle * 57.3f:F1}°, {leftKnee.mechanicalPower:F1}W | " +
                                      $"R Ankle: {rightAnkle.angle * 57.3f:F1}°, {rightAnkle.mechanicalPower:F1}W");
                }
            }

            Console.WriteLine($"  Valid points: {validPoints}/{totalPoints} ({(float)validPoints / totalPoints * 100:F1}%)");
            Console.WriteLine($"  Gait Model Test: {(validPoints == totalPoints ? "PASS" : "FAIL")}");
        }

        static void TestMassDistributionFix()
        {
            Console.WriteLine("--- Fix 1: Mass Distribution & COM Verification ---");

            var config = new SimulationConfig
            {
                gaitCycleDuration = 1.2f,
                bodyMass = 70f,
                slopeAngle = 0f
            };

            var gaitModel = new GaitModel(config);

            Console.WriteLine("  Anthropometric Parameters (Winter, 2009):");
            Console.WriteLine("    Thigh: 10.0% body mass, COM at 43.3% from proximal");
            Console.WriteLine("    Shank: 4.65% body mass, COM at 43.3% from proximal");
            Console.WriteLine("    Foot: 1.45% body mass, COM at 42.9% from heel");

            float dt = 0.01f;
            float[] torqueMagnitudes = new float[3];
            int samples = 120;

            for (int i = 0; i < samples; i++)
            {
                float time = i * dt;
                gaitModel.Update(time, dt);

                torqueMagnitudes[0] += Mathf.Abs(gaitModel.GetJointState(Side.Left, JointType.Hip).torque);
                torqueMagnitudes[1] += Mathf.Abs(gaitModel.GetJointState(Side.Left, JointType.Knee).torque);
                torqueMagnitudes[2] += Mathf.Abs(gaitModel.GetJointState(Side.Left, JointType.Ankle).torque);
            }

            for (int i = 0; i < 3; i++)
            {
                torqueMagnitudes[i] /= samples;
            }

            Console.WriteLine("\n  Average Joint Torques (with proper COM):");
            Console.WriteLine($"    Hip:   {torqueMagnitudes[0]:F2} Nm");
            Console.WriteLine($"    Knee:  {torqueMagnitudes[1]:F2} Nm");
            Console.WriteLine($"    Ankle: {torqueMagnitudes[2]:F2} Nm");

            bool torqueRatioValid = torqueMagnitudes[2] > torqueMagnitudes[1] &&
                                    torqueMagnitudes[0] > torqueMagnitudes[1];
            Console.WriteLine($"\n  Torque hierarchy (Ankle > Hip > Knee): {(torqueRatioValid ? "PASS" : "FAIL")}");
            Console.WriteLine($"  Mass Distribution Fix: {(torqueRatioValid ? "PASS" : "FAIL")}");
        }

        static void TestTorqueSmoothingFix()
        {
            Console.WriteLine("--- Fix 2: Torque Smoothing & Mode Transition ---");

            var simConfig = new SimulationConfig
            {
                gaitCycleDuration = 1.2f,
                bodyMass = 70f,
                slopeAngle = 0f
            };

            var exoConfig = new ExoskeletonConfig();
            var gaitModel = new GaitModel(simConfig);
            var exoController = new ExoskeletonController(exoConfig, simConfig);

            Console.WriteLine("  Smoothing Parameters:");
            Console.WriteLine($"    Torque smoothing time: {exoController.torqueSmoothingTime * 1000:F0} ms");
            Console.WriteLine($"    Mode transition duration: {exoController.modeTransitionDuration * 1000:F0} ms");
            Console.WriteLine($"    Max torque slew rate: {exoController.maxTorqueSlewRate:F0} Nm/s");

            float dt = 0.01f;
            int totalSteps = 240;
            float maxTorqueDelta = 0f;
            float lastTorque = 0f;
            int modeSwitchCount = 0;
            ExoskeletonMode lastMode = ExoskeletonMode.Idle;

            float[] torques = new float[totalSteps];
            ExoskeletonMode[] modes = new ExoskeletonMode[totalSteps];

            for (int i = 0; i < totalSteps; i++)
            {
                float time = i * dt;
                gaitModel.Update(time, dt);
                exoController.Update(time, dt, gaitModel.JointStates);

                var knee = gaitModel.GetJointState(Side.Left, JointType.Knee);
                torques[i] = knee.exoskeletonTorque;
                modes[i] = knee.exoskeletonMode;

                if (i > 0)
                {
                    float delta = Mathf.Abs(torques[i] - lastTorque);
                    maxTorqueDelta = Mathf.Max(maxTorqueDelta, delta);

                    if (modes[i] != lastMode)
                    {
                        modeSwitchCount++;
                        Console.WriteLine($"    t={time:F2}s: Mode switch {lastMode} → {modes[i]}, Δτ={delta:F3} Nm");
                    }
                }

                lastTorque = torques[i];
                lastMode = modes[i];
            }

            float maxAllowedDelta = exoController.maxTorqueSlewRate * dt * 1.5f;
            bool smoothingValid = maxTorqueDelta < maxAllowedDelta;

            Console.WriteLine($"\n  Max torque change per step: {maxTorqueDelta:F4} Nm");
            Console.WriteLine($"  Max allowed: {maxAllowedDelta:F4} Nm");
            Console.WriteLine($"  Mode switches detected: {modeSwitchCount}");
            Console.WriteLine($"  Torque Smoothing Fix: {(smoothingValid ? "PASS" : "FAIL")}");
        }

        static void TestSlopeAdaptationFix()
        {
            Console.WriteLine("--- Fix 3: Slope Adaptive Gait Parameters ---");

            float[] testSlopes = { -10f, -5f, 0f, 5f, 10f };

            Console.WriteLine("  Adaptation Parameters:");
            Console.WriteLine("    Uphill: cadence +15%, step length -20%, support +5%");
            Console.WriteLine("    Downhill: cadence -10%, step length +15%, support -3%");
            Console.WriteLine();

            foreach (float slope in testSlopes)
            {
                var config = new SimulationConfig
                {
                    gaitCycleDuration = 1.2f,
                    bodyMass = 70f,
                    slopeAngle = slope
                };

                float adaptedCycle = config.GetAdaptedGaitCycleDuration();
                float stepLength = config.GetAdaptedStepLength();
                float supportRatio = config.GetSupportPhaseRatio();
                float cadence = 1f / adaptedCycle;

                Console.WriteLine($"  Slope {slope,5:F1}°:");
                Console.WriteLine($"    Cycle: {1.2f:F2}s → {adaptedCycle:F3}s  (Δ: {(adaptedCycle - 1.2f) * 1000:F0} ms)");
                Console.WriteLine($"    Cadence: {1f / 1.2f:F2}Hz → {cadence:F3}Hz");
                Console.WriteLine($"    Step length: 0.70m → {stepLength:F3}m");
                Console.WriteLine($"    Support ratio: 60% → {supportRatio * 100:F1}%");
            }

            bool uphillValid = true;
            bool downhillValid = true;

            var config0 = new SimulationConfig { slopeAngle = 0f };
            var configUp = new SimulationConfig { slopeAngle = 10f };
            var configDown = new SimulationConfig { slopeAngle = -10f };

            uphillValid = configUp.GetAdaptedGaitCycleDuration() < config0.GetAdaptedGaitCycleDuration() &&
                         configUp.GetAdaptedStepLength() < config0.GetAdaptedStepLength() &&
                         configUp.GetSupportPhaseRatio() > config0.GetSupportPhaseRatio();

            downhillValid = configDown.GetAdaptedGaitCycleDuration() > config0.GetAdaptedGaitCycleDuration() &&
                           configDown.GetAdaptedStepLength() > config0.GetAdaptedStepLength() &&
                           configDown.GetSupportPhaseRatio() < config0.GetSupportPhaseRatio();

            Console.WriteLine($"\n  Uphill adaptation (↑cadence, ↓step, ↑support): {(uphillValid ? "PASS" : "FAIL")}");
            Console.WriteLine($"  Downhill adaptation (↓cadence, ↑step, ↓support): {(downhillValid ? "PASS" : "FAIL")}");
            Console.WriteLine($"  Slope Adaptation Fix: {(uphillValid && downhillValid ? "PASS" : "FAIL")}");
        }

        static void TestExoskeletonController()
        {
            Console.WriteLine("--- Testing Exoskeleton Controller ---");

            var simConfig = new SimulationConfig
            {
                gaitCycleDuration = 1.2f,
                bodyMass = 70f,
                slopeAngle = 0f
            };

            var exoConfig = new ExoskeletonConfig();
            var gaitModel = new GaitModel(simConfig);
            var exoController = new ExoskeletonController(exoConfig, simConfig);

            Console.WriteLine($"Testing exoskeleton mode switching...");

            int modeChanges = 0;
            int motorCount = 0;
            int generatorCount = 0;
            int idleCount = 0;

            float dt = 0.01f;
            ExoskeletonMode lastMode = ExoskeletonMode.Idle;

            for (int i = 0; i < 240; i++)
            {
                float time = i * dt;
                gaitModel.Update(time, dt);
                exoController.Update(time, dt, gaitModel.JointStates);

                var kneeMode = exoController.GetMode(Side.Left, JointType.Knee);

                if (kneeMode != lastMode)
                {
                    modeChanges++;
                    lastMode = kneeMode;
                }

                switch (kneeMode)
                {
                    case ExoskeletonMode.Motor: motorCount++; break;
                    case ExoskeletonMode.Generator: generatorCount++; break;
                    case ExoskeletonMode.Idle: idleCount++; break;
                }
            }

            Console.WriteLine($"  Mode changes: {modeChanges}");
            Console.WriteLine($"  Mode distribution - Motor: {motorCount}, Generator: {generatorCount}, Idle: {idleCount}");

            var (motorPower, generatorPower) = exoController.GetTotalPowers(gaitModel.JointStates);
            Console.WriteLine($"  Current powers - Motor: {motorPower:F2}W, Generator: {generatorPower:F2}W");
            Console.WriteLine($"  Net power: {motorPower - generatorPower:F2}W");

            bool pass = modeChanges > 0 && motorCount > 0 && generatorCount > 0;
            Console.WriteLine($"  Exoskeleton Test: {(pass ? "PASS" : "FAIL")}");
        }

        static void TestBatteryManagement()
        {
            Console.WriteLine("--- Testing Battery Management System ---");

            var batteryState = new BatteryState();
            var bms = new BatteryManagementSystem(batteryState);

            Console.WriteLine($"Initial SOC: {batteryState.currentSOC * 100:F1}%");
            Console.WriteLine($"Capacity: {batteryState.capacity}Ah, Voltage: {batteryState.nominalVoltage}V");

            float dt = 0.1f;
            float initialSOC = batteryState.currentSOC;

            Console.WriteLine("\n  Testing discharge (50W for 10s)...");
            for (int i = 0; i < 100; i++)
            {
                bms.Update(50f, dt);
            }
            float socAfterDischarge = batteryState.currentSOC;
            Console.WriteLine($"  SOC after discharge: {socAfterDischarge * 100:F1}% (Δ: {(socAfterDischarge - initialSOC) * 100:F2}%)");

            Console.WriteLine("\n  Testing charge (-30W for 10s)...");
            for (int i = 0; i < 100; i++)
            {
                bms.Update(-30f, dt);
            }
            float socAfterCharge = batteryState.currentSOC;
            Console.WriteLine($"  SOC after charge: {socAfterCharge * 100:F1}% (Δ: {(socAfterCharge - socAfterDischarge) * 100:F2}%)");

            Console.WriteLine($"\n  Total Energy In: {bms.TotalEnergyIn:F1}J");
            Console.WriteLine($"  Total Energy Out: {bms.TotalEnergyOut:F1}J");
            Console.WriteLine($"  Round Trip Efficiency: {bms.GetRoundTripEfficiency() * 100:F1}%");
            Console.WriteLine($"  Health Status: {bms.GetHealthStatus()}");

            bool pass = batteryState.currentSOC > 0.1f && batteryState.currentSOC < 0.95f &&
                        bms.GetRoundTripEfficiency() > 0.5f;
            Console.WriteLine($"  BMS Test: {(pass ? "PASS" : "FAIL")}");
        }

        static void TestDynamicProgramming()
        {
            Console.WriteLine("--- Testing Dynamic Programming Optimizer ---");

            var simConfig = new SimulationConfig
            {
                gaitCycleDuration = 1.2f,
                bodyMass = 70f,
                slopeAngle = 0f
            };

            var exoConfig = new ExoskeletonConfig();
            var batteryState = new BatteryState();

            var planner = new DynamicPlanner(simConfig, exoConfig, batteryState);

            Console.WriteLine("Computing optimal policy (30 timesteps, 10 SOC states)...");
            DateTime startTime = DateTime.Now;
            planner.ComputeOptimalPolicy(30, 10);
            TimeSpan computeTime = DateTime.Now - startTime;

            Console.WriteLine($"  Computation time: {computeTime.TotalMilliseconds:F0}ms");
            Console.WriteLine($"  Policy computed: {planner.PolicyComputed}");

            if (planner.PolicyComputed)
            {
                Console.WriteLine(planner.GetPolicySummary());

                Console.WriteLine("\n  Sampling optimal modes at different times:");
                for (float t = 0; t < 1.2f; t += 0.2f)
                {
                    var (kneeMode, ankleMode) = planner.GetOptimalModes(Side.Left, t, 0.7f);
                    Console.WriteLine($"    t={t:F1}s, SOC=70% | Knee: {kneeMode}, Ankle: {ankleMode}");
                }

                Console.WriteLine("\n  Testing different SOC levels:");
                float[] socLevels = { 0.2f, 0.5f, 0.8f };
                foreach (float soc in socLevels)
                {
                    var (kneeMode, ankleMode) = planner.GetOptimalModes(Side.Left, 0.3f, soc);
                    Console.WriteLine($"    t=0.3s, SOC={soc * 100:F0}% | Knee: {kneeMode}, Ankle: {ankleMode}");
                }
            }

            Console.WriteLine($"  Dynamic Programming Test: {(planner.PolicyComputed ? "PASS" : "FAIL")}");
        }

        static void TestFullSimulation()
        {
            Console.WriteLine("--- Testing Full Simulation Integration ---");

            var simConfig = new SimulationConfig
            {
                gaitCycleDuration = 1.2f,
                bodyMass = 70f,
                slopeAngle = 0f,
                simulationFrequency = 100f
            };

            var exoConfig = new ExoskeletonConfig();
            var batteryState = new BatteryState();
            var gaitModel = new GaitModel(simConfig);
            var exoController = new ExoskeletonController(exoConfig, simConfig);
            var bms = new BatteryManagementSystem(batteryState);
            var ioManager = new InputOutputManager(simConfig);
            var planner = new DynamicPlanner(simConfig, exoConfig, batteryState);

            ioManager.SetInputParameters(1.2f, 70f, 0f);

            Console.WriteLine("Pre-computing optimal policy...");
            planner.ComputeOptimalPolicy(30, 10);

            Console.WriteLine("Running 5-second simulation with DP optimization...");

            float dt = 1f / simConfig.simulationFrequency;
            float time = 0f;
            float duration = 5f;

            while (time < duration)
            {
                gaitModel.Update(time, dt);

                var modeOverrides = planner.GetFullModeOverride(time, batteryState.currentSOC);
                exoController.Update(time, dt, gaitModel.JointStates, modeOverrides);

                var (motorPower, generatorPower) = exoController.GetTotalPowers(gaitModel.JointStates);
                float netPower = motorPower - generatorPower;

                bms.Update(netPower, dt);
                ioManager.Update(time, dt, gaitModel, exoController, bms);

                time += dt;
            }

            ioManager.FinalizeSimulation();
            var result = ioManager.Result;

            Console.WriteLine("\n" + result.GetSummaryText());
            Console.WriteLine($"\n  Total Energy In: {bms.TotalEnergyIn:F1}J");
            Console.WriteLine($"  Total Energy Out: {bms.TotalEnergyOut:F1}J");
            Console.WriteLine($"  Round Trip Efficiency: {bms.GetRoundTripEfficiency() * 100:F1}%");

            bool pass = result.netEnergyConsumption > 0 &&
                        result.finalSOC > 0.1f &&
                        result.totalGeneratorPower > 0 &&
                        result.totalMotorPower > 0;

            Console.WriteLine($"\n  Full Simulation Test: {(pass ? "PASS" : "FAIL")}");
        }

        static void TestFatigueModel()
        {
            Console.WriteLine("--- Testing Muscle Fatigue Model ---");

            var config = new SimulationConfig
            {
                gaitCycleDuration = 1.2f,
                bodyMass = 70f,
                slopeAngle = 0f
            };

            var fatigueModel = new FatigueModel(config);
            var gaitModel = new GaitModel(config);

            Console.WriteLine("  Testing fatigue accumulation during walking...");
            Console.WriteLine($"  Initial Fatigue: {fatigueModel.overallFatigueLevel * 100:F1}%");
            Console.WriteLine($"  Initial Glycogen: {fatigueModel.muscleGlycogen * 100:F1}%");

            float dt = 0.01f;
            float time = 0f;
            float duration = 120f;

            float initialAssistRatio = 0.4f;
            float maxAssistRatio = 0f;

            for (int i = 0; i < duration / dt; i++)
            {
                gaitModel.Update(time, dt);
                fatigueModel.Update(dt, gaitModel.JointStates, 1.2f);

                float adjustedRatio = fatigueModel.GetAdjustedAssistRatio(initialAssistRatio, JointType.Knee);
                if (adjustedRatio > maxAssistRatio) maxAssistRatio = adjustedRatio;

                if (i % 12000 == 0)
                {
                    Console.WriteLine($"    t={time:F0}s | Fatigue: {fatigueModel.overallFatigueLevel * 100:F1}% | " +
                                      $"Glycogen: {fatigueModel.muscleGlycogen * 100:F1}% | " +
                                      $"Lactic: {fatigueModel.lacticAcid * 100:F1}% | " +
                                      $"Assist Boost: +{fatigueModel.currentAssistBoost * 100:F0}%");
                }

                time += dt;
            }

            Console.WriteLine($"\n  Final Fatigue: {fatigueModel.overallFatigueLevel * 100:F1}%");
            Console.WriteLine($"  Final Glycogen: {fatigueModel.muscleGlycogen * 100:F1}%");
            Console.WriteLine($"  Final Lactic Acid: {fatigueModel.lacticAcid * 100:F1}%");
            Console.WriteLine($"  Max Assist Ratio: {maxAssistRatio:F2} (base: {initialAssistRatio})");
            Console.WriteLine($"  Fatigue Level: {fatigueModel.GetFatigueLevel()}");

            Console.WriteLine("\n  Testing recovery...");
            fatigueModel.StartRecovery();
            float fatigueBeforeRecovery = fatigueModel.overallFatigueLevel;

            for (int i = 0; i < 60f / dt; i++)
            {
                fatigueModel.Update(dt, gaitModel.JointStates, 0f);
            }

            Console.WriteLine($"  Fatigue after 60s recovery: {fatigueModel.overallFatigueLevel * 100:F1}% " +
                              $"(-{(fatigueBeforeRecovery - fatigueModel.overallFatigueLevel) * 100:F1}%)");

            Console.WriteLine("\n  Testing regeneration ratio adjustment...");
            float baseRegenRatio = 0.3f;
            float adjustedRegenFatigued = fatigueModel.GetAdjustedRegenerationRatio(baseRegenRatio, JointType.Knee);
            Console.WriteLine($"    Base regen ratio: {baseRegenRatio}");
            Console.WriteLine($"    Adjusted (fatigued): {adjustedRegenFatigued}");

            fatigueModel.Reset();
            float adjustedRegenFresh = fatigueModel.GetAdjustedRegenerationRatio(baseRegenRatio, JointType.Knee);
            Console.WriteLine($"    Adjusted (fresh): {adjustedRegenFresh}");

            bool pass = fatigueBeforeRecovery > 0.3f &&
                        maxAssistRatio > initialAssistRatio &&
                        adjustedRegenFatigued < baseRegenRatio;

            Console.WriteLine($"\n  Fatigue Model Test: {(pass ? "PASS" : "FAIL")}");
        }

        static void TestGaitLearning()
        {
            Console.WriteLine("--- Testing Personalized Gait Learning ---");

            var config = new SimulationConfig
            {
                gaitCycleDuration = 1.2f,
                bodyMass = 70f,
                slopeAngle = 0f
            };

            var gaitLearner = new GaitLearner(config);
            var gaitModel = new GaitModel(config);

            Console.WriteLine("  Testing gait pattern learning over 30 cycles...");
            Console.WriteLine($"  Minimum cycles for confidence: 5");

            float dt = 0.02f;
            float time = 0f;
            int cyclesTrained = 0;
            float lastPhase = 0f;

            float baseRegenRatio = 0.3f;
            float baseAssistRatio = 0.4f;

            while (cyclesTrained < 30)
            {
                gaitModel.Update(time, dt);
                float gaitPhaseLeft = (time % config.gaitCycleDuration) / config.gaitCycleDuration;
                float gaitPhaseRight = (gaitPhaseLeft + 0.5f) % 1f;

                gaitLearner.Update(time, gaitModel.JointStates, gaitPhaseLeft, gaitPhaseRight);

                if (gaitPhaseLeft < 0.02f && lastPhase > 0.9f)
                {
                    cyclesTrained++;
                    var model = gaitLearner.PersonalizedModel;
                    Console.WriteLine($"    Cycle {cyclesTrained} | " +
                                      $"Confidence: {model.learningConfidence * 100:F0}% | " +
                                      $"Cadence: {model.preferredCadence:F0} spm | " +
                                      $"Strength: {model.userStrengthLevel * 100:F0}%");
                }

                lastPhase = gaitPhaseLeft;
                time += dt;
            }

            var personalizedModel = gaitLearner.PersonalizedModel;
            Console.WriteLine($"\n  Learning Results:");
            Console.WriteLine($"    Training Cycles: {personalizedModel.trainingCycles}");
            Console.WriteLine($"    Learning Confidence: {personalizedModel.learningConfidence * 100:F1}%");
            Console.WriteLine($"    Preferred Cadence: {personalizedModel.preferredCadence:F1} spm");
            Console.WriteLine($"    Preferred Step Length: {personalizedModel.preferredStepLength:F2} m");
            Console.WriteLine($"    User Strength Level: {personalizedModel.userStrengthLevel * 100:F1}%");
            Console.WriteLine($"    Energy Consumption: {personalizedModel.energyConsumptionPerKm:F0} J/km");
            Console.WriteLine($"    Optimal Knee Recovery Phase: {personalizedModel.optimalRegenerationPointKnee * 100:F0}%");
            Console.WriteLine($"    Optimal Ankle Recovery Phase: {personalizedModel.optimalRegenerationPointAnkle * 100:F0}%");
            Console.WriteLine($"    Knee Recovery Efficiency: {personalizedModel.regenerationEfficiencyKnee * 100:F1}%");
            Console.WriteLine($"    Ankle Recovery Efficiency: {personalizedModel.regenerationEfficiencyAnkle * 100:F1}%");

            Console.WriteLine("\n  Testing adaptive ratio adjustments...");
            float adjustedRegen = gaitLearner.GetAdjustedRegenerationRatio(baseRegenRatio, JointType.Knee, 0.3f);
            float adjustedAssist = gaitLearner.GetPersonalizedAssistRatio(baseAssistRatio, JointType.Knee);
            Console.WriteLine($"    Base regen ratio: {baseRegenRatio}, Adjusted: {adjustedRegen:F3}");
            Console.WriteLine($"    Base assist ratio: {baseAssistRatio}, Adjusted: {adjustedAssist:F3}");

            Console.WriteLine("\n  Testing preferred recovery phase detection...");
            var kneePhase = gaitLearner.GetPreferredRecoveryPhase(JointType.Knee);
            var anklePhase = gaitLearner.GetPreferredRecoveryPhase(JointType.Ankle);
            Console.WriteLine($"    Preferred Knee Recovery Phase: {kneePhase}");
            Console.WriteLine($"    Preferred Ankle Recovery Phase: {anklePhase}");

            Console.WriteLine("\n  Testing learning reset...");
            gaitLearner.Reset();
            Console.WriteLine($"    Cycles after reset: {gaitLearner.PersonalizedModel.trainingCycles}");

            bool pass = personalizedModel.trainingCycles >= 5 &&
                        personalizedModel.learningConfidence > 0.1f &&
                        personalizedModel.preferredCadence > 0;

            Console.WriteLine($"\n  Gait Learning Test: {(pass ? "PASS" : "FAIL")}");
        }

        static void TestFallDetection()
        {
            Console.WriteLine("--- Testing Fall Detection & Emergency Braking ---");

            var config = new SimulationConfig
            {
                gaitCycleDuration = 1.2f,
                bodyMass = 70f,
                slopeAngle = 0f
            };

            var gaitModel = new GaitModel(config);
            var fallDetector = new FallDetector(config, gaitModel);

            Console.WriteLine("  Testing normal walking stability...");
            Console.WriteLine($"  Initial Risk Level: {fallDetector.CurrentRiskLevel}");
            Console.WriteLine($"  Initial Braking Level: {fallDetector.CurrentBrakingLevel}");

            float dt = 0.01f;
            float time = 0f;

            for (int i = 0; i < 5f / dt; i++)
            {
                gaitModel.Update(time, dt);
                float gaitPhaseLeft = (time % config.gaitCycleDuration) / config.gaitCycleDuration;
                float gaitPhaseRight = (gaitPhaseLeft + 0.5f) % 1f;

                fallDetector.Update(time, dt, gaitModel.JointStates, gaitPhaseLeft, gaitPhaseRight);
                time += dt;
            }

            var stability = fallDetector.StabilityMetrics;
            Console.WriteLine($"\n  Stability Metrics (normal walking):");
            Console.WriteLine($"    Overall Stability Score: {stability.overallStabilityScore * 100:F1}%");
            Console.WriteLine($"    Margin of Stability: {stability.marginOfStability * 100:F1}%");
            Console.WriteLine($"    Dynamic Gait Index: {stability.dynamicGaitIndex * 100:F1}%");
            Console.WriteLine($"    Trunk Sway: {stability.trunkSwayAngle:F1}°");
            Console.WriteLine($"    Risk Level: {fallDetector.CurrentRiskLevel}");
            Console.WriteLine($"    Braking Level: {fallDetector.CurrentBrakingLevel}");

            Console.WriteLine("\n  Testing manual emergency brake trigger...");
            float baseAssistRatio = 0.4f;
            float baseRegenRatio = 0.3f;

            float assistBefore = fallDetector.GetModifiedAssistRatio(baseAssistRatio, JointType.Knee);
            float regenBefore = fallDetector.GetModifiedRegenerationRatio(baseRegenRatio, JointType.Knee);
            Console.WriteLine($"    Before brake - Assist: {assistBefore}, Regen: {regenBefore}");

            fallDetector.TriggerEmergencyBrake();

            float assistAfter = fallDetector.GetModifiedAssistRatio(baseAssistRatio, JointType.Knee);
            float regenAfter = fallDetector.GetModifiedRegenerationRatio(baseRegenRatio, JointType.Knee);
            Console.WriteLine($"    After brake - Assist: {assistAfter}, Regen: {regenAfter:F3}");
            Console.WriteLine($"    Risk Level: {fallDetector.CurrentRiskLevel}");
            Console.WriteLine($"    Braking Level: {fallDetector.CurrentBrakingLevel}");

            Console.WriteLine("\n  Testing ratio modification at different braking levels...");
            fallDetector.Reset();
            var brakingLevels = (BrakingLevel[])Enum.GetValues(typeof(BrakingLevel));

            foreach (var level in brakingLevels)
            {
                if (level == BrakingLevel.None) continue;

                float modifiedAssist = baseAssistRatio;
                float modifiedRegen = baseRegenRatio;

                switch (level)
                {
                    case BrakingLevel.Cautious: modifiedAssist *= 0.8f; modifiedRegen *= 1.2f; break;
                    case BrakingLevel.ReducedAssist: modifiedAssist *= 0.5f; modifiedRegen *= 1.5f; break;
                    case BrakingLevel.PartialBrake: modifiedAssist *= 0.2f; modifiedRegen *= 2.0f; break;
                    case BrakingLevel.FullBrake: modifiedAssist *= 0f; modifiedRegen *= 3.0f; break;
                    case BrakingLevel.EmergencyLock: modifiedAssist *= 0f; modifiedRegen *= 5.0f; break;
                }

                modifiedRegen = Math.Min(modifiedRegen, 1.0f);

                Console.WriteLine($"    {level}: Assist={modifiedAssist:F2}, Regen={modifiedRegen:F2}");
            }

            Console.WriteLine("\n  Testing fall detection status text...");
            string status = fallDetector.GetStatusText();
            Console.WriteLine($"    Status contains 'Fall Detection': {status.Contains("Fall Detection")}");

            fallDetector.Reset();
            Console.WriteLine($"\n  After reset - Risk: {fallDetector.CurrentRiskLevel}, Braking: {fallDetector.CurrentBrakingLevel}");

            bool pass = assistAfter < assistBefore &&
                        regenAfter > regenBefore &&
                        fallDetector.CurrentRiskLevel == FallRiskLevel.None;

            Console.WriteLine($"\n  Fall Detection Test: {(pass ? "PASS" : "FAIL")}");
        }

        static void TestFullSimulationWithNewFeatures()
        {
            Console.WriteLine("--- Testing Full Integration with New Features ---");

            var simConfig = new SimulationConfig
            {
                gaitCycleDuration = 1.2f,
                bodyMass = 70f,
                slopeAngle = 5f,
                simulationFrequency = 100f
            };

            var exoConfig = new ExoskeletonConfig();
            var batteryState = new BatteryState();
            var gaitModel = new GaitModel(simConfig);
            var exoController = new ExoskeletonController(exoConfig, simConfig);
            var bms = new BatteryManagementSystem(batteryState);
            var ioManager = new InputOutputManager(simConfig);

            var fatigueModel = new FatigueModel(simConfig);
            var gaitLearner = new GaitLearner(simConfig);
            var fallDetector = new FallDetector(simConfig, gaitModel);

            ioManager.SetInputParameters(1.2f, 70f, 5f);

            Console.WriteLine("Running 30-second simulation with all features enabled...");
            Console.WriteLine($"  Slope: {simConfig.slopeAngle}°");
            Console.WriteLine($"  Body Mass: {simConfig.bodyMass}kg");

            float dt = 1f / simConfig.simulationFrequency;
            float time = 0f;
            float duration = 30f;

            float maxAssistRatio = 0f;
            float maxRegenRatio = 0f;
            int adaptiveChanges = 0;
            float lastAssistRatio = -1f;

            while (time < duration)
            {
                gaitModel.Update(time, dt);

                float gaitPhaseLeft = gaitModel.GetNormalizedPhase(time, Side.Left);
                float gaitPhaseRight = gaitModel.GetNormalizedPhase(time, Side.Right);

                fatigueModel.Update(dt, gaitModel.JointStates, 1.0f);
                gaitLearner.Update(time, gaitModel.JointStates, gaitPhaseLeft, gaitPhaseRight);
                fallDetector.Update(time, dt, gaitModel.JointStates, gaitPhaseLeft, gaitPhaseRight);

                foreach (Side side in new[] { Side.Left, Side.Right })
                {
                    foreach (JointType joint in new[] { JointType.Knee, JointType.Ankle })
                    {
                        float gaitPhase = side == Side.Left ? gaitPhaseLeft : gaitPhaseRight;

                        float assistRatio = exoConfig.assistRatio;
                        float regenRatio = exoConfig.regenerationRatio;

                        assistRatio = fatigueModel.GetAdjustedAssistRatio(assistRatio, joint);
                        regenRatio = fatigueModel.GetAdjustedRegenerationRatio(regenRatio, joint);

                        regenRatio = gaitLearner.GetAdjustedRegenerationRatio(regenRatio, joint, gaitPhase);
                        assistRatio = gaitLearner.GetPersonalizedAssistRatio(assistRatio, joint);

                        assistRatio = fallDetector.GetModifiedAssistRatio(assistRatio, joint);
                        regenRatio = fallDetector.GetModifiedRegenerationRatio(regenRatio, joint);

                        exoController.SetAdaptiveAssistRatio(side, joint, assistRatio);
                        exoController.SetAdaptiveRegenerationRatio(side, joint, regenRatio);

                        if (assistRatio > maxAssistRatio) maxAssistRatio = assistRatio;
                        if (regenRatio > maxRegenRatio) maxRegenRatio = regenRatio;

                        if (Math.Abs(assistRatio - lastAssistRatio) > 0.01f)
                        {
                            adaptiveChanges++;
                            lastAssistRatio = assistRatio;
                        }
                    }
                }

                exoController.Update(time, dt, gaitModel.JointStates, null);

                var (motorPower, generatorPower) = exoController.GetTotalPowers(gaitModel.JointStates);
                float netPower = motorPower - generatorPower;

                bms.Update(netPower, dt);
                ioManager.Update(time, dt, gaitModel, exoController, bms);

                if (Math.Abs(time - 10f) < dt / 2 || Math.Abs(time - 20f) < dt / 2)
                {
                    Console.WriteLine($"    t={time:F0}s | " +
                                      $"Fatigue: {fatigueModel.overallFatigueLevel * 100:F0}% | " +
                                      $"SOC: {batteryState.currentSOC * 100:F1}% | " +
                                      $"Assist: {maxAssistRatio:F2} | " +
                                      $"Stability: {fallDetector.StabilityMetrics.overallStabilityScore * 100:F0}%");
                }

                time += dt;
            }

            ioManager.FinalizeSimulation();
            var result = ioManager.Result;

            Console.WriteLine($"\n  Simulation Results:");
            Console.WriteLine($"    Duration: {duration:F0}s");
            Console.WriteLine($"    Net Energy Consumption: {result.netEnergyConsumption:F1}J");
            Console.WriteLine($"    Recovered Energy: {result.totalGeneratorPower * duration / result.timeStepCount:F1}W avg");
            Console.WriteLine($"    Final SOC: {result.finalSOC * 100:F1}%");

            Console.WriteLine($"\n  New Feature Performance:");
            Console.WriteLine($"    Fatigue Model - Final Level: {fatigueModel.GetFatigueLevel()} ({fatigueModel.overallFatigueLevel * 100:F1}%)");
            Console.WriteLine($"    Fatigue Model - Max Assist Boost: +{(maxAssistRatio / exoConfig.assistRatio - 1) * 100:F0}%");
            Console.WriteLine($"    Gait Learning - Training Cycles: {gaitLearner.PersonalizedModel.trainingCycles}");
            Console.WriteLine($"    Gait Learning - Confidence: {gaitLearner.PersonalizedModel.learningConfidence * 100:F1}%");
            Console.WriteLine($"    Gait Learning - Max Regen Boost: +{(maxRegenRatio / exoConfig.regenerationRatio - 1) * 100:F0}%");
            Console.WriteLine($"    Fall Detection - Final Risk: {fallDetector.CurrentRiskLevel}");
            Console.WriteLine($"    Fall Detection - Stability Score: {fallDetector.StabilityMetrics.overallStabilityScore * 100:F1}%");
            Console.WriteLine($"    Adaptive Changes: {adaptiveChanges}");

            bool pass = result.netEnergyConsumption > 0 &&
                        result.finalSOC > 0.1f &&
                        maxAssistRatio > exoConfig.assistRatio &&
                        fallDetector.CurrentRiskLevel == FallRiskLevel.None;

            Console.WriteLine($"\n  Full Integration Test: {(pass ? "PASS" : "FAIL")}");
        }
    }
}
#endif
