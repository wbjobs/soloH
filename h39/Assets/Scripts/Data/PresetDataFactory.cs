using UnityEngine;

namespace SoleFrictionSim.Data
{
    public static class PresetDataFactory
    {
        public static RubberMaterial CreateSoftRubber()
        {
            var mat = ScriptableObject.CreateInstance<RubberMaterial>();
            mat.name = "Rubber_Soft";
            mat.shoreHardness = 40f;
            mat.elasticModulus = 1.2f;
            mat.lossFactor = 0.3f;
            mat.poissonRatio = 0.495f;
            mat.hurstExponent = 0.7f;
            mat.rmsRoughness = 50f;
            mat.correlationLength = 200f;
            mat.minimumLengthScale = 1e-9f;
            mat.relaxationTimes = new float[] { 1e-6f, 1e-5f, 1e-4f, 1e-3f, 1e-2f };
            mat.relaxationModuli = new float[] { 3f, 2f, 1.5f, 1.2f, 1.0f };
            return mat;
        }

        public static RubberMaterial CreateMediumRubber()
        {
            var mat = ScriptableObject.CreateInstance<RubberMaterial>();
            mat.name = "Rubber_Medium";
            mat.shoreHardness = 55f;
            mat.elasticModulus = 2.5f;
            mat.lossFactor = 0.25f;
            mat.poissonRatio = 0.495f;
            mat.hurstExponent = 0.7f;
            mat.rmsRoughness = 50f;
            mat.correlationLength = 200f;
            mat.minimumLengthScale = 1e-9f;
            mat.relaxationTimes = new float[] { 1e-6f, 1e-5f, 1e-4f, 1e-3f, 1e-2f };
            mat.relaxationModuli = new float[] { 5f, 3f, 2f, 1.5f, 1.2f };
            return mat;
        }

        public static RubberMaterial CreateHardRubber()
        {
            var mat = ScriptableObject.CreateInstance<RubberMaterial>();
            mat.name = "Rubber_Hard";
            mat.shoreHardness = 70f;
            mat.elasticModulus = 5.0f;
            mat.lossFactor = 0.2f;
            mat.poissonRatio = 0.495f;
            mat.hurstExponent = 0.7f;
            mat.rmsRoughness = 50f;
            mat.correlationLength = 200f;
            mat.minimumLengthScale = 1e-9f;
            mat.relaxationTimes = new float[] { 1e-6f, 1e-5f, 1e-4f, 1e-3f, 1e-2f };
            mat.relaxationModuli = new float[] { 8f, 5f, 3.5f, 2.5f, 2.0f };
            return mat;
        }

        public static GroundSurface CreateDryAsphalt()
        {
            var ground = ScriptableObject.CreateInstance<GroundSurface>();
            ground.name = "Ground_DryAsphalt";
            ground.groundType = GroundType.DryAsphalt;
            ground.roughness = 500f;
            ground.hardness = 20f;
            ground.correlationLength = 500f;
            ground.minimumLengthScale = 1e-9f;
            ground.waterFilmThickness = 0f;
            ground.hurstExponent = 0.8f;
            ground.fluidViscosity = 0.001f;
            ground.InitializeSpectrum(256);
            return ground;
        }

        public static GroundSurface CreateWetAsphalt()
        {
            var ground = ScriptableObject.CreateInstance<GroundSurface>();
            ground.name = "Ground_WetAsphalt";
            ground.groundType = GroundType.WetAsphalt;
            ground.roughness = 500f;
            ground.hardness = 20f;
            ground.correlationLength = 500f;
            ground.minimumLengthScale = 1e-9f;
            ground.waterFilmThickness = 50f;
            ground.hurstExponent = 0.8f;
            ground.fluidViscosity = 0.001f;
            ground.InitializeSpectrum(256);
            return ground;
        }

        public static GroundSurface CreateDryTile()
        {
            var ground = ScriptableObject.CreateInstance<GroundSurface>();
            ground.name = "Ground_DryTile";
            ground.groundType = GroundType.DryTile;
            ground.roughness = 5f;
            ground.hardness = 60f;
            ground.correlationLength = 100f;
            ground.minimumLengthScale = 1e-9f;
            ground.waterFilmThickness = 0f;
            ground.hurstExponent = 0.85f;
            ground.fluidViscosity = 0.001f;
            ground.InitializeSpectrum(256);
            return ground;
        }

        public static GroundSurface CreateWetTile()
        {
            var ground = ScriptableObject.CreateInstance<GroundSurface>();
            ground.name = "Ground_WetTile";
            ground.groundType = GroundType.WetTile;
            ground.roughness = 5f;
            ground.hardness = 60f;
            ground.correlationLength = 100f;
            ground.minimumLengthScale = 1e-9f;
            ground.waterFilmThickness = 10f;
            ground.hurstExponent = 0.85f;
            ground.fluidViscosity = 0.001f;
            ground.InitializeSpectrum(256);
            return ground;
        }

        public static GroundSurface CreateIce()
        {
            var ground = ScriptableObject.CreateInstance<GroundSurface>();
            ground.name = "Ground_Ice";
            ground.groundType = GroundType.Ice;
            ground.roughness = 1f;
            ground.hardness = 10f;
            ground.correlationLength = 200f;
            ground.minimumLengthScale = 1e-9f;
            ground.waterFilmThickness = 100f;
            ground.hurstExponent = 0.9f;
            ground.fluidViscosity = 0.0018f;
            ground.InitializeSpectrum(256);
            return ground;
        }
    }
}
