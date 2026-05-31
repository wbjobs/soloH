#ifndef BB84_PROTOCOL_H
#define BB84_PROTOCOL_H

#include "types.h"
#include "config.h"
#include "alice.h"
#include "bob.h"
#include "eve.h"
#include "quantum.h"
#include "cascade.h"
#include "privacy_amplification.h"
#include "mdi_qkd.h"
#include <memory>

namespace bb84 {

class BB84Protocol {
public:
    explicit BB84Protocol(const Config& config);
    
    RunResult runSingleRun(int run_id);
    
private:
    Config config_;
    Alice alice_;
    Bob bob_;
    Eve eve_;
    QuantumChannel channel_;
    CascadeProtocol cascade_;
    PrivacyAmplification privacy_amp_;
    std::unique_ptr<MDIProtocol> mdi_protocol_;
    std::unique_ptr<DecoyStateProtocol> decoy_protocol_;
    
    RunResult runBB84(int run_id);
    RunResult runMDIQKD(int run_id);
    
    double calculateQBER(const std::vector<bool>& test_bits_alice,
                         const std::vector<bool>& test_bits_bob);
    
    size_t calculateOptimalTestSize(size_t key_length, 
                                     double expected_qber,
                                     double threshold,
                                     double confidence_level = 0.99,
                                     double detection_power = 0.95);
    
    double normalQuantile(double p);
    
    std::vector<bool> extractTestBits(const std::vector<bool>& key,
                                      size_t test_size,
                                      std::vector<size_t>& test_indices);
    
    std::vector<bool> removeTestBits(const std::vector<bool>& key,
                                     const std::vector<size_t>& test_indices);
    
    bool detectEavesdropping(double qber, size_t test_size);
    
    void verifyKeysMatch(const std::vector<bool>& alice_key,
                         const std::vector<bool>& bob_key,
                         int& errors_corrected);
    
    void initializeDecoyStates();
    DecoyResult runDecoyStateAnalysis(
        const std::vector<Photon>& transmitted,
        const std::vector<bool>& detected,
        const std::vector<Basis>& alice_bases,
        const std::vector<Basis>& bob_bases
    );
};

} // namespace bb84

#endif
