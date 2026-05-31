#ifndef BB84_QUANTUM_H
#define BB84_QUANTUM_H

#include "types.h"
#include "config.h"
#include "fiber_model.h"
#include "decoy_state.h"
#include <vector>
#include <memory>

namespace bb84 {

class QuantumChannel {
public:
    explicit QuantumChannel(const Config& config);
    
    Photon transmitPhoton(const Photon& input, bool& lost);
    std::vector<Photon> transmitPhotons(const std::vector<Photon>& input, 
                                        int& total_lost, int& dark_counts);
    
    void setEavesdropperActive(bool active);
    void applyNoise(Photon& photon, bool& lost);
    
    void enableFiberModel(bool enable);
    bool isFiberModelEnabled() const;
    FiberEffectResult getAverageFiberEffects() const;
    
    void setFiberParameters(const FiberParameters& params);
    
private:
    Config config_;
    bool eavesdropper_active_;
    std::unique_ptr<FiberModel> fiber_model_;
    bool fiber_model_enabled_;
    FiberEffectResult avg_fiber_effects_;
    
    bool simulatePhotonLoss();
    bool simulateDarkCount();
    void applyPolarizationError(Photon& photon);
    Basis measureInBasis(const Photon& photon, Basis measurement_basis, bool& bit_result);
    
    void applyFiberEffects(Photon& photon);
};

class PhotonSource {
public:
    PhotonSource();
    Photon generatePhoton(bool bit, Basis basis, double intensity = 1.0);
    std::vector<Photon> generatePhotons(const std::vector<bool>& bits, 
                                        const std::vector<Basis>& bases);
    
    void enableDecoyStates(bool enable, const std::vector<DecoySetting>& settings);
    std::vector<Photon> generatePhotonsWithDecoys(
        const std::vector<bool>& bits,
        const std::vector<Basis>& bases
    );
    
    bool isDecoyEnabled() const;
    DecoyStateProtocol& getDecoyProtocol();
    
private:
    bool decoy_enabled_;
    DecoyStateProtocol decoy_protocol_;
};

class PhotonDetector {
public:
    bool measure(const Photon& photon, Basis measurement_basis, bool& bit_result, bool& detected);
    
private:
    bool simulateClick(double probability);
};

} // namespace bb84

#endif
