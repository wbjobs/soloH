#include "hbsolver/nonlinear.h"
#include <cmath>
#include <stdexcept>
#include <algorithm>

namespace hbsolver {

PolynomialModel::PolynomialModel() {
    coefficients_ = {0.0, 0.02, 0.001, -0.0001};
}

PolynomialModel::PolynomialModel(const RealVec& coefficients) {
    setCoefficients(coefficients);
}

void PolynomialModel::setCoefficients(const RealVec& coefficients) {
    if (coefficients.empty()) {
        throw std::invalid_argument("Coefficients cannot be empty");
    }
    coefficients_ = coefficients;
}

const RealVec& PolynomialModel::getCoefficients() const {
    return coefficients_;
}

double PolynomialModel::computeCurrent(double voltage) const {
    double result = 0.0;
    double v_pow = 1.0;
    for (double coeff : coefficients_) {
        result += coeff * v_pow;
        v_pow *= voltage;
    }
    return result;
}

double PolynomialModel::computeDerivative(double voltage) const {
    double result = 0.0;
    double v_pow = 1.0;
    for (size_t i = 1; i < coefficients_.size(); ++i) {
        result += i * coefficients_[i] * v_pow;
        v_pow *= voltage;
    }
    return result;
}

PiecewiseLinearModel::PiecewiseLinearModel() {
    voltages_ = {-1.0, -0.5, 0.0, 0.5, 1.0};
    currents_ = {-0.02, -0.01, 0.0, 0.01, 0.02};
    computeSlopes();
}

PiecewiseLinearModel::PiecewiseLinearModel(const RealVec& voltages, const RealVec& currents) {
    setPoints(voltages, currents);
}

void PiecewiseLinearModel::setPoints(const RealVec& voltages, const RealVec& currents) {
    if (voltages.size() != currents.size() || voltages.size() < 2) {
        throw std::invalid_argument("Invalid piecewise linear points");
    }
    for (size_t i = 1; i < voltages.size(); ++i) {
        if (voltages[i] <= voltages[i-1]) {
            throw std::invalid_argument("Voltages must be strictly increasing");
        }
    }
    voltages_ = voltages;
    currents_ = currents;
    computeSlopes();
}

void PiecewiseLinearModel::computeSlopes() {
    slopes_.resize(voltages_.size() - 1);
    for (size_t i = 0; i < slopes_.size(); ++i) {
        slopes_[i] = (currents_[i+1] - currents_[i]) / (voltages_[i+1] - voltages_[i]);
    }
}

int PiecewiseLinearModel::findSegment(double voltage) const {
    if (voltage <= voltages_.front()) return 0;
    if (voltage >= voltages_.back()) return static_cast<int>(slopes_.size() - 1);

    int left = 0;
    int right = static_cast<int>(voltages_.size() - 2);
    while (left <= right) {
        int mid = (left + right) / 2;
        if (voltage >= voltages_[mid] && voltage < voltages_[mid+1]) {
            return mid;
        } else if (voltage < voltages_[mid]) {
            right = mid - 1;
        } else {
            left = mid + 1;
        }
    }
    return 0;
}

double PiecewiseLinearModel::computeCurrent(double voltage) const {
    int seg = findSegment(voltage);
    return currents_[seg] + slopes_[seg] * (voltage - voltages_[seg]);
}

double PiecewiseLinearModel::computeDerivative(double voltage) const {
    int seg = findSegment(voltage);
    return slopes_[seg];
}

double PiecewiseLinearModel::sigmoidWeight(double x, double width) const {
    if (std::abs(width) < 1e-15) return (x > 0) ? 1.0 : 0.0;
    double arg = x / width;
    if (arg > 500) return 1.0;
    if (arg < -500) return 0.0;
    return 1.0 / (1.0 + std::exp(-arg));
}

double PiecewiseLinearModel::computeSmoothedDerivative(double voltage, int num_subsamples) const {
    int seg = findSegment(voltage);

    bool near_breakpoint = false;
    double dist_to_lower = (seg > 0) ? std::abs(voltage - voltages_[seg]) : 1e15;
    double dist_to_upper = (seg < static_cast<int>(slopes_.size()) - 1) ?
                           std::abs(voltage - voltages_[seg + 1]) : 1e15;
    double min_dist = std::min(dist_to_lower, dist_to_upper);

    if (min_dist > smoothing_width_ * 5.0) {
        return slopes_[seg];
    }
    near_breakpoint = true;

    double total_weight = 0.0;
    double weighted_sum = 0.0;
    double half_width = smoothing_width_ * 5.0;

    for (int i = 0; i < num_subsamples; ++i) {
        double offset = -half_width + 2.0 * half_width * i / (num_subsamples - 1);
        double v = voltage + offset;

        double w = std::exp(-(offset * offset) / (2.0 * smoothing_width_ * smoothing_width_));

        int sub_seg = findSegment(v);
        double deriv = slopes_[sub_seg];

        int n_segs = static_cast<int>(slopes_.size());
        for (int s = 0; s < n_segs - 1; ++s) {
            double vb = voltages_[s + 1];
            double dist = v - vb;
            double sw = sigmoidWeight(dist, smoothing_width_);
            deriv = (1.0 - sw) * slopes_[s] + sw * slopes_[s + 1];
        }

        weighted_sum += w * deriv;
        total_weight += w;
    }

    if (total_weight > 1e-15) {
        return weighted_sum / total_weight;
    }
    return slopes_[seg];
}

AngelovModel::AngelovModel()
    : vpk_(1.0), ids0_(0.1), vto_(-0.5), lambda_(0.01), alpha_(2.0) {
}

AngelovModel::AngelovModel(double vpk, double ids0, double vto, double lambda, double alpha)
    : vpk_(vpk), ids0_(ids0), vto_(vto), lambda_(lambda), alpha_(alpha) {
}

void AngelovModel::setParameters(double vpk, double ids0, double vto, double lambda, double alpha) {
    vpk_ = vpk;
    ids0_ = ids0;
    vto_ = vto;
    lambda_ = lambda;
    alpha_ = alpha;
}

double AngelovModel::computeCurrent(double voltage) const {
    double vgs_norm = (voltage - vto_) / vpk_;
    double tanh_arg = alpha_ * vgs_norm;
    double ids = ids0_ * (1.0 + std::tanh(tanh_arg));
    return ids * (1.0 + lambda_ * voltage);
}

double AngelovModel::computeDerivative(double voltage) const {
    double vgs_norm = (voltage - vto_) / vpk_;
    double tanh_arg = alpha_ * vgs_norm;
    double tanh_val = std::tanh(tanh_arg);
    double sech2 = 1.0 - tanh_val * tanh_val;

    double term1 = ids0_ * alpha_ / vpk_ * sech2 * (1.0 + lambda_ * voltage);
    double term2 = ids0_ * (1.0 + tanh_val) * lambda_;

    return term1 + term2;
}

std::unique_ptr<NonlinearDevice> NonlinearModelFactory::createPolynomial(const RealVec& coeffs) {
    return std::make_unique<PolynomialModel>(coeffs);
}

std::unique_ptr<NonlinearDevice> NonlinearModelFactory::createPiecewiseLinear(const RealVec& voltages, const RealVec& currents) {
    return std::make_unique<PiecewiseLinearModel>(voltages, currents);
}

std::unique_ptr<NonlinearDevice> NonlinearModelFactory::createAngelov(double vpk, double ids0, double vto, double lambda, double alpha) {
    return std::make_unique<AngelovModel>(vpk, ids0, vto, lambda, alpha);
}

std::unique_ptr<NonlinearDevice> NonlinearModelFactory::createDefaultDiode() {
    RealVec coeffs = {0.0, 0.01, 0.0005, 0.00001};
    return std::make_unique<PolynomialModel>(coeffs);
}

std::unique_ptr<NonlinearDevice> NonlinearModelFactory::createDefaultFET() {
    return std::make_unique<AngelovModel>(1.5, 0.05, -0.3, 0.02, 1.5);
}

}
