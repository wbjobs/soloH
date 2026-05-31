#include "boolean_network.h"
#include <iostream>
#include <fstream>
#include <string>
#include <cstdlib>
#include <chrono>
#include <iomanip>

void print_usage(const char* prog_name) {
    std::cout << "Boolean Network Analysis Tool" << std::endl;
    std::cout << "Usage: " << prog_name << " [OPTIONS] <network_file>" << std::endl;
    std::cout << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -s, --starts <N>       Number of random starts for attractor search (default: 1000)" << std::endl;
    std::cout << "  -m, --max-steps <N>    Max steps per trajectory (default: 1000000)" << std::endl;
    std::cout << "  -b, --basin-samples <N>  Samples for basin size estimation (default: 10000)" << std::endl;
    std::cout << "  -p, --perturb <N>      Number of state flips for perturbation analysis (default: 0)" << std::endl;
    std::cout << "  -l, --landscape <N>    Number of samples for Waddington landscape (default: 0)" << std::endl;
    std::cout << "  -o, --output <FILE>    Output file for landscape data (default: landscape.txt)" << std::endl;
    std::cout << "  --seed <N>             Random seed (default: random)" << std::endl;
    std::cout << "  --deterministic        Use deterministic update order (default)" << std::endl;
    std::cout << "  --stochastic           Use stochastic (random) update order" << std::endl;
    std::cout << "  --sync                 Use synchronous update mode" << std::endl;
    std::cout << "  --hybrid <P>           Use hybrid update mode with sync probability P (0.0-1.0)" << std::endl;
    std::cout << "  --scc                  Compute Strongly Connected Components and reduce network" << std::endl;
    std::cout << "  --knockout <NAME>      Simulate knockout of a specific node" << std::endl;
    std::cout << "  --overexpress <NAME>   Simulate overexpression of a specific node" << std::endl;
    std::cout << "  --robustness           Analyze robustness for all nodes (knockout + overexpression)" << std::endl;
    std::cout << "  -v, --verbose          Verbose output" << std::endl;
    std::cout << "  -h, --help             Show this help message" << std::endl;
    std::cout << std::endl;
    std::cout << "Input file format:" << std::endl;
    std::cout << "  [Nodes]" << std::endl;
    std::cout << "  <num_nodes>" << std::endl;
    std::cout << "  node_name1, RPN_expression1" << std::endl;
    std::cout << "  node_name2, RPN_expression2" << std::endl;
    std::cout << "  ..." << std::endl;
    std::cout << "  [Edges]" << std::endl;
    std::cout << "  from_node, to_node" << std::endl;
    std::cout << "  ..." << std::endl;
    std::cout << "  [Functions]" << std::endl;
    std::cout << "  node_name, RPN_expression" << std::endl;
    std::cout << "  ..." << std::endl;
    std::cout << std::endl;
    std::cout << "RPN operators supported: AND(&), OR(|), NOT(!), XOR(^), NAND, NOR" << std::endl;
    std::cout << "Constants: 0, 1, TRUE, FALSE" << std::endl;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }
    
    std::string network_file;
    size_t num_starts = 1000;
    size_t max_steps = 1000000;
    size_t basin_samples = 10000;
    size_t perturb_flips = 0;
    size_t landscape_samples = 0;
    std::string landscape_output = "landscape.txt";
    unsigned int seed = 0;
    bool use_seed = false;
    bool verbose = false;
    bool deterministic = true;
    bool sync_mode = false;
    bool hybrid_mode = false;
    double sync_probability = 0.5;
    bool compute_scc = false;
    std::string knockout_node;
    std::string overexpress_node;
    bool analyze_robustness = false;
    
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-h" || arg == "--help") {
            print_usage(argv[0]);
            return 0;
        } else if (arg == "-s" || arg == "--starts") {
            if (i + 1 < argc) num_starts = std::stoul(argv[++i]);
        } else if (arg == "-m" || arg == "--max-steps") {
            if (i + 1 < argc) max_steps = std::stoul(argv[++i]);
        } else if (arg == "-b" || arg == "--basin-samples") {
            if (i + 1 < argc) basin_samples = std::stoul(argv[++i]);
        } else if (arg == "-p" || arg == "--perturb") {
            if (i + 1 < argc) perturb_flips = std::stoul(argv[++i]);
        } else if (arg == "-l" || arg == "--landscape") {
            if (i + 1 < argc) landscape_samples = std::stoul(argv[++i]);
        } else if (arg == "-o" || arg == "--output") {
            if (i + 1 < argc) landscape_output = argv[++i];
        } else if (arg == "--seed") {
            if (i + 1 < argc) {
                seed = std::stoul(argv[++i]);
                use_seed = true;
            }
        } else if (arg == "--deterministic") {
            deterministic = true;
        } else if (arg == "--stochastic") {
            deterministic = false;
        } else if (arg == "--sync") {
            sync_mode = true;
            hybrid_mode = false;
        } else if (arg == "--hybrid") {
            if (i + 1 < argc) {
                hybrid_mode = true;
                sync_mode = false;
                sync_probability = std::stod(argv[++i]);
            }
        } else if (arg == "--scc") {
            compute_scc = true;
        } else if (arg == "--knockout") {
            if (i + 1 < argc) {
                knockout_node = argv[++i];
            }
        } else if (arg == "--overexpress") {
            if (i + 1 < argc) {
                overexpress_node = argv[++i];
            }
        } else if (arg == "--robustness") {
            analyze_robustness = true;
        } else if (arg == "-v" || arg == "--verbose") {
            verbose = true;
        } else if (arg[0] != '-') {
            network_file = arg;
        }
    }
    
    if (network_file.empty()) {
        std::cerr << "Error: No network file specified." << std::endl;
        print_usage(argv[0]);
        return 1;
    }
    
    try {
        auto t_start = std::chrono::high_resolution_clock::now();
        
        if (verbose) {
            std::cout << "Loading network from: " << network_file << std::endl;
        }
        
        auto network = bn::BooleanNetwork::from_file(network_file);
        
        if (verbose) {
            std::cout << "Network loaded successfully:" << std::endl;
            std::cout << "  Number of nodes: " << network->num_nodes() << std::endl;
            std::cout << "  Number of edges: " << network->edges().size() << std::endl;
            std::cout << "  Nodes:" << std::endl;
            for (const auto& node : network->nodes()) {
                std::cout << "    " << node.name << " <- " << node.function.to_string() << std::endl;
            }
        }
        
        if (use_seed) {
            std::mt19937 rng(seed);
            std::vector<bn::State> states;
            for (size_t i = 0; i < 100; ++i) {
                states.push_back(network->random_state(rng));
            }
        }
        
        if (compute_scc) {
            std::cout << "\n=== Strongly Connected Components Analysis ===" << std::endl;
            auto scc_result = bn::NetworkReducer::compute_scc(*network);
            bn::NetworkReducer::print_scc(scc_result, *network);
            
            if (scc_result.num_components < network->num_nodes()) {
                std::cout << "\n=== Reduced Network (SCC condensation) ===" << std::endl;
                auto reduced_net = bn::NetworkReducer::reduce(*network, scc_result);
                std::cout << "Reduced nodes: " << reduced_net->num_nodes() << std::endl;
                std::cout << "Reduced edges: " << reduced_net->edges().size() << std::endl;
                for (const auto& node : reduced_net->nodes()) {
                    std::cout << "  " << node.name << " <- " << node.function.to_string() << std::endl;
                }
            }
        }
        
        std::vector<bn::Attractor> attractors;
        
        std::string mode_str = "deterministic asynchronous";
        if (sync_mode) mode_str = "synchronous";
        else if (hybrid_mode) mode_str = "hybrid (p=" + std::to_string(sync_probability) + ")";
        else if (!deterministic) mode_str = "stochastic asynchronous";
        
        if (!sync_mode && !hybrid_mode) {
            bn::AttractorSearch search(*network);
            
            if (verbose) {
                std::cout << "\nSearching for attractors with " << num_starts << " random starts..." << std::endl;
                std::cout << "Update mode: " << mode_str << std::endl;
            }
            
            auto t_search_start = std::chrono::high_resolution_clock::now();
            attractors = deterministic ?
                search.search_all_attractors_deterministic(num_starts, max_steps) :
                search.search_all_attractors(num_starts, max_steps);
            auto t_search_end = std::chrono::high_resolution_clock::now();
            
            if (verbose) {
                std::chrono::duration<double> elapsed = t_search_end - t_search_start;
                std::cout << "Found " << attractors.size() << " attractors in " 
                          << std::fixed << std::setprecision(3) << elapsed.count() << "s" << std::endl;
            }
            
            if (basin_samples > 0 && !attractors.empty()) {
                if (verbose) {
                    std::cout << "\nEstimating basin sizes with " << basin_samples << " samples..." << std::endl;
                }
                search.compute_basin_sizes(attractors, basin_samples, deterministic);
            }
            
            std::cout << "\n=== Attractor Analysis Results ===" << std::endl;
            std::cout << "Update mode: " << mode_str << std::endl;
            std::cout << "Total unique attractors found: " << attractors.size() << std::endl;
            std::cout << "Total visited states: " << search.get_visited().size() << std::endl;
            std::cout << std::endl;
            
            for (size_t i = 0; i < attractors.size(); ++i) {
                const auto& attr = attractors[i];
                std::cout << "--- Attractor " << i << " ---" << std::endl;
                std::string type_str;
                switch (attr.type) {
                    case bn::Attractor::FIXED_POINT: type_str = "Fixed Point"; break;
                    case bn::Attractor::LIMIT_CYCLE: type_str = "Limit Cycle"; break;
                    case bn::Attractor::TRAP_STATE:  type_str = "Trap State"; break;
                }
                std::cout << "Type: " << type_str << std::endl;
                std::cout << "Length: " << attr.length << std::endl;
                std::cout << "Basin size (estimated): " << attr.basin_size;
                if (basin_samples > 0) {
                    double pct = 100.0 * attr.basin_size / basin_samples;
                    std::cout << " (" << std::fixed << std::setprecision(2) << pct << "%)";
                }
                std::cout << std::endl;
                std::cout << "States:" << std::endl;
                for (size_t j = 0; j < attr.states.size(); ++j) {
                    std::cout << "  [" << j << "] " << network->state_to_string(attr.states[j]);
                    if (attr.type == bn::Attractor::LIMIT_CYCLE) {
                        std::cout << " -> [" << (j + 1) % attr.length << "]";
                    }
                    std::cout << std::endl;
                }
                std::cout << std::endl;
            }
        } else {
            bn::HybridAttractorSearch hybrid_search(*network, sync_mode ? 1.0 : sync_probability);
            
            if (verbose) {
                std::cout << "\nSearching for attractors with " << num_starts << " random starts..." << std::endl;
                std::cout << "Update mode: " << mode_str << std::endl;
            }
            
            auto t_search_start = std::chrono::high_resolution_clock::now();
            attractors = hybrid_search.search_all_attractors(num_starts, max_steps, deterministic);
            auto t_search_end = std::chrono::high_resolution_clock::now();
            
            if (verbose) {
                std::chrono::duration<double> elapsed = t_search_end - t_search_start;
                std::cout << "Found " << attractors.size() << " attractors in " 
                          << std::fixed << std::setprecision(3) << elapsed.count() << "s" << std::endl;
            }
            
            if (basin_samples > 0 && !attractors.empty()) {
                if (verbose) {
                    std::cout << "\nEstimating basin sizes with " << basin_samples << " samples..." << std::endl;
                }
                hybrid_search.compute_basin_sizes(attractors, basin_samples, deterministic);
            }
            
            std::cout << "\n=== Attractor Analysis Results ===" << std::endl;
            std::cout << "Update mode: " << mode_str << std::endl;
            std::cout << "Total unique attractors found: " << attractors.size() << std::endl;
            std::cout << std::endl;
            
            for (size_t i = 0; i < attractors.size(); ++i) {
                const auto& attr = attractors[i];
                std::cout << "--- Attractor " << i << " ---" << std::endl;
                std::string type_str;
                switch (attr.type) {
                    case bn::Attractor::FIXED_POINT: type_str = "Fixed Point"; break;
                    case bn::Attractor::LIMIT_CYCLE: type_str = "Limit Cycle"; break;
                    case bn::Attractor::TRAP_STATE:  type_str = "Trap State"; break;
                }
                std::cout << "Type: " << type_str << std::endl;
                std::cout << "Length: " << attr.length << std::endl;
                std::cout << "Basin size (estimated): " << attr.basin_size;
                if (basin_samples > 0) {
                    double pct = 100.0 * attr.basin_size / basin_samples;
                    std::cout << " (" << std::fixed << std::setprecision(2) << pct << "%)";
                }
                std::cout << std::endl;
                std::cout << "States:" << std::endl;
                for (size_t j = 0; j < attr.states.size(); ++j) {
                    std::cout << "  [" << j << "] " << network->state_to_string(attr.states[j]);
                    if (attr.type == bn::Attractor::LIMIT_CYCLE) {
                        std::cout << " -> [" << (j + 1) % attr.length << "]";
                    }
                    std::cout << std::endl;
                }
                std::cout << std::endl;
            }
        }
        
        if (!knockout_node.empty() || !overexpress_node.empty() || analyze_robustness) {
            bn::RobustnessAnalysis robustness(*network);
            robustness.set_original_attractors(attractors);
            
            if (!knockout_node.empty()) {
                auto& name_map = network->get_name_map();
                if (name_map.count(knockout_node)) {
                    size_t idx = name_map.at(knockout_node);
                    std::cout << "\n=== Single Node Knockout: " << knockout_node << " ===" << std::endl;
                    auto result = robustness.simulate_knockout(idx, num_starts, deterministic);
                    
                    std::cout << "Attractor preservation rate: " << std::fixed << std::setprecision(2)
                              << (result.attractor_preservation_rate * 100) << "%" << std::endl;
                    std::cout << "Basin similarity: " << std::fixed << std::setprecision(2)
                              << (result.basin_similarity * 100) << "%" << std::endl;
                    std::cout << "Number of attractors: " << result.attractors.size() << std::endl;
                    for (size_t i = 0; i < result.attractors.size(); ++i) {
                        std::cout << "  [" << i << "] " << network->state_to_string(result.attractors[i].states[0])
                                  << " (basin: " << result.attractors[i].basin_size << ")" << std::endl;
                    }
                } else {
                    std::cerr << "Error: Node '" << knockout_node << "' not found in network." << std::endl;
                }
            }
            
            if (!overexpress_node.empty()) {
                auto& name_map = network->get_name_map();
                if (name_map.count(overexpress_node)) {
                    size_t idx = name_map.at(overexpress_node);
                    std::cout << "\n=== Single Node Overexpression: " << overexpress_node << " ===" << std::endl;
                    auto result = robustness.simulate_overexpression(idx, num_starts, deterministic);
                    
                    std::cout << "Attractor preservation rate: " << std::fixed << std::setprecision(2)
                              << (result.attractor_preservation_rate * 100) << "%" << std::endl;
                    std::cout << "Basin similarity: " << std::fixed << std::setprecision(2)
                              << (result.basin_similarity * 100) << "%" << std::endl;
                    std::cout << "Number of attractors: " << result.attractors.size() << std::endl;
                    for (size_t i = 0; i < result.attractors.size(); ++i) {
                        std::cout << "  [" << i << "] " << network->state_to_string(result.attractors[i].states[0])
                                  << " (basin: " << result.attractors[i].basin_size << ")" << std::endl;
                    }
                } else {
                    std::cerr << "Error: Node '" << overexpress_node << "' not found in network." << std::endl;
                }
            }
            
            if (analyze_robustness) {
                std::cout << "\n=== Full Robustness Analysis ===" << std::endl;
                std::cout << "\n--- Node Knockout Results ---" << std::endl;
                auto ko_results = robustness.analyze_all_knockouts(num_starts, deterministic);
                
                std::cout << std::setw(15) << "Node" << std::setw(20) << "Preservation (%)" 
                          << std::setw(20) << "Basin Sim (%)" << std::endl;
                std::cout << std::string(55, '-') << std::endl;
                for (const auto& r : ko_results) {
                    std::cout << std::setw(15) << r.node_name
                              << std::setw(15) << std::fixed << std::setprecision(2) 
                              << (r.attractor_preservation_rate * 100)
                              << std::setw(15) << std::fixed << std::setprecision(2)
                              << (r.basin_similarity * 100) << std::endl;
                }
                
                std::cout << "\n--- Node Overexpression Results ---" << std::endl;
                auto oe_results = robustness.analyze_all_overexpressions(num_starts, deterministic);
                
                std::cout << std::setw(15) << "Node" << std::setw(20) << "Preservation (%)"
                          << std::setw(20) << "Basin Sim (%)" << std::endl;
                std::cout << std::string(55, '-') << std::endl;
                for (const auto& r : oe_results) {
                    std::cout << std::setw(15) << r.node_name
                              << std::setw(15) << std::fixed << std::setprecision(2)
                              << (r.attractor_preservation_rate * 100)
                              << std::setw(15) << std::fixed << std::setprecision(2)
                              << (r.basin_similarity * 100) << std::endl;
                }
                
                double avg_ko_pres = 0, avg_ko_sim = 0;
                double avg_oe_pres = 0, avg_oe_sim = 0;
                for (const auto& r : ko_results) {
                    avg_ko_pres += r.attractor_preservation_rate;
                    avg_ko_sim += r.basin_similarity;
                }
                for (const auto& r : oe_results) {
                    avg_oe_pres += r.attractor_preservation_rate;
                    avg_oe_sim += r.basin_similarity;
                }
                avg_ko_pres /= ko_results.size();
                avg_ko_sim /= ko_results.size();
                avg_oe_pres /= oe_results.size();
                avg_oe_sim /= oe_results.size();
                
                std::cout << std::string(55, '-') << std::endl;
                std::cout << std::setw(15) << "AVERAGE"
                          << std::setw(15) << std::fixed << std::setprecision(2) << (avg_ko_pres * 100)
                          << std::setw(15) << std::fixed << std::setprecision(2) << (avg_ko_sim * 100) << std::endl;
                std::cout << std::setw(15) << "AVERAGE (OE)"
                          << std::setw(15) << std::fixed << std::setprecision(2) << (avg_oe_pres * 100)
                          << std::setw(15) << std::fixed << std::setprecision(2) << (avg_oe_sim * 100) << std::endl;
            }
        }
        
        if (perturb_flips > 0 && !attractors.empty()) {
            std::cout << "\n=== Perturbation Analysis ===" << std::endl;
            std::cout << "Perturbation: flip " << perturb_flips << " random bits" << std::endl;
            std::mt19937 rng(use_seed ? seed : std::random_device{}());
            
            for (size_t i = 0; i < attractors.size(); ++i) {
                const auto& attr = attractors[i];
                const auto& original_state = attr.states[0];
                
                size_t stay_count = 0;
                size_t switch_count = 0;
                const size_t trials = 1000;
                
                for (size_t t = 0; t < trials; ++t) {
                    auto perturbed = search.perturb(original_state, perturb_flips, rng);
                    auto result_attr = search.find_attractor_from(perturbed);
                    
                    bool stays = false;
                    bn::StateEqual eq;
                    for (const auto& s : attr.states) {
                        for (const auto& rs : result_attr.states) {
                            if (eq(s, rs)) {
                                stays = true;
                                break;
                            }
                        }
                        if (stays) break;
                    }
                    
                    if (stays) stay_count++;
                    else switch_count++;
                }
                
                std::cout << "Attractor " << i << ": " << stay_count << "/" << trials 
                          << " stay, " << switch_count << "/" << trials << " switch" << std::endl;
            }
        }
        
        if (landscape_samples > 0 && !attractors.empty()) {
            if (verbose) {
                std::cout << "\nComputing Waddington landscape with " << landscape_samples << " samples..." << std::endl;
            }
            
            bn::WaddingtonLandscape landscape(*network, attractors);
            landscape.compute_landscape(landscape_samples, 100);
            
            if (verbose) {
                std::cout << "Saving landscape data to: " << landscape_output << std::endl;
            }
            landscape.save_to_hdf5(landscape_output);
            
            const auto& pots = landscape.get_potentials();
            double min_pot = 1e18, max_pot = -1e18, avg_pot = 0;
            for (double p : pots) {
                min_pot = std::min(min_pot, p);
                max_pot = std::max(max_pot, p);
                avg_pot += p;
            }
            avg_pot /= pots.size();
            
            std::cout << "\n=== Waddington Landscape Summary ===" << std::endl;
            std::cout << "Samples: " << landscape_samples << std::endl;
            std::cout << "Potential range: [" << min_pot << ", " << max_pot << "]" << std::endl;
            std::cout << "Average potential: " << avg_pot << std::endl;
            std::cout << "Output file: " << landscape_output << std::endl;
        }
        
        auto t_end = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> total_elapsed = t_end - t_start;
        std::cout << "\nTotal analysis time: " << std::fixed << std::setprecision(3) 
                  << total_elapsed.count() << "s" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}
