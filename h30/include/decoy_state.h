#ifndef BB84_DECOY_STATE_H
#define BB84_DECOY_STATE_H

#include "types.h"
#include "config.h"
#include <vector>

namespace bb84 {

class DecoyStateProtocol {
public:
    DecoyStateProtocol();
    explicit DecoyStateProtocol(const std::vector<DecoySetting>& settings);
    
    static std::vector<DecoySetting> createStandardDecoys(
        double signal_intensity = 0.5,
        double decoy1_intensity = 0.2,
        double decoy2_intensity = 0.05,
        double vacuum_prob = 0.05
    );
    
    DecoyStateType chooseDecoyType(double& chosen_intensity);
    
    std::vector<Photon> generatePhotonsWithDecoys(
        const std::vector<bool>& bits,
        const std::vector<Basis>& bases
    );
    
    DecoyResult analyzeDecoyData(
        const std::vector<Photon>& transmitted_photons,
        const std::vector<bool>& detected,
        const std::vector<Basis>& alice_bases,
        const std::vector<Basis>& bob_bases
    );
    
    double estimateSinglePhotonCount(
        double signal_yield, 
        double decoy_yield,
        double signal_intensity,
        double decoy_intensity
    );
    
    double estimateSinglePhotonError(
        double signal_error,
        double decoy_error,
        double signal_intensity,
        double decoy_intensity,
        double vacuum_yield
    );
    
    void estimatePhotonNumberDistribution(
        double intensity,
        double distribution[5]
    );
    
    double calculateSecureKeyRate(
        double sifted_key_rate,
        double single_photon_fraction,
        double single_photon_error,
        double leakage_fraction = 0.0
    );
    
    void setSettings(const std::vector<DecoySetting>& settings);
    const std::vector<DecoySetting>& getSettings() const;
    
    bool isEnabled() const;
    
private:
    std::vector<DecoySetting> settings_;
    bool enabled_;
    
    double poissonProbability(double lambda, int n);
    double calculateYield(int n, double eta, double p_dark);
    double calculateErrorRate(int n, double eta, double p_dark, double e_opt);
    
    double invertPoissonConstraint(
        double observed_yield,
        double intensity,
        double eta0,
        double p_dark
    );
};

} // namespace bb84

#endif
