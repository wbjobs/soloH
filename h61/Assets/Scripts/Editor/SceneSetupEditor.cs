#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;
using UnityEngine.UI;
using LanderSim.Main;
using LanderSim.UI;

namespace LanderSim.EditorTools
{
    public class SceneSetupEditor : EditorWindow
    {
        [MenuItem("LanderSim/Setup Full Scene")]
        public static void SetupFullScene()
        {
            SetupMainCamera();
            SetupLighting();
            SetupGroundPlane();
            GameObject simulatorObj = SetupLanderSimulator();
            SetupUI(simulatorObj);
            SetupMaterials();

            Debug.Log("LanderSim scene setup complete!");
            EditorUtility.DisplayDialog("Scene Setup",
                "LanderSim scene has been fully configured.\n" +
                "Press Play to start the simulation.", "OK");
        }

        [MenuItem("LanderSim/Create LanderSimulator Only")]
        public static GameObject SetupLanderSimulator()
        {
            GameObject existing = GameObject.Find("LanderSimulator");
            if (existing != null)
            {
                DestroyImmediate(existing);
            }

            GameObject simulatorObj = new GameObject("LanderSimulator");
            LanderSimulator simulator = simulatorObj.AddComponent<LanderSimulator>();

            simulator.mainCamera = Camera.main;
            simulator.terrainOrigin = new Vector3(-128, 0, -128);
            simulator.terrainResolution = 128;
            simulator.terrainCellSize = 2.0f;
            simulator.randomSeed = 42;
            simulator.gridSizeX = 64;
            simulator.gridSizeY = 32;
            simulator.gridSizeZ = 64;
            simulator.gridCellSize = 4.0f;
            simulator.initialPosition = new Vector3(0, 150, 0);
            simulator.initialVelocity = Vector3.zero;
            simulator.dryMass = 500f;
            simulator.initialFuel = 300f;
            simulator.autoStartSimulation = false;
            simulator.pathAlgorithm = PathAlgorithm.AStar;

            return simulatorObj;
        }

        [MenuItem("LanderSim/Setup UI")]
        public static void SetupUI(GameObject simulatorObj)
        {
            GameObject canvasObj = GameObject.Find("Canvas");
            if (canvasObj == null)
            {
                canvasObj = new GameObject("Canvas");
                Canvas canvas = canvasObj.AddComponent<Canvas>();
                canvas.renderMode = RenderMode.ScreenSpaceOverlay;
                canvasObj.AddComponent<CanvasScaler>();
                canvasObj.AddComponent<GraphicRaycaster>();
            }

            GameObject eventSystem = GameObject.Find("EventSystem");
            if (eventSystem == null)
            {
                eventSystem = new GameObject("EventSystem");
                eventSystem.AddComponent<UnityEngine.EventSystems.EventSystem>();
                eventSystem.AddComponent<UnityEngine.EventSystems.StandaloneInputModule>();
            }

            GameObject uiManagerObj = new GameObject("UIManager");
            UIManager uiManager = uiManagerObj.AddComponent<UIManager>();
            uiManager.simulator = simulatorObj.GetComponent<LanderSimulator>();

            CreateUIPanels(canvasObj.transform, uiManager);
        }

        private static void SetupMainCamera()
        {
            Camera cam = Camera.main;
            if (cam == null)
            {
                GameObject camObj = new GameObject("Main Camera");
                cam = camObj.AddComponent<Camera>();
                camObj.tag = "MainCamera";
            }

            cam.transform.position = new Vector3(150, 120, 150);
            cam.transform.rotation = Quaternion.Euler(45, -135, 0);
            cam.fieldOfView = 60f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.05f, 0.05f, 0.15f);

            if (cam.GetComponent<CameraController>() == null)
            {
                cam.gameObject.AddComponent<CameraController>();
            }
        }

