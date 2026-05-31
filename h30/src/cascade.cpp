#include "../include/cascade.h"
#include "../include/utils.h"
#include <cmath>
#include <stdexcept>
#include <random>
#include <iostream>

namespace bb84 {

const double CascadeProtocol::MIN_QBER = 1e-6;

CascadeProtocol::CascadeProtocol(const Config& config) 
    : config_(config) {}

bool CascadeProtocol::computeBlockParity(const std::vector<bool>& key, 
                                         size_t start, size_t end) {
    bool parity = false;
    for (size_t i = start; i < end && i < key.size(); ++i) {
        parity = parity ^ key[i];
    }
    return parity;
}

int CascadeProtocol::binarySearchError(std::vector<bool>& alice_key,
                                       std::vector<bool>& bob_key,
                                       size_t start, size_t end,
                                       bool alice_parity, bool bob_parity,
                                       int& parity_bits) {
    if (end - start <= 1) {
        if (alice_parity != bob_parity) {
            bob_key[start] = !bob_key[start];
            parity_bits++;
            return 1;
        }
        return 0;
    }
    
    size_t mid = start + (end - start) / 2;
    
    bool alice_left = computeBlockParity(alice_key, start, mid);
    bool bob_left = computeBlockParity(bob_key, start, mid);
    parity_bits += 2;
    
    int errors_corrected = 0;
    
    if (alice_left != bob_left) {
        errors_corrected += binarySearchError(alice_key, bob_key, start, mid, 
                                             alice_left, bob_left, parity_bits);
    } else {
        bool alice_right = computeBlockParity(alice_key, mid, end);
        bool bob_right = computeBlockParity(bob_key, mid, end);
        parity_bits += 2;
        
        if (alice_right != bob_right) {
            errors_corrected += binarySearchError(alice_key, bob_key, mid, end,
                                                 alice_right, bob_right, parity_bits);
        }
    }
    
    return errors_corrected;
}

size_t CascadeProtocol::calculateMinimumBlockSize(double qber, size_t key_length) {
    double expected_errors = qber * key_length;
    if (expected_errors < 1.0) expected_errors = 1.0;
    
    size_t min_size = static_cast<size_t>(std::ceil(
        std::min(static_cast<double>(key_length), 1.0 / qber)
    ));
    
    return std::max(static_cast<size_t>(4), min_size);
}

size_t CascadeProtocol::calculateAdaptiveBlockSize(double current_qber, 
                                                   double initial_qber,
                                                   size_t key_length, 
                                                   int pass,
                                                   int previous_errors) {
    double qber_ratio = current_qber / initial_qber;
    
    double growth_factor = std::pow(2.0, qber_ratio + 0.5);
    if (previous_errors == 0) {
        growth_factor = 2.0;
    }
    
    size_t base_size;
    if (pass == 0) {
        double optimal = std::ceil(0.73 / std::max(current_qber, MIN_QBER));
        base_size = static_cast<size_t>(optimal);
    } else {
        double optimal = std::ceil(1.0 / std::max(current_qber, MIN_QBER));
        base_size = static_cast<size_t>(optimal);
        
        if (pass >= 2 && previous_errors > 0) {
            base_size = static_cast<size_t>(base_size * growth_factor);
        }
    }
    
    size_t min_size = calculateMinimumBlockSize(current_qber, key_length);
    size_t max_size = std::min(
        key_length, 
        static_cast<size_t>(key_length * 0.25)
    );
    
    if (pass >= 2) {
        max_size = std::min(
            key_length,
            static_cast<size_t>(key_length * 0.4)
        );
    }
    
    size_t block_size = std::max(min_size, std::min(base_size, max_size));
    
    if (pass >= 1 && current_qber < 0.05 && previous_errors < static_cast<int>(key_length * 0.01)) {
        block_size = std::min(
            static_cast<size_t>(key_length / 4),
            static_cast<size_t>(block_size * 2)
        );
    }
    
    return block_size;
}

double CascadeProtocol::updateQBEREstimate(double old_qber, 
                                           int errors_corrected, 
                                           size_t block_size,
                                           size_t key_length) {
    if (errors_corrected == 0) {
        double decay_factor = 0.5;
        return std::max(MIN_QBER, old_qber * decay_factor);
    }
    
    double new_estimate = static_cast<double>(errors_corrected) / 
                         static_cast<double>(key_length);
    
    double alpha = 0.3;
    double updated = alpha * new_estimate + (1.0 - alpha) * old_qber;
    
    return std::max(MIN_QBER, updated);
}

std::vector<size_t> CascadeProtocol::generateShuffledIndices(size_t length, int pass, uint64_t seed) {
    std::vector<size_t> indices(length);
    for (size_t i = 0; i < length; ++i) {
        indices[i] = i;
    }
    
    std::mt19937_64 rng(seed + static_cast<uint64_t>(pass) * 123456789ULL);
    std::shuffle(indices.begin(), indices.end(), rng);
    
    return indices;
}

bool CascadeProtocol::shouldContinue(int pass, 
                                     int errors_in_pass, 
                                     double current_qber,
                                     int total_parity_bits,
                                     size_t key_length) {
    if (pass >= config_.cascade_passes) {
        return false;
    }
    
    if (errors_in_pass == 0 && pass >= 2) {
        return false;
    }
    
    double information_leakage = static_cast<double>(total_parity_bits) / 
                                static_cast<double>(key_length);
    
    if (information_leakage > 0.5) {
        return false;
    }
    
    if (current_qber < 1e-4 && pass >= 2) {
        return false;
    }
    
    if (errors_in_pass == 0 && current_qber < 0.001) {
        return false;
    }
    
    return true;
}

void CascadeProtocol::runPass(std::vector<bool>& alice_key,
                              std::vector<bool>& bob_key,
                              size_t block_size,
                              int& errors_corrected,
                              int& parity_bits) {
    size_t key_length = alice_key.size();
    size_t num_blocks = (key_length + block_size - 1) / block_size;
    
    for (size_t block = 0; block < num_blocks; ++block) {
        size_t start = block * block_size;
        size_t end = std::min(start + block_size, key_length);
        
        bool alice_parity = computeBlockParity(alice_key, start, end);
        bool bob_parity = computeBlockParity(bob_key, start, end);
        parity_bits += 2;
        
        if (alice_parity != bob_parity) {
            errors_corrected += binarySearchError(alice_key, bob_key, start, end,
                                                 alice_parity, bob_parity, parity_bits);
        }
    }
}

CascadeResult CascadeProtocol::run(std::vector<bool> alice_key,
                                   std::vector<bool> bob_key,
                                   double estimated_qber) {
    CascadeResult result;
    result.total_errors_corrected = 0;
    result.total_parity_bits_exchanged = 0;
    result.passes_completed = 0;
    result.successful = false;
    result.information_leaked = 0.0;
    result.efficiency = 0.0;
    result.qber_per_pass.clear();
    result.errors_per_pass.clear();
    
    if (alice_key.size() != bob_key.size()) {
        throw std::invalid_argument("Alice and Bob keys must have same length");
    }
    
    size_t key_length = alice_key.size();
    if (key_length < 10) {
        result.corrected_key = bob_key;
        result.residual_error_rate = utils::calculateBER(alice_key, bob_key);
        result.successful = true;
        result.qber_per_pass.push_back(result.residual_error_rate);
        return result;
    }
    
    double initial_qber = estimated_qber > 0 ? estimated_qber : 0.01;
    double current_qber = initial_qber;
    int previous_errors = static_cast<int>(initial_qber * key_length);
    
    uint64_t shuffle_seed = utils::RandomGenerator::getInstance().randomUint64();
    
    int pass;
    for (pass = 0; pass < config_.cascade_passes; ++pass) {
        size_t block_size = calculateAdaptiveBlockSize(
            current_qber, initial_qber, key_length, pass, previous_errors
        );
        
        std::vector<size_t> shuffled = generateShuffledIndices(key_length, pass, shuffle_seed);
        
        std::vector<bool> alice_shuffled(key_length);
        std::vector<bool> bob_shuffled(key_length);
        for (size_t i = 0; i < key_length; ++i) {
            alice_shuffled[i] = alice_key[shuffled[i]];
            bob_shuffled[i] = bob_key[shuffled[i]];
        }
        
        int pass_errors = 0;
        int pass_parity = 0;
        
        runPass(alice_shuffled, bob_shuffled, block_size, pass_errors, pass_parity);
        
        for (size_t i = 0; i < key_length; ++i) {
            alice_key[shuffled[i]] = alice_shuffled[i];
            bob_key[shuffled[i]] = bob_shuffled[i];
        }
        
        result.total_errors_corrected += pass_errors;
        result.total_parity_bits_exchanged += pass_parity;
        result.passes_completed++;
        result.qber_per_pass.push_back(current_qber);
        result.errors_per_pass.push_back(pass_errors);
        
        current_qber = updateQBEREstimate(
            current_qber, pass_errors, block_size, key_length
        );
        
        if (!shouldContinue(pass + 1, pass_errors, current_qber,
                           result.total_parity_bits_exchanged, key_length)) {
            break;
        }
        
        previous_errors = pass_errors;
    }
    
    result.corrected_key = bob_key;
    result.residual_error_rate = utils::calculateBER(alice_key, bob_key);
    result.successful = true;
    
    result.information_leaked = static_cast<double>(result.total_parity_bits_exchanged) /
                               static_cast<double>(key_length);
    
    if (result.total_parity_bits_exchanged > 0) {
        result.efficiency = static_cast<double>(result.total_errors_corrected) /
                           static_cast<double>(result.total_parity_bits_exchanged);
    } else {
        result.efficiency = 0.0;
    }
    
    return result;
}

} // namespace bb84
