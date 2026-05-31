using UnityEngine;
using GaitSimulation.Simulation;
using GaitSimulation.Visualization;
using GaitSimulation.Tests;

namespace GaitSimulation.Bootstrap
{
    public class GaitSimulationBootstrap : MonoBehaviour
    {
        [Header("Simulation Settings")]
        public float gaitCycleDuration = 1.2f;
        public float bodyMass = 70f;
        public float slopeAngle = 0f;
        public float simulationDuration = 10f;
        public bool useDynamicProgramming = true;
        public bool autoStartSimulation = false;
        public bool runTests = true;

        private SimulationManager _simulationManager;
        private JointPowerGraph _jointPowerGraph;
        private EnergyFlowGraph _energyFlowGraph;
        private SimulationTester _tester;

        private void Awake()
        {
            InitializeSimulation();
            SetupVisualization();
            SetupTester();

            Debug.Log("=== Gait Simulation System Initialized ===");
            Debug.Log($"Configuration: {gaitCycleDuration}s cycle, {bodyMass}kg, {slopeAngle}° slope");
            Debug.Log($"Optimization: {(useDynamicProgramming ? "Enabled" : "Disabled")}");
        }

        private void Start()
        {
            if (autoStartSimulation && _simulationManager != null)
            {
                _simulationManager.StartSimulation();
            }
        }

        private void InitializeSimulation()
        {
            GameObject simObj = new GameObject("SimulationManager");
            _simulationManager = simObj.AddComponent<SimulationManager>();

            _simulationManager.gaitCycleDuration = gaitCycleDuration;
            _simulationManager.bodyMass = bodyMass;
            _simulationManager.slopeAngle = slopeAngle;
            _simulationManager.simulationDuration = simulationDuration;
            _simulationManager.useDynamicProgramming = useDynamicProgramming;
        }

        private void SetupVisualization()
        {
            GameObject graphContainer = new GameObject("Visualization");

            GameObject powerGraphObj = new GameObject("JointPowerGraph");
            powerGraphObj.transform.SetParent(graphContainer.transform);
            _jointPowerGraph = powerGraphObj.AddComponent<JointPowerGraph>();
            _jointPowerGraph.graphOffset = new Vector2(20f, 250f);
            _jointPowerGraph.maxDataPoints = 500;

            GameObject flowGraphObj = new GameObject("EnergyFlowGraph");
            flowGraphObj.transform.SetParent(graphContainer.transform);
            _energyFlowGraph = flowGraphObj.AddComponent<EnergyFlowGraph>();
            _energyFlowGraph.graphOffset = new Vector2(20f, 20f);
            _energyFlowGraph.maxDataPoints = 500;

            if (_simulationManager != null)
            {
                _simulationManager.jointPowerGraph = _jointPowerGraph;
                _simulationManager.energyFlowGraph = _energyFlowGraph;
            }
        }

        private void SetupTester()
        {
            if (!runTests) return;

            GameObject testerObj = new GameObject("SimulationTester");
            _tester = testerObj.AddComponent<SimulationTester>();
            _tester.runTestsOnStart = runTests;
            _tester.testDuration = 5f;
        }

        public SimulationManager GetSimulationManager()
        {
            return _simulationManager;
        }

        public JointPowerGraph GetJointPowerGraph()
        {
            return _jointPowerGraph;
        }

        public EnergyFlowGraph GetEnergyFlowGraph()
        {
            return _energyFlowGraph;
        }

        public SimulationTester GetTester()
        {
            return _tester;
        }
    }
}
