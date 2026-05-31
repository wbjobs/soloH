#include "../include/eve.h"
#include "../include/utils.h"

namespace bb84 {

Eve::Eve(const Config& config) 
    : config_(config), 
      attack_type_(config.attack_type),
      eavesdropping_strength_(config.eavesdropping_strength) {}

Basis Eve::generateRandomBasis() {
    return utils::RandomGenerator::getInstance().randomBool() 
        ? Basis::DIAGONAL 
        : Basis::RECTILINEAR;
}

Photon Eve::generateReplacementPhoton(bool bit, Basis basis) {
    return photon_source_.generatePhoton(bit, basis);
}

std::vector<Photon> Eve::interceptResendAttack(const std::vector<Photon>& photons,
                                               int& introduced_errors) {
    stolen_bits_.clear();
    measurement_bases_.clear();
    introduced_errors = 0;
    
    std::vector<Photon> modified_photons;
    modified_photons.reserve(photons.size());
    
    for (size_t i = 0; i < photons.size(); ++i) {
        if (!utils::RandomGenerator::getInstance().randomBool(eavesdropping_strength_)) {
            modified_photons.push_back(photons[i]);
            stolen_bits_.push_back(false);
            measurement_bases_.push_back(Basis::RECTILINEAR);
            continue;
        }
        
        Basis eve_basis = generateRandomBasis();
        measurement_bases_.push_back(eve_basis);
        
        bool bit_result = false;
        bool detected = false;
        detector_.measure(photons[i], eve_basis, bit_result, detected);
        
        if (detected) {
            stolen_bits_.push_back(bit_result);
            
            Photon replacement = generateReplacementPhoton(bit_result, eve_basis);
            modified_photons.push_back(replacement);
            
            if (eve_basis != photons[i].basis) {
                introduced_errors++;
            }
        } else {
            stolen_bits_.push_back(false);
            modified_photons.push_back(photons[i]);
        }
    }
    
    return modified_photons;
}

std::vector<Photon> Eve::beamSplittingAttack(const std::vector<Photon>& photons,
                                              int& introduced_errors) {
    stolen_bits_.clear();
    measurement_bases_.clear();
    introduced_errors = 0;
    
    std::vector<Photon> modified_photons;
    modified_photons.reserve(photons.size());
    
    double split_ratio = eavesdropping_strength_ * 0.5;
    
    for (size_t i = 0; i < photons.size(); ++i) {
        if (!utils::RandomGenerator::getInstance().randomBool(eavesdropping_strength_)) {
            modified_photons.push_back(photons[i]);
            stolen_bits_.push_back(false);
            measurement_bases_.push_back(Basis::RECTILINEAR);
            continue;
        }
        
        Basis eve_basis = generateRandomBasis();
        measurement_bases_.push_back(eve_basis);
        
        bool eve_detected = utils::RandomGenerator::getInstance().randomBool(split_ratio);
        bool bob_receives = utils::RandomGenerator::getInstance().randomBool(1.0 - split_ratio);
        
        if (eve_detected) {
            bool bit_result = false;
            bool detected = false;
            detector_.measure(photons[i], eve_basis, bit_result, detected);
            stolen_bits_.push_back(detected ? bit_result : false);
        } else {
            stolen_bits_.push_back(false);
        }
        
        if (bob_receives) {
            Photon modified_photon = photons[i];
            
            double disturbance_prob = split_ratio * 0.15;
            if (utils::RandomGenerator::getInstance().randomBool(disturbance_prob)) {
                if (modified_photon.basis == Basis::RECTILINEAR) {
                    modified_photon.polarization = modified_photon.polarization == Polarization::ZERO 
                        ? Polarization::NINETY : Polarization::ZERO;
                } else {
                    modified_photon.polarization = modified_photon.polarization == Polarization::FORTY_FIVE 
                        ? Polarization::ONE_HUNDRED_THIRTY_FIVE : Polarization::FORTY_FIVE;
                }
                modified_photon.bit_value = !modified_photon.bit_value;
                introduced_errors++;
            }
            
            modified_photons.push_back(modified_photon);
        } else {
            Photon lost_photon = photons[i];
            lost_photon.detected = false;
            modified_photons.push_back(lost_photon);
            introduced_errors++;
        }
    }
    
    return modified_photons;
}

std::vector<Photon> Eve::applyAttack(const std::vector<Photon>& photons,
                                     int& introduced_errors) {
    if (attack_type_ == AttackType::NONE) {
        stolen_bits_.assign(photons.size(), false);
        measurement_bases_.assign(photons.size(), Basis::RECTILINEAR);
        introduced_errors = 0;
        return photons;
    }
    
    if (attack_type_ == AttackType::INTERCEPT_RESEND) {
        return interceptResendAttack(photons, introduced_errors);
    } else {
        return beamSplittingAttack(photons, introduced_errors);
    }
}

const std::vector<bool>& Eve::getStolenBits() const {
    return stolen_bits_;
}

const std::vector<Basis>& Eve::getMeasurementBases() const {
    return measurement_bases_;
}

void Eve::setAttackType(AttackType type) {
    attack_type_ = type;
}

void Eve::setEavesdroppingStrength(double strength) {
    eavesdropping_strength_ = strength;
}

} // namespace bb84
