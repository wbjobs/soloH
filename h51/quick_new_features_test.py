from sar_ship_wake_simulation import (
    SARConfig, SARShipWakeSimulator, OceanDensityProfile,
    InternalWakeSimulator, MultiShipWakeSimulator, WakeModulationSimulator
)
import numpy as np
np.random.seed(42)

config = SARConfig(image_size=(64, 128), pixel_spacing=(5.0, 5.0))
density_profile = OceanDensityProfile()

print('Testing InternalWakeSimulator...')
int_sim = InternalWakeSimulator(config, density_profile)
int_wake = int_sim.generate_internal_wake(ship_speed=8.0, ship_length=100.0, ship_draft=5.0)
print('  Internal wake shape:', int_wake.shape, 'std:', np.std(int_wake))
char = int_sim.get_internal_wake_characteristics(ship_speed=8.0)
print('  Fr_i=' + str(char['internal_froude_number']) + ', angle=' + str(char['internal_wake_angle']) + ' deg')

print('Testing MultiShipWakeSimulator...')
multi_sim = MultiShipWakeSimulator(config)
ship_list = [
    {'speed': 10.0, 'length': 100.0, 'draft': 5.0, 'position': (32, 30), 'heading': 0.0},
    {'speed': 12.0, 'length': 120.0, 'draft': 6.0, 'position': (32, 60), 'heading': 10.0}
]
total_wake, ind_wakes, chars = multi_sim.generate_multi_ship_wake(ship_list)
print('  Total wake shape:', total_wake.shape, 'std:', np.std(total_wake))
print('  Number of individual wakes:', len(ind_wakes))

print('Testing WakeModulationSimulator...')
mod_sim = WakeModulationSimulator(config, density_profile)
ocean_int = int_sim.generate_ocean_internal_waves()
kelvin_wake = ind_wakes[0]['height']
modulated_wake, mod_int = mod_sim.modulate_wake_with_internal_waves(kelvin_wake, ocean_int, ship_speed=10.0)
print('  Modulated wake std:', np.std(modulated_wake))
mtf = mod_sim.modulation_transfer_function(0.1, 0.05)
print('  MTF at k_wake=0.1, k_int=0.05:', mtf)

print('Testing full simulator with new features...')
simulator = SARShipWakeSimulator(config, density_profile)
slc, amp = simulator.run_simulation(
    ship_speed=10.0, ship_length=100.0, ship_draft=5.0,
    include_internal_wake=True, include_ocean_internal_waves=True,
    apply_internal_wave_modulation=True
)
print('  SLC shape:', slc.shape, 'dtype:', slc.dtype)

print('')
print('All new features imported and working correctly!')
