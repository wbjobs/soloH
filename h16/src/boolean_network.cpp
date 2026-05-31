#include "boolean_network.h"
#include <sstream>
#include <fstream>
#include <algorithm>
#include <stack>
#include <stdexcept>
#include <cctype>
#include <cmath>
#include <iostream>

#ifdef BN_WITH_HDF5
#include <H5Cpp.h>
#endif

namespace bn {

size_t StateHash::operator()(const State& s) const noexcept {
    size_t hash = s.size();
    for (size_t i = 0; i < s.size(); ++i) {
        hash ^= (static_cast<size_t>(s[i]) << (i % 64)) + 0x9e3779b9 + (hash << 6) + (hash >> 2);
    }
    return hash;
}

bool StateEqual::operator()(const State& a, const State& b) const noexcept {
    if (a.size() != b.size()) return false;
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i] != b[i]) return false;
    }
    return true;
}

static std::vector<std::string> tokenize(const std::string& s) {
    std::vector<std::string> tokens;
    std::string current;
    for (char c : s) {
        if (std::isspace(c)) {
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
        } else if (c == '&' || c == '|' || c == '!' || c == '(' || c == ')') {
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
            tokens.push_back(std::string(1, c));
        } else {
            current += c;
        }
    }
    if (!current.empty()) {
        tokens.push_back(current);
    }
    return tokens;
}

BooleanFunction::BooleanFunction(const std::string& rpn_expr, 
                                 const std::unordered_map<std::string, size_t>& name_to_idx) {
    parse(rpn_expr, name_to_idx);
}

void BooleanFunction::parse(const std::string& rpn_expr, 
                            const std::unordered_map<std::string, size_t>& name_to_idx) {
    tokens_.clear();
    auto tokens = tokenize(rpn_expr);
    
    for (const auto& tok : tokens) {
        if (tok == "AND" || tok == "&" || tok == "&&") {
            tokens_.push_back({RPNToken::OPERATOR, false, '&', 0});
        } else if (tok == "OR" || tok == "|" || tok == "||") {
            tokens_.push_back({RPNToken::OPERATOR, false, '|', 0});
        } else if (tok == "NOT" || tok == "!" || tok == "~") {
            tokens_.push_back({RPNToken::OPERATOR, false, '!', 0});
        } else if (tok == "XOR" || tok == "^") {
            tokens_.push_back({RPNToken::OPERATOR, false, '^', 0});
        } else if (tok == "NAND") {
            tokens_.push_back({RPNToken::OPERATOR, false, 'n', 0});
        } else if (tok == "NOR") {
            tokens_.push_back({RPNToken::OPERATOR, false, 'r', 0});
        } else if (tok == "1" || tok == "TRUE" || tok == "true" || tok == "T") {
            tokens_.push_back({RPNToken::OPERAND, true, 0, 0});
        } else if (tok == "0" || tok == "FALSE" || tok == "false" || tok == "F") {
            tokens_.push_back({RPNToken::OPERAND, false, 0, 0});
        } else {
            auto it = name_to_idx.find(tok);
            if (it == name_to_idx.end()) {
                throw std::runtime_error("Unknown node in RPN expression: " + tok);
            }
            tokens_.push_back({RPNToken::NODE, false, 0, it->second});
        }
    }
}

bool BooleanFunction::evaluate(const State& state) const {
    std::stack<bool> stk;
    
    for (const auto& tok : tokens_) {
        switch (tok.type) {
            case RPNToken::OPERAND:
                stk.push(tok.value);
                break;
            case RPNToken::NODE:
                stk.push(state[tok.node_idx]);
                break;
            case RPNToken::OPERATOR: {
                if (tok.op == '!') {
                    if (stk.empty()) throw std::runtime_error("Invalid RPN: not enough operands for NOT");
                    bool a = stk.top(); stk.pop();
                    stk.push(!a);
                } else {
                    if (stk.size() < 2) throw std::runtime_error("Invalid RPN: not enough operands");
                    bool b = stk.top(); stk.pop();
                    bool a = stk.top(); stk.pop();
                    switch (tok.op) {
                        case '&': stk.push(a && b); break;
                        case '|': stk.push(a || b); break;
                        case '^': stk.push(a != b); break;
                        case 'n': stk.push(!(a && b)); break;
                        case 'r': stk.push(!(a || b)); break;
                        default: throw std::runtime_error("Unknown operator");
                    }
                }
                break;
            }
        }
    }
    
    if (stk.size() != 1) throw std::runtime_error("Invalid RPN: stack size != 1 at end");
    return stk.top();
}

std::string BooleanFunction::to_string() const {
    std::string s;
    for (const auto& tok : tokens_) {
        if (!s.empty()) s += " ";
        switch (tok.type) {
            case RPNToken::OPERAND: s += tok.value ? "1" : "0"; break;
            case RPNToken::NODE: s += "x" + std::to_string(tok.node_idx); break;
            case RPNToken::OPERATOR:
                switch (tok.op) {
                    case '&': s += "AND"; break;
                    case '|': s += "OR"; break;
                    case '!': s += "NOT"; break;
                    case '^': s += "XOR"; break;
                    case 'n': s += "NAND"; break;
                    case 'r': s += "NOR"; break;
                }
                break;
        }
    }
    return s;
}

