#ifndef BB84_UTILS_H
#define BB84_UTILS_H

#include <random>
#include <vector>
#include <string>
#include <cstdint>

namespace bb84 {
namespace utils {

class RandomGenerator {
public:
    static RandomGenerator& getInstance();
    void seed(uint64_t seed_val);
    double randomDouble(double min = 0.0, double max = 1.0);
    int randomInt(int min, int max);
    bool randomBool(double prob_true = 0.5);
    uint64_t randomUint64();
    std::mt19937_64& getEngine();

private:
    RandomGenerator();
    std::mt19937_64 rng;
    bool seeded;
};

double hammingDistance(const std::vector<bool>& a, const std::vector<bool>& b);
double calculateBER(const std::vector<bool>& a, const std::vector<bool>& b);

std::vector<bool> xorBits(const std::vector<bool>& a, const std::vector<bool>& b);
std::vector<bool> hashToBits(const std::vector<bool>& input, size_t output_len);

std::string basisToString(Basis b);
std::string polarizationToString(Polarization p);
std::string attackTypeToString(AttackType t);
std::string protocolTypeToString(ProtocolType t);
std::string decoyStateToString(DecoyStateType t);
std::string bellStateToString(BellState s);

void printProgressBar(int current, int total, int width = 50);

} // namespace utils
} // namespace bb84

#endif
