Shader "SoleFriction/WaterFilm"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
        _WaterFilmData ("Water Film Data", 2D) = "black" {}
        _MinThickness ("Min Thickness", Float) = 0.0
        _MaxThickness ("Max Thickness", Float) = 1e-4
        _ReflectionStrength ("Reflection Strength", Range(0, 1)) = 0.8
    }
    SubShader
    {
        Tags { "RenderType"="Transparent" "Queue"="Transparent" }
        LOD 200

        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows alpha
        #pragma target 3.0

        sampler2D _MainTex;
        sampler2D _WaterFilmData;
        float _MinThickness;
        float _MaxThickness;
        float _ReflectionStrength;

        struct Input
        {
            float2 uv_MainTex;
            float2 uv_WaterFilmData;
            float3 worldRefl;
            float3 viewDir;
        };

        float3 WaterColor(float thickness)
        {
            float t = clamp((thickness - _MinThickness) / max(_MaxThickness - _MinThickness, 1e-9), 0.0, 1.0);

            float3 deep = float3(0.0, 0.1, 0.3);
            float3 shallow = float3(0.4, 0.7, 0.9);
            float3 dry = float3(0.8, 0.6, 0.4);

            if (thickness < 1e-7)
                return dry;

            return lerp(shallow, deep, t);
        }

        void surf (Input IN, inout SurfaceOutputStandard o)
        {
            float thickness = tex2D(_WaterFilmData, IN.uv_WaterFilmData).r;
            float3 waterCol = WaterColor(thickness);

            float fresnel = pow(1.0 - max(0, dot(normalize(IN.viewDir), float3(0, 1, 0))), 3.0);
            float alpha = thickness > 1e-7 ? 0.6 + fresnel * 0.4 : 0.0;

            float4 texColor = tex2D(_MainTex, IN.uv_MainTex);
            float3 baseCol = lerp(texColor.rgb, waterCol, alpha * 0.8);

            o.Albedo = baseCol;
            o.Metallic = 0.0 + fresnel * _ReflectionStrength * 0.5;
            o.Smoothness = 0.2 + alpha * 0.6;
            o.Alpha = texColor.a;
        }
        ENDCG
    }
    FallBack "Diffuse"
}
