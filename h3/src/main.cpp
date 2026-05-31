#include <iostream>
#include <string>
#include <cstring>
#include <thread>
#include <chrono>

#include "network_simulator.h"

#ifdef USE_QT_CHARTS
#include <QApplication>
#include <QTimer>
#include "real_time_plot.h"
#endif

void printUsage(const char* program_name) {
    std::cout << "Usage: " << program_name << " [options]\n"
              << "\nBasic Options:\n"
              << "  -n, --neurons N        Number of neurons (default: 1000)\n"
              << "  -d, --duration T       Simulation duration in ms (default: 1000)\n"
              << "  -c, --density D        Connection density for random topology (default: 0.1)\n"
              << "  -r, --excitatory R     Excitatory neuron ratio (default: 0.2)\n"
              << "  --delay M              Synaptic delay in ms (default: 0.0)\n"
              << "  -i, --current I        Stimulation current (default: 10.0)\n"
              << "  -s, --start N          Start neuron index for stimulation (default: 0)\n"
              << "  -e, --end N            End neuron index for stimulation (default: 50)\n"
              << "  -t, --threads N        Number of threads (default: auto)\n"
              << "  -dt, --timestep DT     Time step in ms (default: 0.5)\n"
              << "  --seed N               Random seed (default: 42)\n"
              << "  --no-plot              Disable Qt plotting (even if available)\n"
              << "  --no-save              Do not save results to files\n"
              << "\nSTDP Learning:\n"
              << "  --stdp                 Enable STDP learning rule\n"
              << "  --stdp-a+ V            STDP potentiation amplitude (default: 0.01)\n"
              << "  --stdp-a- V            STDP depression amplitude (default: 0.012)\n"
              << "  --stdp-tau+ V          STDP potentiation time constant ms (default: 20)\n"
              << "  --stdp-tau- V          STDP depression time constant ms (default: 20)\n"
              << "  --stdp-wmax V          Maximum synaptic weight (default: 1.0)\n"
              << "  --stdp-interval V      STDP update interval ms (default: 10)\n"
              << "\nSmall-World Topology:\n"
              << "  --small-world          Enable small-world network topology\n"
              << "  --sw-k N               Number of nearest neighbors in ring lattice (default: 4)\n"
              << "  --sw-p P               Rewiring probability (default: 0.1)\n"
              << "\nMulti-Electrode Array (MEA):\n"
              << "  --mea                  Enable MEA recording simulation\n"
              << "  --mea-grid NxM         Electrode grid dimensions (default: 8x8)\n"
              << "  --mea-spacing V        Electrode spacing in um (default: 200)\n"
              << "  --mea-radius V         Recording radius in um (default: 150)\n"
              << "  --mea-lfp-rate V       LFP sampling rate in Hz (default: 1000)\n"
              << "\n  -h, --help             Show this help message\n"
              << std::endl;
}

