namespace GaitSimulation.Core
{
    public enum JointType
    {
        Hip,
        Knee,
        Ankle
    }

    public enum ExoskeletonMode
    {
        Idle,
        Motor,
        Generator
    }

    public enum Side
    {
        Left,
        Right
    }

    public enum GaitPhase
    {
        HeelStrike,
        FootFlat,
        MidStance,
        HeelOff,
        ToeOff,
        EarlySwing,
        LateSwing
    }
}
