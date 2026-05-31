#ifndef GIBBS_SAMPLER_H
#define GIBBS_SAMPLER_H

#include "sequence.h"
#include "pwm.h"
#include "statistics.h"
#include "prior_knowledge.h"
#include "rna_structure.h"
#include <vector>
#include <cmath>
#include <limits>
#include <random>
#include <algorithm>
#include <iostream>
#include <omp.h>

class GibbsSampler {
public:
    struct Options {
        int min_width = 6;
        int max_width = 20;
        int width = 12;
        int iterations = 500;
        int burn_in = 100;
        int n_starts = 3;
        double lambda = 0.5;
        double edge_penalty = 0.3;
        int seed = 42;
        int num_threads = 1;
        bool use_prior_knowledge = false;
        bool use_rna_structure = false;
        PriorKnowledge::Options prior_options;
        RnaStructurePredictor::Options rna_options;
        double prior_weight = 0.5;
        double structure_weight = 0.5;
    };

    static MotifResult run(
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        const Options& options,
        const PriorKnowledge* prior = nullptr,
        const std::vector<RnaStructure>* rna_structures = nullptr
    ) {
        #ifdef _OPENMP
        omp_set_num_threads(options.num_threads);
        #endif
        
        std::vector<std::mt19937> rngs(options.n_starts);
        for (int s = 0; s < options.n_starts; s++) {
            rngs[s].seed(options.seed + s);
        }
        
        std::vector<MotifResult> results(options.n_starts);
        std::vector<double> scores(options.n_starts, -std::numeric_limits<double>::infinity());

        std::vector<RnaStructure> local_structures;
        if (options.use_rna_structure && rna_structures == nullptr) {
            local_structures = RnaStructurePredictor::predict_all(sequences, options.rna_options);
            rna_structures = &local_structures;
        }

        #ifdef _OPENMP
        #pragma omp parallel for schedule(dynamic)
        #endif
        for (int start = 0; start < options.n_starts; start++) {
            results[start] = single_run(sequences, background, options, rngs[start], 
                                        prior, rna_structures);
            scores[start] = results[start].information_content;
        }

        int best_start = 0;
        double best_score = scores[0];
        for (int start = 1; start < options.n_starts; start++) {
            if (scores[start] > best_score) {
                best_score = scores[start];
                best_start = start;
            }
        }

        post_process_result(results[best_start], sequences, background, options);
        return results[best_start];
    }

private:
    static MotifResult single_run(
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        const Options& options,
        std::mt19937& rng,
        const PriorKnowledge* prior = nullptr,
        const std::vector<RnaStructure>* rna_structures = nullptr
    ) {
        int n = static_cast<int>(sequences.size());
        std::vector<int> positions(n, -1);
        std::vector<bool> has_motif(n, false);

        initialize_positions(positions, has_motif, sequences, options, rng);

        PWM pwm(options.width);
        PWM pwm_samples(options.width);
        int sample_count = 0;

        double lambda = options.lambda;
        
        auto combined_priors = compute_combined_priors(sequences, options, prior, rna_structures);

        for (int iter = 0; iter < options.iterations; iter++) {
            for (int s = 0; s < n; s++) {
                if (static_cast<int>(sequences[s].encoded.size()) < options.width) continue;

                int old_pos = positions[s];
                bool old_has = has_motif[s];

                PWM temp_pwm = build_pwm_without_seq(positions, has_motif, sequences, options.width, s, background);
                
                double log_p_no_motif = std::log(1 - lambda);
                int n_positions = static_cast<int>(sequences[s].encoded.size()) - options.width + 1;
                
                std::vector<double> log_p_positions(n_positions);
                for (int p = 0; p < n_positions; p++) {
                    double log_p = std::log(lambda);
                    if (p < static_cast<int>(combined_priors[s].size())) {
                        log_p += combined_priors[s][p];
                    } else {
                        log_p -= std::log(static_cast<double>(n_positions));
                    }
                    
                    for (int i = 0; i < options.width; i++) {
                        int base = sequences[s].encoded[p + i];
                        if (base >= 0 && base < 4) {
                            if (temp_pwm.matrix[i][base] > 0) {
                                log_p += std::log(temp_pwm.matrix[i][base]);
                            } else {
                                log_p += std::log(0.01);
                            }
                        }
                    }
                    log_p_positions[p] = log_p;
                }

                double log_total = log_p_no_motif;
                for (double lp : log_p_positions) {
                    log_total = Statistics::log_sum_exp(log_total, lp);
                }

                double p_has_motif = 1.0 - std::exp(log_p_no_motif - log_total);
                
                std::uniform_real_distribution<double> uni(0.0, 1.0);
                if (uni(rng) > p_has_motif) {
                    positions[s] = -1;
                    has_motif[s] = false;
                } else {
                    std::vector<double> probs(n_positions);
                    for (int p = 0; p < n_positions; p++) {
                        probs[p] = std::exp(log_p_positions[p] - log_total) / p_has_motif;
                    }
                    
                    double r = uni(rng);
                    double cum = 0.0;
                    int chosen_pos = 0;
                    for (int p = 0; p < n_positions; p++) {
                        cum += probs[p];
                        if (r <= cum) {
                            chosen_pos = p;
                            break;
                        }
                    }
                    positions[s] = chosen_pos;
                    has_motif[s] = true;
                }
            }

            if (iter > options.burn_in) {
                pwm = build_pwm(positions, has_motif, sequences, options.width, background);
                for (int i = 0; i < options.width; i++) {
                    for (int j = 0; j < 4; j++) {
                        pwm_samples.matrix[i][j] += pwm.matrix[i][j];
                    }
                }
                sample_count++;
            }
        }

        if (sample_count > 0) {
            for (int i = 0; i < options.width; i++) {
                for (int j = 0; j < 4; j++) {
                    pwm.matrix[i][j] = pwm_samples.matrix[i][j] / sample_count;
                }
            }
        } else {
            pwm = build_pwm(positions, has_motif, sequences, options.width, background);
        }

        MotifResult result;
        result.pwm = pwm;
        result.width = options.width;
        result.algorithm = "Gibbs";
        result.model = "ZOOPS";
        result.information_content = pwm.information_content(background.frequencies);
        result.consensus = pwm.consensus();
        result.e_value = 0.0;
        
        result.sites = extract_sites(sequences, positions, has_motif, pwm, background, options.width);

        return result;
    }

