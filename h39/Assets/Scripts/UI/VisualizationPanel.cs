using UnityEngine;
using UnityEngine.UI;
using System.Collections.Generic;
using SoleFrictionSim.Data;

namespace SoleFrictionSim.UI
{
    public class VisualizationPanel : MonoBehaviour
    {
        [Header("Heatmap Display")]
        [SerializeField] private RawImage _pressureHeatmap;
        [SerializeField] private RawImage _waterFilmHeatmap;
        [SerializeField] private RawImage _wearHeatmap;
        [SerializeField] private RawImage _temperatureHeatmap;

        [Header("Curve Display")]
        [SerializeField] private RectTransform _curveContainer;
        [SerializeField] private Image _curveLinePrefab;
        [SerializeField] private Text _curveMinLabel;
        [SerializeField] private Text _curveMaxLabel;
        [SerializeField] private Text _curveTitle;

        [Header("Color Bar")]
        [SerializeField] private RawImage _pressureColorBar;
        [SerializeField] private Text _pressureMinText;
        [SerializeField] private Text _pressureMaxText;
        [SerializeField] private RawImage _waterColorBar;
        [SerializeField] private Text _waterMinText;
        [SerializeField] private Text _waterMaxText;
        [SerializeField] private RawImage _wearColorBar;
        [SerializeField] private Text _wearMinText;
        [SerializeField] private Text _wearMaxText;
        [SerializeField] private RawImage _temperatureColorBar;
        [SerializeField] private Text _temperatureMinText;
        [SerializeField] private Text _temperatureMaxText;

        [Header("Statistics Display")]
        [SerializeField] private Text _maxPressureText;
        [SerializeField] private Text _avgPressureText;
        [SerializeField] private Text _contactAreaText;
        [SerializeField] private Text _frictionCoeffText;
        [SerializeField] private Text _computeTimeText;
        [SerializeField] private Text _iterationsText;
        [SerializeField] private Text _wearRateText;
        [SerializeField] private Text _predictedLifeText;
        [SerializeField] private Text _maxTemperatureText;
        [SerializeField] private Text _modulusReductionText;

        [Header("Visualization Mode")]
        [SerializeField] private Dropdown _visualizationModeDropdown;
        [SerializeField] private Toggle _showWireframeToggle;
        [SerializeField] private Slider _heatmapIntensitySlider;

        private Texture2D _pressureTexture;
        private Texture2D _waterFilmTexture;
        private Texture2D _wearTexture;
        private Texture2D _temperatureTexture;
        private List<Image> _curveLines = new List<Image>();
        private ContactResult _currentResult;

        public float HeatmapIntensity => _heatmapIntensitySlider.value;
        public VisualizationMode VisualizationMode => (VisualizationMode)_visualizationModeDropdown.value;
        public bool ShowWireframe => _showWireframeToggle.isOn;

        private void Awake()
        {
            _visualizationModeDropdown.onValueChanged.AddListener(OnVisualizationModeChanged);
            _showWireframeToggle.onValueChanged.AddListener(OnShowWireframeChanged);
            _heatmapIntensitySlider.onValueChanged.AddListener(OnIntensityChanged);
        }

        public void UpdateContactResult(ContactResult result)
        {
            _currentResult = result;
            if (result == null) return;

            GeneratePressureHeatmap(result);
            GenerateWaterFilmHeatmap(result);
            GenerateWearHeatmap(result);
            GenerateTemperatureHeatmap(result);
            GenerateFrictionCurve(result);
            UpdateStatistics(result);
        }

        private void GeneratePressureHeatmap(ContactResult result)
        {
            int n = result.Resolution;
            if (_pressureTexture == null || _pressureTexture.width != n)
            {
                _pressureTexture = new Texture2D(n, n, TextureFormat.RGBA32, false);
                _pressureTexture.wrapMode = TextureWrapMode.Clamp;
                _pressureTexture.filterMode = FilterMode.Bilinear;
            }

            float maxP = result.maxContactPressure;
            Color[] colors = new Color[n * n];

            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float p = result.GetPressureAt(i, j);
                    colors[i * n + j] = HeatmapColor(p, 0f, maxP);
                }
            }

            _pressureTexture.SetPixels(colors);
            _pressureTexture.Apply();
            _pressureHeatmap.texture = _pressureTexture;

