#ifndef PRIOR_KNOWLEDGE_H
#define PRIOR_KNOWLEDGE_H

#include "sequence.h"
#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <cmath>
#include <algorithm>
#include <unordered_map>
#include <set>

struct PriorSite {
    std::string seq_name;
    int start;
    int end;
    double weight;
    std::string source;
    std::string motif_name;
};

class PriorKnowledge {
public:
    struct Options {
        double prior_strength = 1.0;
        bool use_experiment_prior = true;
        bool use_prediction_prior = true;
        bool use_conservation_prior = true;
        double min_prior_weight = 0.1;
        double max_prior_weight = 10.0;
    };

    PriorKnowledge() = default;

    void load_bed_file(const std::string& filename, const std::string& source_type = "experiment") {
        std::ifstream file(filename);
        if (!file.is_open()) {
            throw std::runtime_error("Cannot open prior knowledge file: " + filename);
        }

        std::string line;
        while (std::getline(file, line)) {
            if (line.empty() || line[0] == '#') continue;

            std::istringstream iss(line);
            PriorSite site;
            std::string score_str;
            
            if (iss >> site.seq_name >> site.start >> site.end >> site.motif_name >> score_str) {
                try {
                    site.weight = std::stod(score_str);
                } catch (...) {
                    site.weight = 1.0;
                }
                site.source = source_type;
                sites_.push_back(site);
            }
        }

        file.close();
        build_index();
    }

    void load_known_motifs(const std::vector<std::string>& motif_names, 
                           const std::vector<std::vector<int>>& positions_per_seq,
                           double weight = 2.0) {
        for (size_t i = 0; i < positions_per_seq.size(); i++) {
            for (int pos : positions_per_seq[i]) {
                PriorSite site;
                site.seq_name = "seq_" + std::to_string(i);
                site.start = pos;
                site.end = pos;
                site.weight = weight;
                site.source = "known";
                site.motif_name = i < motif_names.size() ? motif_names[i] : "unknown";
                sites_.push_back(site);
            }
        }
        build_index();
    }

    void add_custom_prior(int seq_index, int position, double weight, 
                          const std::string& source = "custom") {
        PriorSite site;
        site.seq_name = "seq_" + std::to_string(seq_index);
        site.start = position;
        site.end = position;
        site.weight = weight;
        site.source = source;
        site.motif_name = "custom";
        sites_.push_back(site);
        build_index();
    }

    std::vector<std::vector<double>> compute_prior_weights(
        const std::vector<FastaSequence>& sequences,
        int motif_width,
        const Options& options
    ) const {
        std::vector<std::vector<double>> prior_weights(sequences.size());
        
        for (size_t s = 0; s < sequences.size(); s++) {
            int n_positions = static_cast<int>(sequences[s].encoded.size()) - motif_width + 1;
            if (n_positions <= 0) {
                prior_weights[s] = std::vector<double>();
                continue;
            }

            prior_weights[s].assign(n_positions, 1.0);
            
            std::string seq_key = sequences[s].name;
            if (seq_key.empty()) {
                seq_key = "seq_" + std::to_string(s);
            }

            auto it = seq_index_.find(seq_key);
            if (it == seq_index_.end()) {
                continue;
            }

            for (int site_idx : it->second) {
                const PriorSite& site = sites_[site_idx];
                
                double site_weight = site.weight * options.prior_strength;
                
                if (site.source == "experiment" && !options.use_experiment_prior) continue;
                if (site.source == "prediction" && !options.use_prediction_prior) continue;
                if (site.source == "conservation" && !options.use_conservation_prior) continue;
                
                site_weight = std::max(options.min_prior_weight, 
                                      std::min(options.max_prior_weight, site_weight));

                int center = (site.start + site.end) / 2;
                int influence_width = motif_width * 2;
                
                for (int p = 0; p < n_positions; p++) {
                    int motif_center = p + motif_width / 2;
                    int distance = std::abs(motif_center - center);
                    
                    if (distance <= influence_width) {
                        double distance_decay = std::exp(-static_cast<double>(distance * distance) / 
                                                       (2.0 * motif_width * motif_width));
                        prior_weights[s][p] *= (1.0 + (site_weight - 1.0) * distance_decay);
                    }
                }
            }

            double max_w = 1.0;
            for (double w : prior_weights[s]) {
                max_w = std::max(max_w, w);
            }
            if (max_w > 1.0) {
                for (double& w : prior_weights[s]) {
                    w = 1.0 + (w - 1.0) / max_w * (options.max_prior_weight - 1.0);
                }
            }
        }

        return prior_weights;
    }

    std::vector<std::vector<double>> compute_log_prior_weights(
        const std::vector<FastaSequence>& sequences,
        int motif_width,
        const Options& options
    ) const {
        auto weights = compute_prior_weights(sequences, motif_width, options);
        std::vector<std::vector<double>> log_weights(weights.size());
        
        for (size_t s = 0; s < weights.size(); s++) {
            log_weights[s].resize(weights[s].size());
            for (size_t p = 0; p < weights[s].size(); p++) {
                log_weights[s][p] = std::log(weights[s][p]);
            }
        }
        
        return log_weights;
    }

    void combine_with_position_prior(
        std::vector<std::vector<double>>& log_priors,
        const std::vector<std::vector<double>>& position_log_priors,
        double prior_weight = 0.5
    ) const {
        for (size_t s = 0; s < log_priors.size(); s++) {
            if (log_priors[s].size() != position_log_priors[s].size()) continue;
            
            for (size_t p = 0; p < log_priors[s].size(); p++) {
                log_priors[s][p] = prior_weight * log_priors[s][p] + 
                                  (1.0 - prior_weight) * position_log_priors[s][p];
            }
        }
    }

    bool has_prior() const {
        return !sites_.empty();
    }

    size_t num_sites() const {
        return sites_.size();
    }

    std::set<std::string> get_sources() const {
        std::set<std::string> sources;
        for (const auto& site : sites_) {
            sources.insert(site.source);
        }
        return sources;
    }

private:
    std::vector<PriorSite> sites_;
    std::unordered_map<std::string, std::vector<int>> seq_index_;

    void build_index() {
        seq_index_.clear();
        for (size_t i = 0; i < sites_.size(); i++) {
            seq_index_[sites_[i].seq_name].push_back(static_cast<int>(i));
        }
    }
};

#endif
