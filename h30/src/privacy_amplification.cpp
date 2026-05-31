#include "../include/privacy_amplification.h"
#include "../include/utils.h"
#include <cmath>
#include <stdexcept>
#include <random>

namespace bb84 {

PrivacyAmplification::PrivacyAmplification(const Config& config) 
    : config_(config) {}

double PrivacyAmplification::calculateShannonEntropy(double qber) {
    if (qber <= 0.0 || qber >= 1.0) return 0.0;
    return -qber * std::log2(qber) - (1.0 - qber) * std::log2(1.0 - qber);
}

double PrivacyAmplification::minEntropyBound(double qber, size_t key_length) {
    double h2 = calculateShannonEntropy(qber);
    return static_cast<double>(key_length) * (1.0 - h2);
}

double PrivacyAmplification::calculateInformationLeakage(double qber,
                                                         size_t key_length,
                                                         int parity_bits,
                                                         int security_param) {
    double eve_info_from_qber = static_cast<double>(key_length) * calculateShannonEntropy(qber);
    double parity_info = static_cast<double>(parity_bits);
    double security_margin = static_cast<double>(security_param);
    
    return eve_info_from_qber + parity_info + security_margin;
}

size_t PrivacyAmplification::calculateFinalKeyLength(size_t input_length,
                                                     double qber,
                                                     int parity_bits,
                                                     int& security_param) {
    security_param = DEFAULT_SECURITY_PARAM;
    
    double min_entropy = minEntropyBound(qber, input_length);
    
    if (min_entropy <= static_cast<double>(2 * security_param + parity_bits)) {
        int max_sp = static_cast<int>(min_entropy / 3.0);
        security_param = std::max(10, max_sp);
    }
    
    if (min_entropy <= static_cast<double>(parity_bits + 20)) {
        return 0;
    }
    
    double leaked = calculateInformationLeakage(qber, input_length, parity_bits, security_param);
    double final_length = min_entropy - leaked;
    
    if (final_length <= 0) {
        security_param = std::max(10, security_param / 2);
        leaked = calculateInformationLeakage(qber, input_length, parity_bits, security_param);
        final_length = min_entropy - leaked;
        
        if (final_length <= 0) {
            return 0;
        }
    }
    
    final_length *= config_.privacy_amplification_factor;
    
    return static_cast<size_t>(std::max(0.0, std::floor(final_length)));
}

std::vector<bool> PrivacyAmplification::generateToeplitzBits(size_t input_length,
                                                             size_t output_length,
                                                             uint64_t seed) {
    size_t toep_size = input_length + output_length - 1;
    std::vector<bool> toep_bits(toep_size);
    
    std::mt19937_64 rng(seed);
    std::bernoulli_distribution dist(0.5);
    
    for (size_t i = 0; i < toep_size; ++i) {
        toep_bits[i] = dist(rng);
    }
    
    return toep_bits;
}

std::vector<bool> PrivacyAmplification::toeplitzHash(const std::vector<bool>& input,
                                                     const std::vector<bool>& toep_bits,
                                                     size_t output_length) {
    const size_t input_length = input.size();
    std::vector<bool> output(output_length, false);
    
    if (input_length == 0 || output_length == 0) {
        return output;
    }
    
    if (toep_bits.size() != input_length + output_length - 1) {
        throw std::invalid_argument("Toeplitz bits size mismatch");
    }
    
    for (size_t row = 0; row < output_length; ++row) {
        bool hash_bit = false;
        for (size_t col = 0; col < input_length; ++col) {
            size_t toep_idx = output_length - 1 - row + col;
            if (toep_bits[toep_idx] && input[col]) {
                hash_bit = !hash_bit;
            }
        }
        output[row] = hash_bit;
    }
    
    return output;
}

PrivacyAmplificationResult PrivacyAmplification::run(const std::vector<bool>& corrected_key,
                                                    double estimated_qber,
                                                    int parity_bits_exchanged) {
    PrivacyAmplificationResult result;
    result.input_key_length = corrected_key.size();
    result.successful = false;
    result.security_parameter = 0;
    result.collision_probability = 1.0;
    
    if (corrected_key.empty()) {
        result.final_key_length = 0;
        result.information_leaked = 0;
        result.compression_factor = 0;
        result.final_key.clear();
        return result;
    }
    
    double qber = estimated_qber > 0 ? estimated_qber : 0.001;
    int security_param = 0;
    
    size_t output_length = calculateFinalKeyLength(
        corrected_key.size(), qber, parity_bits_exchanged, security_param
    );
    
    result.security_parameter = security_param;
    result.collision_probability = std::pow(2.0, -static_cast<double>(security_param));
    
    if (output_length == 0) {
        result.final_key_length = 0;
        result.information_leaked = calculateInformationLeakage(
            qber, corrected_key.size(), parity_bits_exchanged, security_param
        );
        result.compression_factor = 0;
        result.final_key.clear();
        return result;
    }
    
    if (output_length > corrected_key.size()) {
        output_length = corrected_key.size();
    }
    
    uint64_t seed = utils::RandomGenerator::getInstance().randomUint64();
    std::vector<bool> toep_bits = generateToeplitzBits(
        corrected_key.size(), output_length, seed
    );
    
    result.final_key = toeplitzHash(corrected_key, toep_bits, output_length);
    result.final_key_length = result.final_key.size();
    result.information_leaked = calculateInformationLeakage(
        qber, corrected_key.size(), parity_bits_exchanged, security_param
    );
    result.compression_factor = static_cast<double>(result.final_key_length) / 
                               static_cast<double>(corrected_key.size());
    result.successful = true;
    
    return result;
}

} // namespace bb84
