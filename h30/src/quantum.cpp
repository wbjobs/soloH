#include "../include/quantum.h"
#include "../include/utils.h"
#include <cmath>

namespace bb84 {

QuantumChannel::QuantumChannel(const Config& config) 
    : config_(config), eavesdropper_active_(false),
      fiber_model_enabled_(false),
      avg_fiber_effects_{0, 0, 0, 0, 0, 0} {
    
    if (config.use_fiber_model || config.fiber_length_km > 0) {
        FiberParameters params = config.fiber_params;
        if (config.fiber_length_km > 0) {
            params.length_km = config.fiber_length_km;
            params.attenuation_coeff = config.fiber_attenuation;
            params.dispersion_coeff = config.fiber_dispersion;
            params.nonlinear_coeff = config.fiber_nonlinear;
        }
        fiber_model_ = std::make_unique<FiberModel>(params);
        fiber_model_enabled_ = true;
    }
}

void QuantumChannel::setEavesdropperActive(bool active) {
    eavesdropper_active_ = active;
}

void QuantumChannel::enableFiberModel(bool enable) {
    fiber_model_enabled_ = enable;
    if (enable && !fiber_model_) {
        fiber_model_ = std::make_unique<FiberModel>(config_.fiber_params);
    }
}

bool QuantumChannel::isFiberModelEnabled() const {
    return fiber_model_enabled_;
}

FiberEffectResult QuantumChannel::getAverageFiberEffects() const {
    return avg_fiber_effects_;
}

void QuantumChannel::setFiberParameters(const FiberParameters& params) {
    if (!fiber_model_) {
        fiber_model_ = std::make_unique<FiberModel>(params);
    } else {
        fiber_model_->updateParameters(params);
    }
    fiber_model_enabled_ = true;
}

bool QuantumChannel::simulatePhotonLoss() {
    if (fiber_model_enabled_ && fiber_model_) {
        return fiber_model_->getLossProbability();
    }
    return utils::RandomGenerator::getInstance().randomBool(config_.channel_loss_rate);
}

bool QuantumChannel::simulateDarkCount() {
    return utils::RandomGenerator::getInstance().randomBool(config_.dark_count_prob);
}

void QuantumChannel::applyPolarizationError(Photon& photon) {
    double error_prob = 0.01;
    if (utils::RandomGenerator::getInstance().randomBool(error_prob)) {
        int shift = utils::RandomGenerator::getInstance().randomInt(1, 3);
        photon.polarization = static_cast<Polarization>(
            (static_cast<int>(photon.polarization) + shift) % 4
        );
    }
}

bool QuantumChannel::measureInBasis(const Photon& photon, Basis measurement_basis, bool& bit_result) {
    if (photon.basis == measurement_basis) {
        if (photon.polarization == Polarization::ZERO || 
            photon.polarization == Polarization::FORTY_FIVE) {
            bit_result = false;
        } else {
            bit_result = true;
        }
        return true;
    } else {
        bit_result = utils::RandomGenerator::getInstance().randomBool();
        return false;
    }
}

void QuantumChannel::applyFiberEffects(Photon& photon) {
    if (fiber_model_enabled_ && fiber_model_) {
        FiberEffectResult effects = fiber_model_->propagatePhoton(photon);
        
        avg_fiber_effects_.pulse_broadening_factor += effects.pulse_broadening_factor;
        avg_fiber_effects_.polarization_mode_dispersion += effects.polarization_mode_dispersion;
        avg_fiber_effects_.nonlinear_phase_shift += effects.nonlinear_phase_shift;
        avg_fiber_effects_.polarization_rotation += effects.polarization_rotation;
        avg_fiber_effects_.total_attenuation_db += effects.total_attenuation_db;
        avg_fiber_effects_.additional_qber += effects.additional_qber;
    }
}

void QuantumChannel::applyNoise(Photon& photon, bool& lost) {
    if (fiber_model_enabled_ && fiber_model_) {
        applyFiberEffects(photon);
        lost = !photon.detected;
    } else {
        lost = simulatePhotonLoss();
        if (!lost) {
            applyPolarizationError(photon);
        }
    }
}

Photon QuantumChannel::transmitPhoton(const Photon& input, bool& lost) {
    Photon output = input;
    applyNoise(output, lost);
    
    if (!lost && simulateDarkCount()) {
        output.polarization = static_cast<Polarization>(
            utils::RandomGenerator::getInstance().randomInt(0, 3)
        );
        output.bit_value = utils::RandomGenerator::getInstance().randomBool();
    }
    
    output.detected = !lost;
    return output;
}

std::vector<Photon> QuantumChannel::transmitPhotons(const std::vector<Photon>& input,
                                                    int& total_lost, int& dark_counts) {
    std::vector<Photon> output;
    output.reserve(input.size());
    total_lost = 0;
    dark_counts = 0;
    
    avg_fiber_effects_ = {0, 0, 0, 0, 0, 0};
    int processed = 0;
    
    for (const auto& photon : input) {
        bool lost = false;
        Photon transmitted = transmitPhoton(photon, lost);
        
        if (!lost && utils::RandomGenerator::getInstance().randomBool(config_.dark_count_prob)) {
            dark_counts++;
        }
        
        if (lost) {
            total_lost++;
        }
        output.push_back(transmitted);
        processed++;
    }
    
    if (processed > 0 && fiber_model_enabled_) {
        avg_fiber_effects_.pulse_broadening_factor /= processed;
        avg_fiber_effects_.polarization_mode_dispersion /= processed;
        avg_fiber_effects_.nonlinear_phase_shift /= processed;
        avg_fiber_effects_.polarization_rotation /= processed;
        avg_fiber_effects_.total_attenuation_db /= processed;
        avg_fiber_effects_.additional_qber /= processed;
    }
    
    return output;
}

PhotonSource::PhotonSource()
    : decoy_enabled_(false) {}

Photon PhotonSource::generatePhoton(bool bit, Basis basis, double intensity) {
    Photon photon;
    photon.basis = basis;
    photon.bit_value = bit;
    photon.detected = true;
    photon.intensity = intensity;
    
    if (basis == Basis::RECTILINEAR) {
        photon.polarization = bit ? Polarization::NINETY : Polarization::ZERO;
    } else {
        photon.polarization = bit ? Polarization::ONE_HUNDRED_THIRTY_FIVE : Polarization::FORTY_FIVE;
    }
    
    return photon;
}

std::vector<Photon> PhotonSource::generatePhotons(const std::vector<bool>& bits,
                                                  const std::vector<Basis>& bases) {
    if (decoy_enabled_) {
        return generatePhotonsWithDecoys(bits, bases);
    }
    
    std::vector<Photon> photons;
    photons.reserve(bits.size());
    
    for (size_t i = 0; i < bits.size(); ++i) {
        photons.push_back(generatePhoton(bits[i], bases[i]));
    }
    
    return photons;
}

void PhotonSource::enableDecoyStates(bool enable, const std::vector<DecoySetting>& settings) {
    decoy_enabled_ = enable;
    if (enable) {
        decoy_protocol_.setSettings(settings);
    }
}

std::vector<Photon> PhotonSource::generatePhotonsWithDecoys(
    const std::vector<bool>& bits,
    const std::vector<Basis>& bases) {
    
    return decoy_protocol_.generatePhotonsWithDecoys(bits, bases);
}

bool PhotonSource::isDecoyEnabled() const {
    return decoy_enabled_;
}

DecoyStateProtocol& PhotonSource::getDecoyProtocol() {
    return decoy_protocol_;
}

bool PhotonDetector::simulateClick(double probability) {
    return utils::RandomGenerator::getInstance().randomBool(probability);
}

bool PhotonDetector::measure(const Photon& photon, Basis measurement_basis, 
                             bool& bit_result, bool& detected) {
    if (!photon.detected) {
        detected = false;
        bit_result = false;
        return false;
    }
    
    double detection_prob = 0.95;
    if (photon.intensity < 1.0 && photon.intensity > 0) {
        detection_prob *= photon.intensity;
    }
    
    detected = simulateClick(detection_prob);
    if (!detected) {
        bit_result = false;
        return false;
    }
    
    Basis photon_basis = photon.basis;
    
    if (measurement_basis == photon_basis) {
        if (photon.polarization == Polarization::ZERO || 
            photon.polarization == Polarization::FORTY_FIVE) {
            bit_result = false;
        } else {
            bit_result = true;
        }
        return true;
    } else {
        bit_result = utils::RandomGenerator::getInstance().randomBool();
        return false;
    }
}

} // namespace bb84
