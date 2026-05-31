#ifndef BB84_PRIVACY_AMPLIFICATION_H
#define BB84_PRIVACY_AMPLIFICATION_H

#include "types.h"
#include "config.h"
#include <vector>
#include <cstddef>

namespace bb84 {

struct PrivacyAmplificationResult {
    std::vector<bool> final_key;
    size_t final_key_length;
    size_t input_key_length;
    double information_leaked;
    double compression_factor;
    int security_parameter;
    double collision_probability;
    bool successful;
};

class PrivacyAmplification {
public:
    explicit PrivacyAmplification(const Config& config);
    
    PrivacyAmplificationResult run(const std::vector<bool>& corrected_key,
                                   double estimated_qber,
                                   int parity_bits_exchanged);
    
    size_t calculateFinalKeyLength(size_t input_length, 
                                   double qber, 
                                   int parity_bits,
                                   int& security_param);
    
    std::vector<bool> toeplitzHash(const std::vector<bool>& input,
                                   const std::vector<bool>& toep_bits,
                                   size_t output_length);
    
    std::vector<bool> generateToeplitzBits(size_t input_length,
                                           size_t output_length,
                                           uint64_t seed);
    
private:
    Config config_;
    static const int DEFAULT_SECURITY_PARAM = 40;
    
    double calculateShannonEntropy(double qber);
    double minEntropyBound(double qber, size_t key_length);
    double calculateInformationLeakage(double qber, 
                                       size_t key_length,
                                       int parity_bits,
                                       int security_param);
};

} // namespace bb84

#endif