    static void initialize_positions(
        std::vector<int>& positions,
        std::vector<bool>& has_motif,
        const std::vector<FastaSequence>& sequences,
        const Options& options,
        std::mt19937& rng
    ) {
        std::uniform_real_distribution<double> uni(0.0, 1.0);
        
        for (size_t s = 0; s < sequences.size(); s++) {
            if (static_cast<int>(sequences[s].encoded.size()) < options.width) {
                positions[s] = -1;
                has_motif[s] = false;
                continue;
            }

            if (uni(rng) < options.lambda) {
                int max_pos = sequences[s].encoded.size() - options.width + 1;
                std::uniform_int_distribution<int> pos_dist(0, max_pos - 1);
                positions[s] = pos_dist(rng);
                has_motif[s] = true;
            } else {
                positions[s] = -1;
                has_motif[s] = false;
            }
        }
    }

    static PWM build_pwm(
        const std::vector<int>& positions,
        const std::vector<bool>& has_motif,
        const std::vector<FastaSequence>& sequences,
        int width,
        const BackgroundModel& background
    ) {
        int n_sites = 0;
        for (size_t s = 0; s < sequences.size(); s++) {
            if (has_motif[s] && positions[s] >= 0) n_sites++;
        }
        double pseudo_strength = std::max(0.01, 1.0 / (1.0 + n_sites));
        
        PWM pwm(width);
        pwm.initialize_pseudocount_with_background(background.frequencies, pseudo_strength);

        for (size_t s = 0; s < sequences.size(); s++) {
            if (!has_motif[s] || positions[s] < 0) continue;

            int pos = positions[s];
            for (int i = 0; i < width; i++) {
                int base = sequences[s].encoded[pos + i];
                if (base >= 0 && base < 4) {
                    pwm.matrix[i][base] += 1.0;
                }
            }
        }

        pwm.normalize();
        return pwm;
    }

