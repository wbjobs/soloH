#ifndef EM_ALGORITHM_H
#define EM_ALGORITHM_H

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

class EMAlgorithm {
public:
    struct Options {
        int min_width = 6;
        int max_width = 20;
        int width = 12;
        int max_iterations = 100;
        double tolerance = 1e-6;
        double lambda = 0.5;
        double edge_penalty = 0.3;
        int n_starts = 5;
        int seed = 42;
        int num_threads = 1;
        bool use_prior_knowledge = false;
        bool use_rna_structure = false;
        PriorKnowledge::Options prior_options;
        RnaStructurePredictor::Options rna_options;
        double prior_weight = 0.5;
        double structure_weight = 0.5;
    };

    static MotifResult run_zoops(
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
        std::vector<double> log_likelihoods(options.n_starts, -std::numeric_limits<double>::infinity());

        std::vector<RnaStructure> local_structures;
        if (options.use_rna_structure && rna_structures == nullptr) {
            local_structures = RnaStructurePredictor::predict_all(sequences, options.rna_options);
            rna_structures = &local_structures;
        }

        #ifdef _OPENMP
        #pragma omp parallel for schedule(dynamic)
        #endif
        for (int start = 0; start < options.n_starts; start++) {
            results[start] = single_run_zoops(sequences, background, options, rngs[start], 
                                              prior, rna_structures);
            log_likelihoods[start] = results[start].e_value;
        }

        int best_start = 0;
        double best_ll = log_likelihoods[0];
        for (int start = 1; start < options.n_starts; start++) {
            if (log_likelihoods[start] < best_ll) {
                best_ll = log_likelihoods[start];
                best_start = start;
            }
        }

        post_process_result(results[best_start], sequences, background, options);
        return results[best_start];
    }

private:
    static MotifResult single_run_zoops(
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        const Options& options,
        std::mt19937& rng,
        const PriorKnowledge* prior = nullptr,
        const std::vector<RnaStructure>* rna_structures = nullptr
    ) {
        PWM pwm(options.width);
        double lambda = options.lambda;
        
        initialize_pwm_random(pwm, sequences, background, options, rng);

        double prev_log_likelihood = -std::numeric_limits<double>::infinity();
        std::vector<std::vector<double>> responsibilities;
        std::vector<double> seq_has_motif;
        
        auto combined_priors = compute_combined_priors(sequences, options, prior, rna_structures);

        for (int iter = 0; iter < options.max_iterations; iter++) {
            double log_likelihood = e_step(sequences, background, pwm, lambda, options.width, 
                                           responsibilities, seq_has_motif, combined_priors);
            m_step(sequences, background, pwm, lambda, options.width, responsibilities, seq_has_motif);

            double change = std::abs(log_likelihood - prev_log_likelihood);
            prev_log_likelihood = log_likelihood;

            if (change < options.tolerance) {
                break;
            }
        }

        MotifResult result;
        result.pwm = pwm;
        result.width = options.width;
        result.algorithm = "EM";
        result.model = "ZOOPS";
        result.information_content = pwm.information_content(background.frequencies);
        result.consensus = pwm.consensus();
        result.e_value = prev_log_likelihood;
        
        result.sites = extract_sites(sequences, pwm, background, options.width, responsibilities);

        return result;
    }

    static void initialize_pwm_random(
        PWM& pwm,
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        const Options& options,
        std::mt19937& rng
    ) {
        pwm.initialize_pseudocount_with_background(background.frequencies, 0.1);
        
        int n_sites = std::max(1, static_cast<int>(sequences.size() * 0.5));
        std::uniform_int_distribution<int> seq_dist(0, sequences.size() - 1);
        
        for (int s = 0; s < n_sites; s++) {
            int seq_idx = seq_dist(rng);
            const auto& seq = sequences[seq_idx];
            if (static_cast<int>(seq.encoded.size()) < options.width) continue;
            
            std::uniform_int_distribution<int> pos_dist(0, seq.encoded.size() - options.width);
            int pos = pos_dist(rng);
            
            for (int i = 0; i < options.width; i++) {
                int base = seq.encoded[pos + i];
                if (base >= 0 && base < 4) {
                    pwm.matrix[i][base] += 1.0;
                }
            }
        }
        
        pwm.normalize();
    }

