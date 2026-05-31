#include "../include/bob.h"
#include "../include/utils.h"

namespace bb84 {

Bob::Bob() {}

void Bob::generateRandomBases(int count) {
    bases_.clear();
    bases_.reserve(count);
    
    for (int i = 0; i < count; ++i) {
        bases_.push_back(
            utils::RandomGenerator::getInstance().randomBool() 
                ? Basis::DIAGONAL 
                : Basis::RECTILINEAR
        );
    }
}

std::vector<bool> Bob::measurePhotons(const std::vector<Photon>& photons,
                                      std::vector<bool>& detected) {
    measured_bits_.clear();
    detected_.clear();
    
    measured_bits_.reserve(photons.size());
    detected_.reserve(photons.size());
    
    size_t min_size = std::min(photons.size(), bases_.size());
    
    for (size_t i = 0; i < min_size; ++i) {
        bool bit_result = false;
        bool photon_detected = false;
        
        detector_.measure(photons[i], bases_[i], bit_result, photon_detected);
        
        measured_bits_.push_back(bit_result);
        detected_.push_back(photon_detected);
    }
    
    for (size_t i = min_size; i < photons.size(); ++i) {
        measured_bits_.push_back(false);
        detected_.push_back(false);
    }
    
    detected = detected_;
    return measured_bits_;
}

const std::vector<Basis>& Bob::getBases() const {
    return bases_;
}

const std::vector<bool>& Bob::getMeasuredBits() const {
    return measured_bits_;
}

const std::vector<bool>& Bob::getDetected() const {
    return detected_;
}

std::vector<bool> Bob::getSiftedKey(const std::vector<Basis>& alice_bases) {
    std::vector<bool> sifted_key;
    
    size_t min_size = std::min({
        measured_bits_.size(),
        alice_bases.size(),
        detected_.size()
    });
    
    sifted_key.reserve(min_size);
    
    for (size_t i = 0; i < min_size; ++i) {
        if (detected_[i] && bases_[i] == alice_bases[i]) {
            sifted_key.push_back(measured_bits_[i]);
        }
    }
    
    return sifted_key;
}

void Bob::setBases(const std::vector<Basis>& bases) {
    bases_ = bases;
}

} // namespace bb84
