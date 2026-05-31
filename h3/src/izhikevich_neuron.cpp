#include "izhikevich_neuron.h"
#include <cmath>
#include <algorithm>
#include <thread>
#include <future>
#include <iostream>
#include <stdexcept>
#include <fstream>
#include <iomanip>
#include <numeric>

IzhikevichNeuron::IzhikevichNeuron(const NeuronParams& params, double v_init)
    : params_(params), v_(v_init), I_ext_(0.0), fired_(false) {
    u_ = params.b * v_;
}

void IzhikevichNeuron::update(double I, double dt) {
    fired_ = false;

    double total_I = I + I_ext_;

    double v = v_;
    double u = u_;

    double dv = 0.04 * v * v + 5.0 * v + 140.0 - u + total_I;
    double du = params_.a * (params_.b * v - u);

    v += dt * dv;
    u += dt * du;

    v += dt * (0.04 * v * v + 5.0 * v + 140.0 - u + total_I);
    u += dt * (params_.a * (params_.b * v - u));

    if (v >= 30.0) {
        v_ = params_.c;
        u_ = u + params_.d;
        fired_ = true;
    } else {
        v_ = v;
        u_ = u;
    }
}

void IzhikevichNeuron::reset() {
    v_ = -65.0;
    u_ = params_.b * v_;
    fired_ = false;
    I_ext_ = 0.0;
}

STDPUpdater::STDPUpdater(int num_neurons, const STDPConfig& config)
    : num_neurons_(num_neurons),
      config_(config),
      last_update_time_(0.0),
      time_since_update_(0.0),
      eligibility_trace_(Eigen::MatrixXd::Zero(num_neurons, num_neurons)) {
}

void STDPUpdater::recordSpikes(const std::vector<IzhikevichNeuron>& neurons,
                                double current_time) {
    for (int i = 0; i < num_neurons_; ++i) {
        if (neurons[i].isFired()) {
            auto& history = recent_spikes_[i];
            history.push_back(current_time);
            if (history.size() > MAX_HISTORY_SIZE) {
                history.erase(history.begin());
            }
        }
    }
}

void STDPUpdater::applySTDP(Eigen::SparseMatrix<double>& weights) {
    for (int post = 0; post < num_neurons_; ++post) {
        auto post_it = recent_spikes_.find(post);
        if (post_it == recent_spikes_.end() || post_it->second.empty()) continue;

        for (Eigen::SparseMatrix<double>::InnerIterator it(weights, post); it; ++it) {
            int pre = static_cast<int>(it.row());
            if (pre < 0 || pre >= num_neurons_) continue;
            if (pre == post) continue;

            auto pre_it = recent_spikes_.find(pre);
            if (pre_it == recent_spikes_.end() || pre_it->second.empty()) continue;

            double dw = 0.0;

            for (double t_post : post_it->second) {
                for (double t_pre : pre_it->second) {
                    double delta_t = t_pre - t_post;

                    if (delta_t > 0.0 && delta_t < config_.tau_plus * 3.0) {
                        dw += config_.a_plus * std::exp(-delta_t / config_.tau_plus);
                    } else if (delta_t < 0.0 && delta_t > -config_.tau_minus * 3.0) {
                        dw -= config_.a_minus * std::exp(delta_t / config_.tau_minus);
                    }
                }
            }

            double w = it.value();
            w += dw * (config_.w_max - std::abs(w)) * 0.1;
            w = std::max(config_.w_min, std::min(config_.w_max, w));

            if (pre < num_neurons_ && post < num_neurons_) {
                weights.coeffRef(pre, post) = w;
            }
        }
    }

    recent_spikes_.clear();
}