    static double e_step(
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        const PWM& pwm,
        double lambda,
        int width,
        std::vector<std::vector<double>>& responsibilities,
        std::vector<double>& seq_has_motif,
        const std::vector<std::vector<double>>& position_priors
    ) {
        double total_log_likelihood = 0.0;
        responsibilities.clear();
        seq_has_motif.clear();
        responsibilities.resize(sequences.size());
        seq_has_motif.resize(sequences.size(), 0.0);

        std::vector<double> per_seq_ll(sequences.size(), 0.0);

        #ifdef _OPENMP
        #pragma omp parallel for schedule(dynamic) reduction(+:total_log_likelihood)
        #endif
        for (int s = 0; s < static_cast<int>(sequences.size()); s++) {
            const auto& seq = sequences[s];
            int n_positions = static_cast<int>(seq.encoded.size()) - width + 1;
            if (n_positions <= 0) {
                responsibilities[s] = std::vector<double>();
                continue;
            }

            responsibilities[s].resize(n_positions, 0.0);
            std::vector<double> log_site_probs(n_positions);
            
            for (int p = 0; p < n_positions; p++) {
                double log_p_motif = std::log(lambda);
                if (p < static_cast<int>(position_priors[s].size())) {
                    log_p_motif += position_priors[s][p];
                } else {
                    log_p_motif -= std::log(static_cast<double>(n_positions));
                }
                
                double log_p_bg = 0.0;
                
                for (int i = 0; i < width; i++) {
                    int base = seq.encoded[p + i];
                    if (base >= 0 && base < 4) {
                        if (pwm.matrix[i][base] > 0) {
                            log_p_motif += std::log(pwm.matrix[i][base]);
                        }
                        log_p_bg += background.log_background(base);
                    }
                }

                log_site_probs[p] = log_p_motif;
                total_log_likelihood += Statistics::log_sum_exp(log_p_motif, log_p_bg + std::log(1 - lambda));
            }

            double log_norm = Statistics::log_sum_exp(log_site_probs);
            log_norm = Statistics::log_sum_exp(log_norm, std::log(1 - lambda));
            
            for (int p = 0; p < n_positions; p++) {
                responsibilities[s][p] = std::exp(log_site_probs[p] - log_norm);
                seq_has_motif[s] += responsibilities[s][p];
            }
        }

        return total_log_likelihood;
    }

    static void m_step(
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        PWM& pwm,
        double& lambda,
        int width,
        const std::vector<std::vector<double>>& responsibilities,
        const std::vector<double>& seq_has_motif
    ) {
        double total_weight = 0.0;
        for (size_t s = 0; s < sequences.size(); s++) {
            const auto& seq = sequences[s];
            int n_positions = static_cast<int>(seq.encoded.size()) - width + 1;
            if (n_positions <= 0) continue;
            for (int p = 0; p < n_positions; p++) {
                total_weight += responsibilities[s][p];
            }
        }

        double pseudo_strength = std::max(0.01, 1.0 / (1.0 + total_weight));
        pwm.initialize_pseudocount_with_background(background.frequencies, pseudo_strength);

        for (size_t s = 0; s < sequences.size(); s++) {
            const auto& seq = sequences[s];
            int n_positions = static_cast<int>(seq.encoded.size()) - width + 1;
            if (n_positions <= 0) continue;

            for (int p = 0; p < n_positions; p++) {
                double w = responsibilities[s][p];
                total_weight += w;
                
                for (int i = 0; i < width; i++) {
                    int base = seq.encoded[p + i];
                    if (base >= 0 && base < 4) {
                        pwm.matrix[i][base] += w;
                    }
                }
            }
        }

        pwm.normalize();

        double avg_has_motif = 0.0;
        int valid_seqs = 0;
        for (size_t s = 0; s < sequences.size(); s++) {
            if (static_cast<int>(sequences[s].encoded.size()) >= width) {
                avg_has_motif += seq_has_motif[s];
                valid_seqs++;
            }
        }
        if (valid_seqs > 0) {
            avg_has_motif /= valid_seqs;
            lambda = std::min(0.99, std::max(0.01, avg_has_motif));
        }
    }

    static std::vector<MotifSite> extract_sites(
        const std::vector<FastaSequence>& sequences,
        const PWM& pwm,
        const BackgroundModel& background,
        int width,
        const std::vector<std::vector<double>>& responsibilities
    ) {
        std::vector<MotifSite> sites;

        for (size_t s = 0; s < sequences.size(); s++) {
            const auto& seq = sequences[s];
            int n_positions = static_cast<int>(seq.encoded.size()) - width + 1;
            if (n_positions <= 0 || responsibilities[s].empty()) continue;

            int best_pos = 0;
            double best_prob = 0.0;
            for (int p = 0; p < n_positions; p++) {
                if (responsibilities[s][p] > best_prob) {
                    best_prob = responsibilities[s][p];
                    best_pos = p;
                }
            }

            if (best_prob > 0.5) {
                MotifSite site;
                site.seq_index = static_cast<int>(s);
                site.position = best_pos;
                site.strand = 1;
                site.score = pwm.score_site(seq.encoded, best_pos, background.frequencies);
                site.sequence = seq.sequence.substr(best_pos, width);
                site.p_value = 0.0;
                site.e_value = 0.0;
                sites.push_back(site);
            }
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