static std::vector<std::string> split(const std::string& s, char delim) {
    std::vector<std::string> parts;
    std::string current;
    for (char c : s) {
        if (c == delim) {
            if (!current.empty()) {
                parts.push_back(current);
                current.clear();
            }
        } else {
            current += c;
        }
    }
    if (!current.empty()) parts.push_back(current);
    return parts;
}

static std::string trim(const std::string& s) {
    size_t start = 0;
    while (start < s.size() && std::isspace(s[start])) ++start;
    size_t end = s.size();
    while (end > start && std::isspace(s[end - 1])) --end;
    return s.substr(start, end - start);
}

std::unique_ptr<BooleanNetwork> BooleanNetwork::from_file(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file: " + filename);
    }
    
    auto net = std::make_unique<BooleanNetwork>();
    
    std::vector<std::string> all_lines;
    std::string line;
    while (std::getline(file, line)) {
        all_lines.push_back(line);
    }
    
    std::vector<std::pair<std::string, std::string>> node_funcs;
    std::vector<std::pair<std::string, std::string>> edges;
    size_t expected_nodes = 0;
    
    enum class ParseMode { NODES, EDGES, FUNCTIONS };
    ParseMode mode = ParseMode::NODES;
    
    for (const auto& raw_line : all_lines) {
        std::string l = trim(raw_line);
        if (l.empty() || l[0] == '#') continue;
        
        if (l == "[Nodes]") {
            mode = ParseMode::NODES;
            continue;
        } else if (l == "[Edges]") {
            mode = ParseMode::EDGES;
            continue;
        } else if (l == "[Functions]") {
            mode = ParseMode::FUNCTIONS;
            continue;
        }
        
        if (mode == ParseMode::NODES) {
            if (expected_nodes == 0) {
                expected_nodes = std::stoul(l);
                continue;
            }
            auto parts = split(l, ',');
            if (parts.size() >= 2) {
                std::string name = trim(parts[0]);
                std::string rpn = trim(parts[1]);
                node_funcs.emplace_back(name, rpn);
            } else {
                node_funcs.emplace_back(trim(l), "");
            }
        } else if (mode == ParseMode::EDGES) {
            auto parts = split(l, ',');
            if (parts.size() >= 2) {
                edges.emplace_back(trim(parts[0]), trim(parts[1]));
            }
        } else if (mode == ParseMode::FUNCTIONS) {
            auto parts = split(l, ',');
            if (parts.size() >= 2) {
                std::string name = trim(parts[0]);
                std::string rpn = trim(parts[1]);
                for (auto& nf : node_funcs) {
                    if (nf.first == name) {
                        nf.second = rpn;
                        break;
                    }
                }
            }
        }
    }
    
    for (const auto& nf : node_funcs) {
        size_t idx = net->nodes_.size();
        net->name_to_idx_[nf.first] = idx;
        Node node{idx, nf.first, BooleanFunction(), {}};
        net->nodes_.push_back(node);
    }
    
    for (auto& nf : node_funcs) {
        if (!nf.second.empty()) {
            size_t idx = net->name_to_idx_[nf.first];
            net->nodes_[idx].function = BooleanFunction(nf.second, net->name_to_idx_);
        }
    }
    
    for (const auto& e : edges) {
        if (net->name_to_idx_.count(e.first) && net->name_to_idx_.count(e.second)) {
            net->add_edge(net->name_to_idx_[e.first], net->name_to_idx_[e.second]);
        }
    }
    
    if (net->nodes_.size() > 200) {
        throw std::runtime_error("Network exceeds maximum of 200 nodes");
    }
    
    return net;
}

void BooleanNetwork::add_node(const std::string& name, const std::string& rpn_expr) {
    size_t idx = nodes_.size();
    name_to_idx_[name] = idx;
    Node node{idx, name, BooleanFunction(rpn_expr, name_to_idx_), {}};
    nodes_.push_back(node);
}

void BooleanNetwork::add_edge(size_t from, size_t to) {
    edges_.emplace_back(from, to);
    if (std::find(nodes_[to].regulators.begin(), nodes_[to].regulators.end(), from) 
        == nodes_[to].regulators.end()) {
        nodes_[to].regulators.push_back(from);
    }
}

State BooleanNetwork::create_state() const {
    return State(nodes_.size(), false);
}

State BooleanNetwork::random_state(std::mt19937& rng) const {
    State s(nodes_.size());
    std::uniform_int_distribution<int> dist(0, 1);
    for (size_t i = 0; i < nodes_.size(); ++i) {
        s[i] = dist(rng) == 1;
    }
    return s;
}

bool BooleanNetwork::update_node(State& state, size_t node_idx) const {
    bool new_val = nodes_[node_idx].function.evaluate(state);
    bool old_val = state[node_idx];
    state[node_idx] = new_val;
    return old_val != new_val;
}

size_t BooleanNetwork::async_update(State& state, std::mt19937& rng) const {
    std::uniform_int_distribution<size_t> dist(0, nodes_.size() - 1);
    size_t idx = dist(rng);
    update_node(state, idx);
    return idx;
}