void STDPUpdater::updateWeights(Eigen::SparseMatrix<double>& weights,
                                const std::vector<IzhikevichNeuron>& neurons,
                                double current_time,
                                double dt) {
    recordSpikes(neurons, current_time);

    time_since_update_ += dt;

    if (time_since_update_ >= config_.update_interval_ms) {
        applySTDP(weights);
        time_since_update_ = 0.0;
    }

    eligibility_trace_ *= config_.eligibility_decay;

    for (int i = 0; i < num_neurons_; ++i) {
        if (neurons[i].isFired()) {
            for (int j = 0; j < num_neurons_; ++j) {
                if (i != j) {
                    eligibility_trace_(j, i) += 1.0;
                }
            }
        }
    }
}

void STDPUpdater::reset() {
    recent_spikes_.clear();
    eligibility_trace_.setZero();
    last_update_time_ = 0.0;
    time_since_update_ = 0.0;
}

std::vector<std::vector<int>> SmallWorldGenerator::buildRingLattice(int n, int k) {
    std::vector<std::vector<int>> adj(n);

    for (int i = 0; i < n; ++i) {
        for (int j = 1; j <= k / 2; ++j) {
            int right = (i + j) % n;
            int left = (i - j + n) % n;
            adj[i].push_back(right);
            adj[i].push_back(left);
        }
    }

    return adj;
}

void SmallWorldGenerator::rewireConnections(std::vector<std::vector<int>>& adj, int n,
                                             int k, double p, std::mt19937& rng) {
    std::uniform_real_distribution<double> dist(0.0, 1.0);

    for (int i = 0; i < n; ++i) {
        for (size_t idx = 0; idx < adj[i].size(); ++idx) {
            int j = adj[i][idx];

            if (i < j && dist(rng) < p) {
                std::uniform_int_distribution<int> new_neighbor_dist(0, n - 1);
                int new_j = new_neighbor_dist(rng);

                bool exists = false;
                for (int neighbor : adj[i]) {
                    if (neighbor == new_j || new_j == i) {
                        exists = true;
                        break;
                    }
                }

                if (!exists) {
                    adj[i][idx] = new_j;

                    for (size_t k2 = 0; k2 < adj[j].size(); ++k2) {
                        if (adj[j][k2] == i) {
                            adj[j][k2] = new_j;
                            break;
                        }
                    }

                    adj[new_j].push_back(i);
                    for (auto it = adj[j].begin(); it != adj[j].end(); ) {
                        if (*it == i) {
                            it = adj[j].erase(it);
                        } else {
                            ++it;
                        }
                    }
                }
            }
        }
    }
}

void SmallWorldGenerator::generate(Eigen::SparseMatrix<double>& weights,
                                    const std::vector<IzhikevichNeuron>& neurons,
                                    const SmallWorldConfig& sw_config,
                                    std::mt19937& rng) {
    int n = neurons.size();
    int k = sw_config.k_neighbors;
    if (k % 2 != 0) k++;
    if (k < 2) k = 2;

    auto adj = buildRingLattice(n, k);
    rewireConnections(adj, n, k, sw_config.rewire_prob, rng);

    std::vector<Eigen::Triplet<double>> triplets;

    std::uniform_real_distribution<double> weight_dist(0.0, 1.0);

    for (int i = 0; i < n; ++i) {
        for (int j : adj[i]) {
            if (i == j) continue;

            double weight;
            if (neurons[j].isExcitatory()) {
                weight = weight_dist(rng);
            } else {
                weight = -weight_dist(rng);
            }

            if (i >= 0 && i < n && j >= 0 && j < n) {
                triplets.emplace_back(i, j, weight);
            }
        }
    }

    weights.setFromTriplets(triplets.begin(), triplets.end());
    weights.makeCompressed();
}

