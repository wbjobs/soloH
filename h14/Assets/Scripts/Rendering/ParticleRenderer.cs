using System.Collections.Generic;
using UnityEngine;
using FlowVisualization.Particles;

namespace FlowVisualization.Rendering
{
    public class ParticleRenderer : MonoBehaviour
    {
        public Material ParticleMaterial;
        public float ParticleSize = 0.01f;
        public bool RenderParticles = true;
        public bool UseInstancing = true;

        private struct ParticleRenderData
        {
            public Vector3 Position;
            public Color Color;
            public float Size;
        }

        private const int MaxParticlesPerBatch = 1023;
        private List<ParticleRenderData> _particleData = new List<ParticleRenderData>(100000);
        private Mesh _particleMesh;
        private MaterialPropertyBlock _propertyBlock;
        private Vector4[] _positionsArray;
        private Vector4[] _colorsArray;
        private ParticleSystemManager _particleSystem;

        private void Awake()
        {
            _propertyBlock = new MaterialPropertyBlock();
            CreateParticleMesh();

            if (ParticleMaterial == null)
            {
                ParticleMaterial = new Material(Shader.Find("Standard"));
                ParticleMaterial.enableInstancing = true;
            }

            _positionsArray = new Vector4[MaxParticlesPerBatch];
            _colorsArray = new Vector4[MaxParticlesPerBatch];
        }

        private void CreateParticleMesh()
        {
            _particleMesh = new Mesh();
            
            Vector3[] vertices = new Vector3[8];
            int[] triangles = new int[36];

            float size = 0.5f;
            vertices[0] = new Vector3(-size, -size, -size);
            vertices[1] = new Vector3(size, -size, -size);
            vertices[2] = new Vector3(size, size, -size);
            vertices[3] = new Vector3(-size, size, -size);
            vertices[4] = new Vector3(-size, -size, size);
            vertices[5] = new Vector3(size, -size, size);
            vertices[6] = new Vector3(size, size, size);
            vertices[7] = new Vector3(-size, size, size);

            int[] cubeTriangles =
            {
                0, 2, 1, 0, 3, 2,
                1, 6, 5, 1, 2, 6,
                5, 7, 4, 5, 6, 7,
                4, 3, 0, 4, 7, 3,
                3, 6, 2, 3, 7, 6,
                4, 1, 5, 4, 0, 1
            };

            _particleMesh.vertices = vertices;
            _particleMesh.triangles = cubeTriangles;
            _particleMesh.RecalculateNormals();
            _particleMesh.UploadMeshData(true);
        }

        public void UpdateRendering(List<SeedPoint> seedPoints, ParticleSystemManager manager)
        {
            if (_particleSystem == null) _particleSystem = manager;

            if (!RenderParticles) return;

            _particleData.Clear();

            foreach (var seed in seedPoints)
            {
                foreach (var particle in seed.Particles)
                {
                    if (!particle.Data.IsAlive) continue;

                    Color particleColor = manager.GetColorForScalar(particle.Data.ScalarValue);

                    _particleData.Add(new ParticleRenderData
                    {
                        Position = particle.Data.Position,
                        Color = particleColor,
                        Size = ParticleSize
                    });
                }
            }

            if (_particleData.Count == 0) return;

            if (UseInstancing && SystemInfo.supportsInstancing)
            {
                RenderInstanced();
            }
            else
            {
                RenderManual();
            }
        }

        private void RenderInstanced()
        {
            int totalParticles = _particleData.Count;
            int batches = Mathf.CeilToInt(totalParticles / (float)MaxParticlesPerBatch);

            for (int batch = 0; batch < batches; batch++)
            {
                int startIdx = batch * MaxParticlesPerBatch;
                int count = Mathf.Min(MaxParticlesPerBatch, totalParticles - startIdx);

                for (int i = 0; i < count; i++)
                {
                    int idx = startIdx + i;
                    _positionsArray[i] = new Vector4(
                        _particleData[idx].Position.x,
                        _particleData[idx].Position.y,
                        _particleData[idx].Position.z,
                        _particleData[idx].Size
                    );
                    _colorsArray[i] = new Vector4(
                        _particleData[idx].Color.r,
                        _particleData[idx].Color.g,
                        _particleData[idx].Color.b,
                        _particleData[idx].Color.a
                    );
                }

                _propertyBlock.SetVectorArray("_Positions", _positionsArray);
                _propertyBlock.SetVectorArray("_Colors", _colorsArray);
                _propertyBlock.SetInt("_BatchCount", count);

                Graphics.DrawMeshInstanced(
                    _particleMesh,
                    0,
                    ParticleMaterial,
                    new List<Matrix4x4>(),
                    _propertyBlock,
                    UnityEngine.Rendering.ShadowCastingMode.Off,
                    false
                );
            }
        }

        private void RenderManual()
        {
            for (int i = 0; i < _particleData.Count; i++)
            {
                var data = _particleData[i];
                Matrix4x4 matrix = Matrix4x4.TRS(
                    data.Position,
                    Quaternion.identity,
                    Vector3.one * data.Size
                );

                _propertyBlock.SetColor("_Color", data.Color);

                Graphics.DrawMesh(
                    _particleMesh,
                    matrix,
                    ParticleMaterial,
                    0,
                    null,
                    0,
                    _propertyBlock
                );
            }
        }

        public void SetParticleSize(float size)
        {
            ParticleSize = size;
        }

        public void SetParticleMaterial(Material material)
        {
            ParticleMaterial = material;
            if (material != null)
            {
                material.enableInstancing = true;
            }
        }
    }
}
