#ifndef BB84_CASCADE_H
#define BB84_CASCADE_H

#include "types.h"
#include "config.h"
#include <vector>
#include <algorithm>

namespace bb84 {

struct CascadeResult {
    std::vector<bool> corrected_key;
    int total_errors_corrected;
    int total_parity_bits_exchanged;
    int passes_completed;
    double residual_error_rate;
    double information_leaked;
    double efficiency;
    bool successful;
    std::vector<double> qber_per_pass;
    std::vector<int> errors_per_pass;
};

struct Block {
    size_t start;
    size_t end;
    bool parity;
};

class CascadeProtocol {
public:
    explicit CascadeProtocol(const Config& config);
    
    CascadeResult run(std::vector<bool> alice_key, 
                      std::vector<bool> bob_key,
                      double estimated_qber);
    
private:
    Config config_;
    static const double MIN_QBER;
    
    bool computeBlockParity(const std::vector<bool>& key, size_t start, size_t end);
    int binarySearchError(std::vector<bool>& alice_key, 
                          std::vector<bool>& bob_key,
                          size_t start, size_t end,
                          bool alice_parity, bool bob_parity,
                          int& parity_bits);
    
    void runPass(std::vector<bool>& alice_key, 
                 std::vector<bool>& bob_key,
                 size_t block_size,
                 int& errors_corrected,
                 int& parity_bits);
    
    size_t calculateAdaptiveBlockSize(double current_qber, 
                                       double initial_qber,
                                       size_t key_length, 
                                       int pass,
                                       int previous_errors);
    
    double updateQBEREstimate(double old_qber, 
                               int errors_corrected, 
                               size_t block_size,
                               size_t key_length);
    
    std::vector<size_t> generateShuffledIndices(size_t length, int pass, uint64_t seed);
    
    size_t calculateMinimumBlockSize(double qber, size_t key_length);
    
    bool shouldContinue(int pass, 
                        int errors_in_pass, 
                        double current_qber,
                        int total_parity_bits,
                        size_t key_length);
};

} // namespace bb84

#endif
