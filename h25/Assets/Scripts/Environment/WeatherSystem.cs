using System.Collections.Generic;
using UnityEngine;

namespace CitySimulator
{
    public class WeatherSystem : MonoBehaviour
    {
        public static WeatherSystem Instance { get; private set; }

        [SerializeField] private Light directionalLight;
        [SerializeField] private Material skyboxMaterial;
        [SerializeField] private ParticleSystem rainParticles;
        [SerializeField] private ParticleSystem snowParticles;
        [SerializeField] private GameObject fog;

        [SerializeField] private Color clearSkyColor = new Color(0.5f, 0.7f, 1f);
        [SerializeField] private Color rainySkyColor = new Color(0.4f, 0.45f, 0.5f);
        [SerializeField] private Color foggySkyColor = new Color(0.6f, 0.6f, 0.6f);
        [SerializeField] private Color snowySkyColor = new Color(0.8f, 0.85f, 0.9f);
        [SerializeField] private Color nightSkyColor = new Color(0.05f, 0.05f, 0.1f);

        [SerializeField] private Color clearAmbientColor = new Color(0.8f, 0.85f, 0.9f);
        [SerializeField] private Color rainyAmbientColor = new Color(0.4f, 0.45f, 0.5f);
        [SerializeField] private Color foggyAmbientColor = new Color(0.5f, 0.5f, 0.5f);
        [SerializeField] private Color snowyAmbientColor = new Color(0.7f, 0.75f, 0.8f);
        [SerializeField] private Color nightAmbientColor = new Color(0.1f, 0.1f, 0.15f);

        public WeatherType CurrentWeather { get; private set; } = WeatherType.Clear;

        private Material _dynamicSkybox;
        private Material _rainMaterial;
        private Material _snowMaterial;
        private bool _particlesCreated;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            EnsureReferences();

            Shader skyboxShader = skyboxMaterial != null ? skyboxMaterial.shader : Shader.Find("Skybox/Procedural");
            if (skyboxShader == null)
            {
                skyboxShader = Shader.Find("Standard");
                Debug.LogWarning("Skybox/Procedural shader not found, fallback to Standard shader.");
            }
            _dynamicSkybox = new Material(skyboxShader);
            RenderSettings.skybox = _dynamicSkybox;

            EnsureParticleMaterials();
            CreateParticleSystems();
        }

        private void OnDestroy()
        {
            if (_dynamicSkybox != null)
            {
                Destroy(_dynamicSkybox);
                _dynamicSkybox = null;
            }
            if (_rainMaterial != null)
            {
                Destroy(_rainMaterial);
                _rainMaterial = null;
            }
            if (_snowMaterial != null)
            {
                Destroy(_snowMaterial);
                _snowMaterial = null;
            }
        }

        private void EnsureReferences()
        {
            if (directionalLight == null)
            {
                var lightObj = new GameObject("Directional Light");
                lightObj.transform.SetParent(transform);
                lightObj.transform.rotation = Quaternion.Euler(50f, -30f, 0);
                directionalLight = lightObj.AddComponent<Light>();
                directionalLight.type = LightType.Directional;
                directionalLight.intensity = 1f;
            }
        }

        private void EnsureParticleMaterials()
        {
            Shader particleShader = Shader.Find("Particles/Standard Unlit");
            if (particleShader == null)
            {
                particleShader = Shader.Find("Standard");
                Debug.LogWarning("Particles/Standard Unlit shader not found, fallback to Standard shader.");
            }

            if (_rainMaterial == null)
            {
                _rainMaterial = new Material(particleShader);
                _rainMaterial.color = new Color(0.8f, 0.9f, 1f, 0.6f);
            }

            if (_snowMaterial == null)
            {
                _snowMaterial = new Material(particleShader);
                _snowMaterial.color = Color.white;
            }
        }

        private void CreateParticleSystems()
        {
            if (_particlesCreated) return;

            CreateRainParticles();
            CreateSnowParticles();

            if (rainParticles != null)
            {
                rainParticles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            }
            if (snowParticles != null)
            {
                snowParticles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            }

            _particlesCreated = true;
        }

        public void SetWeather(WeatherType weatherType)
        {
            if (!_particlesCreated)
            {
                CreateParticleSystems();
            }

            CurrentWeather = weatherType;

            switch (weatherType)
            {
                case WeatherType.Clear:
                    ApplyClearWeather();
                    break;
                case WeatherType.Rainy:
                    ApplyRainyWeather();
                    break;
                case WeatherType.Foggy:
                    ApplyFoggyWeather();
                    break;
                case WeatherType.Snowy:
                    ApplySnowyWeather();
                    break;
                case WeatherType.Night:
                    ApplyNightWeather();
                    break;
            }

            SimulationManager.Instance?.Log($"Weather changed to: {weatherType}");
        }

        public void ResetWeather()
        {
            SetWeather(WeatherType.Clear);
        }

        private void ApplyClearWeather()
        {
            SetLighting(clearSkyColor, clearAmbientColor, 1f, 1.2f);
            RenderSettings.fog = false;
            StopParticles();
        }

        private void ApplyRainyWeather()
        {
            SetLighting(rainySkyColor, rainyAmbientColor, 0.5f, 0.6f);
            RenderSettings.fog = true;
            RenderSettings.fogColor = rainySkyColor;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogStartDistance = 50f;
            RenderSettings.fogEndDistance = 200f;

            PlayRain();
            StopSnow();
        }

        private void ApplyFoggyWeather()
        {
            SetLighting(foggySkyColor, foggyAmbientColor, 0.6f, 0.7f);
            RenderSettings.fog = true;
            RenderSettings.fogColor = foggySkyColor;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogDensity = 0.01f;

            StopParticles();
        }

