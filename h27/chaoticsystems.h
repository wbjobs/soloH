#ifndef CHAOTICSYSTEMS_H
#define CHAOTICSYSTEMS_H

#include <vector>
#include <functional>
#include "odesolver.h"

enum class SystemType {
    Lorenz,
    Chua
};

struct SystemParameters {
    double sigma;
    double rho;
    double beta;
    double alpha;
    double R;
    double C1;
    double C2;
    double L;
    double Ga;
    double Gb;
    double m0;
    double m1;
};

class ChaoticSystem {
public:
    ChaoticSystem(SystemType type = SystemType::Lorenz);

    void setType(SystemType type);
    SystemType getType() const;

    void setParameters(const SystemParameters& params);
    SystemParameters getParameters() const;

    void setInitialState(const State& state);
    State getInitialState() const;

    State derivatives(const State& y, double t) const;
    State variationalDerivatives(const State& y, const State& delta, double t) const;

    ODEFunction getODEFunction() const;

    static State getDefaultInitialState(SystemType type);
    static SystemParameters getDefaultParameters(SystemType type);

    int dimension() const;

private:
    SystemType m_type;
    SystemParameters m_params;
    State m_initialState;

    State lorenzDerivatives(const State& y, double t) const;
    State chuaDerivatives(const State& y, double t) const;

    State lorenzVariational(const State& y, const State& delta, double t) const;
    State chuaVariational(const State& y, const State& delta, double t) const;

    double chuaNonlinearity(double x) const;
    double chuaNonlinearityDerivative(double x) const;
};

#endif
