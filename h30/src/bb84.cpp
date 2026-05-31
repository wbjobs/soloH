#include "../include/bb84.h"
#include "../include/quantum.h"
#include "../include/utils.h"
#include <iostream>
#include <algorithm>
#include <cmath>
#include <limits>

namespace bb84 {

BB84Protocol::BB84Protocol(const Config& config)
    : config_(config),
      alice_(),
      bob_(),
      eve_(config),
      channel_(config),
      cascade_(config),
      privacy_amp_(config) {
    if (config_.random_seed != 0) {
        utils::RandomGenerator::getInstance().seed(config_.random_seed);
    }
    
    if (config.protocol_type == ProtocolType::MDI_QKD) {
        mdi_protocol_ = std::make_unique<MDIProtocol>(config);
    }
    
    if (config.use_decoy_states) {
        initializeDecoyStates();
    }
}

void BB84Protocol::initializeDecoyStates() {
    if (config_.decoy_settings.empty()) {
        config_.decoy_settings = DecoyStateProtocol::createStandardDecoys();
    }
    decoy_protocol_ = std::make_unique<DecoyStateProtocol>(config_.decoy_settings);
}

DecoyResult BB84Protocol::runDecoyStateAnalysis(
    const std::vector<Photon>& transmitted,
    const std::vector<bool>& detected,
    const std::vector<Basis>& alice_bases,
    const std::vector<Basis>& bob_bases) {
    
    if (decoy_protocol_) {
        return decoy_protocol_->analyzeDecoyData(
            transmitted, detected, alice_bases, bob_bases
        );
    }
    
    DecoyResult empty{};
    empty.decoy_enabled = false;
    return empty;
}

double BB84Protocol::calculateQBER(const std::vector<bool>& test_bits_alice,
                                   const std::vector<bool>& test_bits_bob) {
    return utils::calculateBER(test_bits_alice, test_bits_bob);
}

double BB84Protocol::normalQuantile(double p) {
    if (p <= 0.0 || p >= 1.0) {
        return (p <= 0.0) ? -std::numeric_limits<double>::infinity() 
                          : std::numeric_limits<double>::infinity();
    }
    
    double q = p < 0.5 ? p : 1.0 - p;
    
    static const double a[] = {
        -3.969683028665376e+01,  2.209460984245205e+02,
        -2.759285104469687e+02,  1.383577518672690e+02,
        -3.066479806614716e+01,  2.506628277459239e+00
    };
    static const double b[] = {
        -5.447609879822406e+01,  1.615858368580409e+02,
        -1.556989798598866e+02,  6.680131188771972e+01,
        -1.328068155288572e+01
    };
    
    double r = std::sqrt(-2.0 * std::log(q));
    double x = (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) /
               ((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4]);
    
    if (p >= 0.5) {
        x = -x;
    }
    
    return x;
}

size_t BB84Protocol::calculateOptimalTestSize(size_t key_length,
                                               double expected_qber,
                                               double threshold,
                                               double confidence_level,
                                               double detection_power) {
    if (key_length == 0) return 0;
    
    double alpha = 1.0 - confidence_level;
    double beta = 1.0 - detection_power;
    
    double z_alpha = normalQuantile(1.0 - alpha / 2.0);
    double z_beta = normalQuantile(1.0 - beta);
    
    double p0 = threshold;
    double effect_size = std::abs(expected_qber - p0);
    
    if (effect_size < 0.005) {
        effect_size = 0.02;
    }
    
    double p_bar = (expected_qber + p0) / 2.0;
    double numerator = z_alpha * std::sqrt(p_bar * (1.0 - p_bar) * 2.0) + 
                      z_beta * std::sqrt(expected_qber * (1.0 - expected_qber) + 
                                         p0 * (1.0 - p0));
    
    double n = std::pow(numerator / effect_size, 2.0);
    
    size_t min_test_size = static_cast<size_t>(std::max(30.0, std::ceil(n)));
    size_t max_test_size = static_cast<size_t>(key_length * 0.5);
    
    double max_allowable_fraction = 0.3;
    max_test_size = static_cast<size_t>(key_length * max_allowable_fraction);
    
    size_t optimal_size = std::min(min_test_size, max_test_size);
    optimal_size = std::max(optimal_size, static_cast<size_t>(20));
    
    double config_fraction = config_.test_key_fraction;
    if (config_fraction > 0) {
        size_t config_based = static_cast<size_t>(key_length * config_fraction);
        optimal_size = std::max(optimal_size, config_based);
        optimal_size = std::min(optimal_size, max_test_size);
    }
    
    if (config_.attack_type == AttackType::BEAM_SPLITTING) {
        optimal_size = static_cast<size_t>(optimal_size * 1.5);
        optimal_size = std::min(optimal_size, max_test_size);
    }
    
    return optimal_size;
}

std::vector<bool> BB84Protocol::extractTestBits(const std::vector<bool>& key,
                                                size_t test_size,
                                                std::vector<size_t>& test_indices) {
    std::vector<bool> test_bits;
    test_indices.clear();
    
    if (test_size == 0 || key.empty()) {
        return test_bits;
    }
    
    test_size = std::min(test_size, key.size());
    test_bits.reserve(test_size);
    test_indices.reserve(test_size);
    
    std::vector<size_t> all_indices(key.size());
    for (size_t i = 0; i < key.size(); ++i) {
        all_indices[i] = i;
    }
    
    std::shuffle(all_indices.begin(), all_indices.end(),
                 utils::RandomGenerator::getInstance().getEngine());
    
    for (size_t i = 0; i < test_size; ++i) {
        test_indices.push_back(all_indices[i]);
        test_bits.push_back(key[all_indices[i]]);
    }
    
    std::sort(test_indices.begin(), test_indices.end());
    
    return test_bits;
}

std::vector<bool> BB84Protocol::removeTestBits(const std::vector<bool>& key,
                                               const std::vector<size_t>& test_indices) {
    std::vector<bool> result;
    result.reserve(key.size() - test_indices.size());
    
    size_t test_ptr = 0;
    for (size_t i = 0; i < key.size(); ++i) {
        if (test_ptr < test_indices.size() && i == test_indices[test_ptr]) {
            test_ptr++;
        } else {
            result.push_back(key[i]);
        }
    }
    
    return result;
}

bool BB84Protocol::detectEavesdropping(double qber, size_t test_size) {
    if (test_size == 0) return false;
    
    double p0 = config_.qber_threshold;
    
    if (qber <= p0) {
        return false;
    }
    
    double z_score = (qber - p0) / std::sqrt(p0 * (1.0 - p0) / test_size);
    double critical_value = normalQuantile(0.99);
    
    bool detected_by_threshold = qber > p0;
    bool detected_by_stat = z_score > critical_value;
    
    if (config_.attack_type != AttackType::NONE) {
        return detected_by_threshold || detected_by_stat;
    } else {
        return qber > p0 + 3 * std::sqrt(p0 * (1.0 - p0) / test_size);
    }
}

void BB84Protocol::verifyKeysMatch(const std::vector<bool>& alice_key,
                                   const std::vector<bool>& bob_key,
                                   int& errors_corrected) {
    errors_corrected = 0;
    size_t min_len = std::min(alice_key.size(), bob_key.size());
    
    for (size_t i = 0; i < min_len; ++i) {
        if (alice_key[i] != bob_key[i]) {
            errors_corrected++;
        }
    }
}

RunResult BB84Protocol::runSingleRun(int run_id) {
    if (config_.protocol_type == ProtocolType::MDI_QKD) {
        return runMDIQKD(run_id);
    } else {
        return runBB84(run_id);
    }
}

RunResult BB84Protocol::runBB84(int run_id) {
    RunResult result;
    result.run_id = run_id;
    result.attack_type = config_.attack_type;
    result.eavesdropping_strength_used = config_.eavesdropping_strength;
    result.test_sample_size = 0;
    result.cascade_passes_completed = 0;
    result.security_parameter = 0;
    result.collision_probability = 1.0;
    result.protocol_type = ProtocolType::BB84;
    result.fiber_params = config_.fiber_params;
    
    const int num_photons = config_.num_photons;
    result.total_photons_sent = num_photons;
    
    alice_.generateRandomBits(num_photons);
    alice_.generateRandomBases(num_photons);
    
    PhotonSource source;
    if (config_.use_decoy_states && decoy_protocol_) {
        source.enableDecoyStates(true, config_.decoy_settings);
    }
    
    std::vector<Photon> photons;
    if (source.isDecoyEnabled()) {
        photons = source.generatePhotonsWithDecoys(alice_.getBits(), alice_.getBases());
    } else {
        photons = alice_.preparePhotons();
    }
    
    int eve_errors = 0;
    if (config_.attack_type != AttackType::NONE) {
        photons = eve_.applyAttack(photons, eve_errors);
    }
    
    int photons_lost = 0;
    int dark_counts = 0;
    std::vector<Photon> transmitted = channel_.transmitPhotons(photons, photons_lost, dark_counts);
    
    result.avg_fiber_effects = channel_.getAverageFiberEffects();
    result.photons_lost = photons_lost;
    result.dark_count_events = dark_counts;
    
    bob_.generateRandomBases(num_photons);
    std::vector<bool> detected;
    bob_.measurePhotons(transmitted, detected);
    
    if (config_.use_decoy_states && decoy_protocol_) {
        result.decoy_result = runDecoyStateAnalysis(
            transmitted, detected, alice_.getBases(), bob_.getBases()
        );
    } else {
        result.decoy_result = {};
        result.decoy_result.decoy_enabled = false;
    }
    
    std::vector<bool> alice_sifted = alice_.getSiftedKey(bob_.getBases(), detected);
    std::vector<bool> bob_sifted = bob_.getSiftedKey(alice_.getBases());
    
    result.sifted_key_length = static_cast<int>(alice_sifted.size());
    
    double expected_qber = 0.01;
    if (config_.attack_type == AttackType::INTERCEPT_RESEND) {
        expected_qber = 0.25 * config_.eavesdropping_strength + 0.01;
    } else if (config_.attack_type == AttackType::BEAM_SPLITTING) {
        expected_qber = 0.05 * config_.eavesdropping_strength + 0.01;
    }
    
    if (channel_.isFiberModelEnabled()) {
        expected_qber += result.avg_fiber_effects.additional_qber;
    }
    
    size_t test_size = calculateOptimalTestSize(
        alice_sifted.size(),
        expected_qber,
        config_.qber_threshold,
        0.99,
        0.95
    );
    result.test_sample_size = static_cast<int>(test_size);
    
    std::vector<size_t> test_indices;
    std::vector<bool> alice_test = extractTestBits(alice_sifted, test_size, test_indices);
    std::vector<bool> bob_test = extractTestBits(bob_sifted, test_size, test_indices);
    
    result.qber = calculateQBER(alice_test, bob_test);
    
    result.eavesdropping_detected = detectEavesdropping(result.qber, test_size);
    
    std::vector<bool> alice_key = removeTestBits(alice_sifted, test_indices);
    std::vector<bool> bob_key = removeTestBits(bob_sifted, test_indices);
    
    result.qber_after_basis_reconciliation = utils::calculateBER(alice_key, bob_key);
    
    if (result.eavesdropping_detected || alice_key.empty()) {
        result.cascade_errors_corrected = 0;
        result.final_key_length = 0;
        result.key_generation_rate = 0.0;
        return result;
    }
    
    CascadeResult cascade_result = cascade_.run(alice_key, bob_key, result.qber);
    result.cascade_errors_corrected = cascade_result.total_errors_corrected;
    result.cascade_passes_completed = cascade_result.passes_completed;
    
    bob_key = cascade_result.corrected_key;
    
    if (alice_key.size() != bob_key.size()) {
        size_t min_size = std::min(alice_key.size(), bob_key.size());
        alice_key.resize(min_size);
        bob_key.resize(min_size);
    }
    
    PrivacyAmplificationResult pa_result = privacy_amp_.run(
        bob_key, 
        cascade_result.residual_error_rate,
        cascade_result.total_parity_bits_exchanged
    );
    
    result.final_key_length = static_cast<int>(pa_result.final_key_length);
    result.security_parameter = pa_result.security_parameter;
    result.collision_probability = pa_result.collision_probability;
    
    if (num_photons > 0) {
        result.key_generation_rate = static_cast<double>(result.final_key_length) / 
                                    static_cast<double>(num_photons);
    } else {
        result.key_generation_rate = 0.0;
    }
    
    if (result.decoy_result.decoy_enabled && result.final_key_length > 0) {
        double single_fraction = result.decoy_result.estimated_single_photon_count / 
                                 std::max(1.0, static_cast<double>(result.sifted_key_length));
        double decoy_key_rate = decoy_protocol_->calculateSecureKeyRate(
            result.key_generation_rate,
            single_fraction,
            result.decoy_result.estimated_single_photon_error
        );
        result.final_key_length = static_cast<int>(decoy_key_rate * num_photons);
        result.key_generation_rate = decoy_key_rate;
    }
    
    result.mdi_result = {};
    return result;
}

RunResult BB84Protocol::runMDIQKD(int run_id) {
    RunResult result;
    result.run_id = run_id;
    result.attack_type = config_.attack_type;
    result.eavesdropping_strength_used = config_.eavesdropping_strength;
    result.test_sample_size = 0;
    result.cascade_passes_completed = 0;
    result.security_parameter = 0;
    result.collision_probability = 1.0;
    result.protocol_type = ProtocolType::MDI_QKD;
    result.fiber_params = config_.fiber_params;
    
    const int num_photons = config_.num_photons;
    result.total_photons_sent = num_photons;
    
    alice_.generateRandomBits(num_photons);
    alice_.generateRandomBases(num_photons);
    bob_.generateRandomBits(num_photons);
    bob_.generateRandomBases(num_photons);
    
    PhotonSource source;
    if (config_.use_decoy_states && decoy_protocol_) {
        source.enableDecoyStates(true, config_.decoy_settings);
    }
    
    std::vector<TimeBinPhoton> alice_photons = mdi_protocol_->prepareTimeBinPhotons(
        alice_.getBits(), alice_.getBases(), true
    );
    std::vector<TimeBinPhoton> bob_photons = mdi_protocol_->prepareTimeBinPhotons(
        bob_.getBits(), bob_.getBases(), false
    );
    
    std::vector<Photon> alice_simple;
    std::vector<Photon> bob_simple;
    for (const auto& p : alice_photons) {
        alice_simple.push_back(p.photon);
    }
    for (const auto& p : bob_photons) {
        bob_simple.push_back(p.photon);
    }
    
    int eve_errors = 0;
    if (config_.attack_type != AttackType::NONE) {
        alice_simple = eve_.applyAttack(alice_simple, eve_errors);
        int eve_errors2 = 0;
        bob_simple = eve_.applyAttack(bob_simple, eve_errors2);
    }
    
    int alice_lost = 0, alice_dark = 0;
    int bob_lost = 0, bob_dark = 0;
    std::vector<Photon> alice_transmitted = channel_.transmitPhotons(
        alice_simple, alice_lost, alice_dark
    );
    FiberEffectResult alice_effects = channel_.getAverageFiberEffects();
    
    std::vector<Photon> bob_transmitted = channel_.transmitPhotons(
        bob_simple, bob_lost, bob_dark
    );
    FiberEffectResult bob_effects = channel_.getAverageFiberEffects();
    
    result.avg_fiber_effects.pulse_broadening_factor = 
        (alice_effects.pulse_broadening_factor + bob_effects.pulse_broadening_factor) / 2.0;
    result.avg_fiber_effects.nonlinear_phase_shift = 
        (alice_effects.nonlinear_phase_shift + bob_effects.nonlinear_phase_shift) / 2.0;
    result.avg_fiber_effects.additional_qber = 
        (alice_effects.additional_qber + bob_effects.additional_qber) / 2.0;
    
    result.photons_lost = alice_lost + bob_lost;
    result.dark_count_events = alice_dark + bob_dark;
    
    for (size_t i = 0; i < alice_photons.size(); ++i) {
        alice_photons[i].photon = alice_transmitted[i];
    }
    for (size_t i = 0; i < bob_photons.size(); ++i) {
        bob_photons[i].photon = bob_transmitted[i];
    }
    
    MDIResult mdi_stats;
    std::vector<CharlieResult> charlie_results = mdi_protocol_->performBellStateMeasurements(
        alice_photons, bob_photons, mdi_stats
    );
    result.mdi_result = mdi_stats;
    
    std::vector<bool> alice_sifted = mdi_protocol_->extractSiftedKey(
        alice_.getBits(), alice_.getBases(),
        bob_.getBits(), bob_.getBases(),
        charlie_results, true
    );
    std::vector<bool> bob_sifted = mdi_protocol_->extractSiftedKey(
        alice_.getBits(), alice_.getBases(),
        bob_.getBits(), bob_.getBases(),
        charlie_results, false
    );
    
    result.sifted_key_length = static_cast<int>(alice_sifted.size());
    
    double expected_qber = 0.02;
    if (config_.attack_type == AttackType::INTERCEPT_RESEND) {
        expected_qber += 0.20 * config_.eavesdropping_strength;
    }
    expected_qber += result.avg_fiber_effects.additional_qber;
    
    size_t test_size = calculateOptimalTestSize(
        alice_sifted.size(),
        expected_qber,
        config_.qber_threshold,
        0.99,
        0.95
    );
    result.test_sample_size = static_cast<int>(test_size);
    
    std::vector<size_t> test_indices;
    std::vector<bool> alice_test = extractTestBits(alice_sifted, test_size, test_indices);
    std::vector<bool> bob_test = extractTestBits(bob_sifted, test_size, test_indices);
    
    result.qber = calculateQBER(alice_test, bob_test);
    
    result.eavesdropping_detected = detectEavesdropping(result.qber, test_size);
    
    std::vector<bool> alice_key = removeTestBits(alice_sifted, test_indices);
    std::vector<bool> bob_key = removeTestBits(bob_sifted, test_indices);
    
    result.qber_after_basis_reconciliation = utils::calculateBER(alice_key, bob_key);
    
    if (result.eavesdropping_detected || alice_key.empty()) {
        result.cascade_errors_corrected = 0;
        result.final_key_length = 0;
        result.key_generation_rate = 0.0;
        return result;
    }
    
    CascadeResult cascade_result = cascade_.run(alice_key, bob_key, result.qber);
    result.cascade_errors_corrected = cascade_result.total_errors_corrected;
    result.cascade_passes_completed = cascade_result.passes_completed;
    
    bob_key = cascade_result.corrected_key;
    
    if (alice_key.size() != bob_key.size()) {
        size_t min_size = std::min(alice_key.size(), bob_key.size());
        alice_key.resize(min_size);
        bob_key.resize(min_size);
    }
    
    PrivacyAmplificationResult pa_result = privacy_amp_.run(
        bob_key, 
        cascade_result.residual_error_rate,
        cascade_result.total_parity_bits_exchanged
    );
    
    result.final_key_length = static_cast<int>(pa_result.final_key_length);
    result.security_parameter = pa_result.security_parameter;
    result.collision_probability = pa_result.collision_probability;
    
    double mdi_key_rate = mdi_protocol_->estimateSecureKeyRate(
        static_cast<double>(result.sifted_key_length) / num_photons,
        result.qber,
        mdi_stats.interference_visibility,
        config_.dark_count_prob,
        static_cast<double>(alice_lost) / num_photons,
        static_cast<double>(bob_lost) / num_photons
    );
    
    if (num_photons > 0) {
        result.key_generation_rate = mdi_key_rate;
        result.final_key_length = static_cast<int>(mdi_key_rate * num_photons);
    } else {
        result.key_generation_rate = 0.0;
    }
    
    result.decoy_result = {};
    result.decoy_result.decoy_enabled = false;
    
    return result;
}

} // namespace bb84
