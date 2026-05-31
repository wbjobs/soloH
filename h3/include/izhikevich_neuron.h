#ifndef IZHIKEVICH_NEURON_H
#define IZHIKEVICH_NEURON_H

#include <vector>
#include <deque>
#include <random>
#include <map>
#include <Eigen/Dense>
#include <Eigen/Sparse>

struct NeuronParams {
    double a;
    double b;
    double c;
    double d;
    bool is_excitatory;
};

struct STDPConfig {
    bool enabled = false;
    double a_plus = 0.01;
    double a_minus = 0.012;
    double tau_plus = 20.0;
    double tau_minus = 20.0;
    double w_max = 1.0;
    double w_min = 0.0;
    double update_interval_ms = 10.0;
    double eligibility_decay = 0.99;
};

enum class TopologyType {
    Random,
    SmallWorld
};

struct SmallWorldConfig {
    bool enabled = false;
    int k_neighbors = 4;
    double rewire_prob = 0.1;
};

struct MEAConfig {
    bool enabled = false;
    int grid_size_x = 8;
    int grid_size_y = 8;
    double electrode_spacing_um = 200.0;
    double neuron_spacing_um = 50.0;
    double recording_radius_um = 150.0;
    double lfp_sampling_rate = 1000.0;
    bool record_lfp = true;
    bool record_spikes = true;
};

class IzhikevichNeuron {
public:
    IzhikevichNeuron(const NeuronParams& params, double v_init = -65.0);

    void update(double I, double dt);
    void reset();

    double getV() const { return v_; }
    double getU() const { return u_; }
    bool isFired() const { return fired_; }
    bool isExcitatory() const { return params_.is_excitatory; }

    void setCurrent(double I) { I_ext_ = I; }
    double getCurrent() const { return I_ext_; }

private:
    NeuronParams params_;
    double v_;
    double u_;
    double I_ext_;
    bool fired_;
};

class STDPUpdater {
public:
    STDPUpdater(int num_neurons, const STDPConfig& config);

    void updateWeights(Eigen::SparseMatrix<double>& weights,
                     const std::vector<IzhikevichNeuron>& neurons,
                     double current_time,
                     double dt);

    void reset();

    const std::map<int, std::vector<double>>& getRecentSpikeTimes() const { return recent_spikes_; }

private:
    void recordSpikes(const std::vector<IzhikevichNeuron>& neurons, double current_time);
    void applySTDP(Eigen::SparseMatrix<double>& weights);

    int num_neurons_;
    STDPConfig config_;
    double last_update_time_;
    double time_since_update_;

    std::map<int, std::vector<double>> recent_spikes_;
    Eigen::MatrixXd eligibility_trace_;

    static constexpr int MAX_HISTORY_SIZE = 200;
};

class SmallWorldGenerator {
public:
    static void generate(Eigen::SparseMatrix<double>& weights,
                         const std::vector<IzhikevichNeuron>& neurons,
                         const SmallWorldConfig& sw_config,
                         std::mt19937& rng);

private:
    static std::vector<std::vector<int>> buildRingLattice(int n, int k);
    static void rewireConnections(std::vector<std::vector<int>>& adj, int n, int k,
                                 double p, std::mt19937& rng);
};

class MEARecorder {
public:
    struct Electrode {
        double x_um;
        double y_um;
        std::vector<int> nearby_neurons;
        std::vector<double> lfp_signal;
        std::vector<double> time_points;
        std::vector<std::pair<double, int>> spike_events;
    };

    MEARecorder(int num_neurons, const MEAConfig& config);

    void record(const std::vector<IzhikevichNeuron>& neurons,
                 const std::vector<double>& voltages,
                 double current_time);

    void saveToFile(const std::string& filename) const;
    void saveLFPToFile(const std::string& filename) const;

    const std::vector<Electrode>& getElectrodes() const { return electrodes_; }
    int getNumElectrodes() const { return electrodes_.size(); }

private:
    void mapNeuronsToElectrodes(const std::vector<IzhikevichNeuron>& neurons);
    double computeDistance(double x1, double y1, double x2, double y2) const;
    double computeLFP(const std::vector<int>& nearby_neurons,
                       const std::vector<double>& voltages) const;

    int num_neurons_;
    MEAConfig config_;
    std::vector<Electrode> electrodes_;
    std::vector<double> neuron_x_um_;
    std::vector<double> neuron_y_um_;
    double lfp_dt_;
    double lfp_accum_;
};

class IzhikevichNetwork {
public:
    IzhikevichNetwork(int num_neurons,
                      double excitatory_ratio,
                      double connection_density,
                      double synaptic_delay_ms = 0.0,
                      double dt = 0.5,
                      unsigned int seed = 42);

    void setInputCurrent(int neuron_idx, double current);
    void setInputCurrentRange(int start, int end, double current);
    void addRandomStimulation(double amplitude, int count, unsigned int seed);

    void simulate(double duration, double dt);
    void simulateStep(double dt);

    void enableSTDP(const STDPConfig& stdp_config);
    void enableSmallWorld(const SmallWorldConfig& sw_config);
    void enableMEA(const MEAConfig& mea_config);

    const std::vector<IzhikevichNeuron>& getNeurons() const { return neurons_; }
    const Eigen::SparseMatrix<double>& getWeights() const { return weights_; }
    const std::vector<std::vector<double>>& getVoltageTraces() const { return voltage_traces_; }
    const std::vector<std::vector<double>>& getSpikeTimes() const { return spike_times_; }
    const std::vector<double>& getTimeArray() const { return time_array_; }
    int getNumNeurons() const { return num_neurons_; }
    int getNumExcitatory() const { return num_excitatory_; }
    int getNumInhibitory() const { return num_inhibitory_; }
    double getCurrentTime() const { return current_time_; }
    double getSynapticDelay() const { return synaptic_delay_ms_; }

    const STDPConfig& getSTDPConfig() const { return stdp_config_; }
    bool isSTDPEnabled() const { return stdp_config_.enabled; }
    const MEARecorder* getMEARecorder() const { return mea_recorder_.get(); }

    void setRecordAll(bool record) { record_all_ = record; }
    void setRecordSpikes(bool record) { record_spikes_ = record; }
    void setNumThreads(int num_threads) { num_threads_ = num_threads; }

    void clearRecords();

private:
    void initializeNeurons();
    void initializeWeights();
    void initializeWeightsSmallWorld();
    void updateNeuronsParallel(int start, int end, double dt);
    void advanceDelayBuffer();
    void computeDelayedCurrents();
    void computeInstantCurrents();

    int num_neurons_;
    int num_excitatory_;
    int num_inhibitory_;
    double excitatory_ratio_;
    double connection_density_;
    double synaptic_delay_ms_;
    int delay_steps_;
    unsigned int seed_;

    std::vector<IzhikevichNeuron> neurons_;
    Eigen::SparseMatrix<double> weights_;
    Eigen::VectorXd synaptic_currents_;

    std::deque<Eigen::VectorXd> delay_buffer_;

    std::vector<std::vector<double>> voltage_traces_;
    std::vector<std::vector<double>> spike_times_;
    std::vector<double> time_array_;
    double current_time_;

    bool record_all_;
    bool record_spikes_;
    int num_threads_;

    STDPConfig stdp_config_;
    std::unique_ptr<STDPUpdater> stdp_updater_;

    SmallWorldConfig sw_config_;
    bool use_small_world_;

    std::unique_ptr<MEARecorder> mea_recorder_;
    MEAConfig mea_config_;

    std::mt19937 rng_;
};

#endif
