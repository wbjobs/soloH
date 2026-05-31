#include "../include/fiber_model.h"
#include "../include/utils.h"
#include <cmath>
#include <stdexcept>
#include <numbers>

namespace bb84 {

constexpr double PI = 3.14159265358979323846;
constexpr double LIGHT_SPEED = 2.99792458e8;

FiberModel::FiberModel(const FiberParameters& params)
    : params_(params), speed_of_light_(LIGHT_SPEED) {}

double FiberModel::dbToLinear(double db) {
    return std::pow(10.0, db / 10.0);
}

double FiberModel::linearToDb(double linear) {
    return 10.0 * std::log10(linear);
}

double FiberModel::calculateAttenuation() const {
    double total_loss_db = params_.attenuation_coeff * params_.length_km 
                          + params_.background_loss;
    return total_loss_db;
}

double FiberModel::getLossProbability() const {
    double loss_db = calculateAttenuation();
    double transmission = std::pow(10.0, -loss_db / 10.0);
    return 1.0 - transmission;
}

double FiberModel::calculateChromaticDispersion(double wavelength) const {
    double lambda_0 = 1310.0;
    double S0 = 0.092;
    
    double lambda = wavelength;
    double term = lambda / lambda_0;
    
    double D = S0 / 4.0 * (lambda - std::pow(lambda_0, 4) / std::pow(lambda, 3));
    return D;
}

double FiberModel::calculateGroupVelocityDispersion() const {
    double lambda = params_.wavelength_nm * 1e-9;
    double D = params_.dispersion_coeff * 1e-12;
    
    double beta2 = -D * lambda * lambda / (2.0 * PI * speed_of_light_);
    return beta2;
}

double FiberModel::calculateDispersion(double frequency) const {
    double beta2 = calculateGroupVelocityDispersion();
    double omega = 2.0 * PI * frequency;
    
    double dispersion = beta2 * omega * omega / 2.0;
    return dispersion;
}

double FiberModel::calculatePulseBroadening() const {
    double beta2 = calculateGroupVelocityDispersion();
    double t0 = params_.pulse_width_ps * 1e-12;
    
    double L = params_.length_km * 1000.0;
    double LD = t0 * t0 / std::abs(beta2);
    
    double broadening_factor = std::sqrt(1.0 + std::pow(L / LD, 2));
    return broadening_factor;
}

double FiberModel::calculateSPMEffect(double intensity) const {
    double gamma = params_.nonlinear_coeff;
    double L = params_.length_km * 1000.0;
    double A_eff = params_.effective_area * 1e-12;
    
    double peak_power = intensity / A_eff;
    double nonlinear_length = 1.0 / (gamma * peak_power);
    
    double spm_phase = gamma * peak_power * L;
    return spm_phase;
}

double FiberModel::calculateFourWaveMixing(double intensity) const {
    double L = params_.length_km * 1000.0;
    double alpha = params_.attenuation_coeff / 4.343;
    
    double eta = std::pow(alpha * L, 2) / (1.0 + std::pow(alpha * L, 2));
    double fwm_efficiency = eta * intensity * intensity;
    
    return fwm_efficiency;
}

double FiberModel::calculateNonlinearPhaseShift(double intensity) const {
    double spm = calculateSPMEffect(intensity);
    double fwm = calculateFourWaveMixing(intensity);
    
    double total_phase = spm + 0.1 * fwm;
    return total_phase;
}

double FiberModel::calculatePMD() const {
    double PMD_coeff = 0.1;
    double pmd = PMD_coeff * std::sqrt(params_.length_km);
    return pmd;
}

double FiberModel::calculatePolarizationModeCoupling() const {
    double coupling_strength = 1e-4 * params_.length_km;
    return coupling_strength;
}

double FiberModel::calculatePolarizationRotation() const {
    double beat_length = 10.0;
    double L = params_.length_km * 1000.0;
    
    double rotation = (PI / beat_length) * L;
    
    double coupling = calculatePolarizationModeCoupling();
    double random_rotation = utils::RandomGenerator::getInstance().randomDouble(
        -coupling, coupling
    );
    
    double total_rotation = rotation + random_rotation;
    return total_rotation;
}

double FiberModel::calculateFiberInducedQBER() const {
    double pmd = calculatePMD();
    double pulse_broadening = calculatePulseBroadening();
    
    double broadening_error = (pulse_broadening - 1.0) * 0.01;
    double pmd_error = pmd * 0.005;
    
    double rotation = std::abs(calculatePolarizationRotation());
    double rotation_error = std::sin(rotation) * 0.02;
    
    double nonlinear_error = 0.0;
    if (params_.length_km > 50.0) {
        nonlinear_error = 0.001 * (params_.length_km / 100.0);
    }
    
    double total_qber = broadening_error + pmd_error + rotation_error + nonlinear_error;
    return std::min(0.15, total_qber);
}

FiberEffectResult FiberModel::propagatePhoton(Photon& photon) {
    FiberEffectResult effects;
    
    effects.total_attenuation_db = calculateAttenuation();
    effects.pulse_broadening_factor = calculatePulseBroadening();
    effects.polarization_mode_dispersion = calculatePMD();
    effects.nonlinear_phase_shift = calculateNonlinearPhaseShift(photon.intensity);
    effects.polarization_rotation = calculatePolarizationRotation();
    effects.additional_qber = calculateFiberInducedQBER();
    
    double loss_prob = getLossProbability();
    if (utils::RandomGenerator::getInstance().randomBool(loss_prob)) {
        photon.detected = false;
    }
    
    if (effects.additional_qber > 0 && photon.detected) {
        if (utils::RandomGenerator::getInstance().randomBool(effects.additional_qber)) {
            photon.bit_value = !photon.bit_value;
            
            if (photon.polarization == Polarization::ZERO || 
                photon.polarization == Polarization::NINETY) {
                photon.polarization = (photon.polarization == Polarization::ZERO) 
                    ? Polarization::NINETY : Polarization::ZERO;
            } else {
                photon.polarization = (photon.polarization == Polarization::FORTY_FIVE) 
                    ? Polarization::ONE_HUNDRED_THIRTY_FIVE : Polarization::FORTY_FIVE;
            }
        }
    }
    
    double rotation_std = effects.polarization_mode_dispersion * 0.1;
    double polarization_noise = utils::RandomGenerator::getInstance().randomDouble(
        -rotation_std, rotation_std
    );
    
    if (std::abs(polarization_noise) > 0.5 && photon.detected) {
        int current_pol = static_cast<int>(photon.polarization);
        int shift = polarization_noise > 0 ? 1 : 3;
        photon.polarization = static_cast<Polarization>((current_pol + shift) % 4);
    }
    
    photon.arrival_time_ps += effects.pulse_broadening_factor * 10.0;
    photon.fiber_effects = effects;
    
    return effects;
}

std::vector<Photon> FiberModel::propagatePhotons(std::vector<Photon>& photons,
                                                  FiberEffectResult& avg_effects) {
    avg_effects = {0, 0, 0, 0, 0, 0};
    
    int valid_count = 0;
    for (auto& photon : photons) {
        FiberEffectResult effects = propagatePhoton(photon);
        
        avg_effects.pulse_broadening_factor += effects.pulse_broadening_factor;
        avg_effects.polarization_mode_dispersion += effects.polarization_mode_dispersion;
        avg_effects.nonlinear_phase_shift += effects.nonlinear_phase_shift;
        avg_effects.polarization_rotation += effects.polarization_rotation;
        avg_effects.total_attenuation_db += effects.total_attenuation_db;
        avg_effects.additional_qber += effects.additional_qber;
        
        valid_count++;
    }
    
    if (valid_count > 0) {
        avg_effects.pulse_broadening_factor /= valid_count;
        avg_effects.polarization_mode_dispersion /= valid_count;
        avg_effects.nonlinear_phase_shift /= valid_count;
        avg_effects.polarization_rotation /= valid_count;
        avg_effects.total_attenuation_db /= valid_count;
        avg_effects.additional_qber /= valid_count;
    }
    
    return photons;
}

void FiberModel::updateParameters(const FiberParameters& params) {
    params_ = params;
}

const FiberParameters& FiberModel::getParameters() const {
    return params_;
}

std::complex<double> FiberModel::applyDispersionOperator(std::complex<double> field,
                                                         double frequency) const {
    double phase = calculateDispersion(frequency);
    std::complex<double> op(std::cos(phase), -std::sin(phase));
    return field * op;
}

std::complex<double> FiberModel::applyNonlinearOperator(std::complex<double> field,
                                                        double intensity) const {
    double phase = calculateNonlinearPhaseShift(intensity);
    std::complex<double> op(std::cos(phase), std::sin(phase));
    return field * op;
}

FiberGainMedium::FiberGainMedium(double gain_db, double noise_figure)
    : gain_db_(gain_db), noise_figure_(noise_figure) {
    gain_linear_ = FiberModel::dbToLinear(gain_db);
}

void FiberGainMedium::applyAmplification(std::vector<Photon>& photons,
                                          double& added_noise_photons) {
    added_noise_photons = 0.0;
    
    double nsp = (noise_figure_ * gain_linear_ - 1.0) / (2.0 * (gain_linear_ - 1.0));
    double noise_per_photon = nsp * (gain_linear_ - 1.0);
    
    for (auto& photon : photons) {
        if (photon.detected) {
            photon.intensity *= gain_linear_;
            
            if (utils::RandomGenerator::getInstance().randomBool(noise_per_photon * 0.1)) {
                added_noise_photons += 1.0;
                
                if (utils::RandomGenerator::getInstance().randomBool(0.05)) {
                    photon.bit_value = !photon.bit_value;
                }
            }
        }
    }
}

} // namespace bb84
