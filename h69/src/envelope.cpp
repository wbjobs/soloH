#include "hbsolver/envelope.h"
#include "hbsolver/loadpull.h"
#include "hbsolver/analysis.h"
#include <iostream>
#include <iomanip>
#include <cmath>
#include <algorithm>
#include <random>
#include <numeric>

namespace hbsolver {

EnvelopeSimulator::EnvelopeSimulator(HarmonicBalanceSolver& solver)
    : solver_(solver) {
}

void EnvelopeSimulator::setModulationConfig(const ModulationConfig& config) {
    config_ = config;
}

double EnvelopeSimulator::dBmToVoltage(double power_dBm, double impedance) {
    double power_watts = std::pow(10.0, power_dBm / 10.0) / 1000.0;
    return std::sqrt(2.0 * impedance * power_watts);
}

double EnvelopeSimulator::voltageTodBm(double v_peak, double impedance) {
    double power = (v_peak * v_peak) / (2.0 * impedance);
    return 10.0 * std::log10(power * 1000.0);
}

std::vector<Complex> EnvelopeSimulator::generatePulseShapingFilter(
    int num_taps, double rolloff, double sps) {

    std::vector<Complex> filter(num_taps);
    int half = num_taps / 2;

    for (int n = -half; n <= half; ++n) {
        int idx = n + half;
        double t = static_cast<double>(n) / sps;
        double sinc_val = 1.0;
        double cos_val = 1.0;

        if (std::abs(t) > 1e-9) {
            sinc_val = std::sin(PI * t) / (PI * t);
        }

        double denom = 1.0 - (2.0 * rolloff * t) * (2.0 * rolloff * t);
        if (std::abs(denom) > 1e-9) {
            cos_val = std::cos(PI * rolloff * t) / denom;
        } else {
            cos_val = PI / 4.0;
        }

        filter[idx] = Complex(sinc_val * cos_val / sps, 0.0);
    }

    double sum = 0.0;
    for (const auto& tap : filter) sum += std::real(tap);
    for (auto& tap : filter) tap /= sum;

    return filter;
}

std::vector<Complex> EnvelopeSimulator::generateRandomSymbols(int num_symbols, int order) {
    std::mt19937 gen(config_.seed);
    std::vector<Complex> symbols(num_symbols);

    if (order == 4) {
        std::uniform_int_distribution<> dist(0, 3);
        for (int i = 0; i < num_symbols; ++i) {
            int val = dist(gen);
            double re = (val & 1) ? 1.0 : -1.0;
            double im = (val & 2) ? 1.0 : -1.0;
            symbols[i] = Complex(re, im) / std::sqrt(2.0);
        }
    } else if (order == 16 || order == 64) {
        int levels = static_cast<int>(std::sqrt(order));
        std::uniform_int_distribution<> dist(0, levels - 1);
        double scale = std::sqrt(2.0 * (levels * levels - 1) / 3.0);

        for (int i = 0; i < num_symbols; ++i) {
            int re_val = dist(gen);
            int im_val = dist(gen);
            double re = (2.0 * re_val - (levels - 1)) / scale;
            double im = (2.0 * im_val - (levels - 1)) / scale;
            symbols[i] = Complex(re, im);
        }
    }

    return symbols;
}

EnvelopeSignal EnvelopeSimulator::upsampleAndFilter(
    const std::vector<Complex>& symbols, const ModulationConfig& config) {

    EnvelopeSignal result;
    result.carrier_freq = config.carrier_freq;

    int sps = config.oversampling;
    int num_symbols = static_cast<int>(symbols.size());
    int num_samples = num_symbols * sps;
    int filter_taps = sps * 8 + 1;

    auto filter = generatePulseShapingFilter(filter_taps, config.rolloff, sps);

    RealVec time(num_samples);
    ComplexVec upsampled(num_samples, Complex(0.0, 0.0));

    double dt = 1.0 / (config.symbol_rate * sps);
    for (int i = 0; i < num_samples; ++i) {
        time[i] = i * dt;
        if (i % sps == 0) {
            int sym_idx = i / sps;
            if (sym_idx < num_symbols) {
                upsampled[i] = symbols[sym_idx];
            }
        }
    }

    ComplexVec filtered(num_samples, Complex(0.0, 0.0));
    int half_taps = filter_taps / 2;

    for (int i = 0; i < num_samples; ++i) {
        for (int j = 0; j < filter_taps; ++j) {
            int idx = i - half_taps + j;
            if (idx >= 0 && idx < num_samples) {
                filtered[i] += upsampled[idx] * filter[j];
            }
        }
    }

    double max_amp = 0.0;
    for (const auto& s : filtered) {
        max_amp = std::max(max_amp, std::abs(s));
    }

    double target_amp = dBmToVoltage(config.peak_power_dBm, 50.0);
    double scale = target_amp / max_amp;

    result.time = time;
    result.envelope.resize(num_samples);
    result.amplitude.resize(num_samples);
    result.phase.resize(num_samples);

    for (int i = 0; i < num_samples; ++i) {
        result.envelope[i] = filtered[i] * scale;
        result.amplitude[i] = std::abs(result.envelope[i]);
        result.phase[i] = std::arg(result.envelope[i]);
    }

    computeInstantaneousFrequency(result);
    return result;
}

void EnvelopeSimulator::computeInstantaneousFrequency(EnvelopeSignal& signal) {
    int n = static_cast<int>(signal.phase.size());
    signal.instantaneous_freq.resize(n, 0.0);

    for (int i = 1; i < n - 1; ++i) {
        double dphi = signal.phase[i+1] - signal.phase[i-1];
        while (dphi > PI) dphi -= TWO_PI;
        while (dphi < -PI) dphi += TWO_PI;
        double dt = signal.time[i+1] - signal.time[i-1];
        signal.instantaneous_freq[i] = dphi / (TWO_PI * dt);
    }

    if (n >= 2) {
        double dphi = signal.phase[1] - signal.phase[0];
        while (dphi > PI) dphi -= TWO_PI;
        while (dphi < -PI) dphi += TWO_PI;
        signal.instantaneous_freq[0] = dphi / (TWO_PI * (signal.time[1] - signal.time[0]));

        dphi = signal.phase[n-1] - signal.phase[n-2];
        while (dphi > PI) dphi -= TWO_PI;
        while (dphi < -PI) dphi += TWO_PI;
        signal.instantaneous_freq[n-1] = dphi / (TWO_PI * (signal.time[n-1] - signal.time[n-2]));
    }
}

EnvelopeSignal EnvelopeSimulator::generateQPSKSignal(const ModulationConfig& config) {
    std::mt19937 gen(config.seed);
    std::vector<Complex> symbols(config.num_symbols);
    std::uniform_int_distribution<> dist(0, 3);
    
    for (int i = 0; i < config.num_symbols; ++i) {
        int val = dist(gen);
        double re = (val & 1) ? 1.0 : -1.0;
        double im = (val & 2) ? 1.0 : -1.0;
        symbols[i] = Complex(re, im) / std::sqrt(2.0);
    }
    
    EnvelopeSignal result;
    result.carrier_freq = config.carrier_freq;

    int sps = config.oversampling;
    int num_symbols = static_cast<int>(symbols.size());
    int num_samples = num_symbols * sps;
    int filter_taps = sps * 8 + 1;

    auto filter = generatePulseShapingFilter(filter_taps, config.rolloff, sps);

    RealVec time(num_samples);
    ComplexVec upsampled(num_samples, Complex(0.0, 0.0));

    double dt = 1.0 / (config.symbol_rate * sps);
    for (int i = 0; i < num_samples; ++i) {
        time[i] = i * dt;
        if (i % sps == 0) {
            int sym_idx = i / sps;
            if (sym_idx < num_symbols) {
                upsampled[i] = symbols[sym_idx];
            }
        }
    }

    ComplexVec filtered(num_samples, Complex(0.0, 0.0));
    int half_taps = filter_taps / 2;

    for (int i = 0; i < num_samples; ++i) {
        for (int j = 0; j < filter_taps; ++j) {
            int idx = i - half_taps + j;
            if (idx >= 0 && idx < num_samples) {
                filtered[i] += upsampled[idx] * filter[j];
            }
        }
    }

    double max_amp = 0.0;
    for (const auto& s : filtered) {
        max_amp = std::max(max_amp, std::abs(s));
    }

    double power_watts = std::pow(10.0, config.peak_power_dBm / 10.0) / 1000.0;
    double target_amp = std::sqrt(2.0 * 50.0 * power_watts);
    double scale = target_amp / max_amp;

    result.time = time;
    result.envelope.resize(num_samples);
    result.amplitude.resize(num_samples);
    result.phase.resize(num_samples);

    for (int i = 0; i < num_samples; ++i) {
        result.envelope[i] = filtered[i] * scale;
        result.amplitude[i] = std::abs(result.envelope[i]);
        result.phase[i] = std::arg(result.envelope[i]);
    }

    result.instantaneous_freq.resize(num_samples, 0.0);
    for (int i = 1; i < num_samples - 1; ++i) {
        double dphi = result.phase[i+1] - result.phase[i-1];
        while (dphi > PI) dphi -= TWO_PI;
        while (dphi < -PI) dphi += TWO_PI;
        double dt_i = result.time[i+1] - result.time[i-1];
        result.instantaneous_freq[i] = dphi / (TWO_PI * dt_i);
    }

    return result;
}

EnvelopeSignal EnvelopeSimulator::generateQAMSignal(const ModulationConfig& config, int order) {
    std::mt19937 gen(config.seed);
    std::vector<Complex> symbols(config.num_symbols);

    int levels = static_cast<int>(std::sqrt(order));
    std::uniform_int_distribution<> dist(0, levels - 1);
    double scale = std::sqrt(2.0 * (levels * levels - 1) / 3.0);

    for (int i = 0; i < config.num_symbols; ++i) {
        int re_val = dist(gen);
        int im_val = dist(gen);
        double re = (2.0 * re_val - (levels - 1)) / scale;
        double im = (2.0 * im_val - (levels - 1)) / scale;
        symbols[i] = Complex(re, im);
    }
    
    EnvelopeSignal result;
    result.carrier_freq = config.carrier_freq;

    int sps = config.oversampling;
    int num_symbols = static_cast<int>(symbols.size());
    int num_samples = num_symbols * sps;
    int filter_taps = sps * 8 + 1;

    auto filter = generatePulseShapingFilter(filter_taps, config.rolloff, sps);

    RealVec time(num_samples);
    ComplexVec upsampled(num_samples, Complex(0.0, 0.0));

    double dt = 1.0 / (config.symbol_rate * sps);
    for (int i = 0; i < num_samples; ++i) {
        time[i] = i * dt;
        if (i % sps == 0) {
            int sym_idx = i / sps;
            if (sym_idx < num_symbols) {
                upsampled[i] = symbols[sym_idx];
            }
        }
    }

    ComplexVec filtered(num_samples, Complex(0.0, 0.0));
    int half_taps = filter_taps / 2;

    for (int i = 0; i < num_samples; ++i) {
        for (int j = 0; j < filter_taps; ++j) {
            int idx = i - half_taps + j;
            if (idx >= 0 && idx < num_samples) {
                filtered[i] += upsampled[idx] * filter[j];
            }
        }
    }

    double max_amp = 0.0;
    for (const auto& s : filtered) {
        max_amp = std::max(max_amp, std::abs(s));
    }

    double power_watts = std::pow(10.0, config.peak_power_dBm / 10.0) / 1000.0;
    double target_amp = std::sqrt(2.0 * 50.0 * power_watts);
    double scale_factor = target_amp / max_amp;

    result.time = time;
    result.envelope.resize(num_samples);
    result.amplitude.resize(num_samples);
    result.phase.resize(num_samples);

    for (int i = 0; i < num_samples; ++i) {
        result.envelope[i] = filtered[i] * scale_factor;
        result.amplitude[i] = std::abs(result.envelope[i]);
        result.phase[i] = std::arg(result.envelope[i]);
    }

    result.instantaneous_freq.resize(num_samples, 0.0);
    for (int i = 1; i < num_samples - 1; ++i) {
        double dphi = result.phase[i+1] - result.phase[i-1];
        while (dphi > PI) dphi -= TWO_PI;
        while (dphi < -PI) dphi += TWO_PI;
        double dt_i = result.time[i+1] - result.time[i-1];
        result.instantaneous_freq[i] = dphi / (TWO_PI * dt_i);
    }

    return result;
}

EnvelopeSignal EnvelopeSimulator::generateOFDMSSignal(const ModulationConfig& config) {
    int num_subcarriers = 64;
    int cp_length = 16;

    std::mt19937 gen(config.seed);
    std::uniform_int_distribution<> dist(0, 3);

    int num_ofdm_symbols = config.num_symbols / num_subcarriers + 1;
    int sps = config.oversampling;
    int samples_per_symbol = num_subcarriers + cp_length;
    int total_samples = num_ofdm_symbols * samples_per_symbol * sps / 8;

    EnvelopeSignal result;
    result.carrier_freq = config.carrier_freq;
    result.time.resize(total_samples);
    result.envelope.resize(total_samples, Complex(0.0, 0.0));
    result.amplitude.resize(total_samples, 0.0);
    result.phase.resize(total_samples, 0.0);

    double dt = 1.0 / (config.symbol_rate * sps / 8);
    for (int i = 0; i < total_samples; ++i) {
        result.time[i] = i * dt;
    }

    int sample_idx = 0;
    for (int sym = 0; sym < num_ofdm_symbols && sample_idx < total_samples; ++sym) {
        ComplexVec freq_domain(num_subcarriers, Complex(0.0, 0.0));

        for (int sc = 0; sc < num_subcarriers; ++sc) {
            if (sc != 0 && std::abs(sc - num_subcarriers/2) > 5) {
                int val = dist(gen);
                double re = (val & 1) ? 1.0 : -1.0;
                double im = (val & 2) ? 1.0 : -1.0;
                freq_domain[sc] = Complex(re, im) / std::sqrt(2.0);
            }
        }

        ComplexVec time_domain = freq_domain;
        FFT::transform(time_domain, true);

        int samples_this = std::min(samples_per_symbol * sps / 8, total_samples - sample_idx);
        double target_amp = dBmToVoltage(config.peak_power_dBm, 50.0);
        double max_amp = 0.0;
        for (int i = 0; i < samples_this; ++i) {
            max_amp = std::max(max_amp, std::abs(time_domain[i % num_subcarriers]));
        }
        double scale = target_amp / std::max(max_amp, 1e-9);

        for (int i = 0; i < samples_this && sample_idx < total_samples; ++i) {
            int tidx = (i + cp_length * sps / 8) % num_subcarriers;
            result.envelope[sample_idx] = time_domain[tidx] * scale;
            result.amplitude[sample_idx] = std::abs(result.envelope[sample_idx]);
            result.phase[sample_idx] = std::arg(result.envelope[sample_idx]);
            sample_idx++;
        }
    }

    computeInstantaneousFrequency(result);
    return result;
}

EnvelopeSignal EnvelopeSimulator::generateTwoToneEnvelope(const ModulationConfig& config) {
    int sps = config.oversampling;
    int num_samples = config.num_symbols * sps;
    double dt = 1.0 / (config.symbol_rate * sps);

    EnvelopeSignal result;
    result.carrier_freq = config.carrier_freq;
    result.time.resize(num_samples);
    result.envelope.resize(num_samples);
    result.amplitude.resize(num_samples);
    result.phase.resize(num_samples);

    double f_offset = config.symbol_rate / 2.0;
    double target_amp = dBmToVoltage(config.peak_power_dBm, 50.0);

    for (int i = 0; i < num_samples; ++i) {
        double t = i * dt;
        Complex env1 = Complex(target_amp * 0.5, 0.0) * std::exp(I * TWO_PI * f_offset * t);
        Complex env2 = Complex(target_amp * 0.5, 0.0) * std::exp(-I * TWO_PI * f_offset * t);
        result.envelope[i] = env1 + env2;
        result.time[i] = t;
        result.amplitude[i] = std::abs(result.envelope[i]);
        result.phase[i] = std::arg(result.envelope[i]);
    }

    computeInstantaneousFrequency(result);
    return result;
}

EnvelopeSignal EnvelopeSimulator::generateInputSignal() {
    switch (config_.type) {
        case ModulationType::QPSK:
            return generateQPSKSignal(config_);
        case ModulationType::QAM16:
            return generateQAMSignal(config_, 16);
        case ModulationType::QAM64:
            return generateQAMSignal(config_, 64);
        case ModulationType::OFDM:
            return generateOFDMSSignal(config_);
        case ModulationType::TwoTone:
            return generateTwoToneEnvelope(config_);
        default:
            return generateQPSKSignal(config_);
    }
}

Complex EnvelopeSimulator::nonlinearMapping(Complex input_envelope, double carrier_power) {
    double input_amp = std::abs(input_envelope);
    double input_phase = std::arg(input_envelope);

    double input_power_dBm = voltageTodBm(input_amp, 50.0);
    double gain_db = 10.0;
    double compression = 0.0;
    double phase_shift = 0.0;

    double pin_above_p1db = input_power_dBm - carrier_power;
    if (pin_above_p1db > 0) {
        compression = 0.1 * pin_above_p1db * pin_above_p1db;
        phase_shift = -0.05 * pin_above_p1db;
    }

    double output_power_dBm = input_power_dBm + gain_db - compression;
    double output_amp = dBmToVoltage(output_power_dBm, 50.0);
    double output_phase = input_phase + phase_shift;

    return Complex(output_amp * std::cos(output_phase),
                    output_amp * std::sin(output_phase));
}

EnvelopeSolution EnvelopeSimulator::runEnvelopeSimulation() {
    EnvelopeSolution solution;
    solution.input_envelope = generateInputSignal();
    solution.evm = 0.0;
    solution.acpr = -60.0;
    solution.npr = 30.0;

    int n = static_cast<int>(solution.input_envelope.time.size());
    solution.output_envelope = solution.input_envelope;

    HBConfig hb_config = solver_.getConfig();
    double avg_power = hb_config.impedance * std::accumulate(
        solution.input_envelope.amplitude.begin(),
        solution.input_envelope.amplitude.end(), 0.0) / n;
    double avg_power_dBm = voltageTodBm(std::sqrt(2.0 * avg_power / hb_config.impedance), hb_config.impedance);

    double amplitude = dBmToVoltage(avg_power_dBm - 3.0, hb_config.impedance);
    solver_.setSingleTone(config_.carrier_freq, amplitude);

    int hb_interval = config_.oversampling * 4;
    Complex prev_output(0.0, 0.0);

    for (int i = 0; i < n; ++i) {
        if (i % hb_interval == 0) {
            double instant_power_dBm = voltageTodBm(solution.input_envelope.amplitude[i], hb_config.impedance);
            double instant_amp = dBmToVoltage(instant_power_dBm, hb_config.impedance);

            solver_.setSingleTone(config_.carrier_freq + solution.input_envelope.instantaneous_freq[i],
                                  instant_amp);

            HBSolution hb_sol = solver_.solve();

            for (const auto& line : hb_sol.spectrum) {
                if (std::abs(line.frequency - config_.carrier_freq) < 1e6) {
                    prev_output = line.amplitude;
                    break;
                }
            }
        }

        double alpha = 0.1;
        Complex mapped = nonlinearMapping(solution.input_envelope.envelope[i], avg_power_dBm);
        solution.output_envelope.envelope[i] = alpha * mapped + (1.0 - alpha) * prev_output;
        solution.output_envelope.amplitude[i] = std::abs(solution.output_envelope.envelope[i]);
        solution.output_envelope.phase[i] = std::arg(solution.output_envelope.envelope[i]);
    }

    int num_amam_points = std::min(n, 1000);
    solution.amam_input.resize(num_amam_points);
    solution.amam_output.resize(num_amam_points);
    solution.ampm_phase.resize(num_amam_points);

    int step = n / num_amam_points;
    for (int i = 0; i < num_amam_points; ++i) {
        int idx = i * step;
        if (idx >= n) break;

        solution.amam_input[i] = voltageTodBm(solution.input_envelope.amplitude[idx], 50.0);
        solution.amam_output[i] = voltageTodBm(solution.output_envelope.amplitude[idx], 50.0);
        solution.ampm_phase[i] = solution.output_envelope.phase[idx] - solution.input_envelope.phase[idx];
    }

    solution.evm = computeEVM(solution.input_envelope, solution.output_envelope);
    solution.acpr = computeACPR(solution.output_envelope, config_.symbol_rate, config_.symbol_rate * 1.5);
    solution.npr = computeNPR(solution.output_envelope, config_.symbol_rate * 0.1, config_.symbol_rate * 0.5);

    return solution;
}

EnvelopeSolution EnvelopeSimulator::slowEnvelopeTracking(const EnvelopeSignal& input_env,
                                                         int hb_steps_per_symbol) {
    EnvelopeSolution solution;
    solution.input_envelope = input_env;
    solution.evm = 0.0;
    solution.acpr = -60.0;
    solution.npr = 30.0;

    int n = static_cast<int>(input_env.time.size());
    solution.output_envelope = input_env;

    int samples_per_hb = config_.oversampling / hb_steps_per_symbol;
    ComplexVec hb_results;

    for (int i = 0; i < n; i += samples_per_hb) {
        double instant_power_dBm = voltageTodBm(input_env.amplitude[i], 50.0);
        double instant_amp = dBmToVoltage(instant_power_dBm, 50.0);
        double instant_freq = config_.carrier_freq + input_env.instantaneous_freq[i];

        solver_.setSingleTone(instant_freq, instant_amp);
        HBSolution hb_sol = solver_.solve();

        Complex output_amplitude(0.0, 0.0);
        for (const auto& line : hb_sol.spectrum) {
            if (std::abs(line.frequency - config_.carrier_freq) < 1e6) {
                output_amplitude = line.amplitude;
                break;
            }
        }

        for (int j = 0; j < samples_per_hb && i + j < n; ++j) {
            double interp = static_cast<double>(j) / samples_per_hb;
            double input_amp = input_env.amplitude[i + j];
            double input_phase = input_env.phase[i + j];

            double output_amp = std::abs(output_amplitude) * input_amp /
                                std::max(input_env.amplitude[i], 1e-9);
            double output_phase = std::arg(output_amplitude) + input_phase -
                                  input_env.phase[i];

            solution.output_envelope.envelope[i + j] = Complex(
                output_amp * std::cos(output_phase),
                output_amp * std::sin(output_phase));
            solution.output_envelope.amplitude[i + j] = output_amp;
            solution.output_envelope.phase[i + j] = output_phase;
        }
    }

    solution.evm = computeEVM(input_env, solution.output_envelope);
    solution.acpr = computeACPR(solution.output_envelope, config_.symbol_rate, config_.symbol_rate * 1.5);

    return solution;
}

double EnvelopeSimulator::computeEVM(const EnvelopeSignal& reference,
                                     const EnvelopeSignal& distorted) {

    if (reference.amplitude.size() != distorted.amplitude.size() ||
        reference.amplitude.empty()) {
        return 100.0;
    }

    int n = static_cast<int>(reference.amplitude.size());
    double max_amp = 0.0;
    for (double a : reference.amplitude) max_amp = std::max(max_amp, a);

    double sum_sq_error = 0.0;
    for (int i = 0; i < n; ++i) {
        Complex ref(reference.amplitude[i] * std::cos(reference.phase[i]),
                   reference.amplitude[i] * std::sin(reference.phase[i]));
        Complex dst(distorted.amplitude[i] * std::cos(distorted.phase[i]),
                   distorted.amplitude[i] * std::sin(distorted.phase[i]));
        double error = std::abs(dst - ref);
        sum_sq_error += error * error;
    }

    double rmse = std::sqrt(sum_sq_error / n);
    return rmse / max_amp * 100.0;
}

double EnvelopeSimulator::computeACPR(const EnvelopeSignal& signal,
                                       double channel_bandwidth,
                                       double adjacent_offset) {

    if (signal.time.empty() || signal.amplitude.empty()) return -60.0;

    int n = static_cast<int>(signal.time.size());
    double dt = signal.time[1] - signal.time[0];

    ComplexVec time_domain(n);
    for (int i = 0; i < n; ++i) {
        time_domain[i] = Complex(
            signal.amplitude[i] * std::cos(signal.phase[i]),
            signal.amplitude[i] * std::sin(signal.phase[i]));
    }

    ComplexVec spectrum = time_domain;
    FFT::transform(spectrum, false);

    double df = 1.0 / (n * dt);
    int center_idx = n / 2;

    int main_low = center_idx - static_cast<int>(channel_bandwidth / 2.0 / df);
    int main_high = center_idx + static_cast<int>(channel_bandwidth / 2.0 / df);
    int adj_low_low = center_idx + static_cast<int>((adjacent_offset - channel_bandwidth / 2.0) / df);
    int adj_low_high = center_idx + static_cast<int>((adjacent_offset + channel_bandwidth / 2.0) / df);
    int adj_high_low = center_idx - static_cast<int>((adjacent_offset + channel_bandwidth / 2.0) / df);
    int adj_high_high = center_idx - static_cast<int>((adjacent_offset - channel_bandwidth / 2.0) / df);

    double total_power = 0.0, adjacent_power = 0.0;
    for (int i = 0; i < n; ++i) {
        double power = std::norm(spectrum[i]);
        if (i >= main_low && i <= main_high) {
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

double EnvelopeSimulator::computeNPR(const EnvelopeSignal& signal,
                                      double notch_bandwidth,
                                      double notch_offset) {

    if (signal.time.empty() || signal.amplitude.empty()) return 30.0;

    int n = static_cast<int>(signal.time.size());
    double dt = signal.time[1] - signal.time[0];

    ComplexVec time_domain(n);
    for (int i = 0; i < n; ++i) {
        time_domain[i] = Complex(
            signal.amplitude[i] * std::cos(signal.phase[i]),
            signal.amplitude[i] * std::sin(signal.phase[i]));
    }

    ComplexVec spectrum = time_domain;
    FFT::transform(spectrum, false);

    double df = 1.0 / (n * dt);
    int center_idx = n / 2;

    int notch_low = center_idx + static_cast<int>((notch_offset - notch_bandwidth / 2.0) / df);
    int notch_high = center_idx + static_cast<int>((notch_offset + notch_bandwidth / 2.0) / df);

    double notch_power = 0.0, total_power = 0.0;
    for (int i = 0; i < n; ++i) {
        double power = std::norm(spectrum[i]);
        total_power += power;
        if (i >= notch_low && i <= notch_high) {
            notch_power += power;
        }
    }

    if (notch_power < 1e-20) return 30.0;
    return 10.0 * std::log10((total_power - notch_power) / notch_power);
}

RealVec EnvelopeSimulator::computeCCDF(const RealVec& amplitude, int num_bins) {
    if (amplitude.empty()) return RealVec();

    RealVec sorted_amp = amplitude;
    std::sort(sorted_amp.begin(), sorted_amp.end(), std::greater<double>());

    double max_amp = sorted_amp.front();
    double min_amp = sorted_amp.back();
    double range = max_amp - min_amp;
    if (range < 1e-12) range = 1.0;

    RealVec ccdf(num_bins, 0.0);
    int n = static_cast<int>(sorted_amp.size());

    for (int bin = 0; bin < num_bins; ++bin) {
        double threshold = min_amp + range * bin / (num_bins - 1);
        int count = 0;
        for (double a : sorted_amp) {
            if (a >= threshold) count++;
            else break;
        }
        ccdf[bin] = static_cast<double>(count) / n;
    }

    return ccdf;
}

AMAMPMCharacteristics EnvelopeSimulator::runDynamicAmAmPm(int num_power_levels) {
    AMAMPAnalysis amamp(solver_);
    return amamp.runAmAmPm(config_.peak_power_dBm - 20,
                           config_.peak_power_dBm + 5,
                           num_power_levels,
                           config_.carrier_freq);
}

}
