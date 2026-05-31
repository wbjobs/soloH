#include "../include/config.h"
#include "../include/bb84.h"
#include "../include/stats.h"
#include "../include/utils.h"
#include <iostream>
#include <string>
#include <cstdlib>
#include <stdexcept>

void printUsage(const char* programName) {
    std::cout << "\nBB84 Quantum Key Distribution Protocol Simulator\n";
    std::cout << "================================================\n\n";
    std::cout << "Usage: " << programName << " [options]\n\n";
    std::cout << "Options:\n";
    std::cout << "  -n, --photons N          Number of photons per run (default: 10000)\n";
    std::cout << "  -r, --runs N             Number of simulation runs (default: 100)\n";
    std::cout << "  -l, --loss RATE          Channel loss rate 0-1 (default: 0.1)\n";
    std::cout << "  -d, --dark PROB          Dark count probability (default: 0.001)\n";
    std::cout << "  -a, --attack TYPE        Attack type: none|intercept|beamsplit (default: none)\n";
    std::cout << "  -e, --eavesdrop STRENGTH Eavesdropping strength 0-1 (default: 0.5)\n";
    std::cout << "  -t, --threshold QBER     QBER threshold for detection (default: 0.11)\n";
    std::cout << "  -c, --cascade N          Number of Cascade passes (default: 4)\n";
    std::cout << "  -p, --privacy FACTOR     Privacy amplification factor (default: 0.5)\n";
    std::cout << "  -f, --fraction FRAC      Test key fraction (default: 0.15)\n";
    std::cout << "  -o, --output FILE        Output CSV file (default: bb84_results.csv)\n";
    std::cout << "  -s, --seed SEED          Random seed (default: 0 = random)\n";
    std::cout << "  -v, --verbose            Enable verbose output\n";
    std::cout << "  --protocol TYPE          Protocol: bb84|mdi (default: bb84)\n";
    std::cout << "  --fiber-length KM        Fiber length in km (enables fiber model)\n";
    std::cout << "  --fiber-atten DB         Fiber attenuation dB/km (default: 0.2)\n";
    std::cout << "  --fiber-disp PS           Dispersion ps/nm/km (default: 17)\n";
    std::cout << "  --fiber-nonlin W         Nonlinear coefficient 1/W/km (default: 1.3e-3)\n";
    std::cout << "  --decoy                  Enable decoy state method\n";
    std::cout << "  --no-fiber-model         Disable fiber model even with --fiber-length\n";
    std::cout << "  -h, --help               Show this help message\n\n";
    std::cout << "Protocol Types:\n";
    std::cout << "  bb84 - Standard BB84 protocol\n";
    std::cout << "  mdi  - Measurement-Device-Independent QKD\n\n";
    std::cout << "Attack Types:\n";
    std::cout << "  none      - No eavesdropping\n";
    std::cout << "  intercept - Intercept-resend attack (measures and resends photons)\n";
    std::cout << "  beamsplit - Beam-splitting attack (splits photon beam)\n\n";
    std::cout << "Examples:\n";
    std::cout << "  " << programName << " -n 5000 -r 50\n";
    std::cout << "  " << programName << " -a intercept -e 0.3\n";
    std::cout << "  " << programName << " -a beamsplit -l 0.05 -d 0.0001\n";
    std::cout << "  " << programName << " --protocol mdi --fiber-length 50 --decoy\n";
    std::cout << "  " << programName << " --protocol bb84 --fiber-length 100 --fiber-atten 0.25\n\n";
}

bb84::AttackType parseAttackType(const std::string& type) {
    if (type == "none" || type == "0") return bb84::AttackType::NONE;
    if (type == "intercept" || type == "1") return bb84::AttackType::INTERCEPT_RESEND;
    if (type == "beamsplit" || type == "2") return bb84::AttackType::BEAM_SPLITTING;
    throw std::invalid_argument("Invalid attack type: " + type);
}

bb84::ProtocolType parseProtocolType(const std::string& type) {
    if (type == "bb84" || type == "0") return bb84::ProtocolType::BB84;
    if (type == "mdi" || type == "mdi-qkd" || type == "1") return bb84::ProtocolType::MDI_QKD;
    throw std::invalid_argument("Invalid protocol type: " + type);
}

