#include "chaoticsystems.h"
#include <cmath>
#include <stdexcept>

ChaoticSystem::ChaoticSystem(SystemType type)
    : m_type(type)
{
    m_params = getDefaultParameters(type);
    m_initialState = getDefaultInitialState(type);
}

void ChaoticSystem::setType(SystemType type)
{
    m_type = type;
    if (m_params.sigma == 0 && m_params.R == 0) {
        m_params = getDefaultParameters(type);
        m_initialState = getDefaultInitialState(type);
    }
}

SystemType ChaoticSystem::getType() const
{
    return m_type;
}

void ChaoticSystem::setParameters(const SystemParameters& params)
{
    m_params = params;
}

SystemParameters ChaoticSystem::getParameters() const
{
    return m_params;
}

void ChaoticSystem::setInitialState(const State& state)
{
    m_initialState = state;
}

State ChaoticSystem::getInitialState() const
{
    return m_initialState;
}

State ChaoticSystem::derivatives(const State& y, double t) const
{
    if (m_type == SystemType::Lorenz) {
        return lorenzDerivatives(y, t);
    } else {
        return chuaDerivatives(y, t);
    }
}

State ChaoticSystem::variationalDerivatives(const State& y, const State& delta, double t) const
{
    if (m_type == SystemType::Lorenz) {
        return lorenzVariational(y, delta, t);
    } else {
        return chuaVariational(y, delta, t);
    }
}

ODEFunction ChaoticSystem::getODEFunction() const
{
    return [this](const State& y, double t) {
        return derivatives(y, t);
    };
}

State ChaoticSystem::getDefaultInitialState(SystemType type)
{
    if (type == SystemType::Lorenz) {
        return {1.0, 1.0, 1.0};
    } else {
        return {0.1, 0.0, 0.0};
    }
}

SystemParameters ChaoticSystem::getDefaultParameters(SystemType type)
{
    SystemParameters params{};
    if (type == SystemType::Lorenz) {
        params.sigma = 10.0;
        params.rho = 28.0;
        params.beta = 8.0 / 3.0;
    } else {
        params.alpha = 9.0;
        params.beta = 14.286;
        params.m0 = -1.143;
        params.m1 = -0.714;
        params.R = 1.0;
        params.C1 = 1.0;
        params.C2 = 1.0;
        params.L = 1.0;
    }
    return params;
}

int ChaoticSystem::dimension() const
{
    return 3;
}

State ChaoticSystem::lorenzDerivatives(const State& y, double t) const
{
    (void)t;
    State dy(3);
    dy[0] = m_params.sigma * (y[1] - y[0]);
    dy[1] = y[0] * (m_params.rho - y[2]) - y[1];
    dy[2] = y[0] * y[1] - m_params.beta * y[2];
    return dy;
}

State ChaoticSystem::chuaDerivatives(const State& y, double t) const
{
    (void)t;
    State dy(3);
    double x = y[0];
    double y1 = y[1];
    double z = y[2];

    double g = chuaNonlinearity(x);

    dy[0] = m_params.alpha * (y1 - x - g);
    dy[1] = x - y1 + z;
    dy[2] = -m_params.beta * y1;

    return dy;
}

double ChaoticSystem::chuaNonlinearity(double x) const
{
    double m0 = m_params.m0;
    double m1 = m_params.m1;
    double bp = 1.0;
    double eps = 0.02;

    if (x > bp + eps) {
        return m1 * x + (m1 - m0) * bp;
    } else if (x < -(bp + eps)) {
        return m1 * x - (m1 - m0) * bp;
    } else if (std::abs(x) < bp - eps) {
        return m0 * x;
    } else {
        double alpha;
        if (x > 0) {
            alpha = (x - (bp - eps)) / (2.0 * eps);
        } else {
            alpha = (-x - (bp - eps)) / (2.0 * eps);
        }
        alpha = 3.0 * alpha * alpha - 2.0 * alpha * alpha * alpha;

        double g_outer;
        double g_inner = m0 * x;

        if (x > 0) {
            g_outer = m1 * x + (m1 - m0) * bp;
        } else {
            g_outer = m1 * x - (m1 - m0) * bp;
        }

        return g_inner * (1.0 - alpha) + g_outer * alpha;
    }
}

double ChaoticSystem::chuaNonlinearityDerivative(double x) const
{
    double m0 = m_params.m0;
    double m1 = m_params.m1;
    double bp = 1.0;
    double eps = 0.02;

    if (x > bp + eps) {
        return m1;
    } else if (x < -(bp + eps)) {
        return m1;
    } else if (std::abs(x) < bp - eps) {
        return m0;
    } else {
        double alpha, dalpha_dx;
        double sign = (x > 0) ? 1.0 : -1.0;
        double abs_x = std::abs(x);

        alpha = (abs_x - (bp - eps)) / (2.0 * eps);
        dalpha_dx = sign * (6.0 * alpha - 6.0 * alpha * alpha) / (2.0 * eps);
        alpha = 3.0 * alpha * alpha - 2.0 * alpha * alpha * alpha;

        double g_outer, dg_outer;
        double g_inner = m0 * x;
        double dg_inner = m0;

        if (x > 0) {
            g_outer = m1 * x + (m1 - m0) * bp;
            dg_outer = m1;
        } else {
            g_outer = m1 * x - (m1 - m0) * bp;
            dg_outer = m1;
        }

        return dg_inner * (1.0 - alpha) + (g_outer - g_inner) * (-dalpha_dx) + dg_outer * alpha;
    }
}

State ChaoticSystem::lorenzVariational(const State& y, const State& delta, double t) const
{
    (void)t;
    State ddelta(3);

    double dx = delta[0];
    double dy = delta[1];
    double dz = delta[2];

    ddelta[0] = m_params.sigma * (dy - dx);
    ddelta[1] = dx * (m_params.rho - y[2]) - dy - y[0] * dz;
    ddelta[2] = dx * y[1] + y[0] * dy - m_params.beta * dz;

    return ddelta;
}

State ChaoticSystem::chuaVariational(const State& y, const State& delta, double t) const
{
    (void)t;
    State ddelta(3);

    double dx = delta[0];
    double dy = delta[1];
    double dz = delta[2];

    double dg_dx = chuaNonlinearityDerivative(y[0]);

    ddelta[0] = m_params.alpha * (dy - dx * (1.0 + dg_dx));
    ddelta[1] = dx - dy + dz;
    ddelta[2] = -m_params.beta * dy;

    return ddelta;
}
