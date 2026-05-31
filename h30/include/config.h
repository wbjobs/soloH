#ifndef BB84_CONFIG_H
#define BB84_CONFIG_H

#include "types.h"
#include <string>
#include <vector>

namespace bb84 {

struct Config {
    int num_photons = 10000;
    int num_runs = 100;
    double channel_loss_rate = 0.1;
    double dark_count_prob = 0.001;
    double eavesdropping_strength = 0.5;
    AttackType attack_type = AttackType::NONE;
    double qber_threshold = 0.11;
    int cascade_passes = 4;
    double privacy_amplification_factor = 0.5;
    double test_key_fraction = 0.15;
    std::string output_csv = "bb84_results.csv";
    bool verbose = false;
    uint64_t random_seed = 0;
    
    ProtocolType protocol_type = ProtocolType::BB84;
    bool use_fiber_model = false;
    FiberParameters fiber_params;
    
    bool use_decoy_states = false;
    std::vector<DecoySetting> decoy_settings;
    
    double mdi_coincidence_window_ps = 200.0;
    double fiber_length_km = 0.0;
    double fiber_attenuation = 0.2;
    double fiber_dispersion = 17.0;
    double fiber_nonlinear = 1.3e-3;
};

} // namespace bb84

#endif
