#ifndef BOOLEAN_NETWORK_H
#define BOOLEAN_NETWORK_H

#include <vector>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <random>
#include <functional>
#include <memory>
#include <stack>
#include <queue>
#include <set>

namespace bn {

using State = std::vector<bool>;

struct StateHash {
    size_t operator()(const State& s) const noexcept;
};

struct StateEqual {
    bool operator()(const State& a, const State& b) const noexcept;
};

using StateMap = std::unordered_map<State, size_t, StateHash, StateEqual>;
using StateSet = std::unordered_set<State, StateHash, StateEqual>;

enum class UpdateMode {
    ASYNCHRONOUS,
    ASYNCHRONOUS_DETERMINISTIC,
    SYNCHRONOUS,
    HYBRID
};

struct RPNToken {
    enum Type { OPERAND, OPERATOR, NODE };
    Type type;
    bool value;
    char op;
    size_t node_idx;
};

class BooleanFunction {
public:
    BooleanFunction() = default;
    explicit BooleanFunction(const std::string& rpn_expr, 
                           const std::unordered_map<std::string, size_t>& name_to_idx);
    
    bool evaluate(const State& state) const;
    const std::vector<RPNToken>& get_tokens() const { return tokens_; }
    std::string to_string() const;
    
private:
    std::vector<RPNToken> tokens_;
    void parse(const std::string& rpn_expr, 
               const std::unordered_map<std::string, size_t>& name_to_idx);
};

struct Node {
    size_t index;
    std::string name;
    BooleanFunction function;
    std::vector<size_t> regulators;
};

class BooleanNetwork {
public:
    BooleanNetwork() = default;
    
    static std::unique_ptr<BooleanNetwork> from_file(const std::string& filename);
    
    size_t num_nodes() const { return nodes_.size(); }
    const Node& node(size_t i) const { return nodes_[i]; }
    const std::vector<Node>& nodes() const { return nodes_; }
    const std::vector<std::pair<size_t, size_t>>& edges() const { return edges_; }
    
    State create_state() const;
    State random_state(std::mt19937& rng) const;
    
    bool update_node(State& state, size_t node_idx) const;
    size_t async_update(State& state, std::mt19937& rng) const;
    size_t async_update_deterministic(State& state, size_t& round_counter) const;
    size_t sync_update(State& state) const;
    size_t hybrid_update(State& state, std::mt19937& rng, 
                         double sync_probability,
                         size_t& round_counter,
                         bool deterministic = true) const;
    
    std::string state_to_string(const State& state) const;
    State state_from_string(const std::string& str) const;
    
    const std::unordered_map<std::string, size_t>& get_name_map() const { return name_to_idx_; }
    
    std::unique_ptr<BooleanNetwork> clone() const;
    
private:
    std::vector<Node> nodes_;
    std::vector<std::pair<size_t, size_t>> edges_;
    std::unordered_map<std::string, size_t> name_to_idx_;
    
    void add_node(const std::string& name, const std::string& rpn_expr);
    void add_edge(size_t from, size_t to);
    void set_node_function(size_t idx, const BooleanFunction& func);
    
    friend class NetworkReducer;
    friend class RobustnessAnalysis;
};

struct Attractor {
    enum Type { FIXED_POINT, LIMIT_CYCLE, TRAP_STATE };
    Type type;
    std::vector<State> states;
    size_t length;
    size_t basin_size;
};

class AttractorSearch {
public:
    explicit AttractorSearch(const BooleanNetwork& network);
    
    Attractor find_attractor_from(State state, size_t max_steps = 1000000);
    Attractor find_attractor_from_deterministic(State state, size_t max_steps = 1000000);
    std::vector<Attractor> search_all_attractors(size_t num_random_starts = 1000, 
                                                 size_t max_steps = 1000000);
    std::vector<Attractor> search_all_attractors_deterministic(size_t num_random_starts = 1000, 
                                                               size_t max_steps = 1000000);
    
    void compute_basin_sizes(std::vector<Attractor>& attractors, 
                            size_t num_samples = 10000,
                            bool deterministic = true);
    
    State perturb(const State& state, size_t num_flips, std::mt19937& rng) const;
    
    const StateMap& get_visited() const { return visited_; }
    
private:
    const BooleanNetwork& network_;
    StateMap visited_;
    std::mt19937 rng_;
    
    size_t get_state_id(const State& state);
    bool is_trap_state(const State& state, size_t no_change_steps, size_t threshold) const;
    
