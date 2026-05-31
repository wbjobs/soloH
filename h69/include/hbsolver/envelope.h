#ifndef HBSOLVER_ENVELOPE_H
#define HBSOLVER_ENVELOPE_H

#include "hbsolver/types.h"
#include "hbsolver/hbsolver.h"
#include "hbsolver/fft.h"
#include <vector>
#include <complex>
#include <functional>
#include <memory>

namespace hbsolver {

enum class ModulationType {
    QPSK,
    QAM16,
    QAM64,
    OFDM,
    CW,
    TwoTone,
    Custom
};

struct ModulationConfig {
    ModulationType type = ModulationType::QPSK;
    double carrier_freq = 1e9;
    double symbol_rate = 1e6;
    int num_symbols = 1024;
    double rolloff = 0.35;
    int oversampling = 8;
    double peak_power_dBm = 0.0;
    double papr_dB = 6.0;
    int seed = 42;
};

class EnvelopeSimulator {
public:
    EnvelopeSimulator(HarmonicBalanceSolver& solver);
    ~EnvelopeSimulator() = default;

    void setModulationConfig(const ModulationConfig& config);
    const ModulationConfig& getModulationConfig() const { return config_; }

    EnvelopeSignal generateInputSignal();
    EnvelopeSolution runEnvelopeSimulation();

    AMAMPMCharacteristics runDynamicAmAmPm(int num_power_levels = 21);

    static EnvelopeSignal generateQPSKSignal(const ModulationConfig& config);
    static EnvelopeSignal generateQAMSignal(const ModulationConfig& config, int order);
    static EnvelopeSignal generateOFDMSSignal(const ModulationConfig& config);
    static EnvelopeSignal generateTwoToneEnvelope(const ModulationConfig& config);

    static std::vector<Complex> generatePulseShapingFilter(
        int num_taps, double rolloff, double sps);

    EnvelopeSolution slowEnvelopeTracking(const EnvelopeSignal& input_env,
                                           int hb_steps_per_symbol = 4);

    double computeEVM(const EnvelopeSignal& reference,
                      const EnvelopeSignal& distorted);

    double computeACPR(const EnvelopeSignal& signal,
                        double channel_bandwidth,
                        double adjacent_offset);

    double computeNPR(const EnvelopeSignal& signal,
                      double notch_bandwidth,
                      double notch_offset);

    RealVec computeCCDF(const RealVec& amplitude, int num_bins = 100);

private:
    HarmonicBalanceSolver& solver_;
    ModulationConfig config_;

    double dBmToVoltage(double power_dBm, double impedance = 50.0);
    double voltageTodBm(double v_peak, double impedance = 50.0);

    std::vector<Complex> generateRandomSymbols(int num_symbols, int order);
    EnvelopeSignal upsampleAndFilter(const std::vector<Complex>& symbols,
                                      const ModulationConfig& config);

    void computeInstantaneousFrequency(EnvelopeSignal& signal);

    Complex nonlinearMapping(Complex input_envelope, double carrier_power);
};

}

#endif
