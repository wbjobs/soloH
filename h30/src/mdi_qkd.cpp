#include "../include/mdi_qkd.h"
#include "../include/utils.h"
#include <cmath>
#include <stdexcept>
#include <algorithm>

namespace bb84 {

constexpr double PI = 3.14159265358979323846;

MDIProtocol::MDIProtocol() {}

MDIProtocol::MDIProtocol(const Config& config)
    : config_(config) {}

void MDIProtocol::setConfig(const Config& config) {
    config_ = config;
}

std::vector<TimeBinPhoton> MDIProtocol::prepareTimeBinPhotons(
    const std::vector<bool>& bits,
    const std::vector<Basis>& bases,
    bool is_alice) {
    
    std::vector<TimeBinPhoton> photons;
    photons.reserve(bits.size());
    
    for (size_t i = 0; i < bits.size(); ++i) {
        TimeBinPhoton tb_photon;
        
        Basis basis = bases[i];
        bool bit = bits[i];
        
        tb_photon.basis = basis;
        
        if (is_alice) {
            if (basis == Basis::RECTILINEAR) {
                if (bit) {
                    tb_photon.time_bin = 1;
                    tb_photon.phase = 0;
                } else {
                    tb_photon.time_bin = 0;
                    tb_photon.phase = 0;
                }
            } else {
                if (bit) {
                    tb_photon.time_bin = 0;
                    tb_photon.phase = PI;
                } else {
                    tb_photon.time_bin = 0;
                    tb_photon.phase = 0;
                }
            }
        } else {
            if (basis == Basis::RECTILINEAR) {
                if (bit) {
                    tb_photon.time_bin = 0;
                    tb_photon.phase = 0;
                } else {
                    tb_photon.time_bin = 1;
                    tb_photon.phase = 0;
                }
            } else {
                if (bit) {
                    tb_photon.time_bin = 0;
                    tb_photon.phase = 0;
                } else {
                    tb_photon.time_bin = 0;
                    tb_photon.phase = PI;
                }
            }
        }
        
        tb_photon.photon.basis = basis;
        tb_photon.photon.bit_value = bit;
        tb_photon.photon.detected = true;
        tb_photon.photon.polarization = (basis == Basis::RECTILINEAR) 
            ? Polarization::ZERO : Polarization::FORTY_FIVE;
        
        photons.push_back(tb_photon);
    }
    
    return photons;
}

double MDIProtocol::calculateCoincidenceProbability(
    double time_diff_ps,
    double coincidence_window_ps) {
    
    double sigma = coincidence_window_ps / 2.3548;
    double arg = -0.5 * std::pow(time_diff_ps / sigma, 2);
    return std::exp(arg);
}

BellState MDIProtocol::mapDetectionToBellState(
    int detector1,
    int detector2,
    double phase_diff) {
    
    if (detector1 == 0 && detector2 == 1) {
        return (std::cos(phase_diff) > 0) ? BellState::PSI_MINUS : BellState::PSI_PLUS;
    } else if (detector1 == 1 && detector2 == 0) {
        return (std::cos(phase_diff) > 0) ? BellState::PSI_PLUS : BellState::PSI_MINUS;
    } else if (detector1 == 2 && detector2 == 3) {
        return (std::cos(phase_diff) > 0) ? BellState::PHI_MINUS : BellState::PHI_PLUS;
    } else if (detector1 == 3 && detector2 == 2) {
        return (std::cos(phase_diff) > 0) ? BellState::PHI_PLUS : BellState::PHI_MINUS;
    }
    
    return BellState::PHI_PLUS;
}

BellState MDIProtocol::simulateBellStateMeasurement(
    double phase_alice,
    double phase_bob,
    Basis alice_basis,
    Basis bob_basis,
    double loss_alice,
    double loss_bob,
    double& visibility) {
    
    double phase_diff = phase_alice - phase_bob;
    
    double alice_detected = !utils::RandomGenerator::getInstance().randomBool(loss_alice);
    double bob_detected = !utils::RandomGenerator::getInstance().randomBool(loss_bob);
    
    if (!alice_detected || !bob_detected) {
        visibility = 0.0;
        return BellState::PHI_PLUS;
    }
    
    double interference_term = std::cos(phase_diff);
    
    double visibility_theory = std::abs(interference_term);
    double noise = utils::RandomGenerator::getInstance().randomDouble(-0.05, 0.05);
    visibility = std::max(0.0, std::min(1.0, visibility_theory + noise));
    
    double p_psi_minus = 0.25 * (1.0 + interference_term);
    double p_psi_plus = 0.25 * (1.0 - interference_term);
    double p_phi_minus = 0.25 * (1.0 + interference_term);
    double p_phi_plus = 0.25 * (1.0 - interference_term);
    
    if (alice_basis != bob_basis) {
        p_psi_minus = 0.25;
        p_psi_plus = 0.25;
        p_phi_minus = 0.25;
        p_phi_plus = 0.25;
        visibility = 0.0;
    }
    
    double r = utils::RandomGenerator::getInstance().randomDouble();
    double cumulative = 0.0;
    
    cumulative += p_psi_minus;
    if (r <= cumulative) return BellState::PSI_MINUS;
    
    cumulative += p_psi_plus;
    if (r <= cumulative) return BellState::PSI_PLUS;
    
    cumulative += p_phi_minus;
    if (r <= cumulative) return BellState::PHI_MINUS;
    
    return BellState::PHI_PLUS;
}

CharlieResult MDIProtocol::performBellStateMeasurement(
    const TimeBinPhoton& alice_photon,
    const TimeBinPhoton& bob_photon) {
    
    CharlieResult result;
    result.bell_state = BellState::PHI_PLUS;
    result.detection_success = false;
    
    for (int i = 0; i < 4; ++i) {
        result.detector_clicks[i] = 0;
    }
    
    result.coincidence_window_ps = 200.0;
    result.arrival_time_diff_ps = std::abs(
        alice_photon.photon.arrival_time_ps - bob_photon.photon.arrival_time_ps
    );
    
    double coincidence_prob = calculateCoincidenceProbability(
        result.arrival_time_diff_ps,
        result.coincidence_window_ps
    );
    
    if (!utils::RandomGenerator::getInstance().randomBool(coincidence_prob)) {
        result.interference_visibility = 0.0;
        return result;
    }
    
    double loss_alice = 1.0 - alice_photon.photon.intensity * 0.95;
    double loss_bob = 1.0 - bob_photon.photon.intensity * 0.95;
    
    if (alice_photon.time_bin != bob_photon.time_bin) {
        loss_alice = 0.5;
        loss_bob = 0.5;
    }
    
    double visibility = 0.0;
    result.bell_state = simulateBellStateMeasurement(
        alice_photon.phase,
        bob_photon.phase,
        alice_photon.basis,
        bob_photon.basis,
        loss_alice,
        loss_bob,
        visibility
    );
    
    result.interference_visibility = visibility;
    
    int d1 = 0, d2 = 1;
    if (result.bell_state == BellState::PHI_PLUS || result.bell_state == BellState::PHI_MINUS) {
        d1 = 2;
        d2 = 3;
    }
    
    if (result.bell_state == BellState::PSI_MINUS || result.bell_state == BellState::PHI_MINUS) {
        std::swap(d1, d2);
    }
    
    result.detector_clicks[d1] = 1;
    result.detector_clicks[d2] = 1;
    
    result.detection_success = true;
    
    if (utils::RandomGenerator::getInstance().randomBool(config_.dark_count_prob)) {
        int extra_detector = utils::RandomGenerator::getInstance().randomInt(0, 3);
        result.detector_clicks[extra_detector]++;
    }
    
    return result;
}

std::vector<CharlieResult> MDIProtocol::performBellStateMeasurements(
    const std::vector<TimeBinPhoton>& alice_photons,
    const std::vector<TimeBinPhoton>& bob_photons,
    MDIResult& mdi_stats) {
    
    std::vector<CharlieResult> results;
    
    size_t min_size = std::min(alice_photons.size(), bob_photons.size());
    results.reserve(min_size);
    
    for (int i = 0; i < 4; ++i) {
        mdi_stats.bell_state_measurements[i] = 0;
    }
    mdi_stats.total_coincidence_events = 0;
    mdi_stats.accidental_coincidences = 0;
    mdi_stats.interference_visibility = 0.0;
    mdi_stats.heralding_efficiency = 0.0;
    mdi_stats.basis_mismatch_rate = 0.0;
    mdi_stats.charlie_detection_success = true;
    
    int basis_mismatches = 0;
    int valid_measurements = 0;
    double total_visibility = 0.0;
    
    for (size_t i = 0; i < min_size; ++i) {
        CharlieResult result = performBellStateMeasurement(
            alice_photons[i],
            bob_photons[i]
        );
        
        if (alice_photons[i].basis != bob_photons[i].basis) {
            basis_mismatches++;
        }
        
        if (result.detection_success) {
            mdi_stats.bell_state_measurements[static_cast<int>(result.bell_state)]++;
            mdi_stats.total_coincidence_events++;
            
            if (result.interference_visibility > 0.1) {
                total_visibility += result.interference_visibility;
                valid_measurements++;
            }
            
            if (result.arrival_time_diff_ps > result.coincidence_window_ps * 2) {
                mdi_stats.accidental_coincidences++;
            }
        }
        
        results.push_back(result);
    }
    
    if (valid_measurements > 0) {
        mdi_stats.interference_visibility = total_visibility / valid_measurements;
    }
    
    if (min_size > 0) {
        mdi_stats.heralding_efficiency = static_cast<double>(mdi_stats.total_coincidence_events) / min_size;
        mdi_stats.basis_mismatch_rate = static_cast<double>(basis_mismatches) / min_size;
    }
    
    mdi_stats.charlie_detection_success = mdi_stats.total_coincidence_events > 0;
    
    return results;
}

std::vector<bool> MDIProtocol::extractSiftedKey(
    const std::vector<bool>& alice_bits,
    const std::vector<Basis>& alice_bases,
    const std::vector<bool>& bob_bits,
    const std::vector<Basis>& bob_bases,
    const std::vector<CharlieResult>& charlie_results,
    bool is_alice) {
    
    std::vector<bool> sifted_key;
    
    size_t min_size = std::min({
        alice_bits.size(),
        alice_bases.size(),
        bob_bits.size(),
        bob_bases.size(),
        charlie_results.size()
    });
    
    for (size_t i = 0; i < min_size; ++i) {
        if (!charlie_results[i].detection_success) {
            continue;
        }
        
        if (alice_bases[i] != bob_bases[i]) {
            continue;
        }
        
        Basis basis = alice_bases[i];
        BellState bell = charlie_results[i].bell_state;
        
        bool key_bit;
        
        if (is_alice) {
            if (basis == Basis::RECTILINEAR) {
                key_bit = alice_bits[i];
                if (bell == BellState::PSI_PLUS || bell == BellState::PHI_PLUS) {
                } else {
                    key_bit = !key_bit;
                }
            } else {
                key_bit = alice_bits[i];
                if (bell == BellState::PSI_MINUS || bell == BellState::PHI_MINUS) {
                    key_bit = !key_bit;
                }
            }
        } else {
            if (basis == Basis::RECTILINEAR) {
                key_bit = bob_bits[i];
                if (bell == BellState::PSI_MINUS || bell == BellState::PHI_MINUS) {
                } else {
                    key_bit = !key_bit;
                }
            } else {
                key_bit = bob_bits[i];
                if (bell == BellState::PSI_PLUS || bell == BellState::PHI_PLUS) {
                    key_bit = !key_bit;
                }
            }
        }
        
        sifted_key.push_back(key_bit);
    }
    
    return sifted_key;
}

double MDIProtocol::calculateMDIQBER(
    const std::vector<bool>& alice_key,
    const std::vector<bool>& bob_key,
    const std::vector<CharlieResult>& charlie_results) {
    
    return utils::calculateBER(alice_key, bob_key);
}

double MDIProtocol::estimateEveInformationMDI(
    double qber,
    double visibility,
    double loss) {
    
    double h2 = [](double x) {
        if (x <= 0.0 || x >= 1.0) return 0.0;
        return -x * std::log2(x) - (1.0 - x) * std::log2(1.0 - x);
    };
    
    double V = visibility;
    double e_basis = 0.5 * (1.0 - V);
    double eve_info = h2(qber) + (1.0 - V) * h2(0.5);
    
    return eve_info;
}

double MDIProtocol::estimateSecureKeyRate(
    double sifted_key_rate,
    double qber,
    double interference_visibility,
    double dark_count_prob,
    double loss_alice,
    double loss_bob) {
    
    double h2 = [](double x) {
        if (x <= 0.0 || x >= 1.0) return 0.0;
        return -x * std::log2(x) - (1.0 - x) * std::log2(1.0 - x);
    };
    
    double Q = sifted_key_rate;
    double E = qber;
    double V = interference_visibility;
    
    double e1 = 0.5 * (1.0 - std::sqrt(2.0 * E - E * E));
    
    double total_loss = loss_alice + loss_bob - loss_alice * loss_bob;
    double detection_efficiency = std::pow(10.0, -total_loss / 10.0);
    
    double fEC = 1.2;
    double leak_EC = fEC * h2(E);
    
    double S = Q * (1.0 - h2(e1) - leak_EC);
    
    if (V < 0.9) {
        double visibility_penalty = (1.0 - V) * 0.5;
        S *= (1.0 - visibility_penalty);
    }
    
    return std::max(0.0, S);
}

double MDIProtocol::calculateInterferenceVisibility(
    const std::vector<CharlieResult>& results,
    Basis basis) {
    
    int same_basis = 0;
    double total_visibility = 0.0;
    
    for (const auto& r : results) {
        if (r.detection_success) {
            total_visibility += r.interference_visibility;
            same_basis++;
        }
    }
    
    return same_basis > 0 ? total_visibility / same_basis : 0.0;
}

CharlieServer::CharlieServer(double coincidence_window_ps)
    : coincidence_window_ps_(coincidence_window_ps),
      dark_count_prob_(0.001),
      detector_efficiency_(0.95) {}

CharlieResult CharlieServer::measure(
    const TimeBinPhoton& alice,
    const TimeBinPhoton& bob) {
    
    MDIProtocol mdi;
    return mdi.performBellStateMeasurement(alice, bob);
}

void CharlieServer::announceResult(const CharlieResult& result) {
}

} // namespace bb84
