#ifndef HBSOLVER_CIRCUIT_H
#define HBSOLVER_CIRCUIT_H

#include "hbsolver/types.h"
#include <memory>
#include <vector>
#include <string>

namespace hbsolver {

class CircuitElement {
public:
    CircuitElement(CircuitElementType type, double value, int node1, int node2);
    virtual ~CircuitElement() = default;

    CircuitElementType getType() const { return type_; }
    double getValue() const { return value_; }
    int getNode1() const { return node1_; }
    int getNode2() const { return node2_; }
    std::string getName() const;

    Complex getImpedance(double frequency) const;
    Complex getAdmittance(double frequency) const;

private:
    CircuitElementType type_;
    double value_;
    int node1_;
    int node2_;
};

class MatchingNetwork {
public:
    MatchingNetwork();
    ~MatchingNetwork() = default;

    void addElement(CircuitElementType type, double value, int node1, int node2);
    void addElement(const CircuitElement& element);

    void buildLCSection(double l_series, double c_shunt, int start_node = 1);
    void buildCLSection(double c_series, double l_shunt, int start_node = 1);
    void buildPiNetwork(double c1, double l, double c2, int start_node = 1);
    void buildTNetwork(double l1, double c, double l2, int start_node = 1);
    void buildLNetwork(double series_l, double shunt_c, int start_node = 1);

    Complex computeInputImpedance(double frequency, double load_impedance = 50.0) const;
    Complex computeInputAdmittance(double frequency, double load_impedance = 50.0) const;
    Complex computeTransferFunction(double frequency, double load_impedance = 50.0) const;

    const std::vector<CircuitElement>& getElements() const { return elements_; }
    int getNumNodes() const { return num_nodes_; }

    void setSourceImpedance(double zs) { source_impedance_ = zs; }
    void setLoadImpedance(double zl) { load_impedance_ = zl; }
    double getSourceImpedance() const { return source_impedance_; }
    double getLoadImpedance() const { return load_impedance_; }

    void clear();

private:
    std::vector<CircuitElement> elements_;
    int num_nodes_;
    double source_impedance_;
    double load_impedance_;

    void updateNumNodes();
};

class CircuitTopology {
public:
    CircuitTopology();
    ~CircuitTopology() = default;

    void setInputMatching(const MatchingNetwork& network);
    void setOutputMatching(const MatchingNetwork& network);
    void setBiasResistor(double rb) { bias_resistor_ = rb; }
    void setBypassCapacitor(double cb) { bypass_capacitor_ = cb; }

    const MatchingNetwork& getInputMatching() const { return input_matching_; }
    const MatchingNetwork& getOutputMatching() const { return output_matching_; }
    double getBiasResistor() const { return bias_resistor_; }
    double getBypassCapacitor() const { return bypass_capacitor_; }

    Complex getInputImpedance(double frequency) const;
    Complex getOutputImpedance(double frequency) const;
    Complex getInputAdmittance(double frequency) const;
    Complex getOutputAdmittance(double frequency) const;

private:
    MatchingNetwork input_matching_;
    MatchingNetwork output_matching_;
    double bias_resistor_;
    double bypass_capacitor_;
};

}

#endif