SimulationConfig parseArguments(int argc, char* argv[]) {
    SimulationConfig config;
    bool no_plot = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "-h" || arg == "--help") {
            printUsage(argv[0]);
            std::exit(0);
        } else if ((arg == "-n" || arg == "--neurons") && i + 1 < argc) {
            config.num_neurons = std::atoi(argv[++i]);
        } else if ((arg == "-d" || arg == "--duration") && i + 1 < argc) {
            config.duration = std::atof(argv[++i]);
        } else if ((arg == "-c" || arg == "--density") && i + 1 < argc) {
            config.connection_density = std::atof(argv[++i]);
        } else if ((arg == "-r" || arg == "--excitatory") && i + 1 < argc) {
            config.excitatory_ratio = std::atof(argv[++i]);
        } else if (arg == "--delay" && i + 1 < argc) {
            config.synaptic_delay_ms = std::atof(argv[++i]);
        } else if ((arg == "-i" || arg == "--current") && i + 1 < argc) {
            config.stim_current = std::atof(argv[++i]);
        } else if ((arg == "-s" || arg == "--start") && i + 1 < argc) {
            config.stim_start_neuron = std::atoi(argv[++i]);
        } else if ((arg == "-e" || arg == "--end") && i + 1 < argc) {
            config.stim_end_neuron = std::atoi(argv[++i]);
        } else if ((arg == "-t" || arg == "--threads") && i + 1 < argc) {
            config.num_threads = std::atoi(argv[++i]);
        } else if ((arg == "-dt" || arg == "--timestep") && i + 1 < argc) {
            config.dt = std::atof(argv[++i]);
        } else if (arg == "--seed" && i + 1 < argc) {
            config.seed = std::atoi(argv[++i]);
        } else if (arg == "--no-plot") {
            no_plot = true;
        } else if (arg == "--no-save") {
            config.save_to_file = false;
        } else if (arg == "--stdp") {
            config.use_stdp = true;
        } else if (arg == "--stdp-a+" && i + 1 < argc) {
            config.stdp_a_plus = std::atof(argv[++i]);
        } else if (arg == "--stdp-a-" && i + 1 < argc) {
            config.stdp_a_minus = std::atof(argv[++i]);
        } else if (arg == "--stdp-tau+" && i + 1 < argc) {
            config.stdp_tau_plus = std::atof(argv[++i]);
        } else if (arg == "--stdp-tau-" && i + 1 < argc) {
            config.stdp_tau_minus = std::atof(argv[++i]);
        } else if (arg == "--stdp-wmax" && i + 1 < argc) {
            config.stdp_w_max = std::atof(argv[++i]);
        } else if (arg == "--stdp-interval" && i + 1 < argc) {
            config.stdp_update_interval = std::atof(argv[++i]);
        } else if (arg == "--small-world") {
            config.use_small_world = true;
        } else if (arg == "--sw-k" && i + 1 < argc) {
            config.sw_k_neighbors = std::atoi(argv[++i]);
        } else if (arg == "--sw-p" && i + 1 < argc) {
            config.sw_rewire_prob = std::atof(argv[++i]);
        } else if (arg == "--mea") {
            config.use_mea = true;
        } else if (arg == "--mea-grid" && i + 1 < argc) {
            std::string grid_str = argv[++i];
            size_t x_pos = grid_str.find('x');
            if (x_pos != std::string::npos) {
                config.mea_grid_x = std::atoi(grid_str.substr(0, x_pos).c_str());
                config.mea_grid_y = std::atoi(grid_str.substr(x_pos + 1).c_str());
            }
        } else if (arg == "--mea-spacing" && i + 1 < argc) {
            config.mea_electrode_spacing = std::atof(argv[++i]);
        } else if (arg == "--mea-radius" && i + 1 < argc) {
            config.mea_recording_radius = std::atof(argv[++i]);
        } else if (arg == "--mea-lfp-rate" && i + 1 < argc) {
            config.mea_lfp_sampling_rate = std::atof(argv[++i]);
        } else {
            std::cerr << "Unknown option: " << arg << std::endl;
            printUsage(argv[0]);
            std::exit(1);
        }
    }

    if (no_plot) {
#ifdef USE_QT_CHARTS
        config.record_traces = true;
#endif
    }

    return config;
}

int main(int argc, char* argv[]) {
    SimulationConfig config = parseArguments(argc, argv);

    std::cout << "=== Izhikevich Network Simulator ===" << std::endl;
    std::cout << "Configuration:" << std::endl;
    std::cout << "  Neurons: " << config.num_neurons << std::endl;
    std::cout << "  Excitatory ratio: " << config.excitatory_ratio << std::endl;
    if (config.use_small_world) {
        std::cout << "  Topology: Small-World (k=" << config.sw_k_neighbors
                  << ", p=" << config.sw_rewire_prob << ")" << std::endl;
    } else {
        std::cout << "  Connection density: " << config.connection_density << std::endl;
    }
    std::cout << "  Synaptic delay: " << config.synaptic_delay_ms << " ms" << std::endl;
    std::cout << "  Duration: " << config.duration << " ms" << std::endl;
    std::cout << "  Time step: " << config.dt << " ms" << std::endl;
    std::cout << "  Stim current: " << config.stim_current << std::endl;
    if (config.use_stdp) {
        std::cout << "  STDP: Enabled" << std::endl;
    }
    if (config.use_mea) {
        std::cout << "  MEA: " << config.mea_grid_x << "x" << config.mea_grid_y
                  << " electrodes" << std::endl;
    }
    std::cout << "====================================" << std::endl;

#ifdef USE_QT_CHARTS
    bool use_plot = true;
    for (int i = 1; i < argc; ++i) {
        if (std::string(argv[i]) == "--no-plot") {
            use_plot = false;
            break;
        }
    }

    if (use_plot) {
        QApplication app(argc, argv);

        RealTimePlot plot_window(50);
        plot_window.show();

        NetworkSimulator simulator(config);

        double current_sim_time = 0.0;
        double callback_interval = 50.0;

        QTimer timer;
        bool sim_running = true;

        auto update_callback = [&](const IzhikevichNetwork& network, double time) {
            current_sim_time = time;
            plot_window.updateData(network, time);
            QApplication::processEvents();
        };

        std::thread sim_thread([&]() {
            simulator.runWithCallback(update_callback, callback_interval);
            sim_running = false;
        });

        QObject::connect(&timer, &QTimer::timeout, [&]() {
            if (!sim_running) {
                timer.stop();
            }
        });

        timer.start(100);

        int result = app.exec();

        if (sim_thread.joinable()) {
            sim_thread.join();
        }

        return result;
    }
#endif

    NetworkSimulator simulator(config);
    simulator.run();

    return 0;
}
