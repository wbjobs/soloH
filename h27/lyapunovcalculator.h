#ifndef LYAPUNOVCALCULATOR_H
#define LYAPUNOVCALCULATOR_H

#include <vector>
#include "chaoticsystems.h"
#include "odesolver.h"

class LyapunovCalculator {
public:
    LyapunovCalculator(ChaoticSystem& system, SolverMethod method = SolverMethod::RK4);

    void setTransientSteps(int steps);
    void setOrthSteps(int steps);
    void setStepSize(double dt);

    std::vector<double> computeSpectrum(int maxSteps = 5000);

    double getLargestExponent() const;
    std::vector<double> getCurrentSpectrum() const;

    void reset();

private:
    ChaoticSystem& m_system;
    ODESolver m_solver;
    int m_transientSteps;
    int m_orthSteps;
    double m_stepSize;

    State m_currentState;
    std::vector<State> m_perturbations;
    std::vector<double> m_exponents;
    double m_currentTime;

    void gramSchmidtOrthogonalize();
    void normalizeVectors();
    void evolvePerturbations(const State& state, double dt);
    State variationalStep(const State& state, const State& delta, double t, double dt);
    void initializePerturbations();
    void runTransient();
};

#endif
