#ifndef HBSOLVER_MEMORY_H
#define HBSOLVER_MEMORY_H

#include "hbsolver/types.h"
#include <vector>
#include <memory>

namespace hbsolver {

class MemoryEffect {
public:
    MemoryEffect();
    virtual ~MemoryEffect() = default;

    void setConfig(const MemoryEffectConfig& config);
    const MemoryEffectConfig& getConfig() const { return config_; }

    void enableNonlinearCapacitor(bool enable) { config_.has_nl_capacitor = enable; }
    void enableNonlinearInductor(bool enable) { config_.has_nl_inductor = enable; }

    void setNonlinearCapacitor(const NonlinearCapacitorModel& model);
    void setNonlinearInductor(const NonlinearInductorModel& model);

    void setAbruptJunctionCapacitor(double cj0, double vj, double m);
    void setSaturatingInductor(double l0, double alpha, double i_sat);

    RealVec computeCharge(const RealVec& voltage) const;
    RealVec computeFlux(const RealVec& current) const;

    RealVec computeDisplacementCurrent(const RealVec& voltage, double dt) const;
    RealVec computeInducedVoltage(const RealVec& current, double dt) const;

    RealVec computeCapacitance(const RealVec& voltage) const;
    RealVec computeInductance(const RealVec& current) const;

    ComplexVec computeChargeSpectrum(const ComplexVec& voltage_spectrum) const;
    ComplexVec computeFluxSpectrum(const ComplexVec& current_spectrum) const;

    ComplexMat computeChargeJacobian(const ComplexVec& voltage_spectrum,
                                      const ComplexMat& freq_to_time,
                                      const ComplexMat& time_to_freq) const;

    ComplexMat computeFluxJacobian(const ComplexVec& current_spectrum,
                                    const ComplexMat& freq_to_time,
                                    const ComplexMat& time_to_freq) const;

    static NonlinearCapacitorModel createDefaultVaractor();
    static NonlinearInductorModel createDefaultSaturatingInductor();

private:
    MemoryEffectConfig config_;

    RealVec centralDifference(const RealVec& x, double dt) const;
    RealVec trapezoidalIntegration(const RealVec& f, double dt, double initial = 0.0) const;
};

}

#endif