size_t BooleanNetwork::async_update_deterministic(State& state, size_t& round_counter) const {
    size_t n = nodes_.size();
    StateHash hasher;
    size_t state_hash = hasher(state);
    size_t idx = (state_hash + round_counter) % n;
    update_node(state, idx);
    round_counter++;
    return idx;
}

std::string BooleanNetwork::state_to_string(const State& state) const {
    std::string s;
    s.reserve(state.size());
    for (bool b : state) {
        s += b ? '1' : '0';
    }
    return s;
}

State BooleanNetwork::state_from_string(const std::string& str) const {
    State s(nodes_.size(), false);
    size_t n = std::min(str.size(), nodes_.size());
    for (size_t i = 0; i < n; ++i) {
        s[i] = (str[i] == '1');
    }
    return s;
}

AttractorSearch::AttractorSearch(const BooleanNetwork& network)
    : network_(network), rng_(std::random_device{}()) {}

size_t AttractorSearch::get_state_id(const State& state) {
    auto it = visited_.find(state);
    if (it != visited_.end()) {
        return it->second;
    }
    size_t id = visited_.size();
    visited_[state] = id;
    return id;
}

bool AttractorSearch::is_trap_state(const State& state, size_t no_change_steps, size_t threshold) const {
    size_t n = network_.num_nodes();
    size_t active_count = 0;
    for (bool b : state) {
        if (b) active_count++;
    }
    if (active_count == 0 || active_count == n) {
        return true;
    }
    if (no_change_steps > threshold * n) {
        return true;
    }
    return false;
}

Attractor AttractorSearch::find_attractor_from(State state, size_t max_steps) {
    std::vector<State> trajectory;
    StateMap state_pos;
    size_t no_change_steps = 0;
    State prev_state = state;
    const size_t trap_threshold = 100;
    
    for (size_t step = 0; step < max_steps; ++step) {
        auto it = state_pos.find(state);
        if (it != state_pos.end()) {
            size_t cycle_start = it->second;
            Attractor attr;
            if (cycle_start == trajectory.size() - 1) {
                attr.type = Attractor::FIXED_POINT;
                attr.length = 1;
                attr.states.push_back(state);
            } else {
                attr.type = Attractor::LIMIT_CYCLE;
                attr.length = trajectory.size() - cycle_start;
                for (size_t i = cycle_start; i < trajectory.size(); ++i) {
                    attr.states.push_back(trajectory[i]);
                }
            }
            attr.basin_size = 0;
            return attr;
        }
        
        StateEqual eq;
        if (eq(state, prev_state)) {
            no_change_steps++;
        } else {
            no_change_steps = 0;
            prev_state = state;
        }
        
        if (is_trap_state(state, no_change_steps, trap_threshold)) {
            Attractor attr;
            attr.type = Attractor::TRAP_STATE;
            attr.length = 0;
            attr.states.push_back(state);
            attr.basin_size = 0;
            return attr;
        }
        
        state_pos[state] = trajectory.size();
        trajectory.push_back(state);
        
        network_.async_update(state, rng_);
    }
    
    Attractor attr;
    attr.type = Attractor::TRAP_STATE;
    attr.length = 0;
    attr.states.push_back(state);
    attr.basin_size = 0;
    return attr;
}

Attractor AttractorSearch::find_attractor_from_deterministic(State state, size_t max_steps) {
    std::vector<State> trajectory;
    StateMap state_pos;
    size_t round_counter = 0;
    size_t no_change_steps = 0;
    State prev_state = state;
    const size_t trap_threshold = 100;
    
    for (size_t step = 0; step < max_steps; ++step) {
        auto it = state_pos.find(state);
        if (it != state_pos.end()) {
            size_t cycle_start = it->second;
            Attractor attr;
            if (cycle_start == trajectory.size() - 1) {
                attr.type = Attractor::FIXED_POINT;
                attr.length = 1;
                attr.states.push_back(state);
            } else {
                attr.type = Attractor::LIMIT_CYCLE;
                attr.length = trajectory.size() - cycle_start;
                for (size_t i = cycle_start; i < trajectory.size(); ++i) {
                    attr.states.push_back(trajectory[i]);
                }
            }
            attr.basin_size = 0;
            return attr;
        }
        
        StateEqual eq;
        if (eq(state, prev_state)) {
            no_change_steps++;
        } else {
            no_change_steps = 0;
            prev_state = state;
        }
        
        if (is_trap_state(state, no_change_steps, trap_threshold)) {
            Attractor attr;
            attr.type = Attractor::TRAP_STATE;
            attr.length = 0;
            attr.states.push_back(state);
            attr.basin_size = 0;
            return attr;
        }
        
        state_pos[state] = trajectory.size();
        trajectory.push_back(state);
        
        network_.async_update_deterministic(state, round_counter);
    }
    
    Attractor attr;
    attr.type = Attractor::TRAP_STATE;
    attr.length = 0;
    attr.states.push_back(state);
    attr.basin_size = 0;
    return attr;
}

