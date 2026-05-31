import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from app.models import SimulationParameters, JunctionType
from app.droplet_model import DropletFormationModel


def test_droplet_size_prediction():
    model = DropletFormationModel()
    params = SimulationParameters()

    D, f, Q_ratio, Ca = model.simulate_step(
        params=params,
        Qc_actual=20.0,
        Qd_actual=5.0,
        time=0.0,
        add_noise=False
    )

    assert D > 0
    assert f > 0
    assert Q_ratio == 0.25
    assert Ca > 0
    print(f"Droplet size: {D:.2f} μm")
    print(f"Frequency: {f:.2f} Hz")
    print(f"Q ratio: {Q_ratio:.3f}")
    print(f"Capillary number: {Ca:.6f}")


def test_different_junction_types():
    model = DropletFormationModel()
    params = SimulationParameters()

    for jt in [JunctionType.T, JunctionType.FLOW_FOCUSING, JunctionType.CO_FLOW]:
        params.channel.junctionType = jt
        D, f, _, _ = model.simulate_step(params, add_noise=False)
        print(f"{jt.value}: D={D:.2f} μm, f={f:.2f} Hz")


def test_flow_rate_effect():
    model = DropletFormationModel()
    params = SimulationParameters()

    print("\nFlow rate effect:")
    for Qd in [2, 5, 10, 15]:
        D, f, Qr, _ = model.simulate_step(params, Qd_actual=Qd, add_noise=False)
        print(f"Qd={Qd} μL/min: D={D:.2f} μm, f={f:.2f} Hz, Qr={Qr:.3f}")


def test_polydispersity():
    model = DropletFormationModel()
    sizes = [80 + np.random.normal(0, 2) for _ in range(50)]
    pd = model.compute_polydispersity(np.array(sizes))
    print(f"\nPolydispersity: {pd:.2f}%")


if __name__ == "__main__":
    print("Testing droplet formation model...")
    print("=" * 50)
    test_droplet_size_prediction()
    print("\n" + "=" * 50)
    test_different_junction_types()
    test_flow_rate_effect()
    test_polydispersity()
    print("\nAll tests passed!")
