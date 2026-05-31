#ifndef BB84_TYPES_H
#define BB84_TYPES_H

#include <vector>
#include <bitset>
#include <string>
#include <cstdint>

namespace bb84 {

enum class Basis : uint8_t {
    RECTILINEAR = 0,
    DIAGONAL = 1
};

enum class Polarization : uint8_t {
    ZERO = 0,
    FORTY_FIVE = 1,
    NINETY = 2,
    ONE_HUNDRED_THIRTY_FIVE = 3
};

enum class AttackType {
    NONE = 0,
    INTERCEPT_RESEND = 1,
    BEAM_SPLITTING = 2
};

enum class ProtocolType {
    BB84 = 0,
    MDI_QKD = 1
};

enum class DecoyStateType {
    SIGNAL = 0,
    DECOY1 = 1,
    DECOY2 = 2,
    VACUUM = 3
};

struct DecoySetting {
    DecoyStateType type;
    double intensity;
    double probability;
};

struct FiberParameters {
    double length_km = 0.0;
    double attenuation_coeff = 0.2;
    double dispersion_coeff = 17.0;
    double nonlinear_coeff = 1.3e-3;
    double effective_area = 80.0;
    double wavelength_nm = 1550.0;
    double pulse_width_ps = 100.0;
    double background_loss = 0.0;
};

struct FiberEffectResult {
    double pulse_broadening_factor;
    double polarization_mode_dispersion;
    double nonlinear_phase_shift;
    double polarization_rotation;
    double total_attenuation_db;
    double additional_qber;
};

struct Photon {
    Polarization polarization;
    Basis basis;
    bool bit_value;
    bool detected;
    double intensity = 1.0;
    double arrival_time_ps = 0.0;
    DecoyStateType decoy_type = DecoyStateType::SIGNAL;
    FiberEffectResult fiber_effects;
};

struct KeyBits {
    std::vector<bool> bits;
    std::vector<Basis> bases;
    std::vector<bool> polarization_bits;
    std::vector<DecoyStateType> decoy_types;
    std::vector<double> intensities;
};

struct DecoyResult {
    int signal_count;
    int decoy1_count;
    int decoy2_count;
    int vacuum_count;
    double signal_yield;
    double decoy1_yield;
    double decoy2_yield;
    double vacuum_yield;
    double signal_error_rate;
    double estimated_single_photon_count;
    double estimated_single_photon_error;
    double estimated_photon_number_distribution[5];
    bool decoy_enabled;
};

struct MDIResult {
    int bell_state_measurements[4];
    int total_coincidence_events;
    int accidental_coincidences;
    double interference_visibility;
    double heralding_efficiency;
    double basis_mismatch_rate;
    bool charlie_detection_success;
};

struct RunResult {
    int run_id;
    int total_photons_sent;
    int photons_lost;
    int sifted_key_length;
    int test_sample_size;
    double qber;
    double qber_after_basis_reconciliation;
    int cascade_errors_corrected;
    int cascade_passes_completed;
    int final_key_length;
    int security_parameter;
    double collision_probability;
    bool eavesdropping_detected;
    double eavesdropping_strength_used;
    AttackType attack_type;
    double key_generation_rate;
    int dark_count_events;
    
    ProtocolType protocol_type;
    FiberParameters fiber_params;
    FiberEffectResult avg_fiber_effects;
    DecoyResult decoy_result;
    MDIResult mdi_result;
};

struct StatsSummary {
    double avg_qber;
    double std_qber;
    double avg_key_rate;
    double std_key_rate;
    double eavesdropping_detection_probability;
    double avg_final_key_length;
    double avg_sifted_key_length;
    double avg_photon_loss_rate;
    double avg_dark_count_rate;
    int total_runs;
    int successful_runs;
    
    double avg_pulse_broadening;
    double avg_nonlinear_phase;
    double avg_fiber_qber;
    double avg_decoy_yield_signal;
    double avg_single_photon_fraction;
    double avg_mdi_visibility;
    double avg_mdi_coincidence_rate;
};

} // namespace bb84

#endif
