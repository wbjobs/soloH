#include "lyapunovcalculator.h"
#include <cmath>
#include <iostream>

LyapunovCalculator::LyapunovCalculator(ChaoticSystem& system, SolverMethod method)
    : m_system(system)
    , m_solver(system.getODEFunction(), 0.01, method)
    , m_transientSteps(1000)
    , m_orthSteps(10)
    , m_stepSize(0.01)
    , m_currentTime(0.0)
{
    int dim = m_system.dimension();
    m_exponents.resize(dim, 0.0);
    m_perturbations.resize(dim, State(dim, 0.0));
}

void LyapunovCalculator::setTransientSteps(int steps)
{
    m_transientSteps = steps;
}

void LyapunovCalculator::setOrthSteps(int steps)
{
    m_orthSteps = steps;
}

void LyapunovCalculator::setStepSize(double dt)
{
    m_stepSize = dt;
    m_solver.setStepSize(dt);
}

void LyapunovCalculator::reset()
{
    int dim = m_system.dimension();
    m_currentState = m_system.getInitialState();
    m_exponents.assign(dim, 0.0);
    m_currentTime = 0.0;
    initializePerturbations();
}

void LyapunovCalculator::initializePerturbations()
{
    int dim = m_system.dimension();
    m_perturbations.clear();
    m_perturbations.resize(dim, State(dim, 0.0));

    for (int i = 0; i < dim; ++i) {
        m_perturbations[i][i] = 1.0;
    }
}

void LyapunovCalculator::runTransient()
{
    m_currentState = m_system.getInitialState();
    m_currentTime = 0.0;
    double dt = m_stepSize;

    for (int i = 0; i < m_transientSteps; ++i) {
        m_currentState = m_solver.step(m_currentState, m_currentTime, dt);
        m_currentTime += dt;
    }
}

void LyapunovCalculator::gramSchmidtOrthogonalize()
{
    int dim = m_system.dimension();

    for (int i = 0; i < dim; ++i) {
        for (int j = 0; j < i; ++j) {
            double dot = 0.0;
            double norm2 = 0.0;
            for (int k = 0; k < dim; ++k) {
                dot += m_perturbations[i][k] * m_perturbations[j][k];
                norm2 += m_perturbations[j][k] * m_perturbations[j][k];
            }
            if (norm2 > 0) {
                double coef = dot / norm2;
                for (int k = 0; k < dim; ++k) {
                    m_perturbations[i][k] -= coef * m_perturbations[j][k];
                }
            }
        }
    }
}

void LyapunovCalculator::normalizeVectors()
{
    int dim = m_system.dimension();

    for (int i = 0; i < dim; ++i) {
        double norm = 0.0;
        for (int k = 0; k < dim; ++k) {
            norm += m_perturbations[i][k] * m_perturbations[i][k];
        }
        norm = std::sqrt(norm);

        if (norm > 0) {
            m_exponents[i] += std::log(norm);
            for (int k = 0; k < dim; ++k) {
                m_perturbations[i][k] /= norm;
            }
        }
    }
}

State LyapunovCalculator::variationalStep(const State& state, const State& delta, double t, double dt)
{
    State k1 = m_system.variationalDerivatives(state, delta, t);

    State delta2(delta.size());
    for (size_t i = 0; i < delta.size(); ++i) delta2[i] = delta[i] + 0.5 * dt * k1[i];
    State midState(state.size());
    for (size_t i = 0; i < state.size(); ++i) midState[i] = state[i] + 0.5 * dt * m_system.derivatives(state, t)[i];
    State k2 = m_system.variationalDerivatives(midState, delta2, t + 0.5 * dt);

    State delta3(delta.size());
    for (size_t i = 0; i < delta.size(); ++i) delta3[i] = delta[i] + 0.5 * dt * k2[i];
    State k3 = m_system.variationalDerivatives(midState, delta3, t + 0.5 * dt);

    State delta4(delta.size());
    for (size_t i = 0; i < delta.size(); ++i) delta4[i] = delta[i] + dt * k3[i];
    State midState2(state.size());
    for (size_t i = 0; i < state.size(); ++i) midState2[i] = state[i] + dt * m_system.derivatives(midState, t + 0.5 * dt)[i];
    State k4 = m_system.variationalDerivatives(midState2, delta4, t + dt);

    State result(delta.size());
    for (size_t i = 0; i < delta.size(); ++i) {
        result[i] = delta[i] + (dt / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]);
    }
    return result;
}

void LyapunovCalculator::evolvePerturbations(const State& state, double dt)
{
    int dim = m_system.dimension();
    double t = m_currentTime;

    for (int i = 0; i < dim; ++i) {
        m_perturbations[i] = variationalStep(state, m_perturbations[i], t, dt);
    }
}

std::vector<double> LyapunovCalculator::computeSpectrum(int maxSteps)
{
    reset();
    runTransient();
    initializePerturbations();

    int dim = m_system.dimension();
    m_exponents.assign(dim, 0.0);

    double totalTime = 0.0;
    double dt = m_stepSize;

    for (int step = 0; step < maxSteps; ++step) {
        for (int inner = 0; inner < m_orthSteps; ++inner) {
            m_currentState = m_solver.step(m_currentState, m_currentTime, dt);
            evolvePerturbations(m_currentState, dt);
            m_currentTime += dt;
            totalTime += dt;
        }

        gramSchmidtOrthogonalize();
        normalizeVectors();
    }

    for (int i = 0; i < dim; ++i) {
        m_exponents[i] /= totalTime;
    }

    return m_exponents;
}

double LyapunovCalculator::getLargestExponent() const
{
    if (m_exponents.empty()) return 0.0;
    return m_exponents[0];
}

std::vector<double> LyapunovCalculator::getCurrentSpectrum() const
{
    return m_exponents;
}
