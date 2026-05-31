#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;
using System.IO;

namespace FlowVisualization.Editor
{
    public static class ProjectSetup
    {
        [MenuItem("FlowVisualization/Create Required Folders")]
        public static void CreateFolders()
        {
            string[] folders = {
                "Assets/Plugins",
                "Assets/Resources",
                "Assets/Scenes",
                "Assets/Prefabs"
            };

            foreach (string folder in folders)
            {
                if (!Directory.Exists(folder))
                {
                    Directory.CreateDirectory(folder);
                    Debug.Log($"Created folder: {folder}");
                }
            }

            AssetDatabase.Refresh();
        }

        [MenuItem("FlowVisualization/Setup Main Scene")]
        public static void SetupMainScene()
        {
            UnityEngine.SceneManagement.Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            GameObject flowVis = new GameObject("FlowVisualization");
            flowVis.AddComponent<FlowVisualizationMain>();
            flowVis.AddComponent<SceneInitializer>();

            GameObject cameraObj = new GameObject("Main Camera");
            cameraObj.tag = "MainCamera";
            Camera cam = cameraObj.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.05f, 0.05f, 0.1f);
            cam.fieldOfView = 60f;
            cameraObj.AddComponent<AudioListener>();
            cameraObj.transform.position = new Vector3(0.5f, 0.5f, 2.0f);

            EditorSceneManager.SaveScene(scene, "Assets/Scenes/Main.unity");
            Debug.Log("Main scene created successfully!");
        }

        [MenuItem("FlowVisualization/Check Dependencies")]
        public static void CheckDependencies()
        {
            bool hasComputeShader = File.Exists("Assets/Shaders/ParticleIntegration.compute");
            bool hasParticleShader = File.Exists("Assets/Shaders/ColoredParticle.shader");
            
            Debug.Log("=== Dependency Check ===");
            Debug.Log($"Compute Shader: {(hasComputeShader ? "✓" : "✗")}");
            Debug.Log($"Particle Shader: {(hasParticleShader ? "✓" : "✗")}");
            Debug.Log($"Compute Shaders Supported: {(SystemInfo.supportsComputeShaders ? "Yes" : "No")}");
            Debug.Log($"GPU Instancing Supported: {(SystemInfo.supportsInstancing ? "Yes" : "No")}");
            Debug.Log($"Max Compute Buffer Stride: {SystemInfo.maxComputeBufferStride}");
            Debug.Log($"========================");
        }

        [MenuItem("FlowVisualization/Apply Recommended Settings")]
        public static void ApplyRecommendedSettings()
        {
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Standalone, ScriptingBackend.Mono);
            PlayerSettings.SetApiCompatibilityLevel(BuildTargetGroup.Standalone, ApiCompatibilityLevel.NET_4_6);
            PlayerSettings.gpuSkinning = true;
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = 60;
            Time.fixedDeltaTime = 0.01f;
            Time.maximumDeltaTime = 0.05f;

            Debug.Log("Recommended settings applied.");
        }
    }
}
#endif