static bool attractors_equal(const Attractor& a, const Attractor& b) {
    if (a.type != b.type || a.length != b.length || a.states.size() != b.states.size()) {
        return false;
    }
    StateEqual eq;
    for (const auto& sa : a.states) {
        bool found = false;
        for (const auto& sb : b.states) {
            if (eq(sa, sb)) {
                found = true;
                break;
            }
        }
        if (!found) return false;
    }
    return true;
}

std::vector<Attractor> AttractorSearch::search_all_attractors(size_t num_random_starts, 
                                                              size_t max_steps) {
    std::vector<Attractor> attractors;
    StateEqual eq;
    
    for (size_t i = 0; i < num_random_starts; ++i) {
        State s = network_.random_state(rng_);
        Attractor attr = find_attractor_from(s, max_steps);
        
        bool is_new = true;
        for (const auto& existing : attractors) {
            if (attractors_equal(existing, attr)) {
                is_new = false;
                break;
            }
        }
        
        if (is_new) {
            attractors.push_back(attr);
        }
    }
    
    return attractors;
}

std::vector<Attractor> AttractorSearch::search_all_attractors_deterministic(size_t num_random_starts, 
                                                                            size_t max_steps) {
    std::vector<Attractor> attractors;
    StateEqual eq;
    
    for (size_t i = 0; i < num_random_starts; ++i) {
        State s = network_.random_state(rng_);
        Attractor attr = find_attractor_from_deterministic(s, max_steps);
        
        bool is_new = true;
        for (const auto& existing : attractors) {
            if (attractors_equal(existing, attr)) {
                is_new = false;
                break;
            }
        }
        
        if (is_new) {
            attractors.push_back(attr);
        }
    }
    
    return attractors;
}

void AttractorSearch::compute_basin_sizes(std::vector<Attractor>& attractors, 
                                          size_t num_samples,
                                          bool deterministic) {
    std::vector<size_t> counts(attractors.size(), 0);
    StateEqual eq;
    
    for (size_t i = 0; i < num_samples; ++i) {
        State s = network_.random_state(rng_);
        Attractor attr = deterministic ? 
            find_attractor_from_deterministic(s) : 
            find_attractor_from(s);
        
        for (size_t j = 0; j < attractors.size(); ++j) {
            if (attractors_equal(attractors[j], attr)) {
                counts[j]++;
                break;
            }
        }
    }
    
    for (size_t j = 0; j < attractors.size(); ++j) {
        attractors[j].basin_size = counts[j];
    }
}

State AttractorSearch::perturb(const State& state, size_t num_flips, std::mt19937& rng) const {
    State result = state;
    size_t n = state.size();
    num_flips = std::min(num_flips, n);
    
    std::vector<size_t> indices(n);
    for (size_t i = 0; i < n; ++i) indices[i] = i;
    std::shuffle(indices.begin(), indices.end(), rng);
    
    for (size_t i = 0; i < num_flips; ++i) {
        result[indices[i]] = !result[indices[i]];
    }
    
    return result;
}

WaddingtonLandscape::WaddingtonLandscape(const BooleanNetwork& network, 
                                         const std::vector<Attractor>& attractors)
    : network_(network), attractors_(attractors), rng_(std::random_device{}()) {}

double WaddingtonLandscape::state_distance(const State& a, const State& b) const {
    double dist = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i] != b[i]) dist += 1.0;
    }
    return dist;
}

int WaddingtonLandscape::find_nearest_attractor(const State& state) const {
    int best_idx = -1;
    double best_dist = 1e18;
    
    for (size_t i = 0; i < attractors_.size(); ++i) {
        for (const auto& as : attractors_[i].states) {
            double d = state_distance(state, as);
            if (d < best_dist) {
                best_dist = d;
                best_idx = static_cast<int>(i);
            }
        }
    }
    
    return best_idx;
}

double WaddingtonLandscape::compute_potential(const State& state, size_t steps) {
    State s = state;
    double min_dist = 1e18;
    
    for (size_t i = 0; i < attractors_.size(); ++i) {
        for (const auto& as : attractors_[i].states) {
            double d = state_distance(s, as);
            if (d < min_dist) min_dist = d;
        }
    }
    
    for (size_t t = 0; t < steps; ++t) {
        network_.async_update(s, rng_);
        for (size_t i = 0; i < attractors_.size(); ++i) {
            for (const auto& as : attractors_[i].states) {
                double d = state_distance(s, as);
                if (d < min_dist) min_dist = d;
            }
        }
    }
    
    return min_dist;
}

void WaddingtonLandscape::compute_landscape(size_t num_samples, size_t steps_per_sample) {
    sampled_states_.clear();
    potentials_.clear();
    attractor_labels_.clear();
    
    for (size_t i = 0; i < num_samples; ++i) {
        State s = network_.random_state(rng_);
        sampled_states_.push_back(s);
        potentials_.push_back(compute_potential(s, steps_per_sample));
        attractor_labels_.push_back(find_nearest_attractor(s));
    }
}

