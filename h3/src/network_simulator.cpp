#include "network_simulator.h"
#include <iostream>
#include <fstream>
#include <iomanip>
#include <chrono>
#include <thread>
#include <memory>

NetworkSimulator::NetworkSimulator(const SimulationConfig& config)
    : config_(config), initialized_(false) {
}

void NetworkSimulator::initialize() {
    if (config_.use_small_world) {
        config_.connection_density = 0.0;
    }

    network_ = std::make_unique<IzhikevichNetwork>(
        config_.num_neurons,
        config_.excitatory_ratio,
        config_.connection_density,
        config_.synaptic_delay_ms,
        config_.dt,
        config_.seed
    );

    if (config_.use_small_world) {
        SmallWorldConfig sw_cfg;
        sw_cfg.enabled = true;
        sw_cfg.k_neighbors = config_.sw_k_neighbors;
        sw_cfg.rewire_prob = config_.sw_rewire_prob;
        network_->enableSmallWorld(sw_cfg);
    }

    if (config_.use_stdp) {
        STDPConfig stdp_cfg;
        stdp_cfg.enabled = true;
        stdp_cfg.a_plus = config_.stdp_a_plus;
        stdp_cfg.a_minus = config_.stdp_a_minus;
        stdp_cfg.tau_plus = config_.stdp_tau_plus;
        stdp_cfg.tau_minus = config_.stdp_tau_minus;
        stdp_cfg.w_max = config_.stdp_w_max;
        stdp_cfg.update_interval_ms = config_.stdp_update_interval;
        network_->enableSTDP(stdp_cfg);
    }

    if (config_.use_mea) {
        MEAConfig mea_cfg;
        mea_cfg.enabled = true;
        mea_cfg.grid_size_x = config_.mea_grid_x;
        mea_cfg.grid_size_y = config_.mea_grid_y;
        mea_cfg.electrode_spacing_um = config_.mea_electrode_spacing;
        mea_cfg.recording_radius_um = config_.mea_recording_radius;
        mea_cfg.lfp_sampling_rate = config_.mea_lfp_sampling_rate;
        network_->enableMEA(mea_cfg);
    }

    network_->setInputCurrentRange(config_.stim_start_neuron,
                                    config_.stim_end_neuron,
                                    config_.stim_current);

    if (config_.num_threads > 0) {
        network_->setNumThreads(config_.num_threads);
    }

    network_->setRecordAll(config_.record_traces);
    network_->setRecordSpikes(config_.record_spikes);

    initialized_ = true;

    std::cout << "Network initialized:" << std::endl;
    std::cout << "  Neurons: " << config_.num_neurons << std::endl;
    std::cout << "  Excitatory: " << network_->getNumExcitatory() << std::endl;
    std::cout << "  Inhibitory: " << network_->getNumInhibitory() << std::endl;
    if (config_.use_small_world) {
        std::cout << "  Topology: Small-World (k=" << config_.sw_k_neighbors
                  << ", p=" << config_.sw_rewire_prob << ")" << std::endl;
    } else {
        std::cout << "  Topology: Random (density=" << config_.connection_density << ")" << std::endl;
    }
    std::cout << "  Synaptic delay: " << config_.synaptic_delay_ms << " ms" << std::endl;
    if (config_.use_stdp) {
        std::cout << "  STDP: Enabled (A+=" << config_.stdp_a_plus
                  << ", A-=" << config_.stdp_a_minus << ")" << std::endl;
    }
    if (config_.use_mea) {
        std::cout << "  MEA: " << config_.mea_grid_x << "x" << config_.mea_grid_y
                  << " electrodes" << std::endl;
    }
    std::cout << "  Threads: " << (config_.num_threads > 0 ? config_.num_threads : std::thread::hardware_concurrency()) << std::endl;
}

void NetworkSimulator::run() {
    if (!initialized_) {
        initialize();
    }

    std::cout << "\nStarting simulation (" << config_.duration << " ms)..." << std::endl;

    auto start_time = std::chrono::high_resolution_clock::now();

    int total_steps = static_cast<int>(config_.duration / config_.dt);
    int progress_interval = total_steps / 100;
    if (progress_interval < 1) progress_interval = 1;

    for (int step = 0; step < total_steps; ++step) {
        network_->simulateStep(config_.dt);

        if (step % progress_interval == 0) {
            double progress = 100.0 * step / total_steps;
            std::cout << "\rProgress: " << std::fixed << std::setprecision(1) << progress << "%" << std::flush;
        }
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);

    std::cout << "\rProgress: 100.0%" << std::endl;
    std::cout << "Simulation completed in " << duration.count() << " ms" << std::endl;

    printStatistics();

    if (config_.save_to_file) {
        saveResults();
    }
}

void NetworkSimulator::runWithCallback(UpdateCallback callback, double callback_interval_ms) {
    if (!initialized_) {
        initialize();
    }

    update_callback_ = callback;

    std::cout << "\nStarting simulation with real-time visualization (" << config_.duration << " ms)..." << std::endl;

    int total_steps = static_cast<int>(config_.duration / config_.dt);
    int callback_steps = static_cast<int>(callback_interval_ms / config_.dt);
    if (callback_steps < 1) callback_steps = 1;

    for (int step = 0; step < total_steps; ++step) {
        network_->simulateStep(config_.dt);

        if (step % callback_steps == 0) {
            update_callback_(*network_, network_->getCurrentTime());
        }
    }

    if (update_callback_) {
        update_callback_(*network_, network_->getCurrentTime());
    }

    std::cout << "\nSimulation completed." << std::endl;
    printStatistics();

    if (config_.save_to_file) {
        saveResults();
    }
}

