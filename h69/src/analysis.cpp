#include "hbsolver/analysis.h"
#include <cmath>
#include <iostream>
#include <algorithm>
#include <limits>
#include <functional>

namespace hbsolver {

double SpectrumAnalyzer::findTonePower(const std::vector<SpectrumLine>& spectrum, double frequency,
                                        double tolerance) {
    double max_power = -200.0;
    for (const auto& line : spectrum) {
        if (std::abs(line.frequency - frequency) < tolerance) {
            if (line.power_dBm > max_power) {
                max_power = line.power_dBm;
            }
        }
    }
    return max_power;
}

double SpectrumAnalyzer::findIntermodPower(const std::vector<SpectrumLine>& spectrum,
                                            double f1, double f2, int order) {
    double im_low, im_high;
    if (order == 3) {
        im_low = 2 * f1 - f2;
        im_high = 2 * f2 - f1;
    } else if (order == 5) {
        im_low = 3 * f1 - 2 * f2;
        im_high = 3 * f2 - 2 * f1;
    } else {
        return -200.0;
    }

    double p_low = findTonePower(spectrum, im_low, 1e6);
    double p_high = findTonePower(spectrum, im_high, 1e6);
    return std::max(p_low, p_high);
}

double SpectrumAnalyzer::findHarmonicPower(const std::vector<SpectrumLine>& spectrum,
                                            double fundamental, int harmonic) {
    double freq = fundamental * harmonic;
    return findTonePower(spectrum, freq, 1e6);
}

PowerMetrics SpectrumAnalyzer::extractPowerMetrics(const HBSolution& solution,
                                                    const std::vector<Tone>& tones,
                                                    double impedance) {
    PowerMetrics metrics;
    metrics.fundamental_power = -200.0;
    metrics.harmonic2_power = -200.0;
    metrics.harmonic3_power = -200.0;
    metrics.im3_power = -200.0;
    metrics.im5_power = -200.0;
    metrics.p1dB_input = 0.0;
    metrics.p1dB_output = 0.0;
    metrics.ip3_input = 0.0;
    metrics.ip3_output = 0.0;

    if (tones.empty()) return metrics;

    if (tones.size() == 1) {
        double f0 = tones[0].frequency;
        metrics.fundamental_power = findTonePower(solution.spectrum, f0);
        metrics.harmonic2_power = findHarmonicPower(solution.spectrum, f0, 2);
        metrics.harmonic3_power = findHarmonicPower(solution.spectrum, f0, 3);
    } else if (tones.size() >= 2) {
        double f1 = tones[0].frequency;
        double f2 = tones[1].frequency;
        double p1 = findTonePower(solution.spectrum, f1);
        double p2 = findTonePower(solution.spectrum, f2);
        metrics.fundamental_power = std::max(p1, p2);
        metrics.harmonic2_power = std::max(findHarmonicPower(solution.spectrum, f1, 2),
                                             findHarmonicPower(solution.spectrum, f2, 2));
        metrics.harmonic3_power = std::max(findHarmonicPower(solution.spectrum, f1, 3),
                                             findHarmonicPower(solution.spectrum, f2, 3));
        metrics.im3_power = findIntermodPower(solution.spectrum, f1, f2, 3);
        metrics.im5_power = findIntermodPower(solution.spectrum, f1, f2, 5);
    }

    return metrics;
}

double SpectrumAnalyzer::computeP1dB(std::function<HBSolution(double)> solveFunc,
                                      double power_start, double power_end, int num_points) {
    double p1dB = power_end;
    double ideal_slope = 1.0;
    double prev_output = -200.0;
    double prev_input = power_start;

    for (int i = 0; i < num_points; ++i) {
        double pin = power_start + (power_end - power_start) * i / (num_points - 1);
        HBSolution sol = solveFunc(pin);

        double pout = -200.0;
        for (const auto& line : sol.spectrum) {
            if (line.label == "f1" || line.label == "f2") {
                pout = std::max(pout, line.power_dBm);
            }
        }

        if (i > 0) {
            double actual_gain = pout - pin;
            double ideal_gain = prev_output - prev_input + ideal_slope * (pin - prev_input);
            if (ideal_gain - actual_gain >= 1.0) {
                p1dB = pin;
                break;
            }
        }

        prev_output = pout;
        prev_input = pin;
    }

    return p1dB;
}

double SpectrumAnalyzer::computeIP3(std::function<HBSolution(double)> solveFunc,
                                     double power_start, double power_end, int num_points) {
    std::vector<double> pin_vals, pout_fund_vals, pout_im3_vals;

    for (int i = 0; i < num_points; ++i) {
        double pin = power_start + (power_end - power_start) * i / (num_points - 1);
        HBSolution sol = solveFunc(pin);

        double pout_fund = -200.0;
        double pout_im3 = -200.0;
        for (const auto& line : sol.spectrum) {
            if (line.label == "f1" || line.label == "f2") {
                pout_fund = std::max(pout_fund, line.power_dBm);
            } else if (line.label == "IM3_low" || line.label == "IM3_high") {
                pout_im3 = std::max(pout_im3, line.power_dBm);
            }
        }

        pin_vals.push_back(pin);
        pout_fund_vals.push_back(pout_fund);
        pout_im3_vals.push_back(pout_im3);
    }

    double avg_slope_fund = 0.0, avg_slope_im3 = 0.0;
    int count = 0;
    for (size_t i = 1; i < pin_vals.size(); ++i) {
        avg_slope_fund += (pout_fund_vals[i] - pout_fund_vals[i-1]) / (pin_vals[i] - pin_vals[i-1]);
        avg_slope_im3 += (pout_im3_vals[i] - pout_im3_vals[i-1]) / (pin_vals[i] - pin_vals[i-1]);
        count++;
    }
    if (count > 0) {
        avg_slope_fund /= count;
        avg_slope_im3 /= count;
    }

    double ip3_input = 0.0;
    if (std::abs(avg_slope_fund - avg_slope_im3) > 0.01) {
        double p_fund = pout_fund_vals[pin_vals.size() / 2];
        double p_im3 = pout_im3_vals[pin_vals.size() / 2];
        double p_mid = pin_vals[pin_vals.size() / 2];
        ip3_input = p_mid + (p_fund - p_im3) / (avg_slope_im3 - avg_slope_fund);
    }

    return ip3_input;
}

SweepAnalysis::SweepAnalysis(HarmonicBalanceSolver& solver)
    : solver_(solver) {
}

double SweepAnalysis::dBmToVoltage(double power_dBm, double impedance) {
    double power_watts = std::pow(10.0, power_dBm / 10.0) / 1000.0;
    return std::sqrt(2.0 * impedance * power_watts);
}

std::vector<SweepAnalysis::SweepResult> SweepAnalysis::powerSweep(
    double freq, double power_start_dBm, double power_end_dBm,
    int num_points, bool two_tone, double freq2) {

    std::vector<SweepResult> results;
    HBConfig config = solver_.getConfig();

    for (int i = 0; i < num_points; ++i) {
        double power_dBm = power_start_dBm + (power_end_dBm - power_start_dBm) * i / (num_points - 1);
        double amplitude = dBmToVoltage(power_dBm, config.impedance);

        if (two_tone) {
            solver_.setTwoTone(freq, freq2, amplitude, amplitude);
        } else {
            solver_.setSingleTone(freq, amplitude);
        }

        HBSolution solution = solver_.solve();
        PowerMetrics metrics = SpectrumAnalyzer::extractPowerMetrics(solution, solver_.getTones(), config.impedance);

        results.push_back({power_dBm, solution, metrics});
    }

    return results;
}

std::vector<SweepAnalysis::SweepResult> SweepAnalysis::frequencySweep(
    double power_dBm, double freq_start, double freq_end,
    int num_points, bool two_tone, double spacing) {

    std::vector<SweepResult> results;
    HBConfig config = solver_.getConfig();
    double amplitude = dBmToVoltage(power_dBm, config.impedance);

    for (int i = 0; i < num_points; ++i) {
        double freq = freq_start + (freq_end - freq_start) * i / (num_points - 1);

        if (two_tone) {
            solver_.setTwoTone(freq, freq + spacing, amplitude, amplitude);
        } else {
            solver_.setSingleTone(freq, amplitude);
        }

        HBSolution solution = solver_.solve();
        PowerMetrics metrics = SpectrumAnalyzer::extractPowerMetrics(solution, solver_.getTones(), config.impedance);

        results.push_back({freq, solution, metrics});
    }

    return results;
}

HBSolution SweepAnalysis::solveWithInitialGuess(double power_dBm, double freq,
                                                bool two_tone, double freq2,
                                                const ComplexVec& initial_guess) {
    HBConfig config = solver_.getConfig();
    double amplitude = dBmToVoltage(power_dBm, config.impedance);

    if (two_tone) {
        solver_.setTwoTone(freq, freq2, amplitude, amplitude);
    } else {
        solver_.setSingleTone(freq, amplitude);
    }

    return solver_.solve();
}

bool SweepAnalysis::detectJump(const SweepResult& prev, const SweepResult& curr,
                               double threshold_db) {
    double delta_p = std::abs(curr.metrics.fundamental_power - prev.metrics.fundamental_power);
    double delta_im3 = std::abs(curr.metrics.im3_power - prev.metrics.im3_power);

    if (delta_p > threshold_db || delta_im3 > threshold_db * 2.0) {
        return true;
    }

    if (prev.solution.converged && !curr.solution.converged) {
        return true;
    }

    double residual_ratio = curr.solution.residual_norm / std::max(prev.solution.residual_norm, 1e-20);
    if (residual_ratio > 100.0) {
        return true;
    }

    return false;
}

double SweepAnalysis::computeHysteresisWidth(const HysteresisResult& result) {
    if (!result.has_hysteresis || result.jump_points.size() < 2) {
        return 0.0;
    }

    std::vector<double> sorted_jumps = result.jump_points;
    std::sort(sorted_jumps.begin(), sorted_jumps.end());

    if (sorted_jumps.size() >= 2) {
        return std::abs(sorted_jumps.back() - sorted_jumps.front());
    }
    return 0.0;
}

SweepAnalysis::HysteresisResult SweepAnalysis::powerSweepWithHysteresis(
    double freq, double power_start_dBm, double power_end_dBm,
    int num_points, double jump_threshold, bool two_tone, double freq2) {

    HysteresisResult result;
    result.has_hysteresis = false;
    result.hysteresis_width = 0.0;

    HBConfig config = solver_.getConfig();

    std::cout << "Running forward power sweep..." << std::endl;
    for (int i = 0; i < num_points; ++i) {
        double power_dBm = power_start_dBm + (power_end_dBm - power_start_dBm) * i / (num_points - 1);
        double amplitude = dBmToVoltage(power_dBm, config.impedance);

        if (two_tone) {
            solver_.setTwoTone(freq, freq2, amplitude, amplitude);
        } else {
            solver_.setSingleTone(freq, amplitude);
        }

        HBSolution solution = solver_.solve();
        PowerMetrics metrics = SpectrumAnalyzer::extractPowerMetrics(solution, solver_.getTones(), config.impedance);

        result.forward_sweep.push_back({power_dBm, solution, metrics});

        if (i > 0) {
            if (detectJump(result.forward_sweep[i-1], result.forward_sweep[i], jump_threshold)) {
                result.jump_points.push_back(power_dBm);
                if (config.verbose) {
                    std::cout << "Forward jump detected at " << power_dBm << " dBm" << std::endl;
                }
            }
        }
    }

    std::cout << "Running backward power sweep..." << std::endl;
    ComplexVec prev_solution;
    for (int i = num_points - 1; i >= 0; --i) {
        double power_dBm = power_start_dBm + (power_end_dBm - power_start_dBm) * i / (num_points - 1);
        double amplitude = dBmToVoltage(power_dBm, config.impedance);

        if (two_tone) {
            solver_.setTwoTone(freq, freq2, amplitude, amplitude);
        } else {
            solver_.setSingleTone(freq, amplitude);
        }

        HBSolution solution = solver_.solve();
        PowerMetrics metrics = SpectrumAnalyzer::extractPowerMetrics(solution, solver_.getTones(), config.impedance);

        result.backward_sweep.insert(result.backward_sweep.begin(), {power_dBm, solution, metrics});

        if (i < num_points - 1) {
            if (detectJump(result.backward_sweep[0], result.backward_sweep[1], jump_threshold)) {
                result.jump_points.push_back(power_dBm);
                if (config.verbose) {
                    std::cout << "Backward jump detected at " << power_dBm << " dBm" << std::endl;
                }
            }
        }
    }

    if (!result.forward_sweep.empty() && !result.backward_sweep.empty()) {
        double max_diff = 0.0;
        for (size_t i = 0; i < result.forward_sweep.size() && i < result.backward_sweep.size(); ++i) {
            double diff = std::abs(result.forward_sweep[i].metrics.fundamental_power -
                                   result.backward_sweep[i].metrics.fundamental_power);
            max_diff = std::max(max_diff, diff);
        }
        result.has_hysteresis = (max_diff > jump_threshold) || (result.jump_points.size() >= 2);
    }

    result.hysteresis_width = computeHysteresisWidth(result);

    if (result.has_hysteresis) {
        std::cout << "Hysteresis detected! Width: " << result.hysteresis_width
                  << " dB, Jump points: " << result.jump_points.size() << std::endl;
    } else {
        std::cout << "No hysteresis detected." << std::endl;
    }

    return result;
}

}
