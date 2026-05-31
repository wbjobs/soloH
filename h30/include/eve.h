#ifndef BB84_EVE_H
#define BB84_EVE_H

#include "types.h"
#include "quantum.h"
#include "config.h"
#include <vector>

namespace bb84 {

class Eve {
public:
    explicit Eve(const Config& config);
    
    std::vector<Photon> interceptResendAttack(const std::vector<Photon>& photons,
                                             int& introduced_errors);
    
    std::vector<Photon> beamSplittingAttack(const std::vector<Photon>& photons,
                                            int& introduced_errors);
    
    std::vector<Photon> applyAttack(const std::vector<Photon>& photons,
                                   int& introduced_errors);
    
    const std::vector<bool>& getStolenBits() const;
    const std::vector<Basis>& getMeasurementBases() const;
    
    void setAttackType(AttackType type);
    void setEavesdroppingStrength(double strength);
    
private:
    Config config_;
    AttackType attack_type_;
    double eavesdropping_strength_;
    std::vector<bool> stolen_bits_;
    std::vector<Basis> measurement_bases_;
    PhotonDetector detector_;
    PhotonSource photon_source_;
    
    Basis generateRandomBasis();
    Photon generateReplacementPhoton(bool bit, Basis basis);
};

} // namespace bb84

#endif