    static PWM build_pwm_without_seq(
        const std::vector<int>& positions,
        const std::vector<bool>& has_motif,
        const std::vector<FastaSequence>& sequences,
        int width,
        int exclude_idx,
        const BackgroundModel& background
    ) {
        int n_sites = 0;
        for (size_t s = 0; s < sequences.size(); s++) {
            if (static_cast<int>(s) == exclude_idx) continue;
            if (has_motif[s] && positions[s] >= 0) n_sites++;
        }
        double pseudo_strength = std::max(0.01, 1.0 / (1.0 + n_sites));
        
        PWM pwm(width);
        pwm.initialize_pseudocount_with_background(background.frequencies, pseudo_strength);

        for (size_t s = 0; s < sequences.size(); s++) {
            if (static_cast<int>(s) == exclude_idx) continue;
            if (!has_motif[s] || positions[s] < 0) continue;

            int pos = positions[s];
            for (int i = 0; i < width; i++) {
                int base = sequences[s].encoded[pos + i];
                if (base >= 0 && base < 4) {
                    pwm.matrix[i][base] += 1.0;
                }
            }
        }

        pwm.normalize();
        return pwm;
    }

    static std::vector<MotifSite> extract_sites(
        const std::vector<FastaSequence>& sequences,
        const std::vector<int>& positions,
        const std::vector<bool>& has_motif,
        const PWM& pwm,
        const BackgroundModel& background,
        int width
    ) {
        std::vector<MotifSite> sites;

        for (size_t s = 0; s < sequences.size(); s++) {
            if (!has_motif[s] || positions[s] < 0) continue;

            MotifSite site;
            site.seq_index = static_cast<int>(s);
            site.position = positions[s];
            site.strand = 1;
            site.score = pwm.score_site(sequences[s].encoded, positions[s], background.frequencies);
            site.sequence = sequences[s].sequence.substr(positions[s], width);
            site.p_value = 0.0;
            site.e_value = 0.0;
            sites.push_back(site);
        }

        return sites;
    }

    static std::vector<std::vector<double>> compute_combined_priors(
        const std::vector<FastaSequence>& sequences,
        const Options& options,
        const PriorKnowledge* prior,
        const std::vector<RnaStructure>* rna_structures
    ) {
        auto combined_priors = Statistics::compute_all_position_priors(
            sequences, options.width, options.edge_penalty);

        if (options.use_prior_knowledge && prior != nullptr && prior->has_prior()) {
            auto knowledge_priors = prior->compute_log_prior_weights(
                sequences, options.width, options.prior_options);
            
            for (size_t s = 0; s < combined_priors.size(); s++) {
                if (combined_priors[s].size() != knowledge_priors[s].size()) continue;
                for (size_t p = 0; p < combined_priors[s].size(); p++) {
                    combined_priors[s][p] = 
                        options.prior_weight * knowledge_priors[s][p] +
                        (1.0 - options.prior_weight) * combined_priors[s][p];
                }
            }
        }

        if (options.use_rna_structure && rna_structures != nullptr) {
            auto structure_priors = RnaStructurePredictor::compute_log_structure_weights(
                *rna_structures, options.width, options.rna_options);
            
            for (size_t s = 0; s < combined_priors.size(); s++) {
                if (combined_priors[s].size() != structure_priors[s].size()) continue;
                for (size_t p = 0; p < combined_priors[s].size(); p++) {
                    combined_priors[s][p] += 
                        options.structure_weight * structure_priors[s][p];
                }
            }
        }

        return combined_priors;
    }

    static void post_process_result(
        MotifResult& result,
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        const Options& options
    ) {
        auto score_dist = Statistics::simulate_score_distribution(result.pwm, background, 20000);
        
        double total_sites = 0;
        for (const auto& seq : sequences) {
            int n = static_cast<int>(seq.encoded.size()) - options.width + 1;
            if (n > 0) total_sites += n;
        }

        for (auto& site : result.sites) {
            site.p_value = Statistics::p_value_from_distribution(site.score, score_dist);
            site.e_value = site.p_value * total_sites;
        }

        double best_p_value = 1.0;
        for (const auto& site : result.sites) {
            if (site.p_value < best_p_value) {
                best_p_value = site.p_value;
            }
        }
        result.e_value = best_p_value * total_sites;
    }
};

#endif
