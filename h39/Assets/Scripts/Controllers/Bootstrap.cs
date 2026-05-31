using UnityEngine;
using UnityEngine.UI;
using System.IO;
using SoleFrictionSim.UI;
using SoleFrictionSim.Compute;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.Controllers
{
    public class Bootstrap : MonoBehaviour
    {
        [SerializeField] private ComputeShader _bemComputeShader;
        [SerializeField] private ComputeShader _frictionComputeShader;

        private SimulationController _simulationController;
        private SceneController _sceneController;
        private ParameterPanel _parameterPanel;
        private VisualizationPanel _visualizationPanel;

        private void Awake()
        {
            LoadResources();
            CreateSceneHierarchy();
            SetupUI();
            CreateControllers();
            BindReferences();
        }

        private void Start()
        {
            Debug.Log("Sole Friction Simulation System initialized successfully.");
            Debug.Log("Use mouse to rotate (right), pan (middle), zoom (scroll) the 3D view.");
            Debug.Log("Adjust parameters on the left panel and click 'Start Simulation' to begin.");
        }

        private void LoadResources()
        {
            if (_bemComputeShader == null)
            {
                string computePath = "ComputeShaders/BEMSolver";
                _bemComputeShader = Resources.Load<ComputeShader>(computePath);
                if (_bemComputeShader == null)
                {
                    string fullPath = Path.Combine(Application.dataPath, "ComputeShaders/BEMSolver.compute");
                    if (File.Exists(fullPath))
                    {
                        Debug.LogWarning($"BEM Compute Shader found at {fullPath} but not in Resources folder.");
                    }
                    else
                    {
                        Debug.LogError($"BEM Compute Shader not found. Expected at: Assets/{computePath}.compute");
                    }
                }
            }

            if (_frictionComputeShader == null)
            {
                string computePath = "ComputeShaders/Friction";
                _frictionComputeShader = Resources.Load<ComputeShader>(computePath);
                if (_frictionComputeShader == null)
                {
                    string fullPath = Path.Combine(Application.dataPath, "ComputeShaders/Friction.compute");
                    if (File.Exists(fullPath))
                    {
                        Debug.LogWarning($"Friction Compute Shader found at {fullPath} but not in Resources folder.");
                    }
                    else
                    {
                        Debug.LogError($"Friction Compute Shader not found. Expected at: Assets/{computePath}.compute");
                    }
                }
            }
        }

        private void CreateSceneHierarchy()
        {
            GameObject sceneRoot = new GameObject("SimulationSystem");
            transform.SetParent(sceneRoot.transform);

            CreateCamera(sceneRoot.transform);
            CreateLights(sceneRoot.transform);
            CreateGround(sceneRoot.transform);
            CreateSoleContainer(sceneRoot.transform);
            CreateEventSystem(sceneRoot.transform);
        }

        private void CreateCamera(Transform parent)
        {
            GameObject cameraObj = new GameObject("MainCamera");
            cameraObj.transform.SetParent(parent, false);
            cameraObj.tag = "MainCamera";

            Camera camera = cameraObj.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.1f, 0.1f, 0.18f);
            camera.fieldOfView = 45f;
            camera.nearClipPlane = 0.01f;
            camera.farClipPlane = 10f;

            cameraObj.AddComponent<AudioListener>();

            GameObject targetObj = new GameObject("CameraTarget");
            targetObj.transform.SetParent(parent, false);
            targetObj.transform.position = Vector3.zero;

            _sceneController = cameraObj.AddComponent<SceneController>();
            typeof(SceneController).GetField("_mainCamera",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_sceneController, camera);
            typeof(SceneController).GetField("_target",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_sceneController, targetObj.transform);
        }

        private void CreateLights(Transform parent)
        {
            GameObject lightsRoot = new GameObject("Lights");
            lightsRoot.transform.SetParent(parent, false);

            GameObject mainLightObj = new GameObject("MainLight");
            mainLightObj.transform.SetParent(lightsRoot.transform, false);
            Light mainLight = mainLightObj.AddComponent<Light>();
            mainLight.type = LightType.Directional;
            mainLight.intensity = 1.2f;
            mainLight.color = new Color(1f, 0.98f, 0.95f);
            mainLight.transform.rotation = Quaternion.Euler(45f, 45f, 0f);
            mainLight.shadows = LightShadows.Soft;
            mainLight.shadowStrength = 0.7f;

            GameObject fillLightObj = new GameObject("FillLight");
            fillLightObj.transform.SetParent(lightsRoot.transform, false);
            Light fillLight = fillLightObj.AddComponent<Light>();
            fillLight.type = LightType.Directional;
            fillLight.intensity = 0.4f;
            fillLight.color = new Color(0.7f, 0.8f, 1f);
            fillLight.transform.rotation = Quaternion.Euler(45f, -45f, 0f);
            fillLight.shadows = LightShadows.None;

            GameObject rimLightObj = new GameObject("RimLight");
            rimLightObj.transform.SetParent(lightsRoot.transform, false);
            Light rimLight = rimLightObj.AddComponent<Light>();
            rimLight.type = LightType.Directional;
            rimLight.intensity = 0.6f;
            rimLight.color = new Color(1f, 0.9f, 0.7f);
            rimLight.transform.rotation = Quaternion.Euler(-30f, 180f, 0f);
            rimLight.shadows = LightShadows.None;

            typeof(SceneController).GetField("_mainLight",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_sceneController, mainLight);
            typeof(SceneController).GetField("_fillLight",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_sceneController, fillLight);
            typeof(SceneController).GetField("_rimLight",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_sceneController, rimLight);
        }

        private void CreateGround(Transform parent)
        {
            GameObject groundObj = GameObject.CreatePrimitive(PrimitiveType.Plane);
            groundObj.name = "GroundPlane";
            groundObj.transform.SetParent(parent, false);
            groundObj.transform.localScale = new Vector3(2f, 1f, 2f);

            Material groundMaterial = new Material(Shader.Find("Standard"));
            groundMaterial.color = new Color(0.15f, 0.15f, 0.15f);
            groundMaterial.SetFloat("_Glossiness", 0.1f);
            groundMaterial.SetFloat("_Metallic", 0f);

            Renderer renderer = groundObj.GetComponent<Renderer>();
            renderer.material = groundMaterial;

            typeof(SceneController).GetField("_groundPlane",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_sceneController, groundObj);
            typeof(SceneController).GetField("_groundMaterial",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_sceneController, groundMaterial);
        }

        private void CreateSoleContainer(Transform parent)
        {
            GameObject soleContainer = new GameObject("SoleContainer");
            soleContainer.transform.SetParent(parent, false);
            soleContainer.transform.position = new Vector3(0f, 0.1f, 0f);
        }

        private void CreateEventSystem(Transform parent)
        {
            GameObject eventSystemObj = new GameObject("EventSystem");
            eventSystemObj.transform.SetParent(parent, false);
            eventSystemObj.AddComponent<UnityEngine.EventSystems.EventSystem>();
            eventSystemObj.AddComponent<UnityEngine.EventSystems.StandaloneInputModule>();
        }

        private void SetupUI()
        {
            GameObject canvasObj = new GameObject("UICanvas");
            Canvas canvas = canvasObj.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;

            CanvasScaler scaler = canvasObj.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;

            canvasObj.AddComponent<GraphicRaycaster>();

            CreateParameterPanel(canvasObj.transform);
            CreateVisualizationPanel(canvasObj.transform);
            CreateTitleBar(canvasObj.transform);
        }

        private void CreateParameterPanel(Transform parent)
        {
            GameObject panelObj = new GameObject("ParameterPanel");
            panelObj.transform.SetParent(parent, false);

            RectTransform rect = panelObj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 0f);
            rect.anchorMax = new Vector2(0f, 1f);
            rect.pivot = new Vector2(0f, 0.5f);
            rect.sizeDelta = new Vector2(300f, 0f);
            rect.offsetMin = new Vector2(10f, 10f);
            rect.offsetMax = new Vector2(0f, -10f);

            Image background = panelObj.AddComponent<Image>();
            background.color = new Color(0.08f, 0.08f, 0.12f, 0.9f);

            _parameterPanel = panelObj.AddComponent<ParameterPanel>();
            CreateParameterPanelUI(panelObj.transform);
        }

        private void CreateParameterPanelUI(Transform parent)
        {
            float yPos = -20f;
            float spacing = 55f;
            float labelWidth = 120f;
            float sliderWidth = 150f;

            CreateSectionTitle(parent, "Pattern Parameters", ref yPos);
            _parameterPanel.GetType().GetField("_patternTypeDropdown",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateDropdown(parent, "Pattern Type", ref yPos, labelWidth, sliderWidth,
                    new string[] { "Herringbone", "Wave", "Block" }));

            _parameterPanel.GetType().GetField("_patternDepthSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Pattern Depth", ref yPos,
                    labelWidth, sliderWidth, 0.5f, 10f, 3f, " mm"));

            _parameterPanel.GetType().GetField("_patternSpacingSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Pattern Spacing", ref yPos,
                    labelWidth, sliderWidth, 2f, 20f, 8f, " mm"));

            _parameterPanel.GetType().GetField("_patternAngleSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Pattern Angle", ref yPos,
                    labelWidth, sliderWidth, 0f, 90f, 45f, "°"));

            _parameterPanel.GetType().GetField("_soleWidthSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Sole Width", ref yPos,
                    labelWidth, sliderWidth, 5f, 15f, 10f, " cm"));

            _parameterPanel.GetType().GetField("_soleLengthSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Sole Length", ref yPos,
                    labelWidth, sliderWidth, 20f, 35f, 28f, " cm"));

            yPos -= spacing * 0.5f;
            CreateSectionTitle(parent, "Rubber Material", ref yPos);
            _parameterPanel.GetType().GetField("_shoreHardnessSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Shore Hardness", ref yPos,
                    labelWidth, sliderWidth, 30f, 80f, 60f, ""));

            _parameterPanel.GetType().GetField("_elasticModulusSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Elastic Modulus", ref yPos,
                    labelWidth, sliderWidth, 1f, 20f, 5f, " MPa"));

            _parameterPanel.GetType().GetField("_lossFactorSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Loss Factor", ref yPos,
                    labelWidth, sliderWidth, 0.1f, 1f, 0.3f, ""));

            yPos -= spacing * 0.5f;
            CreateSectionTitle(parent, "Surface Roughness", ref yPos);
            _parameterPanel.GetType().GetField("_hurstExponentSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Hurst Exponent", ref yPos,
                    labelWidth, sliderWidth, 0.1f, 0.9f, 0.7f, ""));

            _parameterPanel.GetType().GetField("_rmsRoughnessSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "RMS Roughness", ref yPos,
                    labelWidth, sliderWidth, 1f, 100f, 20f, " μm"));

            yPos -= spacing * 0.5f;
            CreateSectionTitle(parent, "Ground Surface", ref yPos);
            _parameterPanel.GetType().GetField("_groundTypeDropdown",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateDropdown(parent, "Ground Type", ref yPos, labelWidth, sliderWidth,
                    new string[] { "Dry Asphalt", "Wet Asphalt", "Dry Tile", "Wet Tile", "Ice" }));

            _parameterPanel.GetType().GetField("_waterFilmSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Water Film", ref yPos,
                    labelWidth, sliderWidth, 0f, 500f, 50f, " μm"));

            yPos -= spacing * 0.5f;
            CreateSectionTitle(parent, "Simulation", ref yPos);
            _parameterPanel.GetType().GetField("_normalLoadSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Normal Load", ref yPos,
                    labelWidth, sliderWidth, 100f, 1000f, 500f, " N"));

            _parameterPanel.GetType().GetField("_bemResolutionSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "BEM Resolution", ref yPos,
                    labelWidth, sliderWidth, 32f, 128f, 64f, ""));

            _parameterPanel.GetType().GetField("_hydrodynamicsToggle",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateToggle(parent, "Hydrodynamics", ref yPos, labelWidth, true));

            _parameterPanel.GetType().GetField("_gpuAccelerationToggle",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateToggle(parent, "GPU Acceleration", ref yPos, labelWidth, true));

            yPos -= spacing * 0.5f;
            CreateSectionTitle(parent, "Velocity Range", ref yPos);
            _parameterPanel.GetType().GetField("_minVelocitySlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Min Velocity", ref yPos,
                    labelWidth, sliderWidth, 1e-6f, 0.001f, 1e-6f, " m/s"));

            _parameterPanel.GetType().GetField("_maxVelocitySlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Max Velocity", ref yPos,
                    labelWidth, sliderWidth, 1f, 100f, 10f, " m/s"));

            _parameterPanel.GetType().GetField("_velocitySamplesSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Samples", ref yPos,
                    labelWidth, sliderWidth, 50f, 300f, 100f, ""));

            yPos -= spacing * 0.5f;
            CreateSectionTitle(parent, "Stick-Slip Model", ref yPos);
            _parameterPanel.GetType().GetField("_stickSlipToggle",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateToggle(parent, "Enable Stick-Slip", ref yPos, labelWidth, true));

            _parameterPanel.GetType().GetField("_staticFrictionMultiplierSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Static Multiplier", ref yPos,
                    labelWidth, sliderWidth, 0.1f, 5f, 1.8f, "x"));

            _parameterPanel.GetType().GetField("_transitionVelocitySlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Transition V", ref yPos,
                    labelWidth, sliderWidth, 0.0001f, 0.01f, 0.001f, " m/s"));

            _parameterPanel.GetType().GetField("_transitionSharpnessSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Sharpness", ref yPos,
                    labelWidth, sliderWidth, 0.1f, 2f, 0.8f, ""));

            yPos -= spacing * 0.5f;
            CreateSectionTitle(parent, "Edge Correction", ref yPos);
            _parameterPanel.GetType().GetField("_edgeSmoothingToggle",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateToggle(parent, "Edge Smoothing", ref yPos, labelWidth, true));

            _parameterPanel.GetType().GetField("_edgeSmoothingRadiusSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Smooth Radius", ref yPos,
                    labelWidth, sliderWidth, 0.5f, 3f, 1.5f, " cells"));

            _parameterPanel.GetType().GetField("_edgeStressReductionSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Stress Reduction", ref yPos,
                    labelWidth, sliderWidth, 0.1f, 1f, 0.6f, ""));

            yPos -= spacing * 0.5f;
            CreateSectionTitle(parent, "Wear Simulation", ref yPos);
            _parameterPanel.GetType().GetField("_wearSimulationToggle",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateToggle(parent, "Enable Wear", ref yPos, labelWidth, true));

            _parameterPanel.GetType().GetField("_wearCoefficientSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Wear Coeff", ref yPos,
                    labelWidth, sliderWidth, 1e-8f, 1e-5f, 1e-7f, ""));

            _parameterPanel.GetType().GetField("_slidingDistanceSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Sliding Dist", ref yPos,
                    labelWidth, sliderWidth, 1f, 10000f, 1000f, " m"));

            yPos -= spacing * 0.5f;
            CreateSectionTitle(parent, "Thermal Coupling", ref yPos);
            _parameterPanel.GetType().GetField("_thermalCouplingToggle",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateToggle(parent, "Enable Thermal", ref yPos, labelWidth, true));

            _parameterPanel.GetType().GetField("_ambientTempSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Ambient Temp", ref yPos,
                    labelWidth, sliderWidth, -20f, 60f, 25f, " °C"));

            _parameterPanel.GetType().GetField("_heatPartitionSlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateSliderWithLabel(parent, "Heat Partition", ref yPos,
                    labelWidth, sliderWidth, 0.1f, 0.9f, 0.5f, ""));

            yPos -= spacing * 0.5f;
            CreateSectionTitle(parent, "Controls", ref yPos);
            _parameterPanel.GetType().GetField("_generatePatternButton",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateButton(parent, "Generate Pattern", ref yPos, new Color(0.2f, 0.6f, 0.3f)));

            _parameterPanel.GetType().GetField("_importStlButton",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateButton(parent, "Import STL", ref yPos, new Color(0.2f, 0.4f, 0.6f)));

            _parameterPanel.GetType().GetField("_startSimulationButton",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateButton(parent, "Start Simulation", ref yPos, new Color(0.8f, 0.3f, 0.2f)));

            _parameterPanel.GetType().GetField("_resetButton",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateButton(parent, "Reset", ref yPos, new Color(0.4f, 0.4f, 0.4f)));

            _parameterPanel.GetType().GetField("_exportDataButton",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateButton(parent, "Export CSV", ref yPos, new Color(0.3f, 0.5f, 0.7f)));

            _parameterPanel.GetType().GetField("_exportStlButton",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateButton(parent, "Export Pattern CAD", ref yPos, new Color(0.5f, 0.3f, 0.7f)));

            _parameterPanel.GetType().GetField("_exportWornButton",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateButton(parent, "Export Worn CAD", ref yPos, new Color(0.7f, 0.5f, 0.3f)));

            yPos -= spacing * 0.5f;
            CreateProgressBar(parent, ref yPos);

            _parameterPanel.GetType().GetField("_statusText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, CreateLabel(parent, "Status: Ready", ref yPos, 280f, TextAnchor.UpperLeft, 14));
        }

        private void CreateSectionTitle(Transform parent, string title, ref float yPos)
        {
            GameObject titleObj = new GameObject("SectionTitle");
            titleObj.transform.SetParent(parent, false);

            RectTransform rect = titleObj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 1f);
            rect.anchorMax = new Vector2(1f, 1f);
            rect.pivot = new Vector2(0f, 1f);
            rect.sizeDelta = new Vector2(0f, 25f);
            rect.anchoredPosition = new Vector2(10f, yPos);

            Text text = titleObj.AddComponent<Text>();
            text.text = title;
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.fontSize = 14;
            text.fontStyle = FontStyle.Bold;
            text.color = new Color(0.4f, 0.8f, 1f);
            text.alignment = TextAnchor.MiddleLeft;

            GameObject lineObj = new GameObject("Line");
            lineObj.transform.SetParent(titleObj.transform, false);
            RectTransform lineRect = lineObj.AddComponent<RectTransform>();
            lineRect.anchorMin = new Vector2(0f, 0f);
            lineRect.anchorMax = new Vector2(1f, 0f);
            lineRect.pivot = new Vector2(0.5f, 0f);
            lineRect.sizeDelta = new Vector2(0f, 1f);
            lineRect.anchoredPosition = Vector2.zero;

            Image lineImage = lineObj.AddComponent<Image>();
            lineImage.color = new Color(0.4f, 0.8f, 1f, 0.5f);

            yPos -= 35f;
        }

        private Slider CreateSliderWithLabel(Transform parent, string label, ref float yPos,
            float labelWidth, float sliderWidth, float min, float max, float defaultValue, string unit)
        {
            GameObject container = new GameObject($"{label}_Slider");
            container.transform.SetParent(parent, false);

            RectTransform rect = container.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 1f);
            rect.anchorMax = new Vector2(1f, 1f);
            rect.pivot = new Vector2(0f, 1f);
            rect.sizeDelta = new Vector2(0f, 45f);
            rect.anchoredPosition = new Vector2(10f, yPos);

            Text labelText = CreateLabel(container.transform, label, new Vector2(10f, -10f), labelWidth, 20f, TextAnchor.MiddleLeft, 12);
            Text valueText = CreateLabel(container.transform, $"{defaultValue:0.0}{unit}", new Vector2(labelWidth + sliderWidth - 80f, -10f), 80f, 20f, TextAnchor.MiddleRight, 12);

            GameObject sliderObj = new GameObject("Slider");
            sliderObj.transform.SetParent(container.transform, false);
            RectTransform sliderRect = sliderObj.AddComponent<RectTransform>();
            sliderRect.anchorMin = new Vector2(0f, 0f);
            sliderRect.anchorMax = new Vector2(0f, 0f);
            sliderRect.pivot = new Vector2(0f, 0.5f);
            sliderRect.sizeDelta = new Vector2(sliderWidth, 20f);
            sliderRect.anchoredPosition = new Vector2(labelWidth + 10f, 12f);

            Slider slider = sliderObj.AddComponent<Slider>();
            slider.minValue = min;
            slider.maxValue = max;
            slider.value = defaultValue;

            GameObject backgroundObj = new GameObject("Background");
            backgroundObj.transform.SetParent(sliderObj.transform, false);
            RectTransform bgRect = backgroundObj.AddComponent<RectTransform>();
            bgRect.anchorMin = Vector2.zero;
            bgRect.anchorMax = Vector2.one;
            bgRect.sizeDelta = Vector2.zero;
            Image bgImage = backgroundObj.AddComponent<Image>();
            bgImage.color = new Color(0.2f, 0.2f, 0.25f);

            GameObject fillArea = new GameObject("Fill Area");
            fillArea.transform.SetParent(sliderObj.transform, false);
            RectTransform fillAreaRect = fillArea.AddComponent<RectTransform>();
            fillAreaRect.anchorMin = new Vector2(0f, 0.5f);
            fillAreaRect.anchorMax = new Vector2(1f, 0.5f);
            fillAreaRect.pivot = new Vector2(0f, 0.5f);
            fillAreaRect.sizeDelta = new Vector2(-20f, 10f);
            fillAreaRect.anchoredPosition = Vector2.zero;

            GameObject fill = new GameObject("Fill");
            fill.transform.SetParent(fillArea.transform, false);
            RectTransform fillRect = fill.AddComponent<RectTransform>();
            fillRect.anchorMin = Vector2.zero;
            fillRect.anchorMax = Vector2.one;
            fillRect.sizeDelta = Vector2.zero;
            Image fillImage = fill.AddComponent<Image>();
            fillImage.color = new Color(0.3f, 0.7f, 1f);

            GameObject handleSlideArea = new GameObject("Handle Slide Area");
            handleSlideArea.transform.SetParent(sliderObj.transform, false);
            RectTransform handleAreaRect = handleSlideArea.AddComponent<RectTransform>();
            handleAreaRect.anchorMin = new Vector2(0f, 0.5f);
            handleAreaRect.anchorMax = new Vector2(1f, 0.5f);
            handleAreaRect.pivot = new Vector2(0.5f, 0.5f);
            handleAreaRect.sizeDelta = new Vector2(-20f, 0f);
            handleAreaRect.anchoredPosition = Vector2.zero;

            GameObject handle = new GameObject("Handle");
            handle.transform.SetParent(handleSlideArea.transform, false);
            RectTransform handleRect = handle.AddComponent<RectTransform>();
            handleRect.anchorMin = new Vector2(0.5f, 0.5f);
            handleRect.anchorMax = new Vector2(0.5f, 0.5f);
            handleRect.pivot = new Vector2(0.5f, 0.5f);
            handleRect.sizeDelta = new Vector2(20f, 20f);
            Image handleImage = handle.AddComponent<Image>();
            handleImage.color = new Color(0.8f, 0.9f, 1f);

            slider.fillRect = fillRect;
            slider.handleRect = handleRect;
            slider.targetGraphic = handleImage;

            string valueFieldName = label.Replace(" ", "") + "Value";
            _parameterPanel.GetType().GetField(valueFieldName,
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, valueText);

            yPos -= 50f;
            return slider;
        }

        private Dropdown CreateDropdown(Transform parent, string label, ref float yPos,
            float labelWidth, float dropdownWidth, string[] options)
        {
            GameObject container = new GameObject($"{label}_Dropdown");
            container.transform.SetParent(parent, false);

            RectTransform rect = container.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 1f);
            rect.anchorMax = new Vector2(1f, 1f);
            rect.pivot = new Vector2(0f, 1f);
            rect.sizeDelta = new Vector2(0f, 45f);
            rect.anchoredPosition = new Vector2(10f, yPos);

            CreateLabel(container.transform, label, new Vector2(10f, -10f), labelWidth, 20f, TextAnchor.MiddleLeft, 12);

            GameObject dropdownObj = new GameObject("Dropdown");
            dropdownObj.transform.SetParent(container.transform, false);
            RectTransform dropdownRect = dropdownObj.AddComponent<RectTransform>();
            dropdownRect.anchorMin = new Vector2(0f, 0f);
            dropdownRect.anchorMax = new Vector2(0f, 0f);
            dropdownRect.pivot = new Vector2(0f, 0.5f);
            dropdownRect.sizeDelta = new Vector2(dropdownWidth, 30f);
            dropdownRect.anchoredPosition = new Vector2(labelWidth + 10f, 15f);

            Image dropdownImage = dropdownObj.AddComponent<Image>();
            dropdownImage.color = new Color(0.25f, 0.25f, 0.3f);

            Dropdown dropdown = dropdownObj.AddComponent<Dropdown>();

            GameObject labelObj = new GameObject("Label");
            labelObj.transform.SetParent(dropdownObj.transform, false);
            RectTransform labelRect = labelObj.AddComponent<RectTransform>();
            labelRect.anchorMin = new Vector2(0f, 0f);
            labelRect.anchorMax = new Vector2(1f, 1f);
            labelRect.offsetMin = new Vector2(10f, 2f);
            labelRect.offsetMax = new Vector2(-30f, -2f);
            Text labelText = labelObj.AddComponent<Text>();
            labelText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            labelText.fontSize = 12;
            labelText.color = Color.white;
            labelText.alignment = TextAnchor.MiddleLeft;

            GameObject arrowObj = new GameObject("Arrow");
            arrowObj.transform.SetParent(dropdownObj.transform, false);
            RectTransform arrowRect = arrowObj.AddComponent<RectTransform>();
            arrowRect.anchorMin = new Vector2(1f, 0.5f);
            arrowRect.anchorMax = new Vector2(1f, 0.5f);
            arrowRect.pivot = new Vector2(1f, 0.5f);
            arrowRect.sizeDelta = new Vector2(20f, 20f);
            arrowRect.anchoredPosition = new Vector2(-5f, 0f);
            Text arrowText = arrowObj.AddComponent<Text>();
            arrowText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            arrowText.text = "▼";
            arrowText.fontSize = 10;
            arrowText.color = Color.white;
            arrowText.alignment = TextAnchor.MiddleCenter;

            GameObject template = new GameObject("Template");
            template.transform.SetParent(dropdownObj.transform, false);
            template.SetActive(false);
            RectTransform templateRect = template.AddComponent<RectTransform>();
            templateRect.anchorMin = new Vector2(0f, 1f);
            templateRect.anchorMax = new Vector2(1f, 1f);
            templateRect.pivot = new Vector2(0.5f, 1f);
            templateRect.sizeDelta = new Vector2(0f, 150f);
            templateRect.anchoredPosition = new Vector2(0f, 2f);

            Image templateImage = template.AddComponent<Image>();
            templateImage.color = new Color(0.2f, 0.2f, 0.25f);

            GameObject viewport = new GameObject("Viewport");
            viewport.transform.SetParent(template.transform, false);
            RectTransform viewportRect = viewport.AddComponent<RectTransform>();
            viewportRect.anchorMin = Vector2.zero;
            viewportRect.anchorMax = Vector2.one;
            viewportRect.offsetMin = new Vector2(4f, 4f);
            viewportRect.offsetMax = new Vector2(-4f, -4f);
            viewport.AddComponent<Mask>().showMaskGraphic = false;

            GameObject content = new GameObject("Content");
            content.transform.SetParent(viewport.transform, false);
            RectTransform contentRect = content.AddComponent<RectTransform>();
            contentRect.anchorMin = new Vector2(0f, 1f);
            contentRect.anchorMax = new Vector2(1f, 1f);
            contentRect.pivot = new Vector2(0.5f, 1f);
            contentRect.sizeDelta = new Vector2(0f, 30f);
            contentRect.anchoredPosition = Vector2.zero;

            GameObject item = new GameObject("Item");
            item.transform.SetParent(content.transform, false);
            RectTransform itemRect = item.AddComponent<RectTransform>();
            itemRect.anchorMin = new Vector2(0f, 0.5f);
            itemRect.anchorMax = new Vector2(1f, 0.5f);
            itemRect.pivot = new Vector2(0.5f, 0.5f);
            itemRect.sizeDelta = new Vector2(0f, 30f);

            Image itemImage = item.AddComponent<Image>();
            itemImage.color = new Color(0.3f, 0.3f, 0.35f);

            GameObject itemLabel = new GameObject("ItemLabel");
            itemLabel.transform.SetParent(item.transform, false);
            RectTransform itemLabelRect = itemLabel.AddComponent<RectTransform>();
            itemLabelRect.anchorMin = Vector2.zero;
            itemLabelRect.anchorMax = Vector2.one;
            itemLabelRect.offsetMin = new Vector2(10f, 0f);
            itemLabelRect.offsetMax = new Vector2(-10f, 0f);
            Text itemLabelText = itemLabel.AddComponent<Text>();
            itemLabelText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            itemLabelText.fontSize = 12;
            itemLabelText.color = Color.white;
            itemLabelText.alignment = TextAnchor.MiddleLeft;

            GameObject itemCheckmark = new GameObject("ItemCheckmark");
            itemCheckmark.transform.SetParent(item.transform, false);
            RectTransform checkmarkRect = itemCheckmark.AddComponent<RectTransform>();
            checkmarkRect.anchorMin = new Vector2(1f, 0.5f);
            checkmarkRect.anchorMax = new Vector2(1f, 0.5f);
            checkmarkRect.pivot = new Vector2(1f, 0.5f);
            checkmarkRect.sizeDelta = new Vector2(20f, 20f);
            checkmarkRect.anchoredPosition = new Vector2(-10f, 0f);
            Text checkmarkText = itemCheckmark.AddComponent<Text>();
            checkmarkText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            checkmarkText.text = "✓";
            checkmarkText.fontSize = 14;
            checkmarkText.color = new Color(0.4f, 0.8f, 1f);
            checkmarkText.alignment = TextAnchor.MiddleCenter;

            dropdown.targetGraphic = dropdownImage;
            dropdown.template = templateRect;
            dropdown.captionText = labelText;
            dropdown.itemText = itemLabelText;

            foreach (string option in options)
            {
                dropdown.options.Add(new Dropdown.OptionData(option));
            }
            dropdown.value = 0;

            yPos -= 50f;
            return dropdown;
        }

        private Toggle CreateToggle(Transform parent, string label, ref float yPos, float labelWidth, bool defaultValue)
        {
            GameObject container = new GameObject($"{label}_Toggle");
            container.transform.SetParent(parent, false);

            RectTransform rect = container.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 1f);
            rect.anchorMax = new Vector2(1f, 1f);
            rect.pivot = new Vector2(0f, 1f);
            rect.sizeDelta = new Vector2(0f, 40f);
            rect.anchoredPosition = new Vector2(10f, yPos);

            CreateLabel(container.transform, label, new Vector2(10f, -10f), labelWidth, 20f, TextAnchor.MiddleLeft, 12);

            GameObject toggleObj = new GameObject("Toggle");
            toggleObj.transform.SetParent(container.transform, false);
            RectTransform toggleRect = toggleObj.AddComponent<RectTransform>();
            toggleRect.anchorMin = new Vector2(0f, 0f);
            toggleRect.anchorMax = new Vector2(0f, 0f);
            toggleRect.pivot = new Vector2(0f, 0.5f);
            toggleRect.sizeDelta = new Vector2(30f, 30f);
            toggleRect.anchoredPosition = new Vector2(labelWidth + 10f, 15f);

            Toggle toggle = toggleObj.AddComponent<Toggle>();
            toggle.isOn = defaultValue;

            Image background = toggleObj.AddComponent<Image>();
            background.color = new Color(0.25f, 0.25f, 0.3f);

            GameObject checkmark = new GameObject("Checkmark");
            checkmark.transform.SetParent(toggleObj.transform, false);
            RectTransform checkmarkRect = checkmark.AddComponent<RectTransform>();
            checkmarkRect.anchorMin = Vector2.zero;
            checkmarkRect.anchorMax = Vector2.one;
            checkmarkRect.offsetMin = new Vector2(5f, 5f);
            checkmarkRect.offsetMax = new Vector2(-5f, -5f);
            Text checkmarkText = checkmark.AddComponent<Text>();
            checkmarkText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            checkmarkText.text = "✓";
            checkmarkText.fontSize = 16;
            checkmarkText.color = new Color(0.4f, 0.8f, 1f);
            checkmarkText.alignment = TextAnchor.MiddleCenter;

            toggle.graphic = checkmarkText;
            toggle.targetGraphic = background;

            yPos -= 45f;
            return toggle;
        }

        private Button CreateButton(Transform parent, string label, ref float yPos, Color color)
        {
            GameObject buttonObj = new GameObject($"{label}_Button");
            buttonObj.transform.SetParent(parent, false);

            RectTransform rect = buttonObj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 1f);
            rect.anchorMax = new Vector2(1f, 1f);
            rect.pivot = new Vector2(0f, 1f);
            rect.sizeDelta = new Vector2(0f, 35f);
            rect.anchoredPosition = new Vector2(10f, yPos);
            rect.offsetMax = new Vector2(-10f, yPos);

            Image image = buttonObj.AddComponent<Image>();
            image.color = color;

            Button button = buttonObj.AddComponent<Button>();
            button.targetGraphic = image;

            Text text = CreateLabel(buttonObj.transform, label, Vector2.zero, 0f, 0f, TextAnchor.MiddleCenter, 13);
            text.rectTransform.anchorMin = Vector2.zero;
            text.rectTransform.anchorMax = Vector2.one;
            text.rectTransform.offsetMin = Vector2.zero;
            text.rectTransform.offsetMax = Vector2.zero;
            text.fontStyle = FontStyle.Bold;

            ColorBlock colors = button.colors;
            colors.normalColor = color;
            colors.highlightedColor = color * 1.2f;
            colors.pressedColor = color * 0.8f;
            button.colors = colors;

            yPos -= 42f;
            return button;
        }

        private void CreateProgressBar(Transform parent, ref float yPos)
        {
            GameObject container = new GameObject("ProgressBar");
            container.transform.SetParent(parent, false);

            RectTransform rect = container.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 1f);
            rect.anchorMax = new Vector2(1f, 1f);
            rect.pivot = new Vector2(0f, 1f);
            rect.sizeDelta = new Vector2(0f, 40f);
            rect.anchoredPosition = new Vector2(10f, yPos);
            rect.offsetMax = new Vector2(-10f, yPos);

            GameObject bgObj = new GameObject("Background");
            bgObj.transform.SetParent(container.transform, false);
            RectTransform bgRect = bgObj.AddComponent<RectTransform>();
            bgRect.anchorMin = Vector2.zero;
            bgRect.anchorMax = Vector2.one;
            bgRect.sizeDelta = Vector2.zero;
            Image bgImage = bgObj.AddComponent<Image>();
            bgImage.color = new Color(0.15f, 0.15f, 0.2f);

            GameObject fillObj = new GameObject("Fill");
            fillObj.transform.SetParent(container.transform, false);
            RectTransform fillRect = fillObj.AddComponent<RectTransform>();
            fillRect.anchorMin = Vector2.zero;
            fillRect.anchorMax = new Vector2(0f, 1f);
            fillRect.pivot = new Vector2(0f, 0.5f);
            fillRect.sizeDelta = new Vector2(0f, 0f);
            Image fillImage = fillObj.AddComponent<Image>();
            fillImage.color = new Color(0.3f, 0.7f, 1f);

            Text progressText = CreateLabel(container.transform, "0%", new Vector2(0f, 0f), 0f, 0f, TextAnchor.MiddleCenter, 12);
            progressText.rectTransform.anchorMin = Vector2.zero;
            progressText.rectTransform.anchorMax = Vector2.one;
            progressText.rectTransform.offsetMin = Vector2.zero;
            progressText.rectTransform.offsetMax = Vector2.zero;
            progressText.fontStyle = FontStyle.Bold;

            _parameterPanel.GetType().GetField("_progressBar",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, container.AddComponent<Slider>());

            Slider slider = container.GetComponent<Slider>();
            slider.fillRect = fillRect;
            slider.targetGraphic = bgImage;

            _parameterPanel.GetType().GetField("_progressText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_parameterPanel, progressText);

            yPos -= 45f;
        }

        private Text CreateLabel(Transform parent, string text, Vector2 position, float width, float height, TextAnchor anchor, int fontSize)
        {
            GameObject labelObj = new GameObject("Label");
            labelObj.transform.SetParent(parent, false);

            RectTransform rect = labelObj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 1f);
            rect.anchorMax = new Vector2(0f, 1f);
            rect.pivot = new Vector2(0f, 1f);
            rect.sizeDelta = new Vector2(width, height);
            rect.anchoredPosition = position;

            Text labelText = labelObj.AddComponent<Text>();
            labelText.text = text;
            labelText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            labelText.fontSize = fontSize;
            labelText.color = Color.white;
            labelText.alignment = anchor;

            return labelText;
        }

        private Text CreateLabel(Transform parent, string text, ref float yPos, float width, TextAnchor anchor, int fontSize)
        {
            Text label = CreateLabel(parent, text, new Vector2(10f, yPos), width, 20f, anchor, fontSize);
            yPos -= 25f;
            return label;
        }

        private void CreateVisualizationPanel(Transform parent)
        {
            GameObject panelObj = new GameObject("VisualizationPanel");
            panelObj.transform.SetParent(parent, false);

            RectTransform rect = panelObj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(1f, 0f);
            rect.anchorMax = new Vector2(1f, 1f);
            rect.pivot = new Vector2(1f, 0.5f);
            rect.sizeDelta = new Vector2(350f, 0f);
            rect.offsetMin = new Vector2(0f, 10f);
            rect.offsetMax = new Vector2(-10f, -10f);

            Image background = panelObj.AddComponent<Image>();
            background.color = new Color(0.08f, 0.08f, 0.12f, 0.9f);

            _visualizationPanel = panelObj.AddComponent<VisualizationPanel>();
            CreateVisualizationPanelUI(panelObj.transform);
        }

        private void CreateVisualizationPanelUI(Transform parent)
        {
            float yPos = -20f;

            CreateSectionTitle(parent, "Visualization", ref yPos);

            _visualizationPanel.GetType().GetField("_visualizationModeDropdown",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateDropdown(parent, "View Mode", ref yPos, 120f, 200f,
                    new string[] { "Solid", "Contact Pressure", "Water Film", "Wear Depth", "Temperature", "Wireframe" }));

            _visualizationPanel.GetType().GetField("_showWireframeToggle",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateToggle(parent, "Show Outline", ref yPos, 120f, false));

            _visualizationPanel.GetType().GetField("_heatmapIntensitySlider",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateSliderWithLabel(parent, "Intensity", ref yPos,
                    120f, 200f, 0.1f, 2f, 1f, ""));

            yPos -= 20f;
            CreateSectionTitle(parent, "Contact Pressure", ref yPos);

            _visualizationPanel.GetType().GetField("_pressureHeatmap",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateRawImage(parent, ref yPos, 320f, 200f));

            _visualizationPanel.GetType().GetField("_pressureColorBar",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateRawImage(parent, ref yPos, 320f, 20f));

            _visualizationPanel.GetType().GetField("_pressureMinText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "0", ref yPos, 100f, TextAnchor.MiddleLeft, 10));
            _visualizationPanel.GetType().GetField("_pressureMaxText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "0", new Vector2(240f, yPos + 25f), 100f, 20f, TextAnchor.MiddleRight, 10));

            yPos += 5f;
            CreateSectionTitle(parent, "Water Film", ref yPos);

            _visualizationPanel.GetType().GetField("_waterFilmHeatmap",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateRawImage(parent, ref yPos, 320f, 200f));

            _visualizationPanel.GetType().GetField("_waterColorBar",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateRawImage(parent, ref yPos, 320f, 20f));

            _visualizationPanel.GetType().GetField("_waterMinText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "0", ref yPos, 100f, TextAnchor.MiddleLeft, 10));
            _visualizationPanel.GetType().GetField("_waterMaxText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "0", new Vector2(240f, yPos + 25f), 100f, 20f, TextAnchor.MiddleRight, 10));

            yPos += 5f;
            CreateSectionTitle(parent, "Wear Depth", ref yPos);

            _visualizationPanel.GetType().GetField("_wearHeatmap",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateRawImage(parent, ref yPos, 320f, 200f));

            _visualizationPanel.GetType().GetField("_wearColorBar",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateRawImage(parent, ref yPos, 320f, 20f));

            _visualizationPanel.GetType().GetField("_wearMinText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "0", ref yPos, 100f, TextAnchor.MiddleLeft, 10));
            _visualizationPanel.GetType().GetField("_wearMaxText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "0", new Vector2(240f, yPos + 25f), 100f, 20f, TextAnchor.MiddleRight, 10));

            yPos += 5f;
            CreateSectionTitle(parent, "Temperature", ref yPos);

            _visualizationPanel.GetType().GetField("_temperatureHeatmap",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateRawImage(parent, ref yPos, 320f, 200f));

            _visualizationPanel.GetType().GetField("_temperatureColorBar",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateRawImage(parent, ref yPos, 320f, 20f));

            _visualizationPanel.GetType().GetField("_temperatureMinText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "0", ref yPos, 100f, TextAnchor.MiddleLeft, 10));
            _visualizationPanel.GetType().GetField("_temperatureMaxText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "0", new Vector2(240f, yPos + 25f), 100f, 20f, TextAnchor.MiddleRight, 10));

            yPos += 5f;
            CreateSectionTitle(parent, "Friction Curve", ref yPos);

            _visualizationPanel.GetType().GetField("_curveTitle",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "Friction Coefficient", ref yPos, 320f, TextAnchor.MiddleCenter, 12));

            GameObject curveContainer = new GameObject("CurveContainer");
            curveContainer.transform.SetParent(parent, false);
            RectTransform curveRect = curveContainer.AddComponent<RectTransform>();
            curveRect.anchorMin = new Vector2(0f, 1f);
            curveRect.anchorMax = new Vector2(0f, 1f);
            curveRect.pivot = new Vector2(0f, 1f);
            curveRect.sizeDelta = new Vector2(320f, 150f);
            curveRect.anchoredPosition = new Vector2(10f, yPos);

            Image curveBg = curveContainer.AddComponent<Image>();
            curveBg.color = new Color(0.1f, 0.1f, 0.15f);

            _visualizationPanel.GetType().GetField("_curveContainer",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, curveRect);

            yPos -= 160f;

            _visualizationPanel.GetType().GetField("_curveMinLabel",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "0.001 m/s", ref yPos, 100f, TextAnchor.MiddleLeft, 10));
            _visualizationPanel.GetType().GetField("_curveMaxLabel",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "10 m/s", new Vector2(240f, yPos + 25f), 100f, 20f, TextAnchor.MiddleRight, 10));

            yPos += 5f;
            CreateSectionTitle(parent, "Statistics", ref yPos);

            _visualizationPanel.GetType().GetField("_maxPressureText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "Max Pressure: -", ref yPos, 320f, TextAnchor.MiddleLeft, 11));
            _visualizationPanel.GetType().GetField("_avgPressureText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "Avg Pressure: -", ref yPos, 320f, TextAnchor.MiddleLeft, 11));
            _visualizationPanel.GetType().GetField("_contactAreaText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "Contact Ratio: -", ref yPos, 320f, TextAnchor.MiddleLeft, 11));
            _visualizationPanel.GetType().GetField("_frictionCoeffText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "μ @ 1m/s: -", ref yPos, 320f, TextAnchor.MiddleLeft, 11));
            _visualizationPanel.GetType().GetField("_computeTimeText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "Compute Time: -", ref yPos, 320f, TextAnchor.MiddleLeft, 11));
            _visualizationPanel.GetType().GetField("_iterationsText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "Iterations: -", ref yPos, 320f, TextAnchor.MiddleLeft, 11));

            _visualizationPanel.GetType().GetField("_wearRateText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "Max Wear Rate: -", ref yPos, 320f, TextAnchor.MiddleLeft, 11));
            _visualizationPanel.GetType().GetField("_predictedLifeText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "Predicted Life: -", ref yPos, 320f, TextAnchor.MiddleLeft, 11));
            _visualizationPanel.GetType().GetField("_maxTemperatureText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "Max Temperature: -", ref yPos, 320f, TextAnchor.MiddleLeft, 11));
            _visualizationPanel.GetType().GetField("_modulusReductionText",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, CreateLabel(parent, "Modulus Reduction: -", ref yPos, 320f, TextAnchor.MiddleLeft, 11));

            GameObject curveLinePrefabObj = new GameObject("CurveLinePrefab");
            curveLinePrefabObj.transform.SetParent(parent, false);
            curveLinePrefabObj.SetActive(false);
            Image linePrefab = curveLinePrefabObj.AddComponent<Image>();
            _visualizationPanel.GetType().GetField("_curveLinePrefab",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_visualizationPanel, linePrefab);
        }

        private RawImage CreateRawImage(Transform parent, ref float yPos, float width, float height)
        {
            GameObject imgObj = new GameObject("RawImage");
            imgObj.transform.SetParent(parent, false);

            RectTransform rect = imgObj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 1f);
            rect.anchorMax = new Vector2(0f, 1f);
            rect.pivot = new Vector2(0f, 1f);
            rect.sizeDelta = new Vector2(width, height);
            rect.anchoredPosition = new Vector2(10f, yPos);

            RawImage rawImage = imgObj.AddComponent<RawImage>();
            rawImage.color = new Color(0.1f, 0.1f, 0.15f);

            yPos -= height + 10f;
            return rawImage;
        }

        private void CreateTitleBar(Transform parent)
        {
            GameObject titleObj = new GameObject("TitleBar");
            titleObj.transform.SetParent(parent, false);

            RectTransform rect = titleObj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 1f);
            rect.anchorMax = new Vector2(1f, 1f);
            rect.pivot = new Vector2(0.5f, 1f);
            rect.sizeDelta = new Vector2(0f, 40f);
            rect.anchoredPosition = new Vector2(0f, 0f);

            Image background = titleObj.AddComponent<Image>();
            background.color = new Color(0.05f, 0.05f, 0.08f, 0.95f);

            Text titleText = CreateLabel(titleObj.transform,
                "鞋底摩擦模拟系统 | Sole Friction Simulator",
                new Vector2(0f, 0f), 0f, 0f, TextAnchor.MiddleCenter, 16);
            titleText.rectTransform.anchorMin = new Vector2(0.3f, 0f);
            titleText.rectTransform.anchorMax = new Vector2(0.7f, 1f);
            titleText.rectTransform.offsetMin = Vector2.zero;
            titleText.rectTransform.offsetMax = Vector2.zero;
            titleText.fontStyle = FontStyle.Bold;
            titleText.color = new Color(0.4f, 0.8f, 1f);

            Text versionText = CreateLabel(titleObj.transform,
                "v1.0 | BEM + Persson Theory",
                new Vector2(0f, 0f), 200f, 0f, TextAnchor.MiddleRight, 10);
            versionText.rectTransform.anchorMin = new Vector2(1f, 0f);
            versionText.rectTransform.anchorMax = new Vector2(1f, 1f);
            versionText.rectTransform.offsetMin = new Vector2(-210f, 0f);
            versionText.rectTransform.offsetMax = new Vector2(-10f, 0f);
            versionText.color = new Color(0.6f, 0.6f, 0.7f);
        }

        private void CreateControllers()
        {
            GameObject controllerObj = GameObject.Find("SimulationSystem");
            if (controllerObj == null)
            {
                controllerObj = new GameObject("SimulationSystem");
            }

            _simulationController = controllerObj.AddComponent<SimulationController>();
        }

        private void BindReferences()
        {
            _simulationController.GetType().GetField("_parameterPanel",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_simulationController, _parameterPanel);

            _simulationController.GetType().GetField("_visualizationPanel",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_simulationController, _visualizationPanel);

            _simulationController.GetType().GetField("_bemComputeShader",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_simulationController, _bemComputeShader);

            _simulationController.GetType().GetField("_frictionComputeShader",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_simulationController, _frictionComputeShader);

            GameObject soleContainer = GameObject.Find("SoleContainer");
            if (soleContainer != null)
            {
                _simulationController.GetType().GetField("_soleContainer",
                    System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                    ?.SetValue(_simulationController, soleContainer.transform);
            }

            GameObject groundPlane = GameObject.Find("GroundPlane");
            if (groundPlane != null)
            {
                _simulationController.GetType().GetField("_groundPlane",
                    System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                    ?.SetValue(_simulationController, groundPlane.transform);
            }

            CreateMaterials();

            _parameterPanel.GroundSurfaceChanged += (ground) =>
            {
                _sceneController.UpdateGroundMaterial(ground.groundType);
            };
        }

        private void CreateMaterials()
        {
            Material soleMaterial = new Material(Shader.Find("Standard"));
            soleMaterial.color = new Color(0.1f, 0.1f, 0.12f);
            soleMaterial.SetFloat("_Glossiness", 0.3f);
            soleMaterial.SetFloat("_Metallic", 0.1f);

            Shader heatmapShader = Shader.Find("Custom/Heatmap");
            if (heatmapShader == null)
            {
                string shaderPath = Path.Combine(Application.dataPath, "Shaders/Heatmap.shader");
                if (File.Exists(shaderPath))
                {
                    Debug.LogWarning($"Heatmap shader found at {shaderPath} but not compiled.");
                }
                heatmapShader = Shader.Find("Standard");
            }
            Material heatmapMaterial = new Material(heatmapShader ?? Shader.Find("Standard"));

            Shader waterFilmShader = Shader.Find("Custom/WaterFilm");
            if (waterFilmShader == null)
            {
                string shaderPath = Path.Combine(Application.dataPath, "Shaders/WaterFilm.shader");
                if (File.Exists(shaderPath))
                {
                    Debug.LogWarning($"WaterFilm shader found at {shaderPath} but not compiled.");
                }
                waterFilmShader = Shader.Find("Standard");
            }
            Material waterFilmMaterial = new Material(waterFilmShader ?? Shader.Find("Standard"));

            Material wireframeMaterial = new Material(Shader.Find("Standard"));
            wireframeMaterial.color = new Color(0.3f, 0.7f, 1f);
            wireframeMaterial.SetFloat("_Glossiness", 0.5f);

            _simulationController.GetType().GetField("_soleMaterial",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_simulationController, soleMaterial);

            _simulationController.GetType().GetField("_heatmapMaterial",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_simulationController, heatmapMaterial);

            _simulationController.GetType().GetField("_waterFilmMaterial",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_simulationController, waterFilmMaterial);

            _simulationController.GetType().GetField("_wireframeMaterial",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                ?.SetValue(_simulationController, wireframeMaterial);
        }
    }
}
