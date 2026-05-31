#ifndef TCM_MODEL_H
#define TCM_MODEL_H

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

struct TCMResult {
    MotifResult motif1;
    MotifResult motif2;
    double log_likelihood;
    double correlation;
};

class TCMModel {
public:
    struct Options {
        int width1 = 12;
        int width2 = 12;
        int min_spacing = 0;
        int max_spacing = 100;
        int preferred_spacing = 20;
        double spacing_sigma = 10.0;
        int max_iterations = 100;
        double tolerance = 1e-5;
        int seed = 42;
        int n_starts = 3;
        int num_threads = 1;
        double edge_penalty = 0.3;
        bool use_prior_knowledge = false;
        bool use_rna_structure = false;
        PriorKnowledge::Options prior_options;
        RnaStructurePredictor::Options rna_options;
        double prior_weight = 0.5;
        double structure_weight = 0.5;
    };

    static TCMResult run(
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        const Options& options,
        const PriorKnowledge* prior1 = nullptr,
        const PriorKnowledge* prior2 = nullptr,
        const std::vector<RnaStructure>* rna_structures = nullptr
    ) {
        #ifdef _OPENMP
        omp_set_num_threads(options.num_threads);
        #endif
        
        std::vector<std::mt19937> rngs(options.n_starts);
        for (int s = 0; s < options.n_starts; s++) {
            rngs[s].seed(options.seed + s);
        }
        
        std::vector<TCMResult> results(options.n_starts);
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
            results[start] = single_run(sequences, background, options, rngs[start], 
                                        prior1, prior2, rna_structures);
            log_likelihoods[start] = results[start].log_likelihood;
        }

        int best_start = 0;
        double best_ll = log_likelihoods[0];
        for (int start = 1; start < options.n_starts; start++) {
            if (log_likelihoods[start] > best_ll) {
                best_ll = log_likelihoods[start];
                best_start = start;
            }
        }

        post_process_result(results[best_start], sequences, background, options);
        return results[best_start];
    }

