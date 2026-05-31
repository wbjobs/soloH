#ifndef BB84_ALICE_H
#define BB84_ALICE_H

#include "types.h"
#include "quantum.h"
#include <vector>

namespace bb84 {

class Alice {
public:
    Alice();
    
    void generateRandomBits(int count);
    void generateRandomBases(int count);
    std::vector<Photon> preparePhotons();
    
    const std::vector<bool>& getBits() const;
    const std::vector<Basis>& getBases() const;
    const KeyBits& getKeyBits() const;
    
    std::vector<bool> getSiftedKey(const std::vector<Basis>& bob_bases,
                                   const std::vector<bool>& photon_detected);
    
    void setBits(const std::vector<bool>& bits);
    void setBases(const std::vector<Basis>& bases);
    
private:
    KeyBits key_bits_;
    PhotonSource photon_source_;
};

} // namespace bb84

#endif