int main(int argc, char* argv[]) {
    bb84::Config config;
    
    try {
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            
            if (arg == "-h" || arg == "--help") {
                printUsage(argv[0]);
                return 0;
            } else if (arg == "-n" || arg == "--photons") {
                if (i + 1 < argc) config.num_photons = std::atoi(argv[++i]);
                else throw std::runtime_error("Missing value for --photons");
            } else if (arg == "-r" || arg == "--runs") {
                if (i + 1 < argc) config.num_runs = std::atoi(argv[++i]);
                else throw std::runtime_error("Missing value for --runs");
            } else if (arg == "-l" || arg == "--loss") {
                if (i + 1 < argc) config.channel_loss_rate = std::atof(argv[++i]);
                else throw std::runtime_error("Missing value for --loss");
            } else if (arg == "-d" || arg == "--dark") {
                if (i + 1 < argc) config.dark_count_prob = std::atof(argv[++i]);
                else throw std::runtime_error("Missing value for --dark");
            } else if (arg == "-a" || arg == "--attack") {
                if (i + 1 < argc) config.attack_type = parseAttackType(argv[++i]);
                else throw std::runtime_error("Missing value for --attack");
            } else if (arg == "-e" || arg == "--eavesdrop") {
                if (i + 1 < argc) config.eavesdropping_strength = std::atof(argv[++i]);
                else throw std::runtime_error("Missing value for --eavesdrop");
            } else if (arg == "-t" || arg == "--threshold") {
                if (i + 1 < argc) config.qber_threshold = std::atof(argv[++i]);
                else throw std::runtime_error("Missing value for --threshold");
            } else if (arg == "-c" || arg == "--cascade") {
                if (i + 1 < argc) config.cascade_passes = std::atoi(argv[++i]);
                else throw std::runtime_error("Missing value for --cascade");
            } else if (arg == "-p" || arg == "--privacy") {
                if (i + 1 < argc) config.privacy_amplification_factor = std::atof(argv[++i]);
                else throw std::runtime_error("Missing value for --privacy");
            } else if (arg == "-f" || arg == "--fraction") {
                if (i + 1 < argc) config.test_key_fraction = std::atof(argv[++i]);
                else throw std::runtime_error("Missing value for --fraction");
            } else if (arg == "-o" || arg == "--output") {
                if (i + 1 < argc) config.output_csv = argv[++i];
                else throw std::runtime_error("Missing value for --output");
            } else if (arg == "-s" || arg == "--seed") {
                if (i + 1 < argc) config.random_seed = std::stoull(argv[++i]);
                else throw std::runtime_error("Missing value for --seed");
            } else if (arg == "-v" || arg == "--verbose") {
                config.verbose = true;
            } else if (arg == "--protocol") {
                if (i + 1 < argc) config.protocol_type = parseProtocolType(argv[++i]);
                else throw std::runtime_error("Missing value for --protocol");
            } else if (arg == "--fiber-length") {
                if (i + 1 < argc) config.fiber_length_km = std::atof(argv[++i]);
                else throw std::runtime_error("Missing value for --fiber-length");
            } else if (arg == "--fiber-atten") {
                if (i + 1 < argc) config.fiber_attenuation = std::atof(argv[++i]);
                else throw std::runtime_error("Missing value for --fiber-atten");
            } else if (arg == "--fiber-disp") {
                if (i + 1 < argc) config.fiber_dispersion = std::atof(argv[++i]);
                else throw std::runtime_error("Missing value for --fiber-disp");
            } else if (arg == "--fiber-nonlin") {
                if (i + 1 < argc) config.fiber_nonlinear = std::atof(argv[++i]);
                else throw std::runtime_error("Missing value for --fiber-nonlin");
            } else if (arg == "--decoy") {
                config.use_decoy_states = true;
            } else if (arg == "--no-fiber-model") {
                config.use_fiber_model = false;
            } else {
                throw std::invalid_argument("Unknown option: " + arg);
            }
        }
        
        if (config.fiber_length_km > 0 && config.use_fiber_model) {
            config.fiber_params.length_km = config.fiber_length_km;
            config.fiber_params.attenuation_coeff = config.fiber_attenuation;
            config.fiber_params.dispersion_coeff = config.fiber_dispersion;
            config.fiber_params.nonlinear_coeff = config.fiber_nonlinear;
        }
    } catch (const std::exception& e) {
        std::cerr << "Error parsing arguments: " << e.what() << "\n";
        printUsage(argv[0]);
        return 1;
    }
    
    if (config.num_photons <= 0) {
        std::cerr << "Error: Number of photons must be positive\n";
        return 1;
    }
    if (config.num_runs <= 0) {
        std::cerr << "Error: Number of runs must be positive\n";
        return 1;
    }
    if (config.channel_loss_rate < 0 || config.channel_loss_rate > 1) {
        std::cerr << "Error: Channel loss rate must be between 0 and 1\n";
        return 1;
    }
    if (config.dark_count_prob < 0 || config.dark_count_prob > 1) {
        std::cerr << "Error: Dark count probability must be between 0 and 1\n";
        return 1;
    }
    if (config.eavesdropping_strength < 0 || config.eavesdropping_strength > 1) {
        std::cerr << "Error: Eavesdropping strength must be between 0 and 1\n";
        return 1;
    }
    
    std::cout << "\n========================================\n";
    std::cout << "QKD Protocol Simulator\n";
    std::cout << "========================================\n";
    std::cout << "Configuration:\n";
    std::cout << "  Protocol: " << bb84::utils::protocolTypeToString(config.protocol_type) << "\n";
    std::cout << "  Photons per run: " << config.num_photons << "\n";
    std::cout << "  Number of runs: " << config.num_runs << "\n";
    std::cout << "  Attack type: " << bb84::utils::attackTypeToString(config.attack_type) << "\n";
    std::cout << "  Eavesdropping strength: " << config.eavesdropping_strength << "\n";
    std::cout << "  Channel loss rate: " << config.channel_loss_rate << "\n";
    std::cout << "  Dark count prob: " << config.dark_count_prob << "\n";
    std::cout << "  QBER threshold: " << config.qber_threshold << "\n";
    std::cout << "  Decoy states: " << (config.use_decoy_states ? "Enabled" : "Disabled") << "\n";
    if (config.fiber_length_km > 0 && config.use_fiber_model) {
        std::cout << "  Fiber model: Enabled (" << config.fiber_length_km << " km)\n";
        std::cout << "    Attenuation: " << config.fiber_attenuation << " dB/km\n";
        std::cout << "    Dispersion: " << config.fiber_dispersion << " ps/nm/km\n";
        std::cout << "    Nonlinear: " << config.fiber_nonlinear << " 1/W/km\n";
    } else {
        std::cout << "  Fiber model: Disabled\n";
    }
    std::cout << "========================================\n\n";
    
    bb84::BB84Protocol protocol(config);
    bb84::Statistics stats;
    
    std::cout << "Running simulation...\n";
    for (int run = 0; run < config.num_runs; ++run) {
        if (!config.verbose) {
            bb84::utils::printProgressBar(run + 1, config.num_runs);
        }
        
        bb84::RunResult result = protocol.runSingleRun(run + 1);
        stats.addRun(result);
        
        if (config.verbose) {
            std::cout << "Run " << (run + 1) << "/" << config.num_runs 
                      << ": QBER=" << result.qber 
                      << ", FinalKey=" << result.final_key_length
                      << ", EveDetected=" << (result.eavesdropping_detected ? "YES" : "no");
            if (result.decoy_result.decoy_enabled) {
                std::cout << ", SinglePhotonYield=" << result.decoy_result.estimated_single_photon_count;
            }
            if (result.protocol_type == ProtocolType::MDI_QKD) {
                std::cout << ", Visibility=" << result.mdi_result.interference_visibility;
            }
            std::cout << "\n";
        }
    }
    
    std::cout << "\n\nSimulation complete!\n";
    
    stats.printTerminalTable(config);
    stats.printSummaryTable(config);
    
    std::cout << "Exporting results to CSV...\n";
    if (stats.exportToCSV(config.output_csv, config)) {
        std::cout << "  Detailed results saved to: " << config.output_csv << "\n";
    } else {
        std::cerr << "  Failed to export detailed results!\n";
    }
    
    std::string summary_file = "summary_" + config.output_csv;
    if (stats.exportSummaryToCSV(summary_file, config)) {
        std::cout << "  Summary results saved to: " << summary_file << "\n";
    } else {
        std::cerr << "  Failed to export summary!\n";
    }
    
    std::cout << "\nDone!\n";
    
    return 0;
}
