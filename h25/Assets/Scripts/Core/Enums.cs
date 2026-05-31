namespace CitySimulator
{
    public enum WeatherType
    {
        Clear,
        Rainy,
        Foggy,
        Snowy,
        Night
    }

    public enum CameraMode
    {
        TopDown,
        Follow,
        FirstPerson
    }

    public enum TrafficLightState
    {
        Red,
        Yellow,
        Green
    }

    public enum RoadType
    {
        Straight,
        Curved,
        Intersection
    }

    public enum LaneDirection
    {
        Forward,
        Backward
    }

    public enum VehicleType
    {
        Car,
        Truck,
        Bus,
        Motorcycle
    }

    public enum SimulationState
    {
        Stopped,
        Playing,
        Paused,
        Replaying
    }

    public enum SignType
    {
        Stop,
        Yield,
        SpeedLimit,
        NoParking,
        OneWay,
        PedestrianCrossing
    }
}