MEARecorder::MEARecorder(int num_neurons, const MEAConfig& config)
    : num_neurons_(num_neurons),
      config_(config),
      lfp_dt_(1.0 / config.lfp_sampling_rate * 1000.0),
      lfp_accum_(0.0) {

    int total_electrodes = config.grid_size_x * config.grid_size_y;
    electrodes_.reserve(total_electrodes);

    double start_x = -config.electrode_spacing_um * (config.grid_size_x - 1) / 2.0;
    double start_y = -config.electrode_spacing_um * (config.grid_size_y - 1) / 2.0;

    for (int gy = 0; gy < config.grid_size_y; ++gy) {
        for (int gx = 0; gx < config.grid_size_x; ++gx) {
            Electrode e;
            e.x_um = start_x + gx * config.electrode_spacing_um;
            e.y_um = start_y + gy * config.electrode_spacing_um;
            electrodes_.push_back(e);
        }
    }

    std::mt19937 layout_rng(12345);
    neuron_x_um_.resize(num_neurons);
    neuron_y_um_.resize(num_neurons);

    double array_width = config.electrode_spacing_um * (config.grid_size_x - 1) + 400.0;
    double array_height = config.electrode_spacing_um * (config.grid_size_y - 1) + 400.0;
    std::uniform_real_distribution<double> x_dist(-array_width / 2.0, array_width / 2.0);
    std::uniform_real_distribution<double> y_dist(-array_height / 2.0, array_height / 2.0);

    for (int i = 0; i < num_neurons; ++i) {
        neuron_x_um_[i] = x_dist(layout_rng);
        neuron_y_um_[i] = y_dist(layout_rng);
    }

    for (int i = 0; i < num_neurons; ++i) {
        double nx = neuron_x_um_[i];
        double ny = neuron_y_um_[i];

        for (auto& e : electrodes_) {
            double d = computeDistance(nx, ny, e.x_um, e.y_um);
            if (d <= config.recording_radius_um) {
                e.nearby_neurons.push_back(i);
            }
        }
    }
}

void MEARecorder::mapNeuronsToElectrodes(const std::vector<IzhikevichNeuron>& neurons) {
}

double MEARecorder::computeDistance(double x1, double y1, double x2, double y2) const {
    double dx = x1 - x2;
    double dy = y1 - y2;
    return std::sqrt(dx * dx + dy * dy);
}

double MEARecorder::computeLFP(const std::vector<int>& nearby_neurons,
                                const std::vector<double>& voltages) const {
    if (nearby_neurons.empty()) return 0.0;

    double sum = 0.0;
    for (int idx : nearby_neurons) {
        if (idx >= 0 && idx < static_cast<int>(voltages.size())) {
            sum += voltages[idx];
        }
    }

    return sum / nearby_neurons.size();
}

void MEARecorder::record(const std::vector<IzhikevichNeuron>& neurons,
                          const std::vector<double>& voltages,
                          double current_time) {
    lfp_accum_ += 1.0 / (config_.lfp_sampling_rate / 1000.0);

    bool sample_lfp = false;
    if (lfp_accum_ >= lfp_dt_) {
        lfp_accum_ = 0.0;
        sample_lfp = true;
    }

    for (auto& e : electrodes_) {
        if (sample_lfp && config_.record_lfp) {
            double lfp = computeLFP(e.nearby_neurons, voltages);
            e.lfp_signal.push_back(lfp);
            e.time_points.push_back(current_time);
        }

        if (config_.record_spikes) {
            for (int idx : e.nearby_neurons) {
                if (idx >= 0 && idx < static_cast<int>(neurons.size())) {
                    if (neurons[idx].isFired()) {
                        e.spike_events.emplace_back(current_time, idx);
                    }
                }
            }
        }
    }
}

void MEARecorder::saveToFile(const std::string& filename) const {
    std::ofstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Error: Cannot open MEA file " << filename << std::endl;
        return;
    }

    file << "electrode_id,x_um,y_um,time_ms,neuron_id,event_type\n";

    for (size_t e = 0; e < electrodes_.size(); ++e) {
        const auto& electrode = electrodes_[e];

        for (const auto& event : electrode.spike_events) {
            file << e << "," << electrode.x_um << "," << electrode.y_um << ","
                 << std::fixed << std::setprecision(3) << event.first << ","
                 << event.second << ",spike\n";
        }
    }

    file.close();
    std::cout << "MEA spike data saved to " << filename << std::endl;
}

