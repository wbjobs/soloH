namespace SoleFrictionSim.Data
{
    public enum PatternType
    {
        Herringbone,
        Wave,
        Block
    }

    public enum GroundType
    {
        DryAsphalt,
        WetAsphalt,
        DryTile,
        WetTile,
        Ice
    }

    public enum VisualizationMode
    {
        Solid,
        ContactPressure,
        WaterFilm,
        WearDepth,
        Temperature,
        Wireframe
    }

    public enum ExportFormat
    {
        STL_ASCII,
        STL_Binary,
        DXF_2D,
        OBJ,
        CSV_Data
    }

    public enum SimulationState
    {
        Idle,
        Running,
        Paused,
        Completed,
        Error
    }
}