void WaddingtonLandscape::save_to_hdf5(const std::string& filename) const {
#ifdef BN_WITH_HDF5
    using namespace H5;
    
    const uint64_t MAX_HDF5_DIM = 2147483647ULL;
    
    uint64_t n_states = static_cast<uint64_t>(sampled_states_.size());
    uint64_t n_nodes = static_cast<uint64_t>(network_.num_nodes());
    uint64_t n_attr = static_cast<uint64_t>(attractors_.size());
    
    if (n_states > MAX_HDF5_DIM || n_nodes > MAX_HDF5_DIM) {
        throw std::runtime_error("Dataset dimension exceeds HDF5 maximum (2^31-1)");
    }
    uint64_t total_elements = n_states * n_nodes;
    if (total_elements > MAX_HDF5_DIM) {
        throw std::runtime_error("Total dataset size exceeds HDF5 maximum (2^31-1). "
                                 "Reduce the number of samples or nodes.");
    }
    
    H5File file(filename, H5F_ACC_TRUNC);
    
    hsize_t dims_state[2] = {static_cast<hsize_t>(n_states), static_cast<hsize_t>(n_nodes)};
    DataSpace dspace_state(2, dims_state);
    DataSet dset_state = file.createDataSet("states", PredType::NATIVE_INT, dspace_state);
    
    std::vector<int> state_data(total_elements);
    for (uint64_t i = 0; i < n_states; ++i) {
        for (uint64_t j = 0; j < n_nodes; ++j) {
            uint64_t idx = i * n_nodes + j;
            state_data[idx] = sampled_states_[i][j] ? 1 : 0;
        }
    }
    dset_state.write(state_data.data(), PredType::NATIVE_INT);
    
    hsize_t dims_pot[1] = {static_cast<hsize_t>(n_states)};
    DataSpace dspace_pot(1, dims_pot);
    DataSet dset_pot = file.createDataSet("potentials", PredType::NATIVE_DOUBLE, dspace_pot);
    dset_pot.write(potentials_.data(), PredType::NATIVE_DOUBLE);
    
    DataSet dset_label = file.createDataSet("attractor_labels", PredType::NATIVE_INT, dspace_pot);
    dset_label.write(attractor_labels_.data(), PredType::NATIVE_INT);
    
    hsize_t dims_attr[1] = {static_cast<hsize_t>(n_attr)};
    DataSpace dspace_attr_info(1, dims_attr);
    DataSet dset_attr_len = file.createDataSet("attractor_lengths", PredType::NATIVE_UINT64, dspace_attr_info);
    DataSet dset_attr_basin = file.createDataSet("attractor_basin_sizes", PredType::NATIVE_UINT64, dspace_attr_info);
    
    std::vector<uint64_t> lengths, basins;
    lengths.reserve(n_attr);
    basins.reserve(n_attr);
    for (const auto& a : attractors_) {
        lengths.push_back(static_cast<uint64_t>(a.length));
        basins.push_back(static_cast<uint64_t>(a.basin_size));
    }
    dset_attr_len.write(lengths.data(), PredType::NATIVE_UINT64);
    dset_attr_basin.write(basins.data(), PredType::NATIVE_UINT64);
    
    DataSpace dspace_scalar(H5S_SCALAR);
    Attribute attr_n_nodes = file.createAttribute("num_nodes", PredType::NATIVE_UINT64, dspace_scalar);
    uint64_t n = n_nodes;
    attr_n_nodes.write(PredType::NATIVE_UINT64, &n);
    
    Attribute attr_n_attr = file.createAttribute("num_attractors", PredType::NATIVE_UINT64, dspace_scalar);
    uint64_t na = n_attr;
    attr_n_attr.write(PredType::NATIVE_UINT64, &na);
    
    file.close();
#else
    std::ofstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file for landscape output: " + filename);
    }
    
    size_t n_states = sampled_states_.size();
    size_t n_nodes = network_.num_nodes();
    
    file << "# Waddington Landscape Data" << std::endl;
    file << "# num_nodes: " << n_nodes << std::endl;
    file << "# num_states: " << n_states << std::endl;
    file << "# num_attractors: " << attractors_.size() << std::endl;
    file << "# attractor_info: length basin_size" << std::endl;
    for (size_t i = 0; i < attractors_.size(); ++i) {
        file << "# attractor " << i << ": " << attractors_[i].length << " " << attractors_[i].basin_size << std::endl;
    }
    file << "# Format: state potential attractor_label" << std::endl;
    
    for (size_t i = 0; i < n_states; ++i) {
        file << network_.state_to_string(sampled_states_[i]) << " " 
             << potentials_[i] << " " 
             << attractor_labels_[i] << std::endl;
    }
    file.close();
#endif
}

size_t BooleanNetwork::sync_update(State& state) const {
    State next_state(state.size());
    size_t changes = 0;
    
    for (size_t i = 0; i < nodes_.size(); ++i) {
        bool new_val = nodes_[i].function.evaluate(state);
        next_state[i] = new_val;
        if (new_val != state[i]) changes++;
    }
    
    state.swap(next_state);
    return changes;
}

size_t BooleanNetwork::hybrid_update(State& state, std::mt19937& rng,
                                     double sync_probability,
                                     size_t& round_counter,
                                     bool deterministic) const {
    std::bernoulli_distribution dist(sync_probability);
    
    if (dist(rng)) {
        return sync_update(state);
    } else {
        if (deterministic) {
            return async_update_deterministic(state, round_counter);
        } else {
            return async_update(state, rng);
        }
    }
}

