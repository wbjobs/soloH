#include "hbsolver/hbsolver.h"
#include "hbsolver/nonlinear.h"
#include <iostream>
#include <iomanip>
#include <cmath>
#include <algorithm>
#include <set>
#include <sstream>
#include <stdexcept>

namespace hbsolver {

HarmonicBalanceSolver::HarmonicBalanceSolver()
    : device_(nullptr), num_freq_components_(0), num_time_samples_(0),
      use_memory_effect_(false), load_impedance_(50.0, 0.0), source_impedance_(50.0, 0.0) {
    device_ = NonlinearModelFactory::createDefaultDiode();
    memory_ = std::make_shared<MemoryEffect>();
}

void HarmonicBalanceSolver::setConfig(const HBConfig& config) {
    config_ = config;
}

void HarmonicBalanceSolver::setNonlinearDevice(std::unique_ptr<NonlinearDevice> device) {
    device_ = std::move(device);
}

void HarmonicBalanceSolver::setCircuitTopology(const CircuitTopology& topology) {
    topology_ = topology;
}

void HarmonicBalanceSolver::setTones(const std::vector<Tone>& tones) {
    if (tones.empty()) {
        throw std::invalid_argument("At least one tone is required");
    }
    tones_ = tones;
}

void HarmonicBalanceSolver::setMemoryEffect(std::shared_ptr<MemoryEffect> memory) {
    memory_ = memory;
    use_memory_effect_ = true;
}

void HarmonicBalanceSolver::setLoadImpedance(Complex z) {
    load_impedance_ = z;
}

void HarmonicBalanceSolver::setSourceImpedance(Complex z) {
    source_impedance_ = z;
}

HBSolution HarmonicBalanceSolver::solveWithImpedance(Complex z_load, Complex z_source) {
    setLoadImpedance(z_load);
    setSourceImpedance(z_source);
    return solve();
}

void HarmonicBalanceSolver::buildOmegaMatrix() {
    int M = num_freq_components_;
    omega_matrix_ = ComplexMat(M, ComplexVec(M, Complex(0.0, 0.0)));
    for (int f = 0; f < M; ++f) {
        omega_matrix_[f][f] = Complex(0.0, TWO_PI * freq_components_[f].frequency);
    }
}

void HarmonicBalanceSolver::setSingleTone(double frequency, double amplitude, double phase) {
    tones_.clear();
    tones_.push_back({frequency, amplitude, phase});
}

void HarmonicBalanceSolver::setTwoTone(double freq1, double freq2, double amplitude1, double amplitude2,
                                       double phase1, double phase2) {
    tones_.clear();
    tones_.push_back({freq1, amplitude1, phase1});
    tones_.push_back({freq2, amplitude2, phase2});
}

double HarmonicBalanceSolver::getFundamentalFrequency() const {
    if (tones_.empty()) return 0.0;
    return tones_[0].frequency;
}

void HarmonicBalanceSolver::setupFrequencyGrid() {
    if (tones_.empty()) {
        throw std::runtime_error("No excitation tones specified");
    }

    int num_tones = static_cast<int>(tones_.size());
    int num_harmonics = config_.num_harmonics;

    std::set<std::pair<double, std::vector<int>>> freq_set;

    if (num_tones == 1) {
        for (int h = 0; h <= num_harmonics; ++h) {
            double freq = tones_[0].frequency * h;
            std::vector<int> indices = {h};
            freq_set.insert({freq, indices});
        }
    } else if (num_tones == 2) {
        double f1 = tones_[0].frequency;
        double f2 = tones_[1].frequency;
        for (int m = -num_harmonics; m <= num_harmonics; ++m) {
            for (int n = -num_harmonics; n <= num_harmonics; ++n) {
                int order = std::abs(m) + std::abs(n);
                if (order <= num_harmonics && order > 0) {
                    double freq = m * f1 + n * f2;
                    if (freq >= 0) {
                        std::vector<int> indices = {m, n};
                        freq_set.insert({freq, indices});
                    }
                }
            }
        }
        double freq0 = 0.0;
        std::vector<int> indices0 = {0, 0};
        freq_set.insert({freq0, indices0});
    } else {
        throw std::runtime_error("Only 1 or 2 tone excitation supported");
    }

    freq_components_.clear();
    int idx = 0;
    for (const auto& entry : freq_set) {
        FrequencyComponent fc;
        fc.frequency = entry.first;
        fc.harmonic_index = idx;
        fc.tone_index = entry.second.size() > 0 ? entry.second[0] : 0;
        fc.index = idx;
        freq_components_.push_back(fc);
        idx++;
    }

    num_freq_components_ = static_cast<int>(freq_components_.size());
}

void HarmonicBalanceSolver::setupTimeGrid() {
    int num_harmonics = config_.num_harmonics;
    if (config_.num_time_samples > 0) {
        num_time_samples_ = config_.num_time_samples;
    } else {
        int oversample = 4;
        num_time_samples_ = FFT::nextPowerOfTwo(2 * num_harmonics * oversample + 1);
    }

    double fundamental_freq = tones_[0].frequency;
    if (tones_.size() > 1) {
        double f1 = tones_[0].frequency;
        double f2 = tones_[1].frequency;
        fundamental_freq = std::abs(f2 - f1);
    }

    if (fundamental_freq < 1e-9) {
        fundamental_freq = tones_[0].frequency / 100.0;
    }

    double period = 1.0 / fundamental_freq;
    double dt = period / num_time_samples_;

    time_samples_.resize(num_time_samples_);
    for (int i = 0; i < num_time_samples_; ++i) {
        time_samples_[i] = i * dt;
    }
}

void HarmonicBalanceSolver::setupTransformMatrices() {
    int N = num_time_samples_;
    int M = num_freq_components_;

    freq_to_time_matrix_ = ComplexMat(N, ComplexVec(M, Complex(0.0, 0.0)));
    time_to_freq_matrix_ = ComplexMat(M, ComplexVec(N, Complex(0.0, 0.0)));

    for (int t = 0; t < N; ++t) {
        for (int f = 0; f < M; ++f) {
            double omega = TWO_PI * freq_components_[f].frequency;
            double phase = omega * time_samples_[t];
            Complex phasor(std::cos(phase), std::sin(phase));
            freq_to_time_matrix_[t][f] = phasor;
            time_to_freq_matrix_[f][t] = std::conj(phasor) / static_cast<double>(N);
        }
    }
}

ComplexVec HarmonicBalanceSolver::generateSourceSpectrum() const {
    ComplexVec source(num_freq_components_, Complex(0.0, 0.0));

    for (size_t t = 0; t < tones_.size(); ++t) {
        const auto& tone = tones_[t];
        for (int f = 0; f < num_freq_components_; ++f) {
            if (std::abs(freq_components_[f].frequency - tone.frequency) < 1e-6) {
                source[f] = Complex(tone.amplitude * std::cos(tone.phase),
                                    tone.amplitude * std::sin(tone.phase));
                break;
            }
        }
    }

    return source;
}

RealVec HarmonicBalanceSolver::computeTimeVoltage(const ComplexVec& freq_spectrum) const {
    RealVec time_voltage(num_time_samples_, 0.0);

    for (int t = 0; t < num_time_samples_; ++t) {
        Complex sum(0.0, 0.0);
        for (int f = 0; f < num_freq_components_; ++f) {
            sum += freq_to_time_matrix_[t][f] * freq_spectrum[f];
        }
        time_voltage[t] = std::real(sum);
    }

    return time_voltage;
}

ComplexVec HarmonicBalanceSolver::computeFrequencySpectrum(const RealVec& time_signal) const {
    ComplexVec freq_spectrum(num_freq_components_, Complex(0.0, 0.0));

    for (int f = 0; f < num_freq_components_; ++f) {
        Complex sum(0.0, 0.0);
        for (int t = 0; t < num_time_samples_; ++t) {
            sum += time_to_freq_matrix_[f][t] * time_signal[t];
        }
        freq_spectrum[f] = sum;
    }

    return freq_spectrum;
}

ComplexVec HarmonicBalanceSolver::computeNonlinearCurrent(const ComplexVec& voltage_spectrum) const {
    RealVec time_voltage = computeTimeVoltage(voltage_spectrum);

    RealVec time_current(num_time_samples_);
    for (int t = 0; t < num_time_samples_; ++t) {
        time_current[t] = device_->computeCurrent(time_voltage[t]);
    }

    return computeFrequencySpectrum(time_current);
}

ComplexMat HarmonicBalanceSolver::computeLinearJacobian() const {
    int M = num_freq_components_;
    ComplexMat Y(M, ComplexVec(M, Complex(0.0, 0.0)));

    for (int f = 0; f < M; ++f) {
        double freq = freq_components_[f].frequency;
        Complex yl = topology_.getInputAdmittance(freq);
        Complex yr = topology_.getOutputAdmittance(freq);

        Complex zs = source_impedance_;
        Complex zl = load_impedance_;
        if (std::abs(zs) > 1e-15) {
            yl += 1.0 / zs;
        }
        if (std::abs(zl) > 1e-15) {
            yr += 1.0 / zl;
        }

        Y[f][f] = yl + yr;

        if (use_memory_effect_ && memory_) {
            Complex jomega(0.0, TWO_PI * freq);
            if (memory_->getConfig().has_nl_capacitor) {
                double cj0 = memory_->getConfig().nl_cap.cj0;
                Y[f][f] += jomega * cj0;
            }
            if (memory_->getConfig().has_nl_inductor) {
                double l0 = memory_->getConfig().nl_ind.l0;
                if (std::abs(l0) > 1e-15) {
                    Y[f][f] += 1.0 / (jomega * l0);
                }
            }
        }
    }

    return Y;
}

ComplexMat HarmonicBalanceSolver::computeNonlinearJacobian(const ComplexVec& voltage_spectrum) const {
    int M = num_freq_components_;
    int N = num_time_samples_;

    RealVec time_voltage = computeTimeVoltage(voltage_spectrum);

    RealVec time_conductance(N);
    const PiecewiseLinearModel* pwl_model = dynamic_cast<const PiecewiseLinearModel*>(device_.get());

    for (int t = 0; t < N; ++t) {
        double v = time_voltage[t];
        if (pwl_model) {
            time_conductance[t] = pwl_model->computeSmoothedDerivative(v, 7);
        } else {
            time_conductance[t] = device_->computeDerivative(v);
        }
    }

    for (int t = 0; t < N; ++t) {
        if (!std::isfinite(time_conductance[t]) || std::abs(time_conductance[t]) > 1e12) {
            time_conductance[t] = 0.02;
        }
    }

    double min_cond = 1e-12;
    for (int t = 0; t < N; ++t) {
        if (time_conductance[t] > 0 && time_conductance[t] < min_cond) {
            time_conductance[t] = min_cond;
        } else if (time_conductance[t] < 0 && time_conductance[t] > -min_cond) {
            time_conductance[t] = -min_cond;
        }
    }

    ComplexMat G_diag(N, ComplexVec(N, Complex(0.0, 0.0)));
    for (int t = 0; t < N; ++t) {
        G_diag[t][t] = Complex(time_conductance[t], 0.0);
    }

    ComplexMat temp = MatrixOps::multiply(G_diag, freq_to_time_matrix_);
    ComplexMat Yn = MatrixOps::multiply(time_to_freq_matrix_, temp);

    double regularizer = 1e-6;
    for (int m = 0; m < M; ++m) {
        Yn[m][m] += Complex(regularizer, 0.0);
    }

    return Yn;
}

ComplexVec HarmonicBalanceSolver::computeResidual(const ComplexVec& voltage_spectrum,
                                                  const ComplexVec& source_spectrum,
                                                  const ComplexMat& Y_matrix) const {
    ComplexVec I_nl = computeNonlinearCurrent(voltage_spectrum);

    int M = num_freq_components_;
    ComplexVec I_memory(M, Complex(0.0, 0.0));

    if (use_memory_effect_ && memory_) {
        ComplexVec Q = memory_->computeChargeSpectrum(voltage_spectrum);
        ComplexVec Phi = memory_->computeFluxSpectrum(I_nl);

        for (int f = 0; f < M; ++f) {
            Complex jomega(0.0, TWO_PI * freq_components_[f].frequency);
            I_memory[f] = jomega * Q[f];

            if (std::abs(load_impedance_) > Complex(1e-15, 0.0)) {
                I_memory[f] += voltage_spectrum[f] / (jomega * memory_->getConfig().nl_ind.l0);
            }
        }
    }

    ComplexVec YV(M, Complex(0.0, 0.0));
    for (int i = 0; i < M; ++i) {
        YV[i] = Y_matrix[i][i] * voltage_spectrum[i];
    }

    ComplexVec residual = YV + I_nl + I_memory - source_spectrum;
    return residual;
}

ComplexMat HarmonicBalanceSolver::computeJacobian(const ComplexVec& voltage_spectrum,
                                                  const ComplexMat& Y_matrix) const {
    ComplexMat Yn = computeNonlinearJacobian(voltage_spectrum);

    if (use_memory_effect_ && memory_) {
        ComplexMat Jq = memory_->computeChargeJacobian(
            voltage_spectrum, freq_to_time_matrix_, time_to_freq_matrix_);

        int M = num_freq_components_;
        for (int f = 0; f < M; ++f) {
            Complex jomega(0.0, TWO_PI * freq_components_[f].frequency);
            for (int g = 0; g < M; ++g) {
                Yn[f][g] += jomega * Jq[f][g];
            }
        }
    }

    return MatrixOps::add(Y_matrix, Yn);
}

void HarmonicBalanceSolver::buildSpectrum(HBSolution& solution) const {
    solution.spectrum.clear();

    for (int f = 0; f < num_freq_components_; ++f) {
        SpectrumLine line;
        line.frequency = freq_components_[f].frequency;
        line.amplitude = solution.voltage_spectrum[f];

        double v_peak = std::abs(line.amplitude);
        line.power_dBm = dBmFromVoltage(v_peak, config_.impedance);

        std::ostringstream oss;
        if (line.frequency < 1e-6) {
            oss << "DC";
        } else {
            bool found_tone = false;
            for (size_t t = 0; t < tones_.size(); ++t) {
                if (std::abs(line.frequency - tones_[t].frequency) < 1e-6) {
                    oss << "f" << (t + 1);
                    found_tone = true;
                    break;
                }
            }
            if (!found_tone && tones_.size() >= 2) {
                double f1 = tones_[0].frequency;
                double f2 = tones_[1].frequency;
                if (std::abs(line.frequency - (2*f1 - f2)) < 1e-6) {
                    oss << "IM3_low";
                } else if (std::abs(line.frequency - (2*f2 - f1)) < 1e-6) {
                    oss << "IM3_high";
                } else if (std::abs(line.frequency - (3*f1 - 2*f2)) < 1e-6) {
                    oss << "IM5_low";
                } else if (std::abs(line.frequency - (3*f2 - 2*f1)) < 1e-6) {
                    oss << "IM5_high";
                } else if (std::abs(line.frequency - 2*f1) < 1e-6) {
                    oss << "2f1";
                } else if (std::abs(line.frequency - 2*f2) < 1e-6) {
                    oss << "2f2";
                } else if (std::abs(line.frequency - 3*f1) < 1e-6) {
                    oss << "3f1";
                } else if (std::abs(line.frequency - 3*f2) < 1e-6) {
                    oss << "3f2";
                } else {
                    oss << std::fixed << std::setprecision(2) << (line.frequency / 1e6) << "MHz";
                }
            }
        }
        line.label = oss.str();
        solution.spectrum.push_back(line);
    }
}

HBSolution HarmonicBalanceSolver::solve() {
    if (!device_) {
        throw std::runtime_error("Nonlinear device not set");
    }
    if (tones_.empty()) {
        throw std::runtime_error("No excitation tones specified");
    }

    setupFrequencyGrid();
    setupTimeGrid();
    setupTransformMatrices();

    HBSolution solution;
    solution.converged = false;
    solution.iterations = 0;
    solution.residual_norm = 0.0;
    solution.is_aliased = false;
    solution.aliased_components.clear();

    ComplexMat Y_matrix = computeLinearJacobian();
    ComplexVec source_spectrum = generateSourceSpectrum();

    ComplexVec voltage_spectrum(num_freq_components_, Complex(0.0, 0.0));
    for (int f = 0; f < num_freq_components_; ++f) {
        if (std::abs(Y_matrix[f][f]) > 1e-15) {
            voltage_spectrum[f] = source_spectrum[f] / Y_matrix[f][f];
        }
    }

    if (config_.verbose) {
        std::cout << "Starting Newton-Raphson iteration..." << std::endl;
        std::cout << "Number of frequency components: " << num_freq_components_ << std::endl;
        std::cout << "Number of time samples: " << num_time_samples_ << std::endl;
    }

    double alpha = 1.0;
    for (int iter = 0; iter < config_.max_iterations; ++iter) {
        ComplexVec residual = computeResidual(voltage_spectrum, source_spectrum, Y_matrix);
        double residual_norm = MatrixOps::norm(residual);

        solution.iterations = iter + 1;
        solution.residual_norm = residual_norm;

        if (config_.verbose) {
            std::cout << "Iteration " << iter + 1 << ": residual = " << residual_norm << std::endl;
        }

        if (residual_norm < config_.tolerance) {
            solution.converged = true;
            break;
        }

        ComplexMat J = computeJacobian(voltage_spectrum, Y_matrix);
        ComplexMat J_copy = J;
        ComplexVec residual_copy = -alpha * residual;

        ComplexVec delta_x;
        if (!MatrixOps::solveLinearSystem(J_copy, residual_copy, delta_x)) {
            if (!MatrixOps::gaussElimination(J_copy, residual_copy)) {
                if (config_.verbose) {
                    std::cout << "Warning: Singular Jacobian, updating initial guess" << std::endl;
                }
                break;
            }
            delta_x = residual_copy;
        }

        ComplexVec new_voltage = voltage_spectrum + delta_x;

        double new_residual = MatrixOps::norm(computeResidual(new_voltage, source_spectrum, Y_matrix));
        int backtrack_iter = 0;
        while (new_residual > residual_norm && backtrack_iter < 10) {
            alpha *= 0.5;
            new_voltage = voltage_spectrum + alpha * delta_x;
            new_residual = MatrixOps::norm(computeResidual(new_voltage, source_spectrum, Y_matrix));
            backtrack_iter++;
        }
        alpha = std::min(1.0, alpha * 2.0);

        voltage_spectrum = new_voltage;
    }

    solution.voltage_spectrum = voltage_spectrum;
    solution.current_spectrum = computeNonlinearCurrent(voltage_spectrum);
    solution.time_voltage = computeTimeVoltage(voltage_spectrum);

    RealVec time_current(num_time_samples_);
    for (int t = 0; t < num_time_samples_; ++t) {
        time_current[t] = device_->computeCurrent(solution.time_voltage[t]);
    }
    solution.time_current = time_current;

    buildSpectrum(solution);

    checkAliasing(solution);
    if (solution.is_aliased) {
        solution.voltage_spectrum = applyAntiAliasingFilter(solution.voltage_spectrum, 0.75);
        solution.current_spectrum = applyAntiAliasingFilter(solution.current_spectrum, 0.75);
        solution.time_voltage = applyTimeDomainWindow(solution.time_voltage);
        buildSpectrum(solution);
    }

    return solution;
}

double HarmonicBalanceSolver::getMaximumFrequency() const {
    if (freq_components_.empty()) return 0.0;
    double max_freq = 0.0;
    for (const auto& fc : freq_components_) {
        max_freq = std::max(max_freq, fc.frequency);
    }
    return max_freq;
}

double HarmonicBalanceSolver::getNyquistFrequency() const {
    if (num_time_samples_ < 2) return 0.0;
    double dt = time_samples_[1] - time_samples_[0];
    if (dt < 1e-15) return 0.0;
    return 0.5 / dt;
}

int HarmonicBalanceSolver::checkAliasing(HBSolution& solution) const {
    double nyquist = getNyquistFrequency();
    double max_freq = getMaximumFrequency();

    if (nyquist < 1e-9 || max_freq < 1e-9) return 0;

    int aliased_count = 0;
    solution.aliased_components.clear();

    for (int f = 0; f < num_freq_components_; ++f) {
        double freq = freq_components_[f].frequency;
        if (freq > nyquist * 0.8) {
            double folded = 2 * nyquist - freq;
            if (folded > 0 && folded < nyquist * 0.8) {
                int match_idx = -1;
                for (int g = 0; g < num_freq_components_; ++g) {
                    if (std::abs(freq_components_[g].frequency - folded) < 1e6) {
                        match_idx = g;
                        break;
                    }
                }
                if (match_idx >= 0 && match_idx != f) {
                    double aliased_power = std::abs(solution.current_spectrum[f]);
                    double base_power = std::abs(solution.current_spectrum[match_idx]);
                    if (aliased_power > 1e-9 * base_power) {
                        solution.aliased_components.push_back(f);
                        aliased_count++;
                    }
                }
            }
        }
    }

    solution.is_aliased = aliased_count > 0;

    if (config_.verbose && solution.is_aliased) {
        std::cout << "Warning: Detected " << aliased_count
                  << " aliased frequency components (Nyquist: " << nyquist / 1e6
                  << " MHz, Max: " << max_freq / 1e6 << " MHz)" << std::endl;
    }

    return aliased_count;
}

ComplexVec HarmonicBalanceSolver::applyAntiAliasingFilter(const ComplexVec& spectrum, double cutoff_ratio) const {
    ComplexVec filtered = spectrum;
    double nyquist = getNyquistFrequency();
    double cutoff = cutoff_ratio * nyquist;

    for (int f = 0; f < num_freq_components_; ++f) {
        double freq = freq_components_[f].frequency;
        if (freq > cutoff) {
            double transition_width = 0.1 * nyquist;
            double alpha = 1.0;
            if (freq < cutoff + transition_width) {
                double x = (freq - cutoff) / transition_width;
                alpha = 0.5 * (1.0 + std::cos(PI * x));
            } else {
                alpha = 0.0;
            }
            filtered[f] *= alpha;
        }
    }

    return filtered;
}

RealVec HarmonicBalanceSolver::applyTimeDomainWindow(const RealVec& time_signal) const {
    int N = static_cast<int>(time_signal.size());
    RealVec windowed = time_signal;

    for (int t = 0; t < N; ++t) {
        double x = 2.0 * PI * t / (N - 1);
        double hann = 0.5 * (1.0 - std::cos(x));
        windowed[t] *= hann;
    }

    return windowed;
}

}
