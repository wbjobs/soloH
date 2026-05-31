import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import PIDParameters
from app.pid_controller import PIDController


def test_pid_response():
    params = PIDParameters(
        enabled=True,
        targetDropletSize=80.0,
        Kp=0.5,
        Ki=0.1,
        Kd=0.01,
        outputMin=1.0,
        outputMax=20.0
    )

    pid = PIDController(params)

    print("Testing PID controller response...")
    print("=" * 50)
    print(f"Target size: {params.targetDropletSize} μm")
    print(f"PID params: Kp={params.Kp}, Ki={params.Ki}, Kd={params.Kd}")
    print("\nTime  |  Measurement  |  Error  |  Output")
    print("-" * 50)

    initial_sizes = [60.0, 65.0, 70.0, 74.0, 77.0, 78.5, 79.2, 79.6, 79.8, 80.0]

    for i, size in enumerate(initial_sizes):
        t = i * 0.1
        output, status = pid.compute(size, t)
        print(f"{t:4.1f}s |  {size:7.1f} μm   | {status.error:6.1f} | {output:6.2f} μL/min")

    assert status.currentSize == 80.0
    assert abs(status.error) < 0.1
    print("\nPID test passed!")


def test_pid_disabled():
    params = PIDParameters(enabled=False, targetDropletSize=80.0)
    pid = PIDController(params)
    output, status = pid.compute(60.0, 0.0)
    assert output == 0.0
    assert status.enabled == False
    print("PID disabled test passed!")


if __name__ == "__main__":
    test_pid_response()
    print()
    test_pid_disabled()