void NetworkSimulator::saveResults() const {
    saveSpikeData(config_.output_file);
    saveVoltageTraces("voltage_traces.csv");
    saveWeightMatrix("weight_matrix.csv");
    if (config_.use_mea) {
        saveMEAData();
    }
}

void NetworkSimulator::saveSpikeData(const std::string& filename) const {
    std::ofstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Error: Cannot open file " << filename << " for writing." << std::endl;
        return;
    }

    file << "neuron_id,time,type\n";

    const auto& spike_times = network_->getSpikeTimes();

    for (size_t i = 0; i < spike_times.size(); ++i) {
        std::string type = network_->getNeurons()[i].isExcitatory() ? "excitatory" : "inhibitory";
        for (double time : spike_times[i]) {
            file << i << "," << std::fixed << std::setprecision(3) << time << "," << type << "\n";
        }
    }

    file.close();
    std::cout << "Spike data saved to " << filename << std::endl;
}

void NetworkSimulator::saveVoltageTraces(const std::string& filename) const {
    std::ofstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Error: Cannot open file " << filename << " for writing." << std::endl;
        return;
    }

    const auto& time_array = network_->getTimeArray();
    const auto& voltage_traces = network_->getVoltageTraces();

    if (voltage_traces.empty() || time_array.empty()) {
        std::cerr << "No voltage traces to save." << std::endl;
        file.close();
        return;
    }

    file << "time";
    for (size_t i = 0; i < voltage_traces.size(); ++i) {
        file << ",v" << i;
    }
    file << "\n";

    for (size_t t = 0; t < time_array.size(); ++t) {
        file << std::fixed << std::setprecision(3) << time_array[t];
        for (size_t i = 0; i < voltage_traces.size(); ++i) {
            if (t < voltage_traces[i].size()) {
                file << "," << std::fixed << std::setprecision(2) << voltage_traces[i][t];
            }
        }
        file << "\n";
    }

    file.close();
    std::cout << "Voltage traces saved to " << filename << std::endl;
}

void NetworkSimulator::saveWeightMatrix(const std::string& filename) const {
    std::ofstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Error: Cannot open file " << filename << " for writing." << std::endl;
        return;
    }

    const auto& weights = network_->getWeights();

    file << "pre,post,weight\n";

    for (int k = 0; k < weights.outerSize(); ++k) {
        for (Eigen::SparseMatrix<double>::InnerIterator it(weights, k); it; ++it) {
            int pre = static_cast<int>(it.row());
            int post = static_cast<int>(it.col());
            double w = it.value();
            file << pre << "," << post << "," << std::fixed << std::setprecision(6) << w << "\n";
        }
    }

    file.close();
    std::cout << "Weight matrix saved to " << filename << std::endl;
}

void NetworkSimulator::saveMEAData() const {
    const auto* mea = network_->getMEARecorder();
    if (!mea) return;

    mea->saveToFile("mea_spikes.csv");
    mea->saveLFPToFile("mea_lfp.csv");
}

void NetworkSimulator::printStatistics() const {
    int total_spikes = 0;
    int excitatory_spikes = 0;
    int inhibitory_spikes = 0;
    int active_neurons = 0;

    const auto& spike_times = network_->getSpikeTimes();
    const auto& neurons = network_->getNeurons();

    for (size_t i = 0; i < spike_times.size(); ++i) {
        if (!spike_times[i].empty()) {
            active_neurons++;
            if (neurons[i].isExcitatory()) {
                excitatory_spikes += spike_times[i].size();
            } else {
                inhibitory_spikes += spike_times[i].size();
            }
        }
    }

    total_spikes = excitatory_spikes + inhibitory_spikes;

    std::cout << "\n=== Simulation Statistics ===" << std::endl;
    std::cout << "Total spikes: " << total_spikes << std::endl;
    std::cout << "Excitatory spikes: " << excitatory_spikes << std::endl;
    std::cout << "Inhibitory spikes: " << inhibitory_spikes << std::endl;
    std::cout << "Active neurons: " << active_neurons << "/" << config_.num_neurons << std::endl;
    std::cout << "Average firing rate: " << (total_spikes / config_.duration * 1000.0 / config_.num_neurons) << " Hz" << std::endl;

    if (config_.use_stdp) {
        const auto& weights = network_->getWeights();
        double mean_weight = 0.0;
        double max_weight = 0.0;
        double min_weight = 1e9;
        int nz_count = 0;

        for (int k = 0; k < weights.outerSize(); ++k) {
            for (Eigen::SparseMatrix<double>::InnerIterator it(weights, k); it; ++it) {
                double w = std::abs(it.value());
                mean_weight += w;
                if (w > max_weight) max_weight = w;
                if (w < min_weight && w > 0) min_weight = w;
                nz_count++;
            }
        }

        if (nz_count > 0) {
            mean_weight /= nz_count;
            std::cout << "STDP weight stats: mean=" << mean_weight
                      << ", max=" << max_weight
                      << ", min=" << min_weight << std::endl;
        }
    }

    if (config_.use_mea) {
        const auto* mea = network_->getMEARecorder();
        if (mea) {
            int total_mea_spikes = 0;
            for (const auto& e : mea->getElectrodes()) {
                total_mea_spikes += e.spike_events.size();
            }
            std::cout << "MEA electrodes: " << mea->getNumElectrodes()
                      << ", total detected spikes: " << total_mea_spikes << std::endl;
        }
    }

    std::cout << "=============================" << std::endl;
}
