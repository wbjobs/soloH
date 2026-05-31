Shader "Custom/LCSPointShader"
{
    Properties
    {
        _PointSize ("Point Size", Float) = 0.01
    }
    
    SubShader
    {
        Tags { "RenderType"="Transparent" "Queue"="Transparent" }
        LOD 200

        Pass
        {
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Off
            
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            StructuredBuffer<float3> positions;
            StructuredBuffer<float4> colors;
            float pointSize;

            struct v2f
            {
                float4 position : SV_POSITION;
                float4 color : COLOR;
                float pointSize : PSIZE;
            };

            v2f vert(uint id : SV_VertexID)
            {
                v2f o;
                float3 worldPos = positions[id];
                o.position = UnityObjectToClipPos(float4(worldPos, 1.0));
                o.color = colors[id];
                o.pointSize = pointSize * (1.0 / length(UnityObjectToViewPos(float4(worldPos, 1.0))));
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                float2 uv = (float2)(i.pointSize / 2.0 - abs(i.position.xy % i.pointSize - i.pointSize / 2.0)) / (i.pointSize / 2.0);
                float dist = length(uv);
                if (dist > 1.0) discard;
                
                float alpha = smoothstep(1.0, 0.7, dist);
                return float4(i.color.rgb, i.color.a * alpha);
            }
            ENDCG
        }
    }
}