    friend class RobustnessAnalysis;
};

struct SCCResult {
    std::vector<std::vector<size_t>> components;
    std::vector<size_t> node_to_component;
    std::vector<std::vector<size_t>> condensed_edges;
    size_t num_components;
};

class NetworkReducer {
public:
    static SCCResult compute_scc(const BooleanNetwork& network);
    static std::unique_ptr<BooleanNetwork> reduce(const BooleanNetwork& network, 
                                                  SCCResult& scc_result);
    
    static void print_scc(const SCCResult& scc, const BooleanNetwork& network);
    
private:
    static void tarjan(size_t u, 
                       size_t& index, 
                       std::stack<size_t>& stk,
                       std::vector<bool>& on_stack,
                       std::vector<size_t>& idx,
                       std::vector<size_t>& low,
                       const std::vector<std::vector<size_t>>& adj,
                       SCCResult& result);
    
    static std::string generate_component_function(
        size_t comp_idx,
        const SCCResult& scc,
        const BooleanNetwork& original,
        const std::unordered_map<std::string, size_t>& new_name_map);
};

struct KnockoutResult {
    size_t node_idx;
    std::string node_name;
    std::vector<Attractor> attractors;
    double attractor_preservation_rate;
    double basin_similarity;
};

struct OverexpressionResult {
    size_t node_idx;
    std::string node_name;
    std::vector<Attractor> attractors;
    double attractor_preservation_rate;
    double basin_similarity;
};

class RobustnessAnalysis {
public:
    explicit RobustnessAnalysis(const BooleanNetwork& network);
    
    KnockoutResult simulate_knockout(size_t node_idx, 
                                     size_t num_starts = 500,
                                     bool deterministic = true);
    
    OverexpressionResult simulate_overexpression(size_t node_idx,
                                                 size_t num_starts = 500,
                                                 bool deterministic = true);
    
    std::vector<KnockoutResult> analyze_all_knockouts(size_t num_starts = 500,
                                                      bool deterministic = true);
    
    std::vector<OverexpressionResult> analyze_all_overexpressions(size_t num_starts = 500,
                                                                 bool deterministic = true);
    
    void set_original_attractors(const std::vector<Attractor>& attrs) { original_attractors_ = attrs; }
    
private:
    const BooleanNetwork& network_;
    std::vector<Attractor> original_attractors_;
    std::mt19937 rng_;
    
    double compute_attractor_preservation(const std::vector<Attractor>& perturbed) const;
    double compute_basin_similarity(const std::vector<Attractor>& perturbed) const;
    
    std::unique_ptr<BooleanNetwork> create_knockout_network(size_t node_idx) const;
    std::unique_ptr<BooleanNetwork> create_overexpression_network(size_t node_idx) const;
};

class HybridAttractorSearch {
public:
    HybridAttractorSearch(const BooleanNetwork& network, 
                          double sync_probability = 0.5);
    
    Attractor find_attractor_from(State state, 
                                  size_t max_steps = 1000000,
                                  bool deterministic = true);
    
    std::vector<Attractor> search_all_attractors(size_t num_random_starts = 1000,
                                                 size_t max_steps = 1000000,
                                                 bool deterministic = true);
    
    void compute_basin_sizes(std::vector<Attractor>& attractors,
                            size_t num_samples = 10000,
                            bool deterministic = true);
    
    void set_sync_probability(double p) { sync_probability_ = p; }
    
private:
    const BooleanNetwork& network_;
    double sync_probability_;
    StateMap visited_;
    std::mt19937 rng_;
    
    bool is_trap_state(const State& state, size_t no_change_steps, size_t threshold) const;
};

class WaddingtonLandscape {
public:
    WaddingtonLandscape(const BooleanNetwork& network, 
                        const std::vector<Attractor>& attractors);
    
    void compute_landscape(size_t num_samples = 10000, 
                          size_t steps_per_sample = 100);
    
    void save_to_hdf5(const std::string& filename) const;
    
    const std::vector<State>& get_sampled_states() const { return sampled_states_; }
    const std::vector<double>& get_potentials() const { return potentials_; }
    const std::vector<int>& get_attractor_labels() const { return attractor_labels_; }
    
private:
    const BooleanNetwork& network_;
    const std::vector<Attractor>& attractors_;
    std::mt19937 rng_;
    
    std::vector<State> sampled_states_;
    std::vector<double> potentials_;
    std::vector<int> attractor_labels_;
    
    double compute_potential(const State& state, size_t steps);
    int find_nearest_attractor(const State& state) const;
    double state_distance(const State& a, const State& b) const;
};

} 

#endif
