#include "hbsolver/circuit.h"
#include "hbsolver/matrix.h"
#include <stdexcept>
#include <sstream>
#include <algorithm>

namespace hbsolver {

CircuitElement::CircuitElement(CircuitElementType type, double value, int node1, int node2)
    : type_(type), value_(value), node1_(node1), node2_(node2) {
    if (value <= 0 && type != CircuitElementType::VoltageSource && type != CircuitElementType::CurrentSource) {
        if (type == CircuitElementType::Resistor && value == 0) {
            value_ = 1e-9;
        }
    }
    if (node1_ < 0 || node2_ < 0) {
        throw std::invalid_argument("Node numbers must be non-negative");
    }
}

std::string CircuitElement::getName() const {
    std::ostringstream oss;
    switch (type_) {
        case CircuitElementType::Resistor:
            oss << "R" << node1_ << node2_;
            break;
        case CircuitElementType::Capacitor:
            oss << "C" << node1_ << node2_;
            break;
        case CircuitElementType::Inductor:
            oss << "L" << node1_ << node2_;
            break;
        case CircuitElementType::VoltageSource:
            oss << "V" << node1_ << node2_;
            break;
        case CircuitElementType::CurrentSource:
            oss << "I" << node1_ << node2_;
            break;
    }
    return oss.str();
}

Complex CircuitElement::getImpedance(double frequency) const {
    double omega = TWO_PI * frequency;
    switch (type_) {
        case CircuitElementType::Resistor:
            return Complex(value_, 0.0);
        case CircuitElementType::Capacitor:
            return Complex(0.0, -1.0 / (omega * value_));
        case CircuitElementType::Inductor:
            return Complex(0.0, omega * value_);
        case CircuitElementType::VoltageSource:
            return Complex(0.0, 0.0);
        case CircuitElementType::CurrentSource:
            return Complex(1e15, 0.0);
        default:
            return Complex(0.0, 0.0);
    }
}

Complex CircuitElement::getAdmittance(double frequency) const {
    Complex z = getImpedance(frequency);
    if (std::abs(z) < 1e-15) {
        return Complex(1e15, 0.0);
    }
    return 1.0 / z;
}

MatchingNetwork::MatchingNetwork()
    : num_nodes_(2), source_impedance_(50.0), load_impedance_(50.0) {
}

void MatchingNetwork::addElement(CircuitElementType type, double value, int node1, int node2) {
    elements_.emplace_back(type, value, node1, node2);
    updateNumNodes();
}

void MatchingNetwork::addElement(const CircuitElement& element) {
    elements_.push_back(element);
    updateNumNodes();
}

void MatchingNetwork::buildLCSection(double l_series, double c_shunt, int start_node) {
    addElement(CircuitElementType::Inductor, l_series, start_node, start_node + 1);
    addElement(CircuitElementType::Capacitor, c_shunt, start_node + 1, 0);
    num_nodes_ = std::max(num_nodes_, start_node + 2);
}

void MatchingNetwork::buildCLSection(double c_series, double l_shunt, int start_node) {
    addElement(CircuitElementType::Capacitor, c_series, start_node, start_node + 1);
    addElement(CircuitElementType::Inductor, l_shunt, start_node + 1, 0);
    num_nodes_ = std::max(num_nodes_, start_node + 2);
}

void MatchingNetwork::buildPiNetwork(double c1, double l, double c2, int start_node) {
    addElement(CircuitElementType::Capacitor, c1, start_node, 0);
    addElement(CircuitElementType::Inductor, l, start_node, start_node + 1);
    addElement(CircuitElementType::Capacitor, c2, start_node + 1, 0);
    num_nodes_ = std::max(num_nodes_, start_node + 2);
}

void MatchingNetwork::buildTNetwork(double l1, double c, double l2, int start_node) {
    addElement(CircuitElementType::Inductor, l1, start_node, start_node + 1);
    addElement(CircuitElementType::Capacitor, c, start_node + 1, 0);
    addElement(CircuitElementType::Inductor, l2, start_node + 1, start_node + 2);
    num_nodes_ = std::max(num_nodes_, start_node + 3);
}

void MatchingNetwork::buildLNetwork(double series_l, double shunt_c, int start_node) {
    addElement(CircuitElementType::Inductor, series_l, start_node, start_node + 1);
    addElement(CircuitElementType::Capacitor, shunt_c, start_node + 1, 0);
    num_nodes_ = std::max(num_nodes_, start_node + 2);
}

void MatchingNetwork::updateNumNodes() {
    int max_node = 1;
    for (const auto& elem : elements_) {
        max_node = std::max(max_node, elem.getNode1());
        max_node = std::max(max_node, elem.getNode2());
    }
    num_nodes_ = max_node + 1;
}

void MatchingNetwork::clear() {
    elements_.clear();
    num_nodes_ = 2;
}

Complex MatchingNetwork::computeInputImpedance(double frequency, double load_impedance) const {
    if (elements_.empty()) {
        return Complex(load_impedance, 0.0);
    }

    int n = num_nodes_;
    ComplexMat Y(n, ComplexVec(n, Complex(0.0, 0.0)));

    for (const auto& elem : elements_) {
        Complex y = elem.getAdmittance(frequency);
        int n1 = elem.getNode1();
        int n2 = elem.getNode2();
        Y[n1][n1] += y;
        Y[n2][n2] += y;
        Y[n1][n2] -= y;
        Y[n2][n1] -= y;
    }

    int last_node = n - 1;
    Y[last_node][last_node] += Complex(1.0 / load_impedance, 0.0);

    int m = n - 1;
    ComplexMat Y_red(m, ComplexVec(m, Complex(0.0, 0.0)));
    for (int i = 0; i < m; ++i) {
        for (int j = 0; j < m; ++j) {
            Y_red[i][j] = Y[i + 1][j + 1];
        }
    }

    ComplexVec I(m, Complex(0.0, 0.0));
    I[0] = Complex(1.0, 0.0);

    ComplexVec V;
    if (!MatrixOps::solveLinearSystem(Y_red, I, V)) {
        return Complex(load_impedance, 0.0);
    }

    return Complex(1.0, 0.0) / V[0];
}

Complex MatchingNetwork::computeInputAdmittance(double frequency, double load_impedance) const {
    Complex z = computeInputImpedance(frequency, load_impedance);
    if (std::abs(z) < 1e-15) {
        return Complex(1e15, 0.0);
    }
    return 1.0 / z;
}

Complex MatchingNetwork::computeTransferFunction(double frequency, double load_impedance) const {
    if (elements_.empty()) {
        return Complex(0.5, 0.0);
    }

    int n = num_nodes_;
    ComplexMat Y(n, ComplexVec(n, Complex(0.0, 0.0)));

    for (const auto& elem : elements_) {
        Complex y = elem.getAdmittance(frequency);
        int n1 = elem.getNode1();
        int n2 = elem.getNode2();
        Y[n1][n1] += y;
        Y[n2][n2] += y;
        Y[n1][n2] -= y;
        Y[n2][n1] -= y;
    }

    int last_node = n - 1;
    Y[last_node][last_node] += Complex(1.0 / load_impedance, 0.0);

    int m = n - 1;
    ComplexMat Y_red(m, ComplexVec(m, Complex(0.0, 0.0)));
    for (int i = 0; i < m; ++i) {
        for (int j = 0; j < m; ++j) {
            Y_red[i][j] = Y[i + 1][j + 1];
        }
    }

    ComplexVec I(m, Complex(0.0, 0.0));
    I[0] = Complex(1.0 / source_impedance_, 0.0);

    ComplexVec V;
    if (!MatrixOps::solveLinearSystem(Y_red, I, V)) {
        return Complex(0.0, 0.0);
    }

    Complex v_in = V[0];
    Complex v_out = V[m - 1];

    return v_out / v_in;
}

CircuitTopology::CircuitTopology()
    : bias_resistor_(1000.0), bypass_capacitor_(1e-6) {
}

void CircuitTopology::setInputMatching(const MatchingNetwork& network) {
    input_matching_ = network;
}

void CircuitTopology::setOutputMatching(const MatchingNetwork& network) {
    output_matching_ = network;
}

Complex CircuitTopology::getInputImpedance(double frequency) const {
    return input_matching_.computeInputImpedance(frequency, 50.0);
}

Complex CircuitTopology::getOutputImpedance(double frequency) const {
    return output_matching_.computeInputImpedance(frequency, 50.0);
}

Complex CircuitTopology::getInputAdmittance(double frequency) const {
    return input_matching_.computeInputAdmittance(frequency, 50.0);
}

Complex CircuitTopology::getOutputAdmittance(double frequency) const {
    return output_matching_.computeInputAdmittance(frequency, 50.0);
}

}
