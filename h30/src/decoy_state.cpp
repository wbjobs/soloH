#include "../include/decoy_state.h"
#include "../include/utils.h"
#include "../include/quantum.h"
#include <cmath>
#include <stdexcept>
#include <algorithm>

namespace bb84 {

constexpr double PI = 3.14159265358979323846;

DecoyStateProtocol::DecoyStateProtocol()
    : enabled_(false) {}

DecoyStateProtocol::DecoyStateProtocol(const std::vector<DecoySetting>& settings)
    : settings_(settings), enabled_(!settings.empty()) {}

std::vector<DecoySetting> DecoyStateProtocol::createStandardDecoys(
    double signal_intensity,
    double decoy1_intensity,
    double decoy2_intensity,
    double vacuum_prob) {
    
    std::vector<DecoySetting> settings;
    
    double remaining = 1.0 - vacuum_prob;
    double signal_prob = remaining * 0.7;
    double decoy1_prob = remaining * 0.2;
    double decoy2_prob = remaining * 0.1;
    
    settings.push_back({DecoyStateType::SIGNAL, signal_intensity, signal_prob});
    settings.push_back({DecoyStateType::DECOY1, decoy1_intensity, decoy1_prob});
    settings.push_back({DecoyStateType::DECOY2, decoy2_intensity, decoy2_prob});
    settings.push_back({DecoyStateType::VACUUM, 0.0, vacuum_prob});
    
    return settings;
}

void DecoyStateProtocol::setSettings(const std::vector<DecoySetting>& settings) {
    settings_ = settings;
    enabled_ = !settings.empty();
}

const std::vector<DecoySetting>& DecoyStateProtocol::getSettings() const {
    return settings_;
}

bool DecoyStateProtocol::isEnabled() const {
    return enabled_;
}

double DecoyStateProtocol::poissonProbability(double lambda, int n) {
    if (n < 0) return 0.0;
    if (lambda <= 0) {
        return (n == 0) ? 1.0 : 0.0;
    }
    
    double log_prob = -lambda + n * std::log(lambda);
    
    for (int i = 2; i <= n; ++i) {
        log_prob -= std::log(i);
    }
    
    return std::exp(log_prob);
}

double DecoyStateProtocol::calculateYield(int n, double eta, double p_dark) {
    if (n == 0) {
        return p_dark;
    }
    
    double detection_prob = 1.0 - std::pow(1.0 - eta, n);
    return detection_prob + p_dark - detection_prob * p_dark;
}

double DecoyStateProtocol::calculateErrorRate(int n, double eta, double p_dark, double e_opt) {
    if (n == 0) {
        return 0.5;
    }
    
    double Y_n = calculateYield(n, eta, p_dark);
    double e_signal = e_opt * (1.0 - std::pow(1.0 - eta, n)) / Y_n;
    double e_dark = 0.5 * p_dark / Y_n;
    
    return e_signal + e_dark;
}

DecoyStateType DecoyStateProtocol::chooseDecoyType(double& chosen_intensity) {
    if (!enabled_ || settings_.empty()) {
        chosen_intensity = 1.0;
        return DecoyStateType::SIGNAL;
    }
    
    double r = utils::RandomGenerator::getInstance().randomDouble();
    double cumulative = 0.0;
    
    for (const auto& setting : settings_) {
        cumulative += setting.probability;
        if (r <= cumulative) {
            chosen_intensity = setting.intensity;
            return setting.type;
        }
    }
    
    chosen_intensity = settings_.back().intensity;
    return settings_.back().type;
}

std::vector<Photon> DecoyStateProtocol::generatePhotonsWithDecoys(
    const std::vector<bool>& bits,
    const std::vector<Basis>& bases) {
    
    PhotonSource source;
    std::vector<Photon> photons;
    photons.reserve(bits.size());
    
    for (size_t i = 0; i < bits.size(); ++i) {
        double intensity = 1.0;
        DecoyStateType decoy_type = chooseDecoyType(intensity);
        
        Photon photon = source.generatePhoton(bits[i], bases[i]);
        photon.intensity = intensity;
        photon.decoy_type = decoy_type;
        
        if (decoy_type == DecoyStateType::VACUUM) {
            photon.bit_value = utils::RandomGenerator::getInstance().randomBool();
            photon.detected = false;
        }
        
        photons.push_back(photon);
    }
    
    return photons;
}

DecoyResult DecoyStateProtocol::analyzeDecoyData(
    const std::vector<Photon>& transmitted_photons,
    const std::vector<bool>& detected,
    const std::vector<Basis>& alice_bases,
    const std::vector<Basis>& bob_bases) {
    
    DecoyResult result;
    result.decoy_enabled = enabled_;
    result.signal_count = 0;
    result.decoy1_count = 0;
    result.decoy2_count = 0;
    result.vacuum_count = 0;
    
    int signal_sent = 0, decoy1_sent = 0, decoy2_sent = 0, vacuum_sent = 0;
    int signal_errors = 0;
    
    size_t min_size = std::min({
        transmitted_photons.size(),
        detected.size(),
        alice_bases.size(),
        bob_bases.size()
    });
    
    for (size_t i = 0; i < min_size; ++i) {
        if (!detected[i] || alice_bases[i] != bob_bases[i]) {
            continue;
        }
        
        const auto& photon = transmitted_photons[i];
        
        switch (photon.decoy_type) {
            case DecoyStateType::SIGNAL:
                signal_sent++;
                result.signal_count++;
                if (photon.bit_value != transmitted_photons[i].bit_value) {
                    signal_errors++;
                }
                break;
            case DecoyStateType::DECOY1:
                decoy1_sent++;
                result.decoy1_count++;
                break;
            case DecoyStateType::DECOY2:
                decoy2_sent++;
                result.decoy2_count++;
                break;
            case DecoyStateType::VACUUM:
                vacuum_sent++;
                result.vacuum_count++;
                break;
        }
    }
    
    int total_sent_signal = 0, total_sent_decoy1 = 0, total_sent_decoy2 = 0, total_sent_vacuum = 0;
    for (const auto& photon : transmitted_photons) {
        switch (photon.decoy_type) {
            case DecoyStateType::SIGNAL: total_sent_signal++; break;
            case DecoyStateType::DECOY1: total_sent_decoy1++; break;
            case DecoyStateType::DECOY2: total_sent_decoy2++; break;
            case DecoyStateType::VACUUM: total_sent_vacuum++; break;
        }
    }
    
    result.signal_yield = total_sent_signal > 0 
        ? static_cast<double>(result.signal_count) / total_sent_signal : 0.0;
    result.decoy1_yield = total_sent_decoy1 > 0 
        ? static_cast<double>(result.decoy1_count) / total_sent_decoy1 : 0.0;
    result.decoy2_yield = total_sent_decoy2 > 0 
        ? static_cast<double>(result.decoy2_count) / total_sent_decoy2 : 0.0;
    result.vacuum_yield = total_sent_vacuum > 0 
        ? static_cast<double>(result.vacuum_count) / total_sent_vacuum : 0.0;
    
    result.signal_error_rate = result.signal_count > 0 
        ? static_cast<double>(signal_errors) / result.signal_count : 0.0;
    
    double signal_intensity = 0.5, decoy1_intensity = 0.2;
    for (const auto& s : settings_) {
        if (s.type == DecoyStateType::SIGNAL) signal_intensity = s.intensity;
        if (s.type == DecoyStateType::DECOY1) decoy1_intensity = s.intensity;
    }
    
    result.estimated_single_photon_count = estimateSinglePhotonCount(
        result.signal_yield, result.decoy1_yield,
        signal_intensity, decoy1_intensity
    );
    
    result.estimated_single_photon_error = estimateSinglePhotonError(
        result.signal_error_rate, result.signal_error_rate * 0.8,
        signal_intensity, decoy1_intensity,
        result.vacuum_yield
    );
    
    estimatePhotonNumberDistribution(signal_intensity, result.estimated_photon_number_distribution);
    
    return result;
}

double DecoyStateProtocol::estimateSinglePhotonCount(
    double signal_yield,
    double decoy_yield,
    double signal_intensity,
    double decoy_intensity) {
    
    if (!enabled_) {
        return signal_yield;
    }
    
    double mu = signal_intensity;
    double nu = decoy_intensity;
    
    double Y_mu = signal_yield;
    double Y_nu = decoy_yield;
    
    double Y1_lower = (nu * std::exp(nu) * Y_nu - mu * std::exp(mu) * Y_mu + (mu - nu)) / (nu - mu);
    
    if (mu > nu) {
        Y1_lower = (mu * std::exp(mu) * Y_mu - nu * std::exp(nu) * Y_nu - (mu - nu)) / (mu - nu);
    }
    
    Y1_lower = std::max(0.0, Y1_lower);
    
    double p1_mu = poissonProbability(mu, 1);
    double Q1 = Y1_lower * p1_mu;
    
    return Q1;
}

double DecoyStateProtocol::estimateSinglePhotonError(
    double signal_error,
    double decoy_error,
    double signal_intensity,
    double decoy_intensity,
    double vacuum_yield) {
    
    if (!enabled_) {
        return signal_error;
    }
    
    double mu = signal_intensity;
    double nu = decoy_intensity;
    
    double e_mu = signal_error;
    double e_nu = decoy_error;
    double Y0 = vacuum_yield;
    
    double Q_mu = signal_intensity;
    double Q_nu = decoy_intensity;
    
    double E_mu_Q_mu = e_mu * Q_mu;
    double E_nu_Q_nu = e_nu * Q_nu;
    
    double e1_upper = (std::exp(mu) * E_mu_Q_mu - std::exp(nu) * E_nu_Q_nu) / 
                      (mu - nu);
    e1_upper = std::abs(e1_upper);
    
    double Y1 = 0.1;
    double Q1 = Y1 * poissonProbability(mu, 1);
    
    if (Q1 > 0) {
        e1_upper = (0.5 * Y0 + e1_upper) / Q1;
    }
    
    e1_upper = std::min(0.5, std::max(0.0, e1_upper));
    
    return e1_upper;
}

void DecoyStateProtocol::estimatePhotonNumberDistribution(
    double intensity,
    double distribution[5]) {
    
    for (int n = 0; n < 5; ++n) {
        distribution[n] = poissonProbability(intensity, n);
    }
    
    double remaining = 1.0;
    for (int n = 0; n < 4; ++n) {
        remaining -= distribution[n];
    }
    distribution[4] = remaining;
}

double DecoyStateProtocol::calculateSecureKeyRate(
    double sifted_key_rate,
    double single_photon_fraction,
    double single_photon_error,
    double leakage_fraction) {
    
    if (!enabled_) {
        return sifted_key_rate;
    }
    
    double h2 = [](double x) {
        if (x <= 0.0 || x >= 1.0) return 0.0;
        return -x * std::log2(x) - (1.0 - x) * std::log2(1.0 - x);
    };
    
    double q = single_photon_fraction;
    double e1 = single_photon_error;
    
    double key_rate = sifted_key_rate * q * (1.0 - h2(e1)) - sifted_key_rate * leakage_fraction;
    
    return std::max(0.0, key_rate);
}

double DecoyStateProtocol::invertPoissonConstraint(
    double observed_yield,
    double intensity,
    double eta0,
    double p_dark) {
    
    double Y0 = p_dark;
    double lambda = intensity;
    
    double Y1_lower = (observed_yield * std::exp(lambda) - Y0) / lambda;
    Y1_lower = std::max(0.0, Y1_lower);
    
    return Y1_lower;
}

} // namespace bb84
