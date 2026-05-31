#include "hbsolver/loadpull.h"
#include "hbsolver/analysis.h"
#include <iostream>
#include <iomanip>
#include <cmath>
#include <algorithm>
#include <complex>

namespace hbsolver {

LoadPullAnalysis::LoadPullAnalysis(HarmonicBalanceSolver& solver)
    : solver_(solver), frequency_(1e9), input_power_dBm_(0.0),
      r_min_(10.0), r_max_(200.0), r_points_(11),
      x_min_(-100.0), x_max_(100.0), x_points_(11),
      gamma_max_(0.9), theta_points_(37), mag_points_(11) {
}

double LoadPullAnalysis::dBmToVoltage(double power_dBm, double impedance) {
    double power_watts = std::pow(10.0, power_dBm / 10.0) / 1000.0;
    return std::sqrt(2.0 * impedance * power_watts);
}

double LoadPullAnalysis::voltageTodBm(double v_peak, double impedance) {
    double power = (v_peak * v_peak) / (2.0 * impedance);
    return 10.0 * std::log10(power * 1000.0);
}

Complex LoadPullAnalysis::gammaToZ(Complex gamma, double z0) {
    return z0 * (1.0 + gamma) / (1.0 - gamma);
}

Complex LoadPullAnalysis::zToGamma(Complex z, double z0) {
    return (z - z0) / (z + z0);
}

void LoadPullAnalysis::setImpedanceRange(double r_min, double r_max, int r_points,
                                          double x_min, double x_max, int x_points) {
    r_min_ = r_min;
    r_max_ = r_max;
    r_points_ = r_points;
    x_min_ = x_min;
    x_max_ = x_max;
    x_points_ = x_points;
}

void LoadPullAnalysis::setGammaRange(double gamma_max, int theta_points, int mag_points) {
    gamma_max_ = gamma_max;
    theta_points_ = theta_points;
    mag_points_ = mag_points;
}

std::vector<LoadPullResult> LoadPullAnalysis::runLoadPull() {
    load_results_.clear();

    double amplitude = dBmToVoltage(input_power_dBm_, 50.0);
    solver_.setSingleTone(frequency_, amplitude);

    int total_points = mag_points_ * theta_points_;
    int current = 0;

    for (int m = 0; m < mag_points_; ++m) {
        double gamma_mag = gamma_max_ * m / (mag_points_ - 1);
        for (int t = 0; t < theta_points_; ++t) {
            double theta = 2.0 * PI * t / (theta_points_ - 1);
            Complex gamma(gamma_mag * std::cos(theta), gamma_mag * std::sin(theta));
            Complex z_load = gammaToZ(gamma, 50.0);

            current++;
            if (solver_.getConfig().verbose && current % 50 == 0) {
                std::cout << "Load pull progress: " << current << "/" << total_points << std::endl;
            }

            HBSolution solution = solver_.solveWithImpedance(z_load);
            PowerMetrics metrics = SpectrumAnalyzer::extractPowerMetrics(
                solution, solver_.getTones(), 50.0);

            LoadPullResult result;
            result.load_impedance = z_load;
            result.output_power = metrics.fundamental_power;
            result.gain = metrics.fundamental_power - input_power_dBm_;
            result.efficiency = 0.0;
            result.pae = 0.0;
            result.im3 = metrics.im3_power - metrics.fundamental_power;
            result.is_stable = solution.converged && solution.residual_norm < 1e-3;

            load_results_.push_back(result);
        }
    }

    return load_results_;
}

std::vector<SourcePullResult> LoadPullAnalysis::runSourcePull() {
    source_results_.clear();

    int total_points = mag_points_ * theta_points_;
    int current = 0;

    for (int m = 0; m < mag_points_; ++m) {
        double gamma_mag = gamma_max_ * m / (mag_points_ - 1);
        for (int t = 0; t < theta_points_; ++t) {
            double theta = 2.0 * PI * t / (theta_points_ - 1);
            Complex gamma(gamma_mag * std::cos(theta), gamma_mag * std::sin(theta));
            Complex z_source = gammaToZ(gamma, 50.0);

            current++;
            if (solver_.getConfig().verbose && current % 50 == 0) {
                std::cout << "Source pull progress: " << current << "/" << total_points << std::endl;
            }

            double amplitude = dBmToVoltage(input_power_dBm_, 50.0);
            solver_.setSingleTone(frequency_, amplitude);

            HBSolution solution = solver_.solveWithImpedance(Complex(50.0, 0.0), z_source);
            PowerMetrics metrics = SpectrumAnalyzer::extractPowerMetrics(
                solution, solver_.getTones(), 50.0);

            SourcePullResult result;
            result.source_impedance = z_source;
            result.gain = metrics.fundamental_power - input_power_dBm_;
            result.noise_figure = 0.0;
            result.output_power = metrics.fundamental_power;
            result.is_stable = solution.converged && solution.residual_norm < 1e-3;

            source_results_.push_back(result);
        }
    }

    return source_results_;
}

LoadPullResult LoadPullAnalysis::findOptimumLoad() {
    if (load_results_.empty()) {
        runLoadPull();
    }

    LoadPullResult best = load_results_[0];
    for (const auto& result : load_results_) {
        if (result.is_stable && result.output_power > best.output_power) {
            best = result;
        }
    }
    return best;
}

SourcePullResult LoadPullAnalysis::findOptimumSource() {
    if (source_results_.empty()) {
        runSourcePull();
    }

    SourcePullResult best = source_results_[0];
    for (const auto& result : source_results_) {
        if (result.is_stable && result.gain > best.gain) {
            best = result;
        }
    }
    return best;
}

std::vector<ContourPoint> LoadPullAnalysis::extractContourPoints(
    const std::vector<LoadPullResult>& results,
    std::function<double(const LoadPullResult&)> valueFunc,
    double target, double tolerance) {

    std::vector<ContourPoint> points;

    for (size_t i = 0; i < results.size(); ++i) {
        if (!results[i].is_stable) continue;

        double value = valueFunc(results[i]);
        if (std::abs(value - target) <= tolerance) {
            ContourPoint cp;
            cp.impedance = results[i].load_impedance;
            cp.value = value;
            points.push_back(cp);
        }
    }

    return points;
}

ImpedanceContour LoadPullAnalysis::computePowerContour(double target_power_dBm, double tolerance) {
    if (load_results_.empty()) {
        runLoadPull();
    }

    ImpedanceContour contour;
    contour.name = "Power_" + std::to_string(target_power_dBm) + "dBm";
    contour.target_value = target_power_dBm;
    contour.center_frequency = frequency_;

    contour.points = extractContourPoints(
        load_results_,
        [](const LoadPullResult& r) { return r.output_power; },
        target_power_dBm, tolerance);

    return contour;
}

ImpedanceContour LoadPullAnalysis::computeGainContour(double target_gain_dB, double tolerance) {
    if (load_results_.empty()) {
        runLoadPull();
    }

    ImpedanceContour contour;
    contour.name = "Gain_" + std::to_string(target_gain_dB) + "dB";
    contour.target_value = target_gain_dB;
    contour.center_frequency = frequency_;

    contour.points = extractContourPoints(
        load_results_,
        [](const LoadPullResult& r) { return r.gain; },
        target_gain_dB, tolerance);

    return contour;
}

ImpedanceContour LoadPullAnalysis::computeEfficiencyContour(double target_eff, double tolerance) {
    if (load_results_.empty()) {
        runLoadPull();
    }

    ImpedanceContour contour;
    contour.name = "Efficiency_" + std::to_string(target_eff * 100) + "%";
    contour.target_value = target_eff;
    contour.center_frequency = frequency_;

    contour.points = extractContourPoints(
        load_results_,
        [](const LoadPullResult& r) { return r.efficiency; },
        target_eff, tolerance);

    return contour;
}

ImpedanceContour LoadPullAnalysis::computeIM3Contour(double target_im3_dBc, double tolerance) {
    if (load_results_.empty()) {
        runLoadPull();
    }

    ImpedanceContour contour;
    contour.name = "IM3_" + std::to_string(target_im3_dBc) + "dBc";
    contour.target_value = target_im3_dBc;
    contour.center_frequency = frequency_;

    contour.points = extractContourPoints(
        load_results_,
        [](const LoadPullResult& r) { return r.im3; },
        target_im3_dBc, tolerance);

    return contour;
}

std::vector<ImpedanceContour> LoadPullAnalysis::loadPullContours(
    const std::vector<double>& power_levels) {

    if (load_results_.empty()) {
        runLoadPull();
    }

    std::vector<ImpedanceContour> contours;
    for (double power : power_levels) {
        contours.push_back(computePowerContour(power));
    }
    return contours;
}

std::vector<ImpedanceContour> LoadPullAnalysis::sourcePullContours(
    const std::vector<double>& gain_levels) {

    if (source_results_.empty()) {
        runSourcePull();
    }

    std::vector<ImpedanceContour> contours;
    for (double gain : gain_levels) {
        ImpedanceContour contour;
        contour.name = "Gain_" + std::to_string(gain) + "dB";
        contour.target_value = gain;
        contour.center_frequency = frequency_;

        for (const auto& result : source_results_) {
            if (result.is_stable && std::abs(result.gain - gain) <= 0.5) {
                ContourPoint cp;
                cp.impedance = result.source_impedance;
                cp.value = result.gain;
                contour.points.push_back(cp);
            }
        }
        contours.push_back(contour);
    }
    return contours;
}

bool LoadPullAnalysis::checkStability(Complex z_load, Complex z_source, double f,
                                      Complex s11, Complex s22, Complex s12, Complex s21) {
    Complex gamma_s = (z_source - 50.0) / (z_source + 50.0);
    Complex gamma_l = (z_load - 50.0) / (z_load + 50.0);

    Complex delta = s11 * s22 - s12 * s21;
    double k = (1.0 - std::norm(s11) - std::norm(s22) + std::norm(delta)) /
               (2.0 * std::abs(s12 * s21));

    if (k < 1.0) return false;

    double b1 = 1.0 + std::norm(s11) - std::norm(s22) - std::norm(delta);
    double b2 = 1.0 + std::norm(s22) - std::norm(s11) - std::norm(delta);

    if (b1 > 0 && b2 > 0) return true;
    return false;
}

AMAMPAnalysis::AMAMPAnalysis(HarmonicBalanceSolver& solver)
    : solver_(solver) {
}

double AMAMPAnalysis::dBmToVoltage(double power_dBm, double impedance) {
    double power_watts = std::pow(10.0, power_dBm / 10.0) / 1000.0;
    return std::sqrt(2.0 * impedance * power_watts);
}

AMAMPMCharacteristics AMAMPAnalysis::runAmAmPm(double power_start_dBm, double power_end_dBm,
                                                int num_points, double frequency) {
    AMAMPMCharacteristics characteristics;
    characteristics.p1dB = 0.0;
    characteristics.sat_power = -200.0;
    characteristics.linear_gain = 0.0;
    characteristics.pm1dB = 0.0;

    std::vector<double> input_powers, output_powers, phase_shifts;

    for (int i = 0; i < num_points; ++i) {
        double pin = power_start_dBm + (power_end_dBm - power_start_dBm) * i / (num_points - 1);
        double amplitude = dBmToVoltage(pin, 50.0);

        solver_.setSingleTone(frequency, amplitude);
        HBSolution solution = solver_.solve();

        double pout = -200.0;
        double phase = 0.0;
        for (const auto& line : solution.spectrum) {
            if (std::abs(line.frequency - frequency) < 1e6) {
                pout = line.power_dBm;
                phase = std::arg(line.amplitude);
                break;
            }
        }

        AMAMPMPoint point;
        point.input_power = pin;
        point.output_power = pout;
        point.phase_shift = phase;
        point.gain_compression = pout - pin - characteristics.linear_gain;
        characteristics.points.push_back(point);

        input_powers.push_back(pin);
        output_powers.push_back(pout);
        phase_shifts.push_back(phase);

        if (i >= 2 && characteristics.linear_gain == 0.0) {
            double slope = (output_powers[i] - output_powers[0]) / (input_powers[i] - input_powers[0]);
            if (std::abs(slope - 1.0) < 0.1) {
                characteristics.linear_gain = output_powers[0] - input_powers[0];
            }
        }

        if (i > 0 && characteristics.p1dB == 0.0) {
            double ideal_gain = characteristics.linear_gain + 1.0;
            if ((pout - pin) < characteristics.linear_gain - 1.0) {
                characteristics.p1dB = pin;
                characteristics.pm1dB = phase;
            }
        }

        if (pout > characteristics.sat_power) {
            characteristics.sat_power = pout;
        }
    }

    if (characteristics.linear_gain == 0.0 && !characteristics.points.empty()) {
        characteristics.linear_gain = characteristics.points[1].output_power -
                                     characteristics.points[1].input_power;
    }

    for (auto& point : characteristics.points) {
        point.gain_compression = (point.output_power - point.input_power) - characteristics.linear_gain;
    }

    return characteristics;
}

std::vector<double> AMAMPAnalysis::computeEVM(const EnvelopeSolution& env) {
    std::vector<double> evm_per_symbol;

    const auto& in_amp = env.input_envelope.amplitude;
    const auto& out_amp = env.output_envelope.amplitude;
    const auto& in_phase = env.input_envelope.phase;
    const auto& out_phase = env.output_envelope.phase;

    if (in_amp.size() != out_amp.size() || in_amp.empty()) return evm_per_symbol;

    double max_amp = 0.0;
    for (double a : in_amp) max_amp = std::max(max_amp, a);

    double sum_error = 0.0;
    for (size_t i = 0; i < in_amp.size(); ++i) {
        Complex in_sym(in_amp[i] * std::cos(in_phase[i]), in_amp[i] * std::sin(in_phase[i]));
        Complex out_sym(out_amp[i] * std::cos(out_phase[i]), out_amp[i] * std::sin(out_phase[i]));
        double error = std::abs(out_sym - in_sym) / max_amp;
        evm_per_symbol.push_back(error * 100.0);
        sum_error += error * error;
    }

    return evm_per_symbol;
}

double AMAMPAnalysis::computeACPR(const EnvelopeSolution& env,
                                   double bandwidth, double adjacent_offset) {
    double total_power = 0.0;
    double adjacent_power = 0.0;

    const auto& time = env.output_envelope.time;
    const auto& amp = env.output_envelope.amplitude;

    if (time.empty() || amp.empty()) return -60.0;

    int N = static_cast<int>(time.size());
    double dt = time[1] - time[0];

    ComplexVec signal(N);
    for (int i = 0; i < N; ++i) {
        signal[i] = Complex(amp[i] * std::cos(env.output_envelope.phase[i]),
                           amp[i] * std::sin(env.output_envelope.phase[i]));
    }

    ComplexVec spectrum = signal;
    FFT::transform(spectrum, false);

    double df = 1.0 / (N * dt);
    int main_band_low = static_cast<int>((-bandwidth / 2.0) / df) + N / 2;
    int main_band_high = static_cast<int>((bandwidth / 2.0) / df) + N / 2;
    int adj_low_low = static_cast<int>((adjacent_offset - bandwidth / 2.0) / df) + N / 2;
    int adj_low_high = static_cast<int>((adjacent_offset + bandwidth / 2.0) / df) + N / 2;
    int adj_high_low = static_cast<int>((-adjacent_offset - bandwidth / 2.0) / df) + N / 2;
    int adj_high_high = static_cast<int>((-adjacent_offset + bandwidth / 2.0) / df) + N / 2;

    for (int i = 0; i < N; ++i) {
        double power = std::norm(spectrum[i]);
        if (i >= main_band_low && i <= main_band_high) {
            total_power += power;
        }
        if ((i >= adj_low_low && i <= adj_low_high) ||
            (i >= adj_high_low && i <= adj_high_high)) {
            adjacent_power += power;
        }
    }

    if (total_power < 1e-20) return -60.0;
    return 10.0 * std::log10(adjacent_power / total_power);
}

}
