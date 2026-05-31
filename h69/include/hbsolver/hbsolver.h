#ifndef HBSOLVER_HBSOLVER_H
#define HBSOLVER_HBSOLVER_H

#include "hbsolver/types.h"
#include "hbsolver/nonlinear.h"
#include "hbsolver/circuit.h"
#include "hbsolver/fft.h"
#include "hbsolver/matrix.h"
#include "hbsolver/memory.h"
#include <memory>
#include <vector>

namespace hbsolver {

class HarmonicBalanceSolver {
public:
    HarmonicBalanceSolver();
    ~HarmonicBalanceSolver() = default;

    void setConfig(const HBConfig& config);
    void setNonlinearDevice(std::unique_ptr<NonlinearDevice> device);
    void setCircuitTopology(const CircuitTopology& topology);
    void setTones(const std::vector<Tone>& tones);
    void setSingleTone(double frequency, double amplitude, double phase = 0.0);
    void setTwoTone(double freq1, double freq2, double amplitude1, double amplitude2,
                    double phase1 = 0.0, double phase2 = 0.0);

    void setMemoryEffect(std::shared_ptr<MemoryEffect> memory);
    void enableMemoryEffect(bool enable) { use_memory_effect_ = enable; }
    bool hasMemoryEffect() const { return use_memory_effect_; }

    void setLoadImpedance(Complex z);
    void setSourceImpedance(Complex z);
    Complex getLoadImpedance() const { return load_impedance_; }
    Complex getSourceImpedance() const { return source_impedance_; }

    HBSolution solve();
    HBSolution solveWithImpedance(Complex z_load, Complex z_source = Complex(50.0, 0.0));

    const HBConfig& getConfig() const { return config_; }
    const std::vector<Tone>& getTones() const { return tones_; }
    const std::vector<FrequencyComponent>& getFrequencyComponents() const { return freq_components_; }
    int getNumFrequencyComponents() const { return num_freq_components_; }

    double getFundamentalFrequency() const;

private:
    HBConfig config_;
    std::unique_ptr<NonlinearDevice> device_;
    CircuitTopology topology_;
    std::vector<Tone> tones_;
    std::shared_ptr<MemoryEffect> memory_;
    bool use_memory_effect_;
    Complex load_impedance_;
    Complex source_impedance_;

    int num_freq_components_;
    int num_time_samples_;
    std::vector<FrequencyComponent> freq_components_;
    RealVec time_samples_;
    ComplexMat freq_to_time_matrix_;
    ComplexMat time_to_freq_matrix_;

    ComplexMat omega_matrix_;

    void buildOmegaMatrix();

    void setupFrequencyGrid();
    void setupTimeGrid();
    void setupTransformMatrices();

    ComplexVec generateSourceSpectrum() const;
    RealVec computeTimeVoltage(const ComplexVec& freq_spectrum) const;
    ComplexVec computeFrequencySpectrum(const RealVec& time_signal) const;
    ComplexVec computeNonlinearCurrent(const ComplexVec& voltage_spectrum) const;
    ComplexMat computeLinearJacobian() const;
    ComplexMat computeNonlinearJacobian(const ComplexVec& voltage_spectrum) const;

    ComplexVec computeResidual(const ComplexVec& voltage_spectrum,
                               const ComplexVec& source_spectrum,
                               const ComplexMat& Y_matrix) const;

    ComplexMat computeJacobian(const ComplexVec& voltage_spectrum,
                               const ComplexMat& Y_matrix) const;

    void buildSpectrum(HBSolution& solution) const;

    double getMaximumFrequency() const;
    double getNyquistFrequency() const;
    int checkAliasing(HBSolution& solution) const;
    ComplexVec applyAntiAliasingFilter(const ComplexVec& spectrum, double cutoff_ratio = 0.75) const;
    RealVec applyTimeDomainWindow(const RealVec& time_signal) const;
};

}

#endif
