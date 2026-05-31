#ifndef NETWORK_SIMULATOR_H
#define NETWORK_SIMULATOR_H

#include "izhikevich_neuron.h"
#include <string>
#include <functional>
#include <memory>

struct SimulationConfig {
    int num_neurons = 1000;
    double excitatory_ratio = 0.2;
    double connection_density = 0.1;
    double synaptic_delay_ms = 0.0;
    double duration = 1000.0;
    double dt = 0.5;
    unsigned int seed = 42;
    double stim_current = 10.0;
    int stim_start_neuron = 0;
    int stim_end_neuron = 50;
    int num_threads = 0;
    bool record_traces = true;
    bool record_spikes = true;
    std::string output_file = "spike_data.csv";
    bool save_to_file = true;

    bool use_stdp = false;
    double stdp_a_plus = 0.01;
    double stdp_a_minus = 0.012;
    double stdp_tau_plus = 20.0;
    double stdp_tau_minus = 20.0;
    double stdp_w_max = 1.0;
    double stdp_update_interval = 10.0;

    bool use_small_world = false;
    int sw_k_neighbors = 4;
    double sw_rewire_prob = 0.1;

    bool use_mea = false;
    int mea_grid_x = 8;
    int mea_grid_y = 8;
    double mea_electrode_spacing = 200.0;
    double mea_recording_radius = 150.0;
    double mea_lfp_sampling_rate = 1000.0;
};

class NetworkSimulator {
public:
    using UpdateCallback = std::function<void(const IzhikevichNetwork&, double)>;

    NetworkSimulator(const SimulationConfig& config);

    void initialize();
    void run();
    void runWithCallback(UpdateCallback callback, double callback_interval_ms = 10.0);

    const IzhikevichNetwork& getNetwork() const { return *network_; }
    IzhikevichNetwork& getNetwork() { return *network_; }
    const SimulationConfig& getConfig() const { return config_; }

    void setConfig(const SimulationConfig& config) { config_ = config; }
    void setUpdateCallback(UpdateCallback callback) { update_callback_ = callback; }

    void saveResults() const;
    void saveSpikeData(const std::string& filename) const;
    void saveVoltageTraces(const std::string& filename) const;
    void saveWeightMatrix(const std::string& filename) const;
    void saveMEAData() const;
    void printStatistics() const;

private:
    SimulationConfig config_;
    std::unique_ptr<IzhikevichNetwork> network_;
    UpdateCallback update_callback_;
    bool initialized_ = false;
};

#endif
