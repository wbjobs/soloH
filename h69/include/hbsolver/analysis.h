#ifndef HBSOLVER_ANALYSIS_H
#define HBSOLVER_ANALYSIS_H

#include "hbsolver/types.h"
#include "hbsolver/hbsolver.h"
#include <vector>
#include <string>
#include <functional>

namespace hbsolver {

class SpectrumAnalyzer {
public:
    static PowerMetrics extractPowerMetrics(const HBSolution& solution,
                                            const std::vector<Tone>& tones,
                                            double impedance = 50.0);

    static double findTonePower(const std::vector<SpectrumLine>& spectrum, double frequency,
                                double tolerance = 1e6);
    static double findIntermodPower(const std::vector<SpectrumLine>& spectrum,
                                     double f1, double f2, int order);
    static double findHarmonicPower(const std::vector<SpectrumLine>& spectrum,
                                     double fundamental, int harmonic);

    static double computeP1dB(std::function<HBSolution(double)> solveFunc,
                               double power_start, double power_end, int num_points);
    static double computeIP3(std::function<HBSolution(double)> solveFunc,
                              double power_start, double power_end, int num_points);
};

class SweepAnalysis {
public:
    struct SweepResult {
        double parameter;
        HBSolution solution;
        PowerMetrics metrics;
    };

    struct HysteresisResult {
        std::vector<SweepResult> forward_sweep;
        std::vector<SweepResult> backward_sweep;
        std::vector<double> jump_points;
        bool has_hysteresis;
        double hysteresis_width;
    };

    SweepAnalysis(HarmonicBalanceSolver& solver);

    std::vector<SweepResult> powerSweep(double freq,
                                         double power_start_dBm,
                                         double power_end_dBm,
                                         int num_points,
                                         bool two_tone = false,
                                         double freq2 = 0.0);

    std::vector<SweepResult> frequencySweep(double power_dBm,
                                             double freq_start,
                                             double freq_end,
                                             int num_points,
                                             bool two_tone = false,
                                             double spacing = 1e6);

    HysteresisResult powerSweepWithHysteresis(double freq,
                                               double power_start_dBm,
                                               double power_end_dBm,
                                               int num_points,
                                               double jump_threshold = 0.5,
                                               bool two_tone = false,
                                               double freq2 = 0.0);

    static bool detectJump(const SweepResult& prev, const SweepResult& curr,
                           double threshold_db = 0.5);
    static double computeHysteresisWidth(const HysteresisResult& result);

private:
    HarmonicBalanceSolver& solver_;

    double dBmToVoltage(double power_dBm, double impedance = 50.0);
    HBSolution solveWithInitialGuess(double power_dBm, double freq,
                                     bool two_tone, double freq2,
                                     const ComplexVec& initial_guess);
};

}

#endif
