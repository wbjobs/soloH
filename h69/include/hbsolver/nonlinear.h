#ifndef HBSOLVER_NONLINEAR_H
#define HBSOLVER_NONLINEAR_H

#include "hbsolver/types.h"
#include <memory>
#include <string>

namespace hbsolver {

class NonlinearDevice {
public:
    virtual ~NonlinearDevice() = default;
    virtual double computeCurrent(double voltage) const = 0;
    virtual double computeDerivative(double voltage) const = 0;
    virtual NonlinearModelType getType() const = 0;
    virtual std::string getName() const = 0;
};

class PolynomialModel : public NonlinearDevice {
public:
    PolynomialModel();
    explicit PolynomialModel(const RealVec& coefficients);
    ~PolynomialModel() override = default;

    void setCoefficients(const RealVec& coefficients);
    const RealVec& getCoefficients() const;

    double computeCurrent(double voltage) const override;
    double computeDerivative(double voltage) const override;
    NonlinearModelType getType() const override { return NonlinearModelType::Polynomial; }
    std::string getName() const override { return "Polynomial"; }

private:
    RealVec coefficients_;
};

class PiecewiseLinearModel : public NonlinearDevice {
public:
    PiecewiseLinearModel();
    PiecewiseLinearModel(const RealVec& voltages, const RealVec& currents);
    ~PiecewiseLinearModel() override = default;

    void setPoints(const RealVec& voltages, const RealVec& currents);
    const RealVec& getVoltages() const { return voltages_; }
    const RealVec& getCurrents() const { return currents_; }

    void setSmoothingWidth(double width) { smoothing_width_ = width; }
    double getSmoothingWidth() const { return smoothing_width_; }

    double computeCurrent(double voltage) const override;
    double computeDerivative(double voltage) const override;
    double computeSmoothedDerivative(double voltage, int num_subsamples = 5) const;

    NonlinearModelType getType() const override { return NonlinearModelType::PiecewiseLinear; }
    std::string getName() const override { return "PiecewiseLinear"; }

private:
    RealVec voltages_;
    RealVec currents_;
    RealVec slopes_;
    double smoothing_width_ = 1e-4;

    void computeSlopes();
    int findSegment(double voltage) const;
    double sigmoidWeight(double x, double width) const;
};

class AngelovModel : public NonlinearDevice {
public:
    AngelovModel();
    AngelovModel(double vpk, double ids0, double vto, double lambda, double alpha);
    ~AngelovModel() override = default;

    void setParameters(double vpk, double ids0, double vto, double lambda, double alpha);

    double getVpk() const { return vpk_; }
    double getIds0() const { return ids0_; }
    double getVto() const { return vto_; }
    double getLambda() const { return lambda_; }
    double getAlpha() const { return alpha_; }

    double computeCurrent(double voltage) const override;
    double computeDerivative(double voltage) const override;
    NonlinearModelType getType() const override { return NonlinearModelType::Angelov; }
    std::string getName() const override { return "Angelov"; }

private:
    double vpk_;
    double ids0_;
    double vto_;
    double lambda_;
    double alpha_;
};

class NonlinearModelFactory {
public:
    static std::unique_ptr<NonlinearDevice> createPolynomial(const RealVec& coeffs);
    static std::unique_ptr<NonlinearDevice> createPiecewiseLinear(const RealVec& voltages, const RealVec& currents);
    static std::unique_ptr<NonlinearDevice> createAngelov(double vpk, double ids0, double vto, double lambda, double alpha);
    static std::unique_ptr<NonlinearDevice> createDefaultDiode();
    static std::unique_ptr<NonlinearDevice> createDefaultFET();
};

}

#endif