void MEARecorder::saveLFPToFile(const std::string& filename) const {
    std::ofstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Error: Cannot open LFP file " << filename << std::endl;
        return;
    }

    if (electrodes_.empty() || electrodes_[0].time_points.empty()) {
        std::cerr << "No LFP data to save." << std::endl;
        file.close();
        return;
    }

    file << "time_ms";
    for (size_t e = 0; e < electrodes_.size(); ++e) {
        file << ",ch" << e;
    }
    file << "\n";

    size_t max_timepoints = 0;
    for (const auto& e : electrodes_) {
        if (e.time_points.size() > max_timepoints) {
            max_timepoints = e.time_points.size();
        }
    }

    for (size_t t = 0; t < max_timepoints; ++t) {
        if (!electrodes_[0].time_points.empty() && t < electrodes_[0].time_points.size()) {
            file << std::fixed << std::setprecision(3) << electrodes_[0].time_points[t];
        } else {
            file << 0.0;
        }

        for (size_t e = 0; e < electrodes_.size(); ++e) {
            file << ",";
            if (t < electrodes_[e].lfp_signal.size()) {
                file << std::fixed << std::setprecision(4) << electrodes_[e].lfp_signal[t];
            }
        }
        file << "\n";
    }

    file.close();
    std::cout << "MEA LFP data saved to " << filename << std::endl;
}

IzhikevichNetwork::IzhikevichNetwork(int num_neurons,
                                       double excitatory_ratio,
                                       double connection_density,
                                       double synaptic_delay_ms,
                                       double dt,
                                       unsigned int seed)
    : num_neurons_(num_neurons),
      excitatory_ratio_(excitatory_ratio),
      connection_density_(connection_density),
      synaptic_delay_ms_(synaptic_delay_ms),
      seed_(seed),
      current_time_(0.0),
      record_all_(true),
      record_spikes_(true),
      num_threads_(std::thread::hardware_concurrency()),
      use_small_world_(false),
      rng_(seed) {

    if (num_neurons_ <= 0) {
        throw std::invalid_argument("Number of neurons must be positive");
    }
    if (dt <= 0.0) {
        throw std::invalid_argument("Time step must be positive");
    }

    num_excitatory_ = static_cast<int>(num_neurons * excitatory_ratio);
    num_inhibitory_ = num_neurons - num_excitatory_;

    delay_steps_ = static_cast<int>(std::round(synaptic_delay_ms / dt));
    if (delay_steps_ < 0) delay_steps_ = 0;

    initializeNeurons();
    initializeWeights();

    synaptic_currents_ = Eigen::VectorXd::Zero(num_neurons);

    for (int i = 0; i <= delay_steps_; ++i) {
        delay_buffer_.emplace_back(Eigen::VectorXd::Zero(num_neurons));
    }

    voltage_traces_.resize(num_neurons);
    spike_times_.resize(num_neurons);
}

void IzhikevichNetwork::initializeNeurons() {
    neurons_.reserve(num_neurons_);
    std::uniform_real_distribution<double> dist(0.0, 1.0);

    for (int i = 0; i < num_excitatory_; ++i) {
        NeuronParams params;
        params.a = 0.02;
        params.b = 0.2;
        params.c = -65.0 + 15.0 * dist(rng_) * dist(rng_);
        params.d = 8.0 - 6.0 * dist(rng_) * dist(rng_);
        params.is_excitatory = true;
        neurons_.emplace_back(params);
    }

    for (int i = 0; i < num_inhibitory_; ++i) {
        NeuronParams params;
        params.a = 0.02 + 0.08 * dist(rng_);
        params.b = 0.25 - 0.05 * dist(rng_);
        params.c = -65.0;
        params.d = 2.0;
        params.is_excitatory = false;
        neurons_.emplace_back(params);
    }
}

