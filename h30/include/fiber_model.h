#ifndef BB84_FIBER_MODEL_H
#define BB84_FIBER_MODEL_H

#include "types.h"
#include <complex>
#include <vector>

namespace bb84 {

class FiberModel {
public:
    explicit FiberModel(const FiberParameters& params);
    
    FiberEffectResult propagatePhoton(Photon& photon);
    std::vector<Photon> propagatePhotons(std::vector<Photon>& photons,
                                          FiberEffectResult& avg_effects);
    
    double calculateAttenuation() const;
    double calculateDispersion(double frequency) const;
    double calculatePulseBroadening() const;
    double calculateNonlinearPhaseShift(double intensity) const;
    double calculatePMD() const;
    double calculatePolarizationRotation() const;
    double calculateFiberInducedQBER() const;
    
    double getLossProbability() const;
    
    void updateParameters(const FiberParameters& params);
    const FiberParameters& getParameters() const;
    
    static double dbToLinear(double db);
    static double linearToDb(double linear);
    
private:
    FiberParameters params_;
    double speed_of_light_;
    
    double calculateGroupVelocityDispersion() const;
    double calculateChromaticDispersion(double wavelength) const;
    double calculateFourWaveMixing(double intensity) const;
    double calculateSPMEffect(double intensity) const;
    double calculatePolarizationModeCoupling() const;
    
    std::complex<double> applyDispersionOperator(std::complex<double> field, 
                                                 double frequency) const;
    std::complex<double> applyNonlinearOperator(std::complex<double> field,
                                                double intensity) const;
};

class FiberGainMedium {
public:
    FiberGainMedium(double gain_db, double noise_figure);
    
    void applyAmplification(std::vector<Photon>& photons,
                            double& added_noise_photons);
    
private:
    double gain_db_;
    double noise_figure_;
    double gain_linear_;
};

} // namespace bb84

#endif
