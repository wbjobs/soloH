#include "../include/utils.h"
#include "../include/types.h"
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <sstream>

namespace bb84 {
namespace utils {

RandomGenerator::RandomGenerator() : seeded(false) {
    std::random_device rd;
    rng.seed(rd());
}

RandomGenerator& RandomGenerator::getInstance() {
    static RandomGenerator instance;
    return instance;
}

void RandomGenerator::seed(uint64_t seed_val) {
    rng.seed(seed_val);
    seeded = true;
}

double RandomGenerator::randomDouble(double min, double max) {
    std::uniform_real_distribution<double> dist(min, max);
    return dist(rng);
}

int RandomGenerator::randomInt(int min, int max) {
    std::uniform_int_distribution<int> dist(min, max);
    return dist(rng);
}

bool RandomGenerator::randomBool(double prob_true) {
    std::bernoulli_distribution dist(prob_true);
    return dist(rng);
}

uint64_t RandomGenerator::randomUint64() {
    std::uniform_int_distribution<uint64_t> dist(0, UINT64_MAX);
    return dist(rng);
}

std::mt19937_64& RandomGenerator::getEngine() {
    return rng;
}

double hammingDistance(const std::vector<bool>& a, const std::vector<bool>& b) {
    if (a.size() != b.size()) {
        throw std::invalid_argument("Bit vectors must have same size for Hamming distance");
    }
    double distance = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i] != b[i]) {
            distance++;
        }
    }
    return distance;
}

double calculateBER(const std::vector<bool>& a, const std::vector<bool>& b) {
    if (a.empty() || b.empty()) return 0.0;
    return hammingDistance(a, b) / static_cast<double>(a.size());
}

std::vector<bool> xorBits(const std::vector<bool>& a, const std::vector<bool>& b) {
    if (a.size() != b.size()) {
        throw std::invalid_argument("Bit vectors must have same size for XOR");
    }
    std::vector<bool> result(a.size());
    for (size_t i = 0; i < a.size(); ++i) {
        result[i] = a[i] ^ b[i];
    }
    return result;
}

std::vector<bool> hashToBits(const std::vector<bool>& input, size_t output_len) {
    std::vector<bool> output(output_len, false);
    const size_t input_len = input.size();
    
    for (size_t i = 0; i < output_len; ++i) {
        bool bit = false;
        for (size_t j = 0; j < input_len; ++j) {
            size_t hash_pos = (j * 2654435761ULL + i * 1103515245ULL) % input_len;
            bit = bit ^ input[hash_pos];
        }
        output[i] = bit;
    }
    return output;
}

std::string basisToString(Basis b) {
    switch (b) {
        case Basis::RECTILINEAR: return "Rectilinear";
        case Basis::DIAGONAL: return "Diagonal";
        default: return "Unknown";
    }
}

std::string polarizationToString(Polarization p) {
    switch (p) {
        case Polarization::ZERO: return "0°";
        case Polarization::FORTY_FIVE: return "45°";
        case Polarization::NINETY: return "90°";
        case Polarization::ONE_HUNDRED_THIRTY_FIVE: return "135°";
        default: return "Unknown";
    }
}

std::string attackTypeToString(AttackType t) {
    switch (t) {
        case AttackType::NONE: return "None";
        case AttackType::INTERCEPT_RESEND: return "Intercept-Resend";
        case AttackType::BEAM_SPLITTING: return "Beam-Splitting";
        default: return "Unknown";
    }
}

std::string protocolTypeToString(ProtocolType t) {
    switch (t) {
        case ProtocolType::BB84: return "BB84";
        case ProtocolType::MDI_QKD: return "MDI-QKD";
        default: return "Unknown";
    }
}

std::string decoyStateToString(DecoyStateType t) {
    switch (t) {
        case DecoyStateType::SIGNAL: return "Signal";
        case DecoyStateType::DECOY1: return "Decoy1";
        case DecoyStateType::DECOY2: return "Decoy2";
        case DecoyStateType::VACUUM: return "Vacuum";
        default: return "Unknown";
    }
}

std::string bellStateToString(BellState s) {
    switch (s) {
        case BellState::PHI_PLUS: return "Phi+";
        case BellState::PHI_MINUS: return "Phi-";
        case BellState::PSI_PLUS: return "Psi+";
        case BellState::PSI_MINUS: return "Psi-";
        default: return "Unknown";
    }
}

void printProgressBar(int current, int total, int width) {
    double progress = static_cast<double>(current) / total;
    int pos = static_cast<int>(width * progress);
    
    std::cout << "[";
    for (int i = 0; i < width; ++i) {
        if (i < pos) std::cout << "=";
        else if (i == pos) std::cout << ">";
        else std::cout << " ";
    }
    std::cout << "] " << static_cast<int>(progress * 100.0) << "%\r";
    std::cout.flush();
}

} // namespace utils
} // namespace bb84