        private void ApplySnowyWeather()
        {
            SetLighting(snowySkyColor, snowyAmbientColor, 0.7f, 0.8f);
            RenderSettings.fog = true;
            RenderSettings.fogColor = snowySkyColor;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogStartDistance = 30f;
            RenderSettings.fogEndDistance = 150f;

            StopRain();
            PlaySnow();
        }

        private void ApplyNightWeather()
        {
            SetLighting(nightSkyColor, nightAmbientColor, 0.1f, 0.2f);
            directionalLight.transform.rotation = Quaternion.Euler(-10f, -30f, 0);
            RenderSettings.fog = false;
            StopParticles();

            if (_dynamicSkybox != null)
            {
                _dynamicSkybox.SetFloat("_SunSize", 0.0f);
                _dynamicSkybox.SetFloat("_AtmosphereThickness", 0.5f);
            }
        }

        private void SetLighting(Color skyColor, Color ambientColor, float lightIntensity, float sunSize)
        {
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = ambientColor;
            RenderSettings.fogColor = skyColor;

            if (_dynamicSkybox != null)
            {
                _dynamicSkybox.SetColor("_SkyTint", skyColor);
                _dynamicSkybox.SetColor("_GroundColor", new Color(0.2f, 0.2f, 0.2f));
                _dynamicSkybox.SetFloat("_SunSize", sunSize);
                _dynamicSkybox.SetFloat("_AtmosphereThickness", 1.0f);
            }

            if (directionalLight != null)
            {
                directionalLight.intensity = lightIntensity;
                directionalLight.color = Color.Lerp(directionalLight.color, new Color(1f, 0.95f, 0.9f), 0.5f);
                if (CurrentWeather != WeatherType.Night)
                {
                    directionalLight.transform.rotation = Quaternion.Euler(50f, -30f, 0);
                }
            }

            DynamicGI.UpdateEnvironment();
        }

        private void PlayRain()
        {
            if (rainParticles == null)
            {
                CreateRainParticles();
            }
            if (rainParticles != null && !rainParticles.isPlaying)
            {
                rainParticles.Play();
            }
            if (snowParticles != null && snowParticles.isPlaying)
            {
                snowParticles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            }
        }

        private void StopRain()
        {
            if (rainParticles != null && rainParticles.isPlaying)
            {
                rainParticles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            }
        }

        private void PlaySnow()
        {
            if (snowParticles == null)
            {
                CreateSnowParticles();
            }
            if (snowParticles != null && !snowParticles.isPlaying)
            {
                snowParticles.Play();
            }
            if (rainParticles != null && rainParticles.isPlaying)
            {
                rainParticles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            }
        }

        private void StopSnow()
        {
            if (snowParticles != null && snowParticles.isPlaying)
            {
                snowParticles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            }
        }

        private void StopParticles()
        {
            StopRain();
            StopSnow();
        }

        private void CreateRainParticles()
        {
            if (rainParticles != null) return;

            GameObject rainObj = new GameObject("Rain");
            rainObj.transform.SetParent(transform);
            rainObj.transform.position = new Vector3(0, 50f, 0);
            rainParticles = rainObj.AddComponent<ParticleSystem>();

            var main = rainParticles.main;
            main.loop = true;
            main.startSpeed = 15f;
            main.startLifetime = 3f;
            main.startSize = 0.1f;
            main.maxParticles = 5000;
            main.gravityModifier = 2f;
            main.playOnAwake = false;
            main.stopAction = ParticleSystemStopAction.None;

            var emission = rainParticles.emission;
            emission.rateOverTime = 1000;
            emission.enabled = true;

            var shape = rainParticles.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(200f, 1f, 200f);

            var renderer = rainParticles.GetComponent<ParticleSystemRenderer>();
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            if (_rainMaterial == null)
            {
                EnsureParticleMaterials();
            }
            renderer.material = _rainMaterial;
        }

        private void CreateSnowParticles()
        {
            if (snowParticles != null) return;

            GameObject snowObj = new GameObject("Snow");
            snowObj.transform.SetParent(transform);
            snowObj.transform.position = new Vector3(0, 50f, 0);
            snowParticles = snowObj.AddComponent<ParticleSystem>();

            var main = snowParticles.main;
            main.loop = true;
            main.startSpeed = 2f;
            main.startLifetime = 10f;
            main.startSize = 0.15f;
            main.maxParticles = 3000;
            main.gravityModifier = 0.5f;
            main.playOnAwake = false;
            main.stopAction = ParticleSystemStopAction.None;

            var emission = snowParticles.emission;
            emission.rateOverTime = 500;
            emission.enabled = true;

            var shape = snowParticles.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(200f, 1f, 200f);

            var force = snowParticles.forceOverLifetime;
            force.enabled = true;
            force.x = new ParticleSystem.MinMaxCurve(-0.5f, 0.5f);
            force.z = new ParticleSystem.MinMaxCurve(-0.5f, 0.5f);

            var renderer = snowParticles.GetComponent<ParticleSystemRenderer>();
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            if (_snowMaterial == null)
            {
                EnsureParticleMaterials();
            }
            renderer.material = _snowMaterial;
        }

        public void UpdateWeatherParticlesPosition(Vector3 targetPos)
        {
            if (rainParticles != null)
            {
                rainParticles.transform.position = new Vector3(targetPos.x, 50f, targetPos.z);
            }
            if (snowParticles != null)
            {
                snowParticles.transform.position = new Vector3(targetPos.x, 50f, targetPos.z);
            }
        }
    }
}
