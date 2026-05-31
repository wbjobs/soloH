#ifndef BB84_BOB_H
#define BB84_BOB_H

#include "types.h"
#include "quantum.h"
#include <vector>

namespace bb84 {

class Bob {
public:
    Bob();
    
    void generateRandomBases(int count);
    std::vector<bool> measurePhotons(const std::vector<Photon>& photons,
                                     std::vector<bool>& detected);
    
    const std::vector<Basis>& getBases() const;
    const std::vector<bool>& getMeasuredBits() const;
    const std::vector<bool>& getDetected() const;
    
    std::vector<bool> getSiftedKey(const std::vector<Basis>& alice_bases);
    
    void setBases(const std::vector<Basis>& bases);
    
private:
    std::vector<Basis> bases_;
    std::vector<bool> measured_bits_;
    std::vector<bool> detected_;
    PhotonDetector detector_;
};

} // namespace bb84

#endif
