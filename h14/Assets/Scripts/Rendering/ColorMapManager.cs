using UnityEngine;
using FlowVisualization.Core;

namespace FlowVisualization.Rendering
{
    public class ColorMapManager : MonoBehaviour
    {
        public enum ColormapType
        {
            Jet,
            Viridis,
            Plasma,
            Rainbow,
            CoolWarm,
            Grayscale
        }

        public ColormapType ActiveColormap = ColormapType.Jet;
        public ScalarFieldType FieldType = ScalarFieldType.VelocityMagnitude;
        public float MinValue = 0f;
        public float MaxValue = 5f;
        public bool UseLogScale = false;
        public float Gamma = 1.0f;

        private Texture2D _colormapTexture;
        private const int TextureWidth = 256;

        public Texture2D ColormapTexture => _colormapTexture;

        private void Awake()
        {
            CreateColormapTexture();
        }

        private void CreateColormapTexture()
        {
            _colormapTexture = new Texture2D(TextureWidth, 1, TextureFormat.RGBA32, false);
            _colormapTexture.wrapMode = TextureWrapMode.Clamp;
            _colormapTexture.filterMode = FilterMode.Bilinear;
            UpdateColormap();
        }

        public void UpdateColormap()
        {
            if (_colormapTexture == null) CreateColormapTexture();

            Color[] colors = new Color[TextureWidth];
            for (int i = 0; i < TextureWidth; i++)
            {
                float t = i / (float)(TextureWidth - 1);
                colors[i] = GetColorFromColormap(t, ActiveColormap);
            }
            _colormapTexture.SetPixels(colors);
            _colormapTexture.Apply();
        }

        public static Color GetColorFromColormap(float t, ColormapType type)
        {
            t = Mathf.Clamp01(t);

            switch (type)
            {
                case ColormapType.Jet:
                    return JetColormap(t);
                case ColormapType.Viridis:
                    return ViridisColormap(t);
                case ColormapType.Plasma:
                    return PlasmaColormap(t);
                case ColormapType.Rainbow:
                    return RainbowColormap(t);
                case ColormapType.CoolWarm:
                    return CoolWarmColormap(t);
                case ColormapType.Grayscale:
                    return Color.Lerp(Color.black, Color.white, t);
                default:
                    return JetColormap(t);
            }
        }

        private static Color JetColormap(float t)
        {
            float r = 0f, g = 0f, b = 0f;

            if (t < 0.25f)
            {
                r = 0f;
                g = 0f;
                b = 0.5f + t * 2f;
            }
            else if (t < 0.5f)
            {
                r = 0f;
                g = (t - 0.25f) * 4f;
                b = 1f;
            }
            else if (t < 0.75f)
            {
                r = (t - 0.5f) * 4f;
                g = 1f;
                b = 1f - (t - 0.5f) * 4f;
            }
            else
            {
                r = 1f;
                g = 1f - (t - 0.75f) * 4f;
                b = 0f;
            }

            return new Color(r, g, b, 1f);
        }

        private static Color ViridisColormap(float t)
        {
            float r = 0.2777f + t * 0.105f + t * t * (-0.3308f) + t * t * t * (-4.6343f) + t * t * t * t * (4.7861f);
            float g = 0.0054f + t * 1.4073f + t * t * (0.2148f) + t * t * t * (-2.1474f) + t * t * t * t * (0.2868f);
            float b = 0.3340f + t * 1.3845f + t * t * (0.0933f) + t * t * t * (-1.1060f) + t * t * t * t * (-0.1771f);
            return new Color(Mathf.Clamp01(r), Mathf.Clamp01(g), Mathf.Clamp01(b), 1f);
        }

        private static Color PlasmaColormap(float t)
        {
            float r = 0.0504f + t * (2.3095f) + t * t * (-2.9236f) + t * t * t * (1.4964f);
            float g = 0.0268f + t * (0.1457f) + t * t * (1.4267f) + t * t * t * (-0.2963f);
            float b = 0.5357f + t * (0.3852f) + t * t * (-1.2995f) + t * t * t * (0.7141f);
            return new Color(Mathf.Clamp01(r), Mathf.Clamp01(g), Mathf.Clamp01(b), 1f);
        }

        private static Color RainbowColormap(float t)
        {
            float hue = t * 0.8f;
            return Color.HSVToRGB(hue, 1f, 1f);
        }

        private static Color CoolWarmColormap(float t)
        {
            if (t < 0.5f)
            {
                float t2 = t * 2f;
                return new Color(0.2f * t2, 0.4f * t2, 0.8f + 0.2f * t2, 1f);
            }
            else
            {
                float t2 = (t - 0.5f) * 2f;
                return new Color(0.8f + 0.2f * t2, 0.4f * (1f - t2), 0.2f * (1f - t2), 1f);
            }
        }

        public Color MapScalar(float value)
        {
            float normalizedValue;

            if (UseLogScale)
            {
                float logMin = Mathf.Log10(Mathf.Max(MinValue, 1e-10f));
                float logMax = Mathf.Log10(Mathf.Max(MaxValue, 1e-10f));
                float logVal = Mathf.Log10(Mathf.Max(value, 1e-10f));
                normalizedValue = (logVal - logMin) / (logMax - logMin);
            }
            else
            {
                normalizedValue = (value - MinValue) / (MaxValue - MinValue);
            }

            if (Gamma != 1.0f)
            {
                normalizedValue = Mathf.Pow(Mathf.Clamp01(normalizedValue), Gamma);
            }

            return GetColorFromColormap(Mathf.Clamp01(normalizedValue), ActiveColormap);
        }

        public void SetFieldType(ScalarFieldType type)
        {
            FieldType = type;
        }

        public void SetColormap(ColormapType type)
        {
            ActiveColormap = type;
            UpdateColormap();
        }

        public void SetRange(float min, float max)
        {
            MinValue = min;
            MaxValue = max;
        }
    }
}
