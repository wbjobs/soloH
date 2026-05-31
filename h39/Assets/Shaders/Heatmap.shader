Shader "SoleFriction/Heatmap"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
        _PressureData ("Pressure Data", 2D) = "black" {}
        _MinPressure ("Min Pressure", Float) = 0.0
        _MaxPressure ("Max Pressure", Float) = 1000000.0
        _Intensity ("Intensity", Float) = 1.0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        LOD 200

        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows
        #pragma target 3.0

        sampler2D _MainTex;
        sampler2D _PressureData;
        float _MinPressure;
        float _MaxPressure;
        float _Intensity;

        struct Input
        {
            float2 uv_MainTex;
            float2 uv_PressureData;
        };

        float3 HeatmapColor(float value)
        {
            float t = clamp((value - _MinPressure) / max(_MaxPressure - _MinPressure, 1e-6), 0.0, 1.0);
            t = pow(t, 0.75) * _Intensity;

            float3 blue = float3(0.0, 0.2, 0.8);
            float3 cyan = float3(0.0, 0.8, 1.0);
            float3 green = float3(0.0, 0.9, 0.2);
            float3 yellow = float3(1.0, 0.9, 0.0);
            float3 orange = float3(1.0, 0.5, 0.0);
            float3 red = float3(1.0, 0.0, 0.0);

            if (t < 0.2)
                return lerp(blue, cyan, t / 0.2);
            else if (t < 0.4)
                return lerp(cyan, green, (t - 0.2) / 0.2);
            else if (t < 0.6)
                return lerp(green, yellow, (t - 0.4) / 0.2);
            else if (t < 0.8)
                return lerp(yellow, orange, (t - 0.6) / 0.2);
            else
                return lerp(orange, red, (t - 0.8) / 0.2);
        }

        void surf (Input IN, inout SurfaceOutputStandard o)
        {
            float pressure = tex2D(_PressureData, IN.uv_PressureData).r;
            float3 color = HeatmapColor(pressure);

            float4 texColor = tex2D(_MainTex, IN.uv_MainTex);
            o.Albedo = color * texColor.rgb;
            o.Metallic = 0.1;
            o.Smoothness = 0.3;
            o.Alpha = texColor.a;
        }
        ENDCG
    }
    FallBack "Diffuse"
}
