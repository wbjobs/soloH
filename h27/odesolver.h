#ifndef ODESOLVER_H
#define ODESOLVER_H

#include <vector>
#include <functional>
#include <array>

using State = std::vector<double>;
using ODEFunction = std::function<State(const State&, double)>;

enum class SolverMethod {
    RK4,
    AdaptiveRK45
};

class ODESolver {
public:
    ODESolver(ODEFunction func, double stepSize = 0.01, SolverMethod method = SolverMethod::RK4);

    void setStepSize(double stepSize);
    void setMethod(SolverMethod method);
    void setTolerance(double tol);

    State step(const State& y, double t, double& dt);

    State rk4Step(const State& y, double t, double dt);
    State adaptiveRK45Step(const State& y, double t, double& dt);

private:
    ODEFunction m_func;
    double m_stepSize;
    SolverMethod m_method;
    double m_tolerance;
    double m_maxStep;
    double m_minStep;

    State computeK(const State& y, double t, double dt, const State& k1, int stage);
    double estimateError(const State& y4, const State& y5);
};

#endif
