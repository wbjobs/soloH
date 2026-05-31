#ifndef HBSOLVER_LOADPULL_H
#define HBSOLVER_LOADPULL_H

#include "hbsolver/types.h"
#include "hbsolver/hbsolver.h"
#include <vector>
#include <memory>
#include <functional>

namespace hbsolver {

class LoadPullAnalysis {
public:
    LoadPullAnalysis(HarmonicBalanceSolver& solver);
    ~LoadPullAnalysis() = default;

    void setFrequency(double frequency) { frequency_ = frequency; }
    void setInputPower(double power_dBm) { input_power_dBm_ = power_dBm; }
    void setImpedanceRange(double r_min, double r_max, int r_points,
                           double x_min, double x_max, int x_points);
    void setGammaRange(double gamma_max, int theta_points, int mag_points);

    std::vector<LoadPullResult> runLoadPull();
    std::vector<SourcePullResult> runSourcePull();

    LoadPullResult findOptimumLoad();
    SourcePullResult findOptimumSource();

    ImpedanceContour computePowerContour(double target_power_dBm, double tolerance = 0.5);
    ImpedanceContour computeGainContour(double target_gain_dB, double tolerance = 0.2);
    ImpedanceContour computeEfficiencyContour(double target_eff, double tolerance = 0.02);
    ImpedanceContour computeIM3Contour(double target_im3_dBc, double tolerance = 1.0);

    std::vector<ImpedanceContour> loadPullContours(const std::vector<double>& power_levels);
    std::vector<ImpedanceContour> sourcePullContours(const std::vector<double>& gain_levels);

    static bool checkStability(Complex z_load, Complex z_source, double f,
                                Complex s11, Complex s22, Complex s12, Complex s21);

    const std::vector<LoadPullResult>& getLoadResults() const { return load_results_; }
    const std::vector<SourcePullResult>& getSourceResults() const { return source_results_; }

private:
    HarmonicBalanceSolver& solver_;
    double frequency_;
    double input_power_dBm_;

    double r_min_, r_max_;
    int r_points_;
    double x_min_, x_max_;
    int x_points_;

    double gamma_max_;
    int theta_points_;
    int mag_points_;

    std::vector<LoadPullResult> load_results_;
    std::vector<SourcePullResult> source_results_;

    double dBmToVoltage(double power_dBm, double impedance = 50.0);
    double voltageTodBm(double v_peak, double impedance = 50.0);

    Complex gammaToZ(Complex gamma, double z0 = 50.0);
    Complex zToGamma(Complex z, double z0 = 50.0);

    std::vector<ContourPoint> extractContourPoints(
        const std::vector<LoadPullResult>& results,
        std::function<double(const LoadPullResult&)> valueFunc,
        double target, double tolerance);
};

class AMAMPAnalysis {
public:
    AMAMPAnalysis(HarmonicBalanceSolver& solver);
    ~AMAMPAnalysis() = default;

    AMAMPMCharacteristics runAmAmPm(double power_start_dBm, double power_end_dBm,
                                     int num_points, double frequency);

    static std::vector<double> computeEVM(const EnvelopeSolution& env);
    static double computeACPR(const EnvelopeSolution& env,
                              double bandwidth, double adjacent_offset);

private:
    HarmonicBalanceSolver& solver_;

    double dBmToVoltage(double power_dBm, double impedance = 50.0);
};

}

#endif