            GenerateColorBar(_pressureColorBar, 0f, maxP, "Pa");
            _pressureMinText.text = "0";
            _pressureMaxText.text = $"{maxP:0.0e0} Pa";
        }

        private void GenerateWaterFilmHeatmap(ContactResult result)
        {
            if (result.waterFilmThickness == null) return;

            int n = result.waterFilmThickness.GetLength(0);
            if (_waterFilmTexture == null || _waterFilmTexture.width != n)
            {
                _waterFilmTexture = new Texture2D(n, n, TextureFormat.RGBA32, false);
                _waterFilmTexture.wrapMode = TextureWrapMode.Clamp;
                _waterFilmTexture.filterMode = FilterMode.Bilinear;
            }

            float maxH = 0f;
            for (int i = 0; i < n; i++)
                for (int j = 0; j < n; j++)
                    if (result.waterFilmThickness[i, j] > maxH) maxH = result.waterFilmThickness[i, j];

            Color[] colors = new Color[n * n];
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float h = result.waterFilmThickness[i, j];
                    colors[i * n + j] = WaterFilmColor(h, 0f, maxH);
                }
            }

            _waterFilmTexture.SetPixels(colors);
            _waterFilmTexture.Apply();
            _waterFilmHeatmap.texture = _waterFilmTexture;

            GenerateColorBar(_waterColorBar, 0f, maxH, "m", true);
            _waterMinText.text = "0";
            _waterMaxText.text = $"{maxH:0.0e0} m";
        }

        private void GenerateWearHeatmap(ContactResult result)
        {
            if (result.wearDepth == null) return;

            int n = result.wearDepth.GetLength(0);
            if (_wearTexture == null || _wearTexture.width != n)
            {
                _wearTexture = new Texture2D(n, n, TextureFormat.RGBA32, false);
                _wearTexture.wrapMode = TextureWrapMode.Clamp;
                _wearTexture.filterMode = FilterMode.Bilinear;
            }

            float maxWear = 0f;
            for (int i = 0; i < n; i++)
                for (int j = 0; j < n; j++)
                    if (result.wearDepth[i, j] > maxWear) maxWear = result.wearDepth[i, j];

            Color[] colors = new Color[n * n];
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float w = result.wearDepth[i, j];
                    colors[i * n + j] = WearColor(w, 0f, maxWear);
                }
            }

            _wearTexture.SetPixels(colors);
            _wearTexture.Apply();
            if (_wearHeatmap != null) _wearHeatmap.texture = _wearTexture;

            GenerateColorBar(_wearColorBar, 0f, maxWear, "m", false, true);
            if (_wearMinText != null) _wearMinText.text = "0";
            if (_wearMaxText != null) _wearMaxText.text = $"{maxWear:0.0e0} m";
        }

        private void GenerateTemperatureHeatmap(ContactResult result)
        {
            if (result.temperatureField == null) return;

            int n = result.temperatureField.GetLength(0);
            if (_temperatureTexture == null || _temperatureTexture.width != n)
            {
                _temperatureTexture = new Texture2D(n, n, TextureFormat.RGBA32, false);
                _temperatureTexture.wrapMode = TextureWrapMode.Clamp;
                _temperatureTexture.filterMode = FilterMode.Bilinear;
            }

            float minT = float.MaxValue;
            float maxT = float.MinValue;
            for (int i = 0; i < n; i++)
                for (int j = 0; j < n; j++)
                {
                    float t = result.temperatureField[i, j];
                    if (t < minT) minT = t;
                    if (t > maxT) maxT = t;
                }

            if (maxT <= minT) maxT = minT + 1f;

            Color[] colors = new Color[n * n];
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float temp = result.temperatureField[i, j];
                    colors[i * n + j] = TemperatureColor(temp, minT, maxT);
                }
            }

            _temperatureTexture.SetPixels(colors);
            _temperatureTexture.Apply();
            if (_temperatureHeatmap != null) _temperatureHeatmap.texture = _temperatureTexture;

            GenerateColorBar(_temperatureColorBar, minT, maxT, "°C", false, false, true);
            if (_temperatureMinText != null) _temperatureMinText.text = $"{minT:0.0}°C";
            if (_temperatureMaxText != null) _temperatureMaxText.text = $"{maxT:0.0}°C";
        }

        private Color WearColor(float value, float minVal, float maxVal)
        {
            float t = Mathf.Clamp01((value - minVal) / Mathf.Max(maxVal - minVal, 1e-9f));
            t = Mathf.Pow(t, 0.75f) * _heatmapIntensitySlider.value;

            Color light = new Color(1.0f, 1.0f, 0.8f);
            Color yellow = new Color(1.0f, 0.9f, 0.2f);
            Color orange = new Color(1.0f, 0.5f, 0.0f);
            Color red = new Color(0.9f, 0.1f, 0.1f);
            Color darkRed = new Color(0.5f, 0.0f, 0.0f);

            if (t < 0.25f) return Color.Lerp(light, yellow, t / 0.25f);
            else if (t < 0.5f) return Color.Lerp(yellow, orange, (t - 0.25f) / 0.25f);
            else if (t < 0.75f) return Color.Lerp(orange, red, (t - 0.5f) / 0.25f);
            else return Color.Lerp(red, darkRed, (t - 0.75f) / 0.25f);
        }

        private Color TemperatureColor(float value, float minVal, float maxVal)
        {
            float t = Mathf.Clamp01((value - minVal) / Mathf.Max(maxVal - minVal, 1e-6f));
            t = Mathf.Pow(t, 0.75f) * _heatmapIntensitySlider.value;

            Color blue = new Color(0.0f, 0.3f, 0.8f);
            Color cyan = new Color(0.0f, 0.8f, 1.0f);
            Color green = new Color(0.2f, 0.9f, 0.3f);
            Color yellow = new Color(1.0f, 0.9f, 0.1f);
            Color orange = new Color(1.0f, 0.5f, 0.0f);
            Color red = new Color(1.0f, 0.0f, 0.0f);
            Color white = new Color(1.0f, 0.95f, 0.9f);

            if (t < 0.167f) return Color.Lerp(blue, cyan, t / 0.167f);
            else if (t < 0.333f) return Color.Lerp(cyan, green, (t - 0.167f) / 0.167f);
            else if (t < 0.5f) return Color.Lerp(green, yellow, (t - 0.333f) / 0.167f);
            else if (t < 0.667f) return Color.Lerp(yellow, orange, (t - 0.5f) / 0.167f);
            else if (t < 0.833f) return Color.Lerp(orange, red, (t - 0.667f) / 0.167f);
            else return Color.Lerp(red, white, (t - 0.833f) / 0.167f);
        }

        private void GenerateFrictionCurve(ContactResult result)
        {
            if (result.slipVelocities == null || result.frictionCoefficients == null) return;

            foreach (var line in _curveLines)
            {
                if (line != null) Destroy(line.gameObject);
            }
            _curveLines.Clear();

            int n = result.slipVelocities.Length;
            float minV = Mathf.Log10(result.slipVelocities[0]);
            float maxV = Mathf.Log10(result.slipVelocities[n - 1]);
            float minMu = float.MaxValue;
            float maxMu = float.MinValue;

            for (int i = 0; i < n; i++)
            {
                if (result.frictionCoefficients[i] < minMu) minMu = result.frictionCoefficients[i];
                if (result.frictionCoefficients[i] > maxMu) maxMu = result.frictionCoefficients[i];
            }

            minMu = Mathf.Max(0, minMu - 0.1f);
            maxMu = maxMu + 0.1f;

            RectTransform containerRect = _curveContainer.rect;
            float width = containerRect.width;
            float height = containerRect.height;

            Vector2[] points = new Vector2[n];
            for (int i = 0; i < n; i++)
            {
                float logV = Mathf.Log10(result.slipVelocities[i]);
                float x = (logV - minV) / (maxV - minV) * width;
                float y = (result.frictionCoefficients[i] - minMu) / (maxMu - minMu) * height;
                points[i] = new Vector2(x, y);
            }

            for (int i = 0; i < n - 1; i++)
            {
                Vector2 p1 = points[i];
                Vector2 p2 = points[i + 1];
                DrawLineSegment(p1, p2, width, height);
            }

            _curveMinLabel.text = $"{result.slipVelocities[0]:0.0e0} m/s";
            _curveMaxLabel.text = $"{result.slipVelocities[n - 1]:0.0e0} m/s";
            _curveTitle.text = $"Friction Coefficient (μ={minMu:0.2f}-{maxMu:0.2f})";
        }

        private void DrawLineSegment(Vector2 p1, Vector2 p2, float width, float height)
        {
            Vector2 diff = p2 - p1;
            float length = diff.magnitude;
            float angle = Mathf.Atan2(diff.y, diff.x) * Mathf.Rad2Deg;

            var line = Instantiate(_curveLinePrefab, _curveContainer);
            var rect = line.rectTransform;

            rect.anchorMin = Vector2.zero;
            rect.anchorMax = Vector2.zero;
            rect.pivot = new Vector2(0f, 0.5f);

            rect.sizeDelta = new Vector2(length, 2f);
            rect.anchoredPosition = new Vector2(p1.x, p1.y);
            rect.localRotation = Quaternion.Euler(0, 0, angle);

            line.color = new Color(0.3f, 0.8f, 1f);
            _curveLines.Add(line);
        }

        private void UpdateStatistics(ContactResult result)
        {
            _maxPressureText.text = $"Max Pressure: {result.maxContactPressure:0.0e0} Pa";
            _avgPressureText.text = $"Avg Pressure: {result.averagePressure:0.0e0} Pa";
            _contactAreaText.text = $"Contact Ratio: {result.contactAreaRatio * 100:0.0}%";

            if (result.frictionCoefficients != null && result.frictionCoefficients.Length > 0)
            {
                int midIdx = result.frictionCoefficients.Length / 2;
                _frictionCoeffText.text = $"μ @ 1m/s: {result.frictionCoefficients[midIdx]:0.3f}";
            }

            _computeTimeText.text = $"Compute Time: {result.computeTime:0.00}s";
            _iterationsText.text = $"Iterations: {result.iterations}";

            if (_wearRateText != null)
            {
                string wearRate = result.maxWearRate > 0 ? $"{result.maxWearRate:0.0e0} m/s" : "-";
                _wearRateText.text = $"Max Wear Rate: {wearRate}";
            }

            if (_predictedLifeText != null)
            {
                string life = result.predictedLifeKm > 0 ? $"{result.predictedLifeKm:0.0} km" : "-";
                _predictedLifeText.text = $"Predicted Life: {life}";
            }

            if (_maxTemperatureText != null)
            {
                string temp = result.maxTemperature > 0 ? $"{result.maxTemperature:0.1} °C" : "-";
                _maxTemperatureText.text = $"Max Temperature: {temp}";
            }

            if (_modulusReductionText != null)
            {
                string modReduction = result.modulusReductionPercent > 0 ? $"{result.modulusReductionPercent:0.0}%" : "-";
                _modulusReductionText.text = $"Modulus Reduction: {modReduction}";
            }
        }

        private Color HeatmapColor(float value, float minVal, float maxVal)
        {
            float t = Mathf.Clamp01((value - minVal) / Mathf.Max(maxVal - minVal, 1e-6f));
            t = Mathf.Pow(t, 0.75f) * _heatmapIntensitySlider.value;

            Color blue = new Color(0.0f, 0.2f, 0.8f);
            Color cyan = new Color(0.0f, 0.8f, 1.0f);
            Color green = new Color(0.0f, 0.9f, 0.2f);
            Color yellow = new Color(1.0f, 0.9f, 0.0f);
            Color orange = new Color(1.0f, 0.5f, 0.0f);
            Color red = new Color(1.0f, 0.0f, 0.0f);

            if (t < 0.2f) return Color.Lerp(blue, cyan, t / 0.2f);
            else if (t < 0.4f) return Color.Lerp(cyan, green, (t - 0.2f) / 0.2f);
            else if (t < 0.6f) return Color.Lerp(green, yellow, (t - 0.4f) / 0.2f);
            else if (t < 0.8f) return Color.Lerp(yellow, orange, (t - 0.6f) / 0.2f);
            else return Color.Lerp(orange, red, (t - 0.8f) / 0.2f);
        }

        private Color WaterFilmColor(float value, float minVal, float maxVal)
        {
            float t = Mathf.Clamp01((value - minVal) / Mathf.Max(maxVal - minVal, 1e-9f));

            Color dry = new Color(0.8f, 0.6f, 0.4f);
            Color shallow = new Color(0.4f, 0.7f, 0.9f);
            Color deep = new Color(0.0f, 0.1f, 0.3f);

            if (value < 1e-7f) return dry;
            if (t < 0.5f) return Color.Lerp(shallow, deep, t * 2f);
            return deep;
        }

        private void GenerateColorBar(RawImage target, float minVal, float maxVal, string unit, 
            bool isWater = false, bool isWear = false, bool isTemperature = false)
        {
            if (target == null) return;
            
            int height = 256;
            int width = 32;

            Texture2D tex = new Texture2D(width, height, TextureFormat.RGBA32, false);
            Color[] colors = new Color[width * height];

            for (int y = 0; y < height; y++)
            {
                float t = (float)y / (height - 1);
                float val = minVal + t * (maxVal - minVal);
                Color c;
                
                if (isWater)
                    c = WaterFilmColor(val, minVal, maxVal);
                else if (isWear)
                    c = WearColor(val, minVal, maxVal);
                else if (isTemperature)
                    c = TemperatureColor(val, minVal, maxVal);
                else
                    c = HeatmapColor(val, minVal, maxVal);

                for (int x = 0; x < width; x++)
                {
                    colors[y * width + x] = c;
                }
            }

            tex.SetPixels(colors);
            tex.Apply();
            target.texture = tex;
        }

        private void OnVisualizationModeChanged(int value)
        {
            VisualizationModeChanged?.Invoke((VisualizationMode)value);
        }

        private void OnShowWireframeChanged(bool show)
        {
            WireframeToggled?.Invoke(show);
        }

        private void OnIntensityChanged(float value)
        {
            if (_currentResult != null)
            {
                GeneratePressureHeatmap(_currentResult);
                GenerateWaterFilmHeatmap(_currentResult);
                GenerateWearHeatmap(_currentResult);
                GenerateTemperatureHeatmap(_currentResult);
            }
            IntensityChanged?.Invoke(value);
        }

        public event System.Action<VisualizationMode> VisualizationModeChanged;
        public event System.Action<bool> WireframeToggled;
        public event System.Action<float> IntensityChanged;
    }
}