void IzhikevichNetwork::initializeWeights() {
    if (use_small_world_) {
        weights_ = Eigen::SparseMatrix<double>(num_neurons_, num_neurons_);
        SmallWorldGenerator::generate(weights_, neurons_, sw_config_, rng_);
        return;
    }

    weights_ = Eigen::SparseMatrix<double>(num_neurons_, num_neurons_);

    std::uniform_real_distribution<double> dist(0.0, 1.0);
    std::uniform_real_distribution<double> weight_dist(0.0, 1.0);

    std::vector<Eigen::Triplet<double>> triplets;
    triplets.reserve(static_cast<size_t>(num_neurons_ * num_neurons_ * connection_density_));

    for (int i = 0; i < num_neurons_; ++i) {
        for (int j = 0; j < num_neurons_; ++j) {
            if (i == j) continue;

            if (dist(rng_) < connection_density_) {
                double weight;
                if (neurons_[i].isExcitatory()) {
                    weight = weight_dist(rng_);
                } else {
                    weight = -weight_dist(rng_);
                }
                if (j >= 0 && j < num_neurons_ && i >= 0 && i < num_neurons_) {
                    triplets.emplace_back(j, i, weight);
                }
            }
        }
    }

    weights_.setFromTriplets(triplets.begin(), triplets.end());
    weights_.makeCompressed();
}

void IzhikevichNetwork::initializeWeightsSmallWorld() {
    weights_ = Eigen::SparseMatrix<double>(num_neurons_, num_neurons_);
    SmallWorldGenerator::generate(weights_, neurons_, sw_config_, rng_);
}

void IzhikevichNetwork::enableSTDP(const STDPConfig& stdp_config) {
    stdp_config_ = stdp_config;
    stdp_config_.enabled = true;
    stdp_updater_ = std::make_unique<STDPUpdater>(num_neurons_, stdp_config_);
}

void IzhikevichNetwork::enableSmallWorld(const SmallWorldConfig& sw_config) {
    sw_config_ = sw_config;
    sw_config_.enabled = true;
    use_small_world_ = true;
}

void IzhikevichNetwork::enableMEA(const MEAConfig& mea_config) {
    mea_config_ = mea_config;
    mea_config_.enabled = true;
    mea_recorder_ = std::make_unique<MEARecorder>(num_neurons_, mea_config_);
}

void IzhikevichNetwork::setInputCurrent(int neuron_idx, double current) {
    if (neuron_idx >= 0 && neuron_idx < num_neurons_) {
        neurons_[neuron_idx].setCurrent(current);
    }
}

void IzhikevichNetwork::setInputCurrentRange(int start, int end, double current) {
    for (int i = start; i < end && i < num_neurons_; ++i) {
        neurons_[i].setCurrent(current);
    }
}

void IzhikevichNetwork::addRandomStimulation(double amplitude, int count, unsigned int stim_seed) {
    std::mt19937 stim_rng(stim_seed);
    std::uniform_int_distribution<int> neuron_dist(0, num_excitatory_ - 1);
    std::uniform_real_distribution<double> current_dist(0.0, amplitude);

    for (int i = 0; i < count; ++i) {
        int idx = neuron_dist(stim_rng);
        if (idx >= 0 && idx < num_neurons_) {
            neurons_[idx].setCurrent(current_dist(stim_rng));
        }
    }
}

void IzhikevichNetwork::simulate(double duration, double dt) {
    int num_steps = static_cast<int>(duration / dt);

    for (int step = 0; step < num_steps; ++step) {
        simulateStep(dt);
    }
}