std::unique_ptr<BooleanNetwork> BooleanNetwork::clone() const {
    auto net = std::make_unique<BooleanNetwork>();
    net->nodes_ = nodes_;
    net->edges_ = edges_;
    net->name_to_idx_ = name_to_idx_;
    return net;
}

void BooleanNetwork::set_node_function(size_t idx, const BooleanFunction& func) {
    if (idx < nodes_.size()) {
        nodes_[idx].function = func;
    }
}

SCCResult NetworkReducer::compute_scc(const BooleanNetwork& network) {
    SCCResult result;
    size_t n = network.num_nodes();
    
    std::vector<std::vector<size_t>> adj(n);
    for (const auto& e : network.edges()) {
        adj[e.first].push_back(e.second);
    }
    
    result.num_components = 0;
    result.node_to_component.resize(n, static_cast<size_t>(-1));
    
    size_t index = 0;
    std::stack<size_t> stk;
    std::vector<bool> on_stack(n, false);
    std::vector<size_t> idx(n, static_cast<size_t>(-1));
    std::vector<size_t> low(n, 0);
    
    for (size_t i = 0; i < n; ++i) {
        if (idx[i] == static_cast<size_t>(-1)) {
            tarjan(i, index, stk, on_stack, idx, low, adj, result);
        }
    }
    
    result.condensed_edges.resize(result.num_components);
    std::vector<std::set<size_t>> edge_set(result.num_components);
    
    for (const auto& e : network.edges()) {
        size_t from_comp = result.node_to_component[e.first];
        size_t to_comp = result.node_to_component[e.second];
        if (from_comp != to_comp) {
            edge_set[from_comp].insert(to_comp);
        }
    }
    
    for (size_t i = 0; i < result.num_components; ++i) {
        result.condensed_edges[i].assign(edge_set[i].begin(), edge_set[i].end());
    }
    
    return result;
}

void NetworkReducer::tarjan(size_t u,
                            size_t& index,
                            std::stack<size_t>& stk,
                            std::vector<bool>& on_stack,
                            std::vector<size_t>& idx,
                            std::vector<size_t>& low,
                            const std::vector<std::vector<size_t>>& adj,
                            SCCResult& result) {
    idx[u] = index;
    low[u] = index;
    index++;
    
    stk.push(u);
    on_stack[u] = true;
    
    for (size_t v : adj[u]) {
        if (idx[v] == static_cast<size_t>(-1)) {
            tarjan(v, index, stk, on_stack, idx, low, adj, result);
            low[u] = std::min(low[u], low[v]);
        } else if (on_stack[v]) {
            low[u] = std::min(low[u], idx[v]);
        }
    }
    
    if (low[u] == idx[u]) {
        std::vector<size_t> component;
        size_t comp_id = result.num_components++;
        
        while (true) {
            size_t v = stk.top();
            stk.pop();
            on_stack[v] = false;
            component.push_back(v);
            result.node_to_component[v] = comp_id;
            
            if (v == u) break;
        }
        
        result.components.push_back(component);
    }
}

std::unique_ptr<BooleanNetwork> NetworkReducer::reduce(const BooleanNetwork& network,
                                                       SCCResult& scc_result) {
    auto reduced = std::make_unique<BooleanNetwork>();
    size_t n_comp = scc_result.num_components;
    
    std::unordered_map<std::string, size_t> new_name_map;
    
    for (size_t i = 0; i < n_comp; ++i) {
        std::string name = "CMP_" + std::to_string(i);
        new_name_map[name] = i;
        reduced->add_node(name, "");
    }
    
    for (size_t i = 0; i < n_comp; ++i) {
        std::string func_rpn = generate_component_function(i, scc_result, network, new_name_map);
        reduced->nodes_[i].function = BooleanFunction(func_rpn, new_name_map);
    }
    
    for (size_t i = 0; i < n_comp; ++i) {
        for (size_t j : scc_result.condensed_edges[i]) {
            reduced->add_edge(i, j);
        }
    }
    
    return reduced;
}

std::string NetworkReducer::generate_component_function(
    size_t comp_idx,
    const SCCResult& scc,
    const BooleanNetwork& original,
    const std::unordered_map<std::string, size_t>& new_name_map) {
    
    const auto& comp = scc.components[comp_idx];
    size_t rep_node = comp[0];
    
    const auto& original_func = original.node(rep_node).function;
    const auto& tokens = original_func.get_tokens();
    
    std::string rpn;
    for (const auto& tok : tokens) {
        if (!rpn.empty()) rpn += " ";
        
        switch (tok.type) {
            case RPNToken::OPERAND:
                rpn += tok.value ? "1" : "0";
                break;
            case RPNToken::OPERATOR:
                switch (tok.op) {
                    case '&': rpn += "AND"; break;
                    case '|': rpn += "OR"; break;
                    case '!': rpn += "NOT"; break;
                    case '^': rpn += "XOR"; break;
                    case 'n': rpn += "NAND"; break;
                    case 'r': rpn += "NOR"; break;
                }
                break;
            case RPNToken::NODE: {
                size_t orig_idx = tok.node_idx;
                size_t target_comp = scc.node_to_component[orig_idx];
                rpn += "CMP_" + std::to_string(target_comp);
                break;
            }
        }
    }
    
    return rpn;
}

