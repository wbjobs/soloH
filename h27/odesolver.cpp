#include "odesolver.h"
#include <cmath>
#include <algorithm>

ODESolver::ODESolver(ODEFunction func, double stepSize, SolverMethod method)
    : m_func(func)
    , m_stepSize(stepSize)
    , m_method(method)
    , m_tolerance(1e-6)
    , m_maxStep(0.1)
    , m_minStep(1e-8)
{
}

void ODESolver::setStepSize(double stepSize)
{
    m_stepSize = stepSize;
}

void ODESolver::setMethod(SolverMethod method)
{
    m_method = method;
}

void ODESolver::setTolerance(double tol)
{
    m_tolerance = tol;
}

State ODESolver::step(const State& y, double t, double& dt)
{
    if (m_method == SolverMethod::RK4) {
        dt = m_stepSize;
        return rk4Step(y, t, dt);
    } else {
        return adaptiveRK45Step(y, t, dt);
    }
}

State ODESolver::rk4Step(const State& y, double t, double dt)
{
    size_t n = y.size();
    State k1 = m_func(y, t);
    State y2(n);
    for (size_t i = 0; i < n; ++i) y2[i] = y[i] + 0.5 * dt * k1[i];
    State k2 = m_func(y2, t + 0.5 * dt);
    State y3(n);
    for (size_t i = 0; i < n; ++i) y3[i] = y[i] + 0.5 * dt * k2[i];
    State k3 = m_func(y3, t + 0.5 * dt);
    State y4(n);
    for (size_t i = 0; i < n; ++i) y4[i] = y[i] + dt * k3[i];
    State k4 = m_func(y4, t + dt);

    State result(n);
    for (size_t i = 0; i < n; ++i) {
        result[i] = y[i] + (dt / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]);
    }
    return result;
}

State ODESolver::adaptiveRK45Step(const State& y, double t, double& dt)
{
    const double c2 = 1.0 / 4.0;
    const double c3 = 3.0 / 8.0;
    const double c4 = 12.0 / 13.0;
    const double c5 = 1.0;
    const double c6 = 1.0 / 2.0;

    const double a21 = 1.0 / 4.0;
    const double a31 = 3.0 / 32.0;
    const double a32 = 9.0 / 32.0;
    const double a41 = 1932.0 / 2197.0;
    const double a42 = -7200.0 / 2197.0;
    const double a43 = 7296.0 / 2197.0;
    const double a51 = 439.0 / 216.0;
    const double a52 = -8.0;
    const double a53 = 3680.0 / 513.0;
    const double a54 = -845.0 / 4104.0;
    const double a61 = -8.0 / 27.0;
    const double a62 = 2.0;
    const double a63 = -3544.0 / 2565.0;
    const double a64 = 1859.0 / 4104.0;
    const double a65 = -11.0 / 40.0;

    const double b1 = 16.0 / 135.0;
    const double b3 = 6656.0 / 12825.0;
    const double b4 = 28561.0 / 56430.0;
    const double b5 = -9.0 / 50.0;
    const double b6 = 2.0 / 55.0;

    const double b1s = 25.0 / 216.0;
    const double b3s = 1408.0 / 2565.0;
    const double b4s = 2197.0 / 4104.0;
    const double b5s = -1.0 / 5.0;

    size_t n = y.size();
    State result(n);
    double h = dt;

    while (true) {
        h = std::min(std::max(h, m_minStep), m_maxStep);

        State k1 = m_func(y, t);

        State y2(n);
        for (size_t i = 0; i < n; ++i) y2[i] = y[i] + h * a21 * k1[i];
        State k2 = m_func(y2, t + c2 * h);

        State y3(n);
        for (size_t i = 0; i < n; ++i) y3[i] = y[i] + h * (a31 * k1[i] + a32 * k2[i]);
        State k3 = m_func(y3, t + c3 * h);

        State y4(n);
        for (size_t i = 0; i < n; ++i) y4[i] = y[i] + h * (a41 * k1[i] + a42 * k2[i] + a43 * k3[i]);
        State k4 = m_func(y4, t + c4 * h);

        State y5(n);
        for (size_t i = 0; i < n; ++i) y5[i] = y[i] + h * (a51 * k1[i] + a52 * k2[i] + a53 * k3[i] + a54 * k4[i]);
        State k5 = m_func(y5, t + c5 * h);

        State y6(n);
        for (size_t i = 0; i < n; ++i) y6[i] = y[i] + h * (a61 * k1[i] + a62 * k2[i] + a63 * k3[i] + a64 * k4[i] + a65 * k5[i]);
        State k6 = m_func(y6, t + c6 * h);

        State y5th(n), y4th(n);
        for (size_t i = 0; i < n; ++i) {
            y5th[i] = y[i] + h * (b1 * k1[i] + b3 * k3[i] + b4 * k4[i] + b5 * k5[i] + b6 * k6[i]);
            y4th[i] = y[i] + h * (b1s * k1[i] + b3s * k3[i] + b4s * k4[i] + b5s * k5[i]);
        }

        double error = estimateError(y4th, y5th);

        if (error <= m_tolerance || h <= m_minStep) {
            result = y5th;
            if (error > 0) {
                double factor = 0.9 * std::pow(m_tolerance / error, 0.2);
                factor = std::min(std::max(factor, 0.1), 5.0);
                dt = h * factor;
            } else {
                dt = h * 2.0;
            }
            break;
        } else {
            double factor = 0.9 * std::pow(m_tolerance / error, 0.2);
            factor = std::min(std::max(factor, 0.1), 5.0);
            h *= factor;
        }
    }

    return result;
}

double ODESolver::estimateError(const State& y4, const State& y5)
{
    double error = 0.0;
    for (size_t i = 0; i < y4.size(); ++i) {
        double sc = std::abs(y4[i]) + std::abs(y5[i]) + 1e-10;
        error += std::pow((y5[i] - y4[i]) / sc, 2);
    }
    return std::sqrt(error / y4.size());
}

State ODESolver::computeK(const State& y, double t, double dt, const State& k1, int stage)
{
    return State();
}
