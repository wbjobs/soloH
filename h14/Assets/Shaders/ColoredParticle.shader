Shader "FlowVisualization/ColoredParticle"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
        _Glossiness ("Smoothness", Range(0,1)) = 0.5
        _Metallic ("Metallic", Range(0,1)) = 0.0
        _EmissionStrength ("Emission", Range(0,2)) = 1.0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 200

        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows
        #pragma target 3.0

        struct Input
        {
            float2 uv_MainTex;
            float3 worldPos;
        };

        sampler2D _MainTex;
        half _Glossiness;
        half _Metallic;
        half _EmissionStrength;

        UNITY_INSTANCING_BUFFER_START(Props)
            UNITY_DEFINE_INSTANCED_PROP(fixed4, _Color)
        UNITY_INSTANCING_BUFFER_END(Props)

        void surf (Input IN, inout SurfaceOutputStandard o)
        {
            fixed4 c = tex2D (_MainTex, IN.uv_MainTex);
            fixed4 instColor = UNITY_ACCESS_INSTANCED_PROP(Props, _Color);
            o.Albedo = c.rgb * instColor.rgb;
            o.Metallic = _Metallic;
            o.Smoothness = _Glossiness;
            o.Emission = instColor.rgb * _EmissionStrength;
            o.Alpha = c.a * instColor.a;
        }
        ENDCG
    }
    FallBack "Diffuse"
}