void NetworkReducer::print_scc(const SCCResult& scc, const BooleanNetwork& network) {
    std::cout << "Strongly Connected Components (" << scc.num_components << "):" << std::endl;
    for (size_t i = 0; i < scc.components.size(); ++i) {
        std::cout << "  Component " << i << ": { ";
        for (size_t node_idx : scc.components[i]) {
            std::cout << network.node(node_idx).name << " ";
        }
        std::cout << "}" << std::endl;
    }
    
    std::cout << "\nCondensed DAG edges:" << std::endl;
    for (size_t i = 0; i < scc.condensed_edges.size(); ++i) {
        if (!scc.condensed_edges[i].empty()) {
            std::cout << "  CMP_" << i << " -> ";
            for (size_t j : scc.condensed_edges[i]) {
                std::cout << "CMP_" << j << " ";
            }
            std::cout << std::endl;
        }
    }
}

RobustnessAnalysis::RobustnessAnalysis(const BooleanNetwork& network)
    : network_(network), rng_(std::random_device{}()) {}

std::unique_ptr<BooleanNetwork> RobustnessAnalysis::create_knockout_network(size_t node_idx) const {
    auto net = network_.clone();
    BooleanFunction const_false("0", net->get_name_map());
    net->set_node_function(node_idx, const_false);
    return net;
}

std::unique_ptr<BooleanNetwork> RobustnessAnalysis::create_overexpression_network(size_t node_idx) const {
    auto net = network_.clone();
    BooleanFunction const_true("1", net->get_name_map());
    net->set_node_function(node_idx, const_true);
    return net;
}

double RobustnessAnalysis::compute_attractor_preservation(const std::vector<Attractor>& perturbed) const {
    if (original_attractors_.empty()) return 0.0;
    
    StateEqual eq;
    size_t preserved = 0;
    
    for (const auto& orig : original_attractors_) {
        for (const auto& pert : perturbed) {
            if (orig.states.size() != pert.states.size()) continue;
            
            bool match = true;
            for (const auto& os : orig.states) {
                bool found = false;
                for (const auto& ps : pert.states) {
                    if (eq(os, ps)) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    match = false;
                    break;
                }
            }
            
            if (match) {
                preserved++;
                break;
            }
        }
    }
    
    return static_cast<double>(preserved) / original_attractors_.size();
}

double RobustnessAnalysis::compute_basin_similarity(const std::vector<Attractor>& perturbed) const {
    if (original_attractors_.empty() || perturbed.empty()) return 0.0;
    
    double total_original = 0;
    for (const auto& a : original_attractors_) total_original += a.basin_size;
    if (total_original == 0) return 0.0;
    
    double total_perturbed = 0;
    for (const auto& a : perturbed) total_perturbed += a.basin_size;
    if (total_perturbed == 0) return 0.0;
    
    StateEqual eq;
    double overlap = 0.0;
    
    for (const auto& orig : original_attractors_) {
        for (const auto& pert : perturbed) {
            bool states_match = true;
            if (orig.states.size() != pert.states.size()) {
                states_match = false;
            } else {
                for (const auto& os : orig.states) {
                    bool found = false;
                    for (const auto& ps : pert.states) {
                        if (eq(os, ps)) {
                            found = true;
                            break;
                        }
                    }
                    if (!found) {
                        states_match = false;
                        break;
                    }
                }
            }
            
            if (states_match) {
                double orig_pct = orig.basin_size / total_original;
                double pert_pct = pert.basin_size / total_perturbed;
                overlap += std::min(orig_pct, pert_pct);
                break;
            }
        }
    }
    
    return overlap;
}

KnockoutResult RobustnessAnalysis::simulate_knockout(size_t node_idx,
                                                     size_t num_starts,
                                                     bool deterministic) {
    KnockoutResult result;
    result.node_idx = node_idx;
    result.node_name = network_.node(node_idx).name;
    
    auto ko_net = create_knockout_network(node_idx);
    AttractorSearch search(*ko_net);
    
    result.attractors = deterministic ?
        search.search_all_attractors_deterministic(num_starts) :
        search.search_all_attractors(num_starts);
    
    search.compute_basin_sizes(result.attractors, num_starts * 2, deterministic);
    
    result.attractor_preservation_rate = compute_attractor_preservation(result.attractors);
    result.basin_similarity = compute_basin_similarity(result.attractors);
    
    return result;
}

OverexpressionResult RobustnessAnalysis::simulate_overexpression(size_t node_idx,
                                                                 size_t num_starts,
                                                                 bool deterministic) {
    OverexpressionResult result;
    result.node_idx = node_idx;
    result.node_name = network_.node(node_idx).name;
    
    auto oe_net = create_overexpression_network(node_idx);
    AttractorSearch search(*oe_net);
    
    result.attractors = deterministic ?
        search.search_all_attractors_deterministic(num_starts) :
        search.search_all_attractors(num_starts);
    
    search.compute_basin_sizes(result.attractors, num_starts * 2, deterministic);
    
    result.attractor_preservation_rate = compute_attractor_preservation(result.attractors);
    result.basin_similarity = compute_basin_similarity(result.attractors);
    
    return result;
}

