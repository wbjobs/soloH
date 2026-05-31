#ifndef HBSOLVER_TYPES_H
#define HBSOLVER_TYPES_H

#include <complex>
#include <vector>
#include <string>
#include <cmath>

namespace hbsolver {

using Complex = std::complex<double>;
using RealVec = std::vector<double>;
using ComplexVec = std::vector<Complex>;
using ComplexMat = std::vector<ComplexVec>;
using RealMat = std::vector<RealVec>;
using IntVec = std::vector<int>;
using StringVec = std::vector<std::string>;

constexpr double PI = 3.14159265358979323846;
constexpr double TWO_PI = 2.0 * PI;
constexpr Complex I(0.0, 1.0);
constexpr double SQRT2 = 1.41421356237309504880;

enum class NonlinearModelType {
    Polynomial,
    PiecewiseLinear,
    Angelov
};

enum class CircuitElementType {
    Resistor,
    Capacitor,
    Inductor,
    VoltageSource,
    CurrentSource
};

struct FrequencyComponent {
    int harmonic_index;
    int tone_index;
    double frequency;
    int index;
};

struct Tone {
    double frequency;
    double amplitude;
    double phase;
};

struct SpectrumLine {
    double frequency;
    Complex amplitude;
    double power_dBm;
    std::string label;
};

struct HBConfig {
    int num_harmonics = 5;
    int num_time_samples = 0;
    int max_iterations = 100;
    double tolerance = 1e-8;
    double impedance = 50.0;
    bool verbose = false;
};

struct HBSolution {
    ComplexVec voltage_spectrum;
    ComplexVec current_spectrum;
    RealVec time_voltage;
    RealVec time_current;
    std::vector<SpectrumLine> spectrum;
    int iterations;
    double residual_norm;
    bool converged;
    bool is_aliased;
    std::vector<int> aliased_components;
};

struct PowerMetrics {
    double fundamental_power;
    double harmonic2_power;
    double harmonic3_power;
    double im3_power;
    double im5_power;
    double p1dB_input;
    double p1dB_output;
    double ip3_input;
    double ip3_output;
};

struct NonlinearCapacitorModel {
    RealVec c_coeffs;
    double cj0;
    double vj;
    double m;
    bool use_abrupt = false;

    double computeCapacitance(double voltage) const {
        if (use_abrupt) {
            return cj0 / std::pow(1.0 - voltage / vj, m);
        }
        double c = 0.0;
        double v_pow = 1.0;
        for (double coeff : c_coeffs) {
            c += coeff * v_pow;
            v_pow *= voltage;
        }
        return c;
    }

    double computeCharge(double voltage) const {
        if (use_abrupt) {
            return cj0 * vj / (1.0 - m) * (1.0 - std::pow(1.0 - voltage / vj, 1.0 - m));
        }
        double q = 0.0;
        double v_pow = voltage;
        for (size_t i = 0; i < c_coeffs.size(); ++i) {
            q += c_coeffs[i] * v_pow / (i + 1.0);
            v_pow *= voltage;
        }
        return q;
    }

    double computeDqDv(double voltage) const {
        return computeCapacitance(voltage);
    }
};

struct NonlinearInductorModel {
    RealVec l_coeffs;
    double l0;
    double alpha;
    double i_sat;

    double computeInductance(double current) const {
        if (l_coeffs.empty()) {
            return l0 / (1.0 + alpha * std::abs(current / i_sat));
        }
        double l = 0.0;
        double i_pow = 1.0;
        for (double coeff : l_coeffs) {
            l += coeff * i_pow;
            i_pow *= current * current;
        }
        return l;
    }

    double computeFlux(double current) const {
        if (l_coeffs.empty()) {
            return l0 * i_sat / alpha * std::log(1.0 + alpha * std::abs(current / i_sat)) *
                   (current > 0 ? 1.0 : -1.0);
        }
        double phi = 0.0;
        double i_pow = current;
        for (size_t i = 0; i < l_coeffs.size(); ++i) {
            phi += l_coeffs[i] * i_pow / (2 * i + 1.0);
            i_pow *= current * current;
        }
        return phi;
    }

    double computeDphiDi(double current) const {
        return computeInductance(current);
    }
};

struct MemoryEffectConfig {
    bool has_nl_capacitor = false;
    bool has_nl_inductor = false;
    NonlinearCapacitorModel nl_cap;
    NonlinearInductorModel nl_ind;
    double thermal_tau = 1e-6;
    double trap_tau = 1e-5;
};

struct LoadPullResult {
    Complex load_impedance;
    double output_power;
    double gain;
    double efficiency;
    double pae;
    double im3;
    bool is_stable;
};

struct SourcePullResult {
    Complex source_impedance;
    double gain;
    double noise_figure;
    double output_power;
    bool is_stable;
};

struct ContourPoint {
    Complex impedance;
    double value;
};

struct ImpedanceContour {
    std::string name;
    double target_value;
    std::vector<ContourPoint> points;
    double center_frequency;
};

struct EnvelopeSignal {
    double carrier_freq;
    RealVec time;
    ComplexVec envelope;
    RealVec amplitude;
    RealVec phase;
    RealVec instantaneous_freq;
};

struct EnvelopeSolution {
    EnvelopeSignal input_envelope;
    EnvelopeSignal output_envelope;
    RealVec amam_input;
    RealVec amam_output;
    RealVec ampm_phase;
    double evm;
    double acpr;
    double npr;
};

struct AMAMPMPoint {
    double input_power;
    double output_power;
    double phase_shift;
    double gain_compression;
};

struct AMAMPMCharacteristics {
    std::vector<AMAMPMPoint> points;
    double p1dB;
    double sat_power;
    double linear_gain;
    double pm1dB;
};

inline double dBm(double power_watts, double impedance = 50.0) {
    return 10.0 * std::log10(std::max(power_watts, 1e-15) * 1000.0);
}

inline double dBmFromVoltage(double v_peak, double impedance = 50.0) {
    double power = (v_peak * v_peak) / (2.0 * impedance);
    return dBm(power, impedance);
}

inline ComplexVec operator*(const ComplexVec& v, double s) {
    ComplexVec result(v.size());
    for (size_t i = 0; i < v.size(); ++i) result[i] = v[i] * s;
    return result;
}

inline ComplexVec operator*(double s, const ComplexVec& v) {
    return v * s;
}

inline ComplexVec operator+(const ComplexVec& a, const ComplexVec& b) {
    ComplexVec result(a.size());
    for (size_t i = 0; i < a.size(); ++i) result[i] = a[i] + b[i];
    return result;
}

inline ComplexVec operator-(const ComplexVec& a, const ComplexVec& b) {
    ComplexVec result(a.size());
    for (size_t i = 0; i < a.size(); ++i) result[i] = a[i] - b[i];
    return result;
}

}

#endif
