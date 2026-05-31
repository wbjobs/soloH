#include "hbsolver/memory.h"
#include "hbsolver/fft.h"
#include "hbsolver/matrix.h"
#include <cmath>
#include <stdexcept>
#include <iostream>

namespace hbsolver {

MemoryEffect::MemoryEffect() {
    config_.has_nl_capacitor = false;
    config_.has_nl_inductor = false;
    config_.nl_cap = createDefaultVaractor();
    config_.nl_ind = createDefaultSaturatingInductor();
}

void MemoryEffect::setConfig(const MemoryEffectConfig& config) {
    config_ = config;
}

void MemoryEffect::setNonlinearCapacitor(const NonlinearCapacitorModel& model) {
    config_.nl_cap = model;
    config_.has_nl_capacitor = true;
}

void MemoryEffect::setNonlinearInductor(const NonlinearInductorModel& model) {
    config_.nl_ind = model;
    config_.has_nl_inductor = true;
}

void MemoryEffect::setAbruptJunctionCapacitor(double cj0, double vj, double m) {
    config_.nl_cap.cj0 = cj0;
    config_.nl_cap.vj = vj;
    config_.nl_cap.m = m;
    config_.nl_cap.use_abrupt = true;
    config_.has_nl_capacitor = true;
}

void MemoryEffect::setSaturatingInductor(double l0, double alpha, double i_sat) {
    config_.nl_ind.l0 = l0;
    config_.nl_ind.alpha = alpha;
    config_.nl_ind.i_sat = i_sat;
    config_.has_nl_inductor = true;
}

NonlinearCapacitorModel MemoryEffect::createDefaultVaractor() {
    NonlinearCapacitorModel model;
    model.cj0 = 1e-12;
    model.vj = 0.7;
    model.m = 0.5;
    model.use_abrupt = true;
    return model;
}

NonlinearInductorModel MemoryEffect::createDefaultSaturatingInductor() {
    NonlinearInductorModel model;
    model.l0 = 1e-9;
    model.alpha = 1.0;
    model.i_sat = 0.1;
    return model;
}

RealVec MemoryEffect::computeCharge(const RealVec& voltage) const {
    if (!config_.has_nl_capacitor) {
        return RealVec(voltage.size(), 0.0);
    }

    double vj = config_.nl_cap.vj;
    RealVec charge(voltage.size());
    for (size_t i = 0; i < voltage.size(); ++i) {
        double v = voltage[i];
        
        if (config_.nl_cap.use_abrupt) {
            if (v >= vj * 0.9) v = vj * 0.9;
            if (v <= -vj * 10.0) v = -vj * 10.0;
        }
        
        charge[i] = config_.nl_cap.computeCharge(v);
        
        if (!std::isfinite(charge[i])) {
            charge[i] = 0.0;
        }
    }
    return charge;
}

RealVec MemoryEffect::computeFlux(const RealVec& current) const {
    if (!config_.has_nl_inductor) {
        return RealVec(current.size(), 0.0);
    }

    double i_sat = config_.nl_ind.i_sat;
    RealVec flux(current.size());
    for (size_t idx = 0; idx < current.size(); ++idx) {
        double i_val = current[idx];
        
        if (std::abs(i_val) > i_sat * 100.0) {
            i_val = (i_val > 0 ? 1.0 : -1.0) * i_sat * 100.0;
        }
        
        flux[idx] = config_.nl_ind.computeFlux(i_val);
        
        if (!std::isfinite(flux[idx])) {
            flux[idx] = 0.0;
        }
    }
    return flux;
}

RealVec MemoryEffect::centralDifference(const RealVec& x, double dt) const {
    RealVec dx(x.size(), 0.0);
    int n = static_cast<int>(x.size());

    for (int i = 1; i < n - 1; ++i) {
        dx[i] = (x[i+1] - x[i-1]) / (2.0 * dt);
    }

    if (n >= 2) {
        dx[0] = (x[1] - x[0]) / dt;
        dx[n-1] = (x[n-1] - x[n-2]) / dt;
    }

    return dx;
}

RealVec MemoryEffect::trapezoidalIntegration(const RealVec& f, double dt, double initial) const {
    RealVec integral(f.size(), 0.0);
    integral[0] = initial;

    for (size_t i = 1; i < f.size(); ++i) {
        integral[i] = integral[i-1] + 0.5 * dt * (f[i] + f[i-1]);
    }

    return integral;
}

RealVec MemoryEffect::computeDisplacementCurrent(const RealVec& voltage, double dt) const {
    if (!config_.has_nl_capacitor) {
        return RealVec(voltage.size(), 0.0);
    }

    RealVec charge = computeCharge(voltage);
    return centralDifference(charge, dt);
}

RealVec MemoryEffect::computeInducedVoltage(const RealVec& current, double dt) const {
    if (!config_.has_nl_inductor) {
        return RealVec(current.size(), 0.0);
    }

    RealVec flux = computeFlux(current);
    return centralDifference(flux, dt);
}

RealVec MemoryEffect::computeCapacitance(const RealVec& voltage) const {
    if (!config_.has_nl_capacitor) {
        return RealVec(voltage.size(), 0.0);
    }

    double vj = config_.nl_cap.vj;
    double cj0 = config_.nl_cap.cj0;
    double c_max = cj0 * 100.0;
    double c_min = cj0 * 0.01;
    
    RealVec cap(voltage.size());
    for (size_t idx = 0; idx < voltage.size(); ++idx) {
        double v = voltage[idx];
        
        if (config_.nl_cap.use_abrupt) {
            if (v >= vj * 0.9) v = vj * 0.9;
            if (v <= -vj * 10.0) v = -vj * 10.0;
        }
        
        cap[idx] = config_.nl_cap.computeCapacitance(v);
        
        if (!std::isfinite(cap[idx])) {
            cap[idx] = cj0;
        }
        cap[idx] = std::max(c_min, std::min(c_max, cap[idx]));
    }
    return cap;
}

RealVec MemoryEffect::computeInductance(const RealVec& current) const {
    if (!config_.has_nl_inductor) {
        return RealVec(current.size(), 0.0);
    }

    double l0 = config_.nl_ind.l0;
    double i_sat = config_.nl_ind.i_sat;
    double l_max = l0 * 10.0;
    double l_min = l0 * 0.1;
    
    RealVec ind(current.size());
    for (size_t idx = 0; idx < current.size(); ++idx) {
        double i_val = current[idx];
        
        if (std::abs(i_val) > i_sat * 100.0) {
            i_val = (i_val > 0 ? 1.0 : -1.0) * i_sat * 100.0;
        }
        
        ind[idx] = config_.nl_ind.computeInductance(i_val);
        
        if (!std::isfinite(ind[idx])) {
            ind[idx] = l0;
        }
        ind[idx] = std::max(l_min, std::min(l_max, ind[idx]));
    }
    return ind;
}

ComplexVec MemoryEffect::computeChargeSpectrum(const ComplexVec& voltage_spectrum) const {
    if (!config_.has_nl_capacitor) {
        return ComplexVec(voltage_spectrum.size(), Complex(0.0, 0.0));
    }

    int N = static_cast<int>(voltage_spectrum.size());
    int N_time = FFT::nextPowerOfTwo(N * 4);

    ComplexVec time_domain = FFT::frequencyToTimeN(voltage_spectrum, N_time);
    RealVec time_voltage(N_time);
    for (int i = 0; i < N_time; ++i) {
        time_voltage[i] = std::real(time_domain[i]);
    }

    RealVec time_charge = computeCharge(time_voltage);

    ComplexVec freq_charge = FFT::timeToFrequencyN(time_charge, N);
    return freq_charge;
}

ComplexVec MemoryEffect::computeFluxSpectrum(const ComplexVec& current_spectrum) const {
    if (!config_.has_nl_inductor) {
        return ComplexVec(current_spectrum.size(), Complex(0.0, 0.0));
    }

    int N = static_cast<int>(current_spectrum.size());
    int N_time = FFT::nextPowerOfTwo(N * 4);

    ComplexVec time_domain = FFT::frequencyToTimeN(current_spectrum, N_time);
    RealVec time_current(N_time);
    for (int i = 0; i < N_time; ++i) {
        time_current[i] = std::real(time_domain[i]);
    }

    RealVec time_flux = computeFlux(time_current);

    ComplexVec freq_flux = FFT::timeToFrequencyN(time_flux, N);
    return freq_flux;
}

ComplexMat MemoryEffect::computeChargeJacobian(const ComplexVec& voltage_spectrum,
                                                const ComplexMat& freq_to_time,
                                                const ComplexMat& time_to_freq) const {
    int M = static_cast<int>(voltage_spectrum.size());
    int N = static_cast<int>(freq_to_time.size());

    ComplexMat J(M, ComplexVec(M, Complex(0.0, 0.0)));

    if (!config_.has_nl_capacitor) {
        return J;
    }

    RealVec time_voltage(N, 0.0);
    for (int t = 0; t < N; ++t) {
        Complex sum(0.0, 0.0);
        for (int f = 0; f < M; ++f) {
            sum += freq_to_time[t][f] * voltage_spectrum[f];
        }
        time_voltage[t] = std::real(sum);
    }

    RealVec time_capacitance(N);
    double cj0 = config_.nl_cap.cj0;
    double vj = config_.nl_cap.vj;
    double c_max = cj0 * 100.0;
    double c_min = cj0 * 0.01;
    
    for (int t = 0; t < N; ++t) {
        double v = time_voltage[t];
        
        if (config_.nl_cap.use_abrupt) {
            if (v >= vj * 0.9) {
                v = vj * 0.9;
            }
            if (v <= -vj * 10.0) {
                v = -vj * 10.0;
            }
        }
        
        time_capacitance[t] = config_.nl_cap.computeCapacitance(v);
        
        if (!std::isfinite(time_capacitance[t])) {
            time_capacitance[t] = cj0;
        }
        time_capacitance[t] = std::max(c_min, std::min(c_max, time_capacitance[t]));
    }

    ComplexMat C_diag(N, ComplexVec(N, Complex(0.0, 0.0)));
    for (int t = 0; t < N; ++t) {
        C_diag[t][t] = Complex(time_capacitance[t], 0.0);
    }

    ComplexMat temp = MatrixOps::multiply(C_diag, freq_to_time);
    J = MatrixOps::multiply(time_to_freq, temp);

    double regularizer = 1e-15;
    for (int m = 0; m < M; ++m) {
        J[m][m] += Complex(regularizer, 0.0);
    }

    return J;
}

ComplexMat MemoryEffect::computeFluxJacobian(const ComplexVec& current_spectrum,
                                              const ComplexMat& freq_to_time,
                                              const ComplexMat& time_to_freq) const {
    int M = static_cast<int>(current_spectrum.size());
    int N = static_cast<int>(freq_to_time.size());

    ComplexMat J(M, ComplexVec(M, Complex(0.0, 0.0)));

    if (!config_.has_nl_inductor) {
        return J;
    }

    RealVec time_current(N, 0.0);
    for (int t = 0; t < N; ++t) {
        Complex sum(0.0, 0.0);
        for (int f = 0; f < M; ++f) {
            sum += freq_to_time[t][f] * current_spectrum[f];
        }
        time_current[t] = std::real(sum);
    }

    RealVec time_inductance(N);
    double l0 = config_.nl_ind.l0;
    double i_sat = config_.nl_ind.i_sat;
    double l_max = l0 * 10.0;
    double l_min = l0 * 0.1;
    
    for (int t = 0; t < N; ++t) {
        double i = time_current[t];
        
        if (std::abs(i) > i_sat * 100.0) {
            i = (i > 0 ? 1.0 : -1.0) * i_sat * 100.0;
        }
        
        time_inductance[t] = config_.nl_ind.computeInductance(i);
        
        if (!std::isfinite(time_inductance[t])) {
            time_inductance[t] = l0;
        }
        time_inductance[t] = std::max(l_min, std::min(l_max, time_inductance[t]));
    }

    ComplexMat L_diag(N, ComplexVec(N, Complex(0.0, 0.0)));
    for (int t = 0; t < N; ++t) {
        L_diag[t][t] = Complex(time_inductance[t], 0.0);
    }

    ComplexMat temp = MatrixOps::multiply(L_diag, freq_to_time);
    J = MatrixOps::multiply(time_to_freq, temp);

    double regularizer = 1e-15;
    for (int m = 0; m < M; ++m) {
        J[m][m] += Complex(regularizer, 0.0);
    }

    return J;
}

}
