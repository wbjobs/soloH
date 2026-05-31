#include "../include/alice.h"
#include "../include/utils.h"

namespace bb84 {

Alice::Alice() {}

void Alice::generateRandomBits(int count) {
    key_bits_.bits.clear();
    key_bits_.bits.reserve(count);
    
    for (int i = 0; i < count; ++i) {
        key_bits_.bits.push_back(
            utils::RandomGenerator::getInstance().randomBool()
        );
    }
}

void Alice::generateRandomBases(int count) {
    key_bits_.bases.clear();
    key_bits_.bases.reserve(count);
    key_bits_.polarization_bits.clear();
    key_bits_.polarization_bits.reserve(count);
    
    for (int i = 0; i < count; ++i) {
        Basis basis = utils::RandomGenerator::getInstance().randomBool() 
            ? Basis::DIAGONAL 
            : Basis::RECTILINEAR;
        key_bits_.bases.push_back(basis);
        key_bits_.polarization_bits.push_back(
            basis == Basis::RECTILINEAR ? false : true
        );
    }
}

std::vector<Photon> Alice::preparePhotons() {
    if (key_bits_.bits.size() != key_bits_.bases.size()) {
        generateRandomBits(key_bits_.bases.size());
    }
    
    return photon_source_.generatePhotons(key_bits_.bits, key_bits_.bases);
}

const std::vector<bool>& Alice::getBits() const {
    return key_bits_.bits;
}

const std::vector<Basis>& Alice::getBases() const {
    return key_bits_.bases;
}

const KeyBits& Alice::getKeyBits() const {
    return key_bits_;
}

std::vector<bool> Alice::getSiftedKey(const std::vector<Basis>& bob_bases,
                                      const std::vector<bool>& photon_detected) {
    std::vector<bool> sifted_key;
    
    size_t min_size = std::min({
        key_bits_.bits.size(), 
        bob_bases.size(), 
        photon_detected.size()
    });
    
    sifted_key.reserve(min_size);
    
    for (size_t i = 0; i < min_size; ++i) {
        if (photon_detected[i] && key_bits_.bases[i] == bob_bases[i]) {
            sifted_key.push_back(key_bits_.bits[i]);
        }
    }
    
    return sifted_key;
}

void Alice::setBits(const std::vector<bool>& bits) {
    key_bits_.bits = bits;
}

void Alice::setBases(const std::vector<Basis>& bases) {
    key_bits_.bases = bases;
}

} // namespace bb84