private:
    static double spacing_prior_log(int pos1, int pos2, int w1, int w2, const Options& options) {
        int end1 = pos1 + w1;
        int end2 = pos2 + w2;
        
        if (pos1 < pos2) {
            int spacing = pos2 - end1;
            if (spacing < options.min_spacing || spacing > options.max_spacing) {
                return -std::numeric_limits<double>::infinity();
            }
            double diff = spacing - options.preferred_spacing;
            return -0.5 * (diff * diff) / (options.spacing_sigma * options.spacing_sigma);
        } else {
            int spacing = pos1 - end2;
            if (spacing < options.min_spacing || spacing > options.max_spacing) {
                return -std::numeric_limits<double>::infinity();
            }
            double diff = spacing - options.preferred_spacing;
            return -0.5 * (diff * diff) / (options.spacing_sigma * options.spacing_sigma);
        }
    }

    static bool positions_overlap(int pos1, int pos2, int w1, int w2) {
        int end1 = pos1 + w1;
        int end2 = pos2 + w2;
        return !(end1 <= pos2 || end2 <= pos1);
    }

    static TCMResult single_run(
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        const Options& options,
        std::mt19937& rng,
        const PriorKnowledge* prior1 = nullptr,
        const PriorKnowledge* prior2 = nullptr,
        const std::vector<RnaStructure>* rna_structures = nullptr
    ) {
        PWM pwm1(options.width1);
        PWM pwm2(options.width2);
        
        initialize_pwms(pwm1, pwm2, sequences, background, options, rng);

        double lambda0 = 0.2;
        double lambda1 = 0.3;
        double lambda2 = 0.3;
        double lambda_both = 0.2;

        std::vector<std::vector<double>> resp1, resp2;
        std::vector<double> resp_none, resp_motif1, resp_motif2, resp_both;
        double prev_ll = -std::numeric_limits<double>::infinity();
        
        auto combined_priors1 = compute_combined_priors(sequences, options.width1, options, 
                                                       prior1, rna_structures);
        auto combined_priors2 = compute_combined_priors(sequences, options.width2, options, 
                                                       prior2, rna_structures);

        for (int iter = 0; iter < options.max_iterations; iter++) {
            double ll = e_step(sequences, background, pwm1, pwm2,
                               lambda0, lambda1, lambda2, lambda_both,
                               options,
                               resp1, resp2, resp_none, resp_motif1, resp_motif2, resp_both,
                               position_priors1, position_priors2);
            
            m_step(sequences, pwm1, pwm2, 
                   lambda0, lambda1, lambda2, lambda_both,
                   options.width1, options.width2,
                   resp1, resp2, resp_motif1, resp_motif2, resp_both,
                   background);

            double change = std::abs(ll - prev_ll);
            prev_ll = ll;

            if (change < options.tolerance) {
                break;
            }
        }

        TCMResult result;
        result.motif1.pwm = pwm1;
        result.motif1.width = options.width1;
        result.motif1.algorithm = "EM-TCM";
        result.motif1.model = "TCM";
        result.motif1.consensus = pwm1.consensus();
        result.motif1.information_content = pwm1.information_content(background.frequencies);
        
        result.motif2.pwm = pwm2;
        result.motif2.width = options.width2;
        result.motif2.algorithm = "EM-TCM";
        result.motif2.model = "TCM";
        result.motif2.consensus = pwm2.consensus();
        result.motif2.information_content = pwm2.information_content(background.frequencies);
        
        result.log_likelihood = prev_ll;
        
        result.motif1.sites = extract_sites(sequences, pwm1, background, options.width1, resp1, 0.3);
        result.motif2.sites = extract_sites(sequences, pwm2, background, options.width2, resp2, 0.3);
        
        result.correlation = compute_correlation(resp_motif1, resp_motif2, resp_both);

        return result;
    }

    static void initialize_pwms(
        PWM& pwm1, PWM& pwm2,
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        const Options& options,
        std::mt19937& rng
    ) {
        pwm1.initialize_pseudocount_with_background(background.frequencies, 0.1);
        pwm2.initialize_pseudocount_with_background(background.frequencies, 0.1);

        int half = static_cast<int>(sequences.size() / 2);
        std::uniform_int_distribution<int> seq1_dist(0, half - 1);
        std::uniform_int_distribution<int> seq2_dist(half, static_cast<int>(sequences.size()) - 1);

        for (int s = 0; s < std::min(20, half); s++) {
            int idx1 = seq1_dist(rng);
            int idx2 = seq2_dist(rng);
            
            if (static_cast<int>(sequences[idx1].encoded.size()) >= options.width1) {
                std::uniform_int_distribution<int> pos_dist(0, sequences[idx1].encoded.size() - options.width1);
                int pos = pos_dist(rng);
                for (int i = 0; i < options.width1; i++) {
                    int base = sequences[idx1].encoded[pos + i];
                    if (base >= 0 && base < 4) pwm1.matrix[i][base] += 1.0;
                }
            }
            
            if (static_cast<int>(sequences[idx2].encoded.size()) >= options.width2) {
                std::uniform_int_distribution<int> pos_dist(0, sequences[idx2].encoded.size() - options.width2);
                int pos = pos_dist(rng);
                for (int i = 0; i < options.width2; i++) {
                    int base = sequences[idx2].encoded[pos + i];
                    if (base >= 0 && base < 4) pwm2.matrix[i][base] += 1.0;
                }
            }
        }

        pwm1.normalize();
        pwm2.normalize();
    }

    static double e_step(
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        const PWM& pwm1, const PWM& pwm2,
        double lambda0, double lambda1, double lambda2, double lambda_both,
        const Options& options,
        std::vector<std::vector<double>>& resp1,
        std::vector<std::vector<double>>& resp2,
        std::vector<double>& resp_none,
        std::vector<double>& resp_motif1,
        std::vector<double>& resp_motif2,
        std::vector<double>& resp_both,
        const std::vector<std::vector<double>>& position_priors1,
        const std::vector<std::vector<double>>& position_priors2
    ) {
        double total_ll = 0.0;
        int n = static_cast<int>(sequences.size());
        int width1 = options.width1;
        int width2 = options.width2;
        
        resp1.assign(n, std::vector<double>());
        resp2.assign(n, std::vector<double>());
        resp_none.assign(n, 0.0);
        resp_motif1.assign(n, 0.0);
        resp_motif2.assign(n, 0.0);
        resp_both.assign(n, 0.0);

        #ifdef _OPENMP
        #pragma omp parallel for schedule(dynamic) reduction(+:total_ll)
        #endif
        for (int s = 0; s < n; s++) {
            const auto& seq = sequences[s];
            int n1 = static_cast<int>(seq.encoded.size()) - width1 + 1;
            int n2 = static_cast<int>(seq.encoded.size()) - width2 + 1;

            if (n1 <= 0 || n2 <= 0) {
                resp_none[s] = 1.0;
                continue;
            }

            resp1[s].assign(n1, 0.0);
            resp2[s].assign(n2, 0.0);

            std::vector<double> log_p1(n1);
            std::vector<double> log_p2(n2);
            std::vector<double> site_score1(n1);
            std::vector<double> site_score2(n2);

            for (int p = 0; p < n1; p++) {
                double log_score = 0.0;
                for (int i = 0; i < width1; i++) {
                    int base = seq.encoded[p + i];
                    if (base >= 0 && base < 4 && pwm1.matrix[i][base] > 0) {
                        log_score += std::log(pwm1.matrix[i][base]);
                    }
                }
                site_score1[p] = log_score;
                
                log_p1[p] = std::log(lambda1);
                if (p < static_cast<int>(position_priors1[s].size())) {
                    log_p1[p] += position_priors1[s][p];
                } else {
                    log_p1[p] -= std::log(static_cast<double>(n1));
                }
                log_p1[p] += log_score;
            }

            for (int p = 0; p < n2; p++) {
                double log_score = 0.0;
                for (int i = 0; i < width2; i++) {
                    int base = seq.encoded[p + i];
                    if (base >= 0 && base < 4 && pwm2.matrix[i][base] > 0) {
                        log_score += std::log(pwm2.matrix[i][base]);
                    }
                }
                site_score2[p] = log_score;
                
                log_p2[p] = std::log(lambda2);
                if (p < static_cast<int>(position_priors2[s].size())) {
                    log_p2[p] += position_priors2[s][p];
                } else {
                    log_p2[p] -= std::log(static_cast<double>(n2));
                }
                log_p2[p] += log_score;
            }

            double log_p_none = std::log(lambda0);
            for (char c : seq.sequence) {
                int base = FastaParser::char_to_code(c);
                if (base >= 0 && base < 4) {
                    log_p_none += background.log_background(base);
                }
            }

            double log_p_motif1 = Statistics::log_sum_exp(log_p1);
            double log_p_motif2 = Statistics::log_sum_exp(log_p2);

            std::vector<double> log_p_both_pairs;
            log_p_both_pairs.reserve(n1 * n2);
            std::vector<std::pair<int, int>> valid_pairs;
            valid_pairs.reserve(n1 * n2);
            
            for (int p1 = 0; p1 < n1; p1++) {
                for (int p2 = 0; p2 < n2; p2++) {
                    if (positions_overlap(p1, p2, width1, width2)) {
                        continue;
                    }
                    
                    double log_spacing = spacing_prior_log(p1, p2, width1, width2, options);
                    if (log_spacing == -std::numeric_limits<double>::infinity()) {
                        continue;
                    }
                    
                    double log_p_both = std::log(lambda_both) + 
                                       site_score1[p1] + site_score2[p2] +
                                       log_spacing;
                    
                    if (p1 < static_cast<int>(position_priors1[s].size())) {
                        log_p_both += position_priors1[s][p1];
                    }
                    if (p2 < static_cast<int>(position_priors2[s].size())) {
                        log_p_both += position_priors2[s][p2];
                    }
                    
                    log_p_both_pairs.push_back(log_p_both);
                    valid_pairs.push_back({p1, p2});
                }
            }

            double log_p_both = -std::numeric_limits<double>::infinity();
            if (!log_p_both_pairs.empty()) {
                log_p_both = Statistics::log_sum_exp(log_p_both_pairs);
            }

            double log_norm = log_p_none;
            log_norm = Statistics::log_sum_exp(log_norm, log_p_motif1);
            log_norm = Statistics::log_sum_exp(log_norm, log_p_motif2);
            log_norm = Statistics::log_sum_exp(log_norm, log_p_both);

            total_ll += log_norm;

            resp_none[s] = std::exp(log_p_none - log_norm);
            resp_motif1[s] = std::exp(log_p_motif1 - log_norm);
            resp_motif2[s] = std::exp(log_p_motif2 - log_norm);
            resp_both[s] = std::exp(log_p_both - log_norm);

            for (int p = 0; p < n1; p++) {
                resp1[s][p] = std::exp(log_p1[p] - log_norm);
            }

            for (int p = 0; p < n2; p++) {
                resp2[s][p] = std::exp(log_p2[p] - log_norm);
            }

            if (!valid_pairs.empty()) {
                for (size_t idx = 0; idx < valid_pairs.size(); idx++) {
                    int p1 = valid_pairs[idx].first;
                    int p2 = valid_pairs[idx].second;
                    double joint_prob = std::exp(log_p_both_pairs[idx] - log_norm);
                    resp1[s][p1] += joint_prob;
                    resp2[s][p2] += joint_prob;
                }
            }
        }

        return total_ll;
    }

    static void m_step(
        const std::vector<FastaSequence>& sequences,
        PWM& pwm1, PWM& pwm2,
        double& lambda0, double& lambda1, double& lambda2, double& lambda_both,
        int width1, int width2,
        const std::vector<std::vector<double>>& resp1,
        const std::vector<std::vector<double>>& resp2,
        const std::vector<double>& resp_motif1,
        const std::vector<double>& resp_motif2,
        const std::vector<double>& resp_both,
        const BackgroundModel& background
    ) {
        double total1 = 0.0, total2 = 0.0;
        for (size_t s = 0; s < sequences.size(); s++) {
            const auto& seq = sequences[s];
            int n1 = static_cast<int>(seq.encoded.size()) - width1 + 1;
            int n2 = static_cast<int>(seq.encoded.size()) - width2 + 1;
            if (n1 <= 0 || n2 <= 0) continue;
            
            for (int p = 0; p < n1; p++) total1 += resp1[s][p];
            for (int p = 0; p < n2; p++) total2 += resp2[s][p];
        }

        double pseudo_strength1 = std::max(0.01, 1.0 / (1.0 + total1));
        double pseudo_strength2 = std::max(0.01, 1.0 / (1.0 + total2));
        pwm1.initialize_pseudocount_with_background(background.frequencies, pseudo_strength1);
        pwm2.initialize_pseudocount_with_background(background.frequencies, pseudo_strength2);

        total1 = 0.0; total2 = 0.0;
        double sum_none = 0.0, sum_m1 = 0.0, sum_m2 = 0.0, sum_both = 0.0;
        int valid_seqs = 0;

        for (size_t s = 0; s < sequences.size(); s++) {
            const auto& seq = sequences[s];
            int n1 = static_cast<int>(seq.encoded.size()) - width1 + 1;
            int n2 = static_cast<int>(seq.encoded.size()) - width2 + 1;
            if (n1 <= 0 || n2 <= 0) continue;
            
            valid_seqs++;
            sum_none += resp_none[s];
            sum_m1 += resp_motif1[s];
            sum_m2 += resp_motif2[s];
            sum_both += resp_both[s];

            for (int p = 0; p < n1; p++) {
                double w = resp1[s][p];
                total1 += w;
                for (int i = 0; i < width1; i++) {
                    int base = seq.encoded[p + i];
                    if (base >= 0 && base < 4) pwm1.matrix[i][base] += w;
                }
            }

            for (int p = 0; p < n2; p++) {
                double w = resp2[s][p];
                total2 += w;
                for (int i = 0; i < width2; i++) {
                    int base = seq.encoded[p + i];
                    if (base >= 0 && base < 4) pwm2.matrix[i][base] += w;
                }
            }
        }

        pwm1.normalize();
        pwm2.normalize();

        if (valid_seqs > 0) {
            double total = sum_none + sum_m1 + sum_m2 + sum_both;
            lambda0 = sum_none / total;
            lambda1 = sum_m1 / total;
            lambda2 = sum_m2 / total;
            lambda_both = sum_both / total;
            
            double min_lambda = 0.05;
            if (lambda0 < min_lambda) lambda0 = min_lambda;
            if (lambda1 < min_lambda) lambda1 = min_lambda;
            if (lambda2 < min_lambda) lambda2 = min_lambda;
            if (lambda_both < min_lambda) lambda_both = min_lambda;
            
            double sum = lambda0 + lambda1 + lambda2 + lambda_both;
            lambda0 /= sum;
            lambda1 /= sum;
            lambda2 /= sum;
            lambda_both /= sum;
        }
    }

    static std::vector<MotifSite> extract_sites(
        const std::vector<FastaSequence>& sequences,
        const PWM& pwm,
        const BackgroundModel& background,
        int width,
        const std::vector<std::vector<double>>& responsibilities,
        double threshold
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

            if (best_prob > threshold) {
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

    static double compute_correlation(
        const std::vector<double>& resp_motif1,
        const std::vector<double>& resp_motif2,
        const std::vector<double>& resp_both
    ) {
        int n = static_cast<int>(resp_motif1.size());
        double mean1 = 0, mean2 = 0;
        
        for (int i = 0; i < n; i++) {
            mean1 += resp_motif1[i] + resp_both[i];
            mean2 += resp_motif2[i] + resp_both[i];
        }
        mean1 /= n;
        mean2 /= n;

        double cov = 0, var1 = 0, var2 = 0;
        for (int i = 0; i < n; i++) {
            double x = resp_motif1[i] + resp_both[i] - mean1;
            double y = resp_motif2[i] + resp_both[i] - mean2;
            cov += x * y;
            var1 += x * x;
            var2 += y * y;
        }

        if (var1 > 0 && var2 > 0) {
            return cov / std::sqrt(var1 * var2);
        }
        return 0.0;
    }

    static std::vector<std::vector<double>> compute_combined_priors(
        const std::vector<FastaSequence>& sequences,
        int width,
        const Options& options,
        const PriorKnowledge* prior,
        const std::vector<RnaStructure>* rna_structures
    ) {
        auto combined_priors = Statistics::compute_all_position_priors(
            sequences, width, options.edge_penalty);

        if (options.use_prior_knowledge && prior != nullptr && prior->has_prior()) {
            auto knowledge_priors = prior->compute_log_prior_weights(
                sequences, width, options.prior_options);
            
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
                *rna_structures, width, options.rna_options);
            
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
        TCMResult& result,
        const std::vector<FastaSequence>& sequences,
        const BackgroundModel& background,
        const Options& options
    ) {
        auto score_dist1 = Statistics::simulate_score_distribution(result.motif1.pwm, background, 20000);
        auto score_dist2 = Statistics::simulate_score_distribution(result.motif2.pwm, background, 20000);
        
        double total_sites1 = 0, total_sites2 = 0;
        for (const auto& seq : sequences) {
            int n1 = static_cast<int>(seq.encoded.size()) - options.width1 + 1;
            int n2 = static_cast<int>(seq.encoded.size()) - options.width2 + 1;
            if (n1 > 0) total_sites1 += n1;
            if (n2 > 0) total_sites2 += n2;
        }

        double best_p1 = 1.0, best_p2 = 1.0;
        for (auto& site : result.motif1.sites) {
            site.p_value = Statistics::p_value_from_distribution(site.score, score_dist1);
            site.e_value = site.p_value * total_sites1;
            best_p1 = std::min(best_p1, site.p_value);
        }
        for (auto& site : result.motif2.sites) {
            site.p_value = Statistics::p_value_from_distribution(site.score, score_dist2);
            site.e_value = site.p_value * total_sites2;
            best_p2 = std::min(best_p2, site.p_value);
        }
        
        result.motif1.e_value = best_p1 * total_sites1;
        result.motif2.e_value = best_p2 * total_sites2;
    }
};

#endif