void IzhikevichNetwork::simulateStep(double dt) {
    if (delay_steps_ > 0) {
        computeDelayedCurrents();
    } else {
        computeInstantCurrents();
    }

    int chunk_size = (num_neurons_ + num_threads_ - 1) / num_threads_;
    if (chunk_size < 1) chunk_size = 1;

    int actual_threads = std::min(num_threads_, (num_neurons_ + chunk_size - 1) / chunk_size);
    if (actual_threads < 1) actual_threads = 1;

    std::vector<std::future<void>> futures;
    futures.reserve(actual_threads);

    for (int t = 0; t < actual_threads; ++t) {
        int start = t * chunk_size;
        int end = std::min(start + chunk_size, num_neurons_);

        if (start < num_neurons_ && start < end) {
            futures.push_back(std::async(std::launch::async,
                [this, start, end, dt]() {
                    updateNeuronsParallel(start, end, dt);
                }));
        }
    }

    for (auto& f : futures) {
        f.get();
    }

    if (stdp_updater_) {
        stdp_updater_->updateWeights(weights_, neurons_, current_time_ + dt, dt);
    }

    current_time_ += dt;

    if (record_all_) {
        time_array_.push_back(current_time_);
        for (int i = 0; i < num_neurons_; ++i) {
            voltage_traces_[i].push_back(neurons_[i].getV());
        }
    }

    if (record_spikes_) {
        for (int i = 0; i < num_neurons_; ++i) {
            if (neurons_[i].isFired()) {
                spike_times_[i].push_back(current_time_);
            }
        }
    }

    if (mea_recorder_) {
        std::vector<double> current_voltages(num_neurons_);
        for (int i = 0; i < num_neurons_; ++i) {
            current_voltages[i] = neurons_[i].getV();
        }
        mea_recorder_->record(neurons_, current_voltages, current_time_);
    }
}

void IzhikevichNetwork::computeInstantCurrents() {
    synaptic_currents_.setZero();

    for (int i = 0; i < num_neurons_; ++i) {
        if (neurons_[i].isFired()) {
            for (Eigen::SparseMatrix<double>::InnerIterator it(weights_, i); it; ++it) {
                int target_idx = static_cast<int>(it.row());
                if (target_idx >= 0 && target_idx < num_neurons_) {
                    synaptic_currents_(target_idx) += it.value();
                }
            }
        }
    }
}

void IzhikevichNetwork::computeDelayedCurrents() {
    advanceDelayBuffer();

    Eigen::VectorXd current_step = Eigen::VectorXd::Zero(num_neurons_);

    for (int i = 0; i < num_neurons_; ++i) {
        if (neurons_[i].isFired()) {
            for (Eigen::SparseMatrix<double>::InnerIterator it(weights_, i); it; ++it) {
                int target_idx = static_cast<int>(it.row());
                if (target_idx >= 0 && target_idx < num_neurons_) {
                    current_step(target_idx) += it.value();
                }
            }
        }
    }

    delay_buffer_.back() = current_step;

    if (delay_buffer_.size() > 1) {
        synaptic_currents_ = delay_buffer_.front();
    } else {
        synaptic_currents_ = current_step;
    }
}

void IzhikevichNetwork::advanceDelayBuffer() {
    if (delay_buffer_.size() > 1) {
        delay_buffer_.pop_front();
        delay_buffer_.emplace_back(Eigen::VectorXd::Zero(num_neurons_));
    }
}

void IzhikevichNetwork::updateNeuronsParallel(int start, int end, double dt) {
    for (int i = start; i < end && i < num_neurons_; ++i) {
        if (i >= 0 && i < synaptic_currents_.size()) {
            neurons_[i].update(synaptic_currents_(i), dt);
        }
    }
}

void IzhikevichNetwork::clearRecords() {
    for (auto& trace : voltage_traces_) {
        trace.clear();
    }
    for (auto& spikes : spike_times_) {
        spikes.clear();
    }
    time_array_.clear();
    current_time_ = 0.0;

    for (auto& buf : delay_buffer_) {
        buf.setZero();
    }

    if (stdp_updater_) {
        stdp_updater_->reset();
    }
}