        private static void SetupLighting()
        {
            GameObject lightObj = GameObject.Find("Directional Light");
            if (lightObj == null)
            {
                lightObj = new GameObject("Directional Light");
                Light light = lightObj.AddComponent<Light>();
                light.type = LightType.Directional;
            }

            lightObj.transform.rotation = Quaternion.Euler(45, 30, 0);
            Light dirLight = lightObj.GetComponent<Light>();
            dirLight.intensity = 1.2f;
            dirLight.color = new Color(1f, 0.95f, 0.85f);
            dirLight.shadows = LightShadows.Soft;

            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.2f, 0.25f, 0.4f);
            RenderSettings.ambientEquatorColor = new Color(0.15f, 0.15f, 0.2f);
            RenderSettings.ambientGroundColor = new Color(0.1f, 0.1f, 0.12f);
        }

        private static void SetupGroundPlane()
        {
            GameObject ground = GameObject.Find("GroundReference");
            if (ground != null)
            {
                DestroyImmediate(ground);
            }

            ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "GroundReference";
            ground.transform.position = new Vector3(0, -0.01f, 0);
            ground.transform.localScale = new Vector3(30, 1, 30);
            Renderer renderer = ground.GetComponent<Renderer>();
            renderer.material = new Material(Shader.Find("Standard"));
            renderer.material.color = new Color(0.15f, 0.12f, 0.1f);
            renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;

            DestroyImmediate(ground.GetComponent<Collider>());
        }

        private static void SetupMaterials()
        {
            string materialsFolder = "Assets/Materials";
            if (!AssetDatabase.IsValidFolder(materialsFolder))
            {
                AssetDatabase.CreateFolder("Assets", "Materials");
            }

            Material terrainMat = CreateMaterial("TerrainMaterial",
                new Color(0.45f, 0.38f, 0.32f), 0.8f, 0.2f);
            AssetDatabase.CreateAsset(terrainMat, $"{materialsFolder}/TerrainMaterial.mat");

            Debug.Log("Materials created successfully");
        }

        private static Material CreateMaterial(string name, Color color,
            float metallic, float smoothness)
        {
            Material mat = new Material(Shader.Find("Standard"));
            mat.name = name;
            mat.color = color;
            mat.SetFloat("_Metallic", metallic);
            mat.SetFloat("_Glossiness", smoothness);
            return mat;
        }

        private static void CreateUIPanels(Transform parent, UIManager uiManager)
        {
            GameObject mainPanelObj = CreatePanel(parent, "MainPanel",
                new Vector2(10, 10), new Vector2(250, 400),
                new Color(0.1f, 0.1f, 0.1f, 0.9f));
            uiManager.mainPanel = mainPanelObj;

            GameObject infoPanelObj = CreatePanel(parent, "InfoPanel",
                new Vector2(Screen.width - 260, 10), new Vector2(250, 300),
                new Color(0.1f, 0.1f, 0.1f, 0.9f));
            uiManager.infoPanel = infoPanelObj;

            GameObject controlsPanelObj = CreatePanel(parent, "ControlsPanel",
                new Vector2(10, Screen.height - 110), new Vector2(400, 100),
                new Color(0.1f, 0.1f, 0.1f, 0.9f));
            uiManager.controlsPanel = controlsPanelObj;

            GameObject monteCarloPanelObj = CreatePanel(parent, "MonteCarloPanel",
                new Vector2(Screen.width - 260, 320), new Vector2(250, 250),
                new Color(0.1f, 0.1f, 0.1f, 0.9f));
            uiManager.monteCarloPanel = monteCarloPanelObj;

            CreateMainPanelControls(mainPanelObj.transform, uiManager);
            CreateInfoPanelControls(infoPanelObj.transform, uiManager);
            CreateControlsPanelControls(controlsPanelObj.transform, uiManager);
            CreateMonteCarloPanelControls(monteCarloPanelObj.transform, uiManager);
        }

        private static GameObject CreatePanel(Transform parent, string name,
            Vector2 position, Vector2 size, Color color)
        {
            GameObject panel = new GameObject(name);
            panel.transform.SetParent(parent, false);

            RectTransform rt = panel.AddComponent<RectTransform>();
            rt.anchorMin = new Vector2(0, 1);
            rt.anchorMax = new Vector2(0, 1);
            rt.pivot = new Vector2(0, 1);
            rt.anchoredPosition = position;
            rt.sizeDelta = size;

            Image image = panel.AddComponent<Image>();
            image.color = color;

            return panel;
        }

        private static void CreateMainPanelControls(Transform parent, UIManager uiManager)
        {
            float y = -20;
            float buttonHeight = 30;
            float spacing = 5;

            CreateLabel(parent, "=== SIMULATION CONTROLS ===", 10, y, 230, 20, 14, FontStyle.Bold);
            y -= 25;

            uiManager.generateTerrainBtn = CreateButton(parent, "Generate Terrain", 10, y, 230, buttonHeight);
            y -= buttonHeight + spacing;

            uiManager.generateGridBtn = CreateButton(parent, "Generate Grid", 10, y, 230, buttonHeight);
            y -= buttonHeight + spacing;

            uiManager.generateRiskMapBtn = CreateButton(parent, "Generate Risk Map", 10, y, 230, buttonHeight);
            y -= buttonHeight + spacing;

            uiManager.planPathBtn = CreateButton(parent, "Plan Path", 10, y, 230, buttonHeight);
            y -= buttonHeight + spacing;

            uiManager.simulateBtn = CreateButton(parent, "Simulate Trajectory", 10, y, 230, buttonHeight);
            y -= buttonHeight + spacing;

            uiManager.monteCarloBtn = CreateButton(parent, "Run Monte Carlo", 10, y, 230, buttonHeight);
            y -= buttonHeight + spacing;

            uiManager.resetBtn = CreateButton(parent, "Reset Simulation", 10, y, 230, buttonHeight);
            y -= buttonHeight + spacing * 2;

            CreateLabel(parent, "Path Algorithm:", 10, y, 100, 20);
            uiManager.algorithmDropdown = CreateDropdown(parent, 110, y, 130, buttonHeight,
                new string[] { "A*", "RRT", "RRT*" });
            y -= buttonHeight + spacing;

            CreateLabel(parent, "Random Seed:", 10, y, 100, 20);
            uiManager.seedInputField = CreateInputField(parent, 110, y, 130, buttonHeight, "42");
            y -= buttonHeight + spacing;

            CreateLabel(parent, "Time Scale:", 10, y, 100, 20);
            uiManager.timeScaleSlider = CreateSlider(parent, 110, y, 130, buttonHeight, 0.1f, 5f, 1f);
        }

        private static void CreateInfoPanelControls(Transform parent, UIManager uiManager)
        {
            float y = -20;

            CreateLabel(parent, "=== INFORMATION ===", 10, y, 230, 20, 14, FontStyle.Bold);
            y -= 25;

            uiManager.infoText = CreateText(parent, "", 10, y, 230, 200, 11, TextAnchor.UpperLeft);
            y -= 205;

            CreateLabel(parent, "=== SELECTED SITE ===", 10, y, 230, 20, 12, FontStyle.Bold);
            y -= 22;

            uiManager.selectedSiteText = CreateText(parent, "Select a landing site", 10, y, 230, 80, 11, TextAnchor.UpperLeft);
        }

        private static void CreateControlsPanelControls(Transform parent, UIManager uiManager)
        {
            float x = 10;
            float y = -15;
            float toggleWidth = 120;
            float spacing = 10;

            CreateLabel(parent, "VISUALIZATION:", x, y, 100, 20, 12, FontStyle.Bold);
            x += 105;

            uiManager.showHeatmapToggle = CreateToggle(parent, "Heatmap", x, y, toggleWidth, 25, true);
            x += toggleWidth + spacing;

            uiManager.showTrajectoryToggle = CreateToggle(parent, "Trajectory", x, y, toggleWidth, 25, true);
            x += toggleWidth + spacing;

            uiManager.showVelocityVectorsToggle = CreateToggle(parent, "Velocity", x, y, toggleWidth, 25, false);
            x += toggleWidth + spacing;

            uiManager.showThrustVectorsToggle = CreateToggle(parent, "Thrust", x, y, toggleWidth, 25, false);
            x += toggleWidth + spacing;

            uiManager.showDeviationVectorsToggle = CreateToggle(parent, "Deviation", x, y, toggleWidth, 25, false);

            y -= 35;
            x = 10;

            uiManager.statusText = CreateText(parent, "Status: Ready", x, y, 380, 25, 14, TextAnchor.MiddleLeft);
        }

        private static void CreateMonteCarloPanelControls(Transform parent, UIManager uiManager)
        {
            float y = -20;

            CreateLabel(parent, "=== MONTE CARLO ===", 10, y, 230, 20, 14, FontStyle.Bold);
            y -= 25;

            CreateLabel(parent, "Simulations:", 10, y, 100, 20);
            uiManager.monteCarloCountSlider = CreateSlider(parent, 110, y, 130, 30, 10, 500, 100);
            y -= 35;

            uiManager.monteCarloProgressText = CreateText(parent, "Progress: 0/0", 10, y, 230, 25, 12, TextAnchor.MiddleLeft);
            y -= 30;

            uiManager.monteCarloResultsText = CreateText(parent, "", 10, y, 230, 150, 11, TextAnchor.UpperLeft);
        }

        private static Button CreateButton(Transform parent, string text,
            float x, float y, float width, float height)
        {
            GameObject buttonObj = new GameObject($"Button_{text}");
            buttonObj.transform.SetParent(parent, false);

            RectTransform rt = buttonObj.AddComponent<RectTransform>();
            rt.anchorMin = new Vector2(0, 1);
            rt.anchorMax = new Vector2(0, 1);
            rt.pivot = new Vector2(0, 1);
            rt.anchoredPosition = new Vector2(x, y);
            rt.sizeDelta = new Vector2(width, height);

            Image image = buttonObj.AddComponent<Image>();
            image.color = new Color(0.3f, 0.3f, 0.35f, 1f);

            Button button = buttonObj.AddComponent<Button>();
            ColorBlock colors = button.colors;
            colors.normalColor = new Color(0.3f, 0.3f, 0.35f);
            colors.highlightedColor = new Color(0.45f, 0.45f, 0.5f);
            colors.pressedColor = new Color(0.2f, 0.2f, 0.25f);
            button.colors = colors;

            GameObject textObj = new GameObject("Text");
            textObj.transform.SetParent(buttonObj.transform, false);

            RectTransform textRt = textObj.AddComponent<RectTransform>();
            textRt.anchorMin = Vector2.zero;
            textRt.anchorMax = Vector2.one;
            textRt.offsetMin = Vector2.zero;
            textRt.offsetMax = Vector2.zero;

            Text textComp = textObj.AddComponent<Text>();
            textComp.text = text;
            textComp.alignment = TextAnchor.MiddleCenter;
            textComp.color = Color.white;
            textComp.fontSize = 12;
            textComp.font = Resources.GetBuiltinResource<Font>("Arial.ttf");

            return button;
        }

        private static Text CreateLabel(Transform parent, string text,
            float x, float y, float width, float height,
            int fontSize = 12, FontStyle style = FontStyle.Normal)
        {
            Text textComp = CreateText(parent, text, x, y, width, height, fontSize, TextAnchor.MiddleLeft);
            textComp.fontStyle = style;
            return textComp;
        }

        private static Text CreateText(Transform parent, string text,
            float x, float y, float width, float height,
            int fontSize, TextAnchor anchor)
        {
            GameObject textObj = new GameObject($"Text_{text.Substring(0, Mathf.Min(10, text.Length))}");
            textObj.transform.SetParent(parent, false);

            RectTransform rt = textObj.AddComponent<RectTransform>();
            rt.anchorMin = new Vector2(0, 1);
            rt.anchorMax = new Vector2(0, 1);
            rt.pivot = new Vector2(0, 1);
            rt.anchoredPosition = new Vector2(x, y);
            rt.sizeDelta = new Vector2(width, height);

            Text textComp = textObj.AddComponent<Text>();
            textComp.text = text;
            textComp.alignment = anchor;
            textComp.color = Color.white;
            textComp.fontSize = fontSize;
            textComp.horizontalOverflow = HorizontalWrapMode.Wrap;
            textComp.verticalOverflow = VerticalWrapMode.Truncate;
            textComp.font = Resources.GetBuiltinResource<Font>("Arial.ttf");

            return textComp;
        }

        private static Dropdown CreateDropdown(Transform parent,
            float x, float y, float width, float height, string[] options)
        {
            GameObject dropdownObj = new GameObject("Dropdown");
            dropdownObj.transform.SetParent(parent, false);

            RectTransform rt = dropdownObj.AddComponent<RectTransform>();
            rt.anchorMin = new Vector2(0, 1);
            rt.anchorMax = new Vector2(0, 1);
            rt.pivot = new Vector2(0, 1);
            rt.anchoredPosition = new Vector2(x, y);
            rt.sizeDelta = new Vector2(width, height);

            Image image = dropdownObj.AddComponent<Image>();
            image.color = new Color(0.2f, 0.2f, 0.25f);

            Dropdown dropdown = dropdownObj.AddComponent<Dropdown>();
            dropdown.targetGraphic = image;

            GameObject labelObj = new GameObject("Label");
            labelObj.transform.SetParent(dropdownObj.transform, false);
            RectTransform labelRt = labelObj.AddComponent<RectTransform>();
            labelRt.anchorMin = new Vector2(0, 0);
            labelRt.anchorMax = new Vector2(1, 1);
            labelRt.offsetMin = new Vector2(10, 3);
            labelRt.offsetMax = new Vector2(-30, -3);

            Text label = labelObj.AddComponent<Text>();
            label.color = Color.white;
            label.fontSize = 12;
            label.alignment = TextAnchor.MiddleLeft;
            label.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            dropdown.captionText = label;

            GameObject itemTextObj = new GameObject("ItemText");
            Text itemText = itemTextObj.AddComponent<Text>();
            itemText.color = Color.black;
            itemText.fontSize = 12;
            itemText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            dropdown.itemText = itemText;

            dropdown.options.Clear();
            foreach (string opt in options)
            {
                dropdown.options.Add(new Dropdown.OptionData(opt));
            }
            dropdown.value = 0;

            return dropdown;
        }

        private static InputField CreateInputField(Transform parent,
            float x, float y, float width, float height, string defaultText)
        {
            GameObject inputObj = new GameObject("InputField");
            inputObj.transform.SetParent(parent, false);

            RectTransform rt = inputObj.AddComponent<RectTransform>();
            rt.anchorMin = new Vector2(0, 1);
            rt.anchorMax = new Vector2(0, 1);
            rt.pivot = new Vector2(0, 1);
            rt.anchoredPosition = new Vector2(x, y);
            rt.sizeDelta = new Vector2(width, height);

            Image image = inputObj.AddComponent<Image>();
            image.color = new Color(0.15f, 0.15f, 0.2f);

            InputField input = inputObj.AddComponent<InputField>();
            input.targetGraphic = image;

            GameObject textObj = new GameObject("Text");
            textObj.transform.SetParent(inputObj.transform, false);
            RectTransform textRt = textObj.AddComponent<RectTransform>();
            textRt.anchorMin = Vector2.zero;
            textRt.anchorMax = Vector2.one;
            textRt.offsetMin = new Vector2(8, 4);
            textRt.offsetMax = new Vector2(-8, -4);

            Text text = textObj.AddComponent<Text>();
            text.color = Color.white;
            text.fontSize = 12;
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.supportRichText = false;
            input.textComponent = text;
            input.text = defaultText;

            GameObject placeholderObj = new GameObject("Placeholder");
            placeholderObj.transform.SetParent(inputObj.transform, false);
            RectTransform placeholderRt = placeholderObj.AddComponent<RectTransform>();
            placeholderRt.anchorMin = Vector2.zero;
            placeholderRt.anchorMax = Vector2.one;
            placeholderRt.offsetMin = new Vector2(8, 4);
            placeholderRt.offsetMax = new Vector2(-8, -4);

            Text placeholder = placeholderObj.AddComponent<Text>();
            placeholder.color = new Color(0.5f, 0.5f, 0.5f);
            placeholder.fontSize = 12;
            placeholder.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            placeholder.text = "Enter seed...";
            input.placeholder = placeholder;

            return input;
        }

        private static Slider CreateSlider(Transform parent,
            float x, float y, float width, float height,
            float minValue, float maxValue, float defaultValue)
        {
            GameObject sliderObj = new GameObject("Slider");
            sliderObj.transform.SetParent(parent, false);

            RectTransform rt = sliderObj.AddComponent<RectTransform>();
            rt.anchorMin = new Vector2(0, 1);
            rt.anchorMax = new Vector2(0, 1);
            rt.pivot = new Vector2(0, 1);
            rt.anchoredPosition = new Vector2(x, y);
            rt.sizeDelta = new Vector2(width, height);

            Slider slider = sliderObj.AddComponent<Slider>();
            slider.minValue = minValue;
            slider.maxValue = maxValue;
            slider.value = defaultValue;

            GameObject bgObj = new GameObject("Background");
            bgObj.transform.SetParent(sliderObj.transform, false);
            RectTransform bgRt = bgObj.AddComponent<RectTransform>();
            bgRt.anchorMin = new Vector2(0, 0.5f);
            bgRt.anchorMax = new Vector2(1, 0.5f);
            bgRt.offsetMin = new Vector2(0, -5);
            bgRt.offsetMax = new Vector2(0, 5);

            Image bgImage = bgObj.AddComponent<Image>();
            bgImage.color = new Color(0.15f, 0.15f, 0.2f);

            GameObject fillArea = new GameObject("Fill Area");
            fillArea.transform.SetParent(sliderObj.transform, false);
            RectTransform fillAreaRt = fillArea.AddComponent<RectTransform>();
            fillAreaRt.anchorMin = new Vector2(0, 0.5f);
            fillAreaRt.anchorMax = new Vector2(1, 0.5f);
            fillAreaRt.offsetMin = new Vector2(0, -3);
            fillAreaRt.offsetMax = new Vector2(0, 3);

            GameObject fill = new GameObject("Fill");
            fill.transform.SetParent(fillArea.transform, false);
            RectTransform fillRt = fill.AddComponent<RectTransform>();
            fillRt.anchorMin = Vector2.zero;
            fillRt.anchorMax = Vector2.one;
            fillRt.offsetMin = Vector2.zero;
            fillRt.offsetMax = Vector2.zero;

            Image fillImage = fill.AddComponent<Image>();
            fillImage.color = new Color(0.3f, 0.6f, 0.9f);
            slider.fillRect = fillRt;

            GameObject handleArea = new GameObject("Handle Slide Area");
            handleArea.transform.SetParent(sliderObj.transform, false);
            RectTransform handleAreaRt = handleArea.AddComponent<RectTransform>();
            handleAreaRt.anchorMin = new Vector2(0, 0.5f);
            handleAreaRt.anchorMax = new Vector2(1, 0.5f);
            handleAreaRt.offsetMin = new Vector2(0, -10);
            handleAreaRt.offsetMax = new Vector2(0, 10);

            GameObject handle = new GameObject("Handle");
            handle.transform.SetParent(handleArea.transform, false);
            RectTransform handleRt = handle.AddComponent<RectTransform>();
            handleRt.sizeDelta = new Vector2(12, 20);

            Image handleImage = handle.AddComponent<Image>();
            handleImage.color = new Color(0.5f, 0.7f, 1f);
            slider.handleRect = handleRt;
            slider.targetGraphic = handleImage;

            return slider;
        }

        private static Toggle CreateToggle(Transform parent, string text,
            float x, float y, float width, float height, bool defaultValue)
        {
            GameObject toggleObj = new GameObject($"Toggle_{text}");
            toggleObj.transform.SetParent(parent, false);

            RectTransform rt = toggleObj.AddComponent<RectTransform>();
            rt.anchorMin = new Vector2(0, 1);
            rt.anchorMax = new Vector2(0, 1);
            rt.pivot = new Vector2(0, 1);
            rt.anchoredPosition = new Vector2(x, y);
            rt.sizeDelta = new Vector2(width, height);

            Toggle toggle = toggleObj.AddComponent<Toggle>();
            toggle.isOn = defaultValue;

            GameObject bgObj = new GameObject("Background");
            bgObj.transform.SetParent(toggleObj.transform, false);
            RectTransform bgRt = bgObj.AddComponent<RectTransform>();
            bgRt.anchorMin = new Vector2(0, 0.5f);
            bgRt.anchorMax = new Vector2(0, 0.5f);
            bgRt.pivot = new Vector2(0, 0.5f);
            bgRt.anchoredPosition = Vector2.zero;
            bgRt.sizeDelta = new Vector2(20, 20);

            Image bgImage = bgObj.AddComponent<Image>();
            bgImage.color = new Color(0.2f, 0.2f, 0.25f);
            toggle.targetGraphic = bgImage;

            GameObject checkObj = new GameObject("Checkmark");
            checkObj.transform.SetParent(bgObj.transform, false);
            RectTransform checkRt = checkObj.AddComponent<RectTransform>();
            checkRt.anchorMin = Vector2.zero;
            checkRt.anchorMax = Vector2.one;
            checkRt.offsetMin = new Vector2(3, 3);
            checkRt.offsetMax = new Vector2(-3, -3);

            Image checkImage = checkObj.AddComponent<Image>();
            checkImage.color = new Color(0.3f, 0.8f, 0.4f);
            toggle.graphic = checkImage;

            GameObject labelObj = new GameObject("Label");
            labelObj.transform.SetParent(toggleObj.transform, false);
            RectTransform labelRt = labelObj.AddComponent<RectTransform>();
            labelRt.anchorMin = new Vector2(0, 0);
            labelRt.anchorMax = new Vector2(1, 1);
            labelRt.offsetMin = new Vector2(25, 0);
            labelRt.offsetMax = Vector2.zero;

            Text label = labelObj.AddComponent<Text>();
            label.text = text;
            label.color = Color.white;
            label.fontSize = 11;
            label.alignment = TextAnchor.MiddleLeft;
            label.font = Resources.GetBuiltinResource<Font>("Arial.ttf");

            return toggle;
        }
    }
}
#endif