std::vector<KnockoutResult> RobustnessAnalysis::analyze_all_knockouts(size_t num_starts,
                                                                      bool deterministic) {
    std::vector<KnockoutResult> results;
    for (size_t i = 0; i < network_.num_nodes(); ++i) {
        results.push_back(simulate_knockout(i, num_starts, deterministic));
    }
    return results;
}

std::vector<OverexpressionResult> RobustnessAnalysis::analyze_all_overexpressions(size_t num_starts,
                                                                                   bool deterministic) {
    std::vector<OverexpressionResult> results;
    for (size_t i = 0; i < network_.num_nodes(); ++i) {
        results.push_back(simulate_overexpression(i, num_starts, deterministic));
    }
    return results;
}

HybridAttractorSearch::HybridAttractorSearch(const BooleanNetwork& network,
                                             double sync_probability)
    : network_(network), sync_probability_(sync_probability),
      rng_(std::random_device{}()) {}

bool HybridAttractorSearch::is_trap_state(const State& state, size_t no_change_steps, size_t threshold) const {
    size_t n = network_.num_nodes();
    size_t active_count = 0;
    for (bool b : state) if (b) active_count++;
    
    if (active_count == 0 || active_count == n) return true;
    if (no_change_steps > threshold * n) return true;
    return false;
}

Attractor HybridAttractorSearch::find_attractor_from(State state,
                                                     size_t max_steps,
                                                     bool deterministic) {
    std::vector<State> trajectory;
    StateMap state_pos;
    size_t round_counter = 0;
    size_t no_change_steps = 0;
    State prev_state = state;
    const size_t trap_threshold = 100;
    StateEqual eq;
    
    for (size_t step = 0; step < max_steps; ++step) {
        auto it = state_pos.find(state);
        if (it != state_pos.end()) {
            size_t cycle_start = it->second;
            Attractor attr;
            if (cycle_start == trajectory.size() - 1) {
                attr.type = Attractor::FIXED_POINT;
                attr.length = 1;
                attr.states.push_back(state);
            } else {
                attr.type = Attractor::LIMIT_CYCLE;
                attr.length = trajectory.size() - cycle_start;
                for (size_t i = cycle_start; i < trajectory.size(); ++i) {
                    attr.states.push_back(trajectory[i]);
                }
            }
            attr.basin_size = 0;
            return attr;
        }
        
        if (eq(state, prev_state)) {
            no_change_steps++;
        } else {
            no_change_steps = 0;
            prev_state = state;
        }
        
        if (is_trap_state(state, no_change_steps, trap_threshold)) {
            Attractor attr;
            attr.type = Attractor::TRAP_STATE;
            attr.length = 0;
            attr.states.push_back(state);
            attr.basin_size = 0;
            return attr;
        }
        
        state_pos[state] = trajectory.size();
        trajectory.push_back(state);
        
        network_.hybrid_update(state, rng_, sync_probability_, round_counter, deterministic);
    }
    
    Attractor attr;
    attr.type = Attractor::TRAP_STATE;
    attr.length = 0;
    attr.states.push_back(state);
    attr.basin_size = 0;
    return attr;
}

std::vector<Attractor> HybridAttractorSearch::search_all_attractors(size_t num_random_starts,
                                                                    size_t max_steps,
                                                                    bool deterministic) {
    std::vector<Attractor> attractors;
    StateEqual eq;
    
    for (size_t i = 0; i < num_random_starts; ++i) {
        State s = network_.random_state(rng_);
        Attractor attr = find_attractor_from(s, max_steps, deterministic);
        
        bool is_new = true;
        for (const auto& existing : attractors) {
            if (existing.type != attr.type || existing.length != attr.length) continue;
            
            bool match = true;
            for (const auto& es : existing.states) {
                bool found = false;
                for (const auto& as : attr.states) {
                    if (eq(es, as)) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    match = false;
                    break;
                }
            }
            if (match) {
                is_new = false;
                break;
            }
        }
        
        if (is_new) {
            attractors.push_back(attr);
        }
    }
    
    return attractors;
}

void HybridAttractorSearch::compute_basin_sizes(std::vector<Attractor>& attractors,
                                                size_t num_samples,
                                                bool deterministic) {
    std::vector<size_t> counts(attractors.size(), 0);
    StateEqual eq;
    
    for (size_t i = 0; i < num_samples; ++i) {
        State s = network_.random_state(rng_);
        Attractor attr = find_attractor_from(s, 1000000, deterministic);
        
        for (size_t j = 0; j < attractors.size(); ++j) {
            if (attractors[j].type != attr.type || attractors[j].length != attr.length) continue;
            
            bool match = true;
            for (const auto& es : attractors[j].states) {
                bool found = false;
                for (const auto& as : attr.states) {
                    if (eq(es, as)) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    match = false;
                    break;
                }
            }
            if (match) {
                counts[j]++;
                break;
            }
        }
    }
    
    for (size_t j = 0; j < attractors.size(); ++j) {
        attractors[j].basin_size = counts[j];
    }
}

}
