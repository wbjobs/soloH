using UnityEngine;
using FlowVisualization.Compute;
using FlowVisualization.Rendering;

namespace FlowVisualization
{
    public class SceneInitializer : MonoBehaviour
    {
        public ComputeShader ParticleIntegrationShader;
        public Material LineMaterial;
        public Material ParticleMaterial;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void InitializeProject()
        {
            Application.targetFrameRate = 60;
            QualitySettings.vSyncCount = 0;
            System.Threading.Thread.CurrentThread.Priority = System.Threading.ThreadPriority.Highest;
        }

        private void Awake()
        {
            GameObject mainObj = GameObject.Find("FlowVisualization");
            if (mainObj == null)
            {
                mainObj = new GameObject("FlowVisualization");
            }

            FlowVisualizationMain main = mainObj.GetComponent<FlowVisualizationMain>();
            if (main == null)
            {
                main = mainObj.AddComponent<FlowVisualizationMain>();
            }

            if (mainObj.GetComponent<ParticleSystemManager>() == null)
            {
                mainObj.AddComponent<ParticleSystemManager>();
            }
            if (mainObj.GetComponent<LineRendererManager>() == null)
            {
                var lrm = mainObj.AddComponent<LineRendererManager>();
                if (LineMaterial != null) lrm.LineMaterial = LineMaterial;
            }
            if (mainObj.GetComponent<ParticleRenderer>() == null)
            {
                var pr = mainObj.AddComponent<ParticleRenderer>();
                if (ParticleMaterial != null) pr.ParticleMaterial = ParticleMaterial;
            }
            if (mainObj.GetComponent<ColorMapManager>() == null)
            {
                mainObj.AddComponent<ColorMapManager>();
            }
            if (mainObj.GetComponent<GPUParticleSystem>() == null)
            {
                var gpu = mainObj.AddComponent<GPUParticleSystem>();
                if (ParticleIntegrationShader != null)
                {
                    gpu.ParticleIntegrationShader = ParticleIntegrationShader;
                }
            }

            SetupLighting();
            SetupBoundsVisualization(mainObj);
        }

        private void SetupLighting()
        {
            if (GameObject.FindObjectOfType<Light>() == null)
            {
                GameObject lightObj = new GameObject("Directional Light");
                Light light = lightObj.AddComponent<Light>();
                light.type = LightType.Directional;
                light.color = Color.white;
                light.intensity = 1.0f;
                light.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            }

            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.2f, 0.3f, 0.5f);
            RenderSettings.ambientEquatorColor = new Color(0.3f, 0.35f, 0.4f);
            RenderSettings.ambientGroundColor = new Color(0.15f, 0.15f, 0.15f);
        }

        private void SetupBoundsVisualization(GameObject parent)
        {
            GameObject boundsObj = new GameObject("FieldBounds");
            boundsObj.transform.SetParent(parent.transform);

            LineRenderer lr = boundsObj.AddComponent<LineRenderer>();
            lr.material = new Material(Shader.Find("Sprites/Default"));
            lr.material.color = new Color(0.5f, 0.5f, 0.5f, 0.3f);
            lr.widthMultiplier = 0.002f;
            lr.positionCount = 16;
            lr.loop = false;
            lr.useWorldSpace = true;

            Vector3 min = Vector3.zero;
            Vector3 max = Vector3.one;

            Vector3[] points = new Vector3[16];
            points[0] = new Vector3(min.x, min.y, min.z);
            points[1] = new Vector3(max.x, min.y, min.z);
            points[2] = new Vector3(max.x, min.y, max.z);
            points[3] = new Vector3(min.x, min.y, max.z);
            points[4] = new Vector3(min.x, min.y, min.z);

            points[5] = new Vector3(min.x, max.y, min.z);
            points[6] = new Vector3(max.x, max.y, min.z);
            points[7] = new Vector3(max.x, max.y, max.z);
            points[8] = new Vector3(min.x, max.y, max.z);
            points[9] = new Vector3(min.x, max.y, min.z);

            points[10] = new Vector3(min.x, min.y, min.z);
            points[11] = new Vector3(min.x, max.y, min.z);
            points[12] = new Vector3(max.x, max.y, min.z);
            points[13] = new Vector3(max.x, min.y, min.z);
            points[14] = new Vector3(max.x, min.y, max.z);
            points[15] = new Vector3(max.x, max.y, max.z);

            lr.SetPositions(points);
        }
    }
}
