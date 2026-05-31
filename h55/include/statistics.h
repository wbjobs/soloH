#ifndef STATISTICS_H
#define STATISTICS_H

#include <vector>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <stdexcept>

class Statistics {
public:
    static double log_sum_exp(const std::vector<double>& log_probs) {
        if (log_probs.empty()) return -std::numeric_limits<double>::infinity();
        
        double max_log = *std::max_element(log_probs.begin(), log_probs.end());
        if (max_log == -std::numeric_limits<double>::infinity()) {
            return max_log;
        }
        
        double sum = 0.0;
        for (double lp : log_probs) {
            sum += std::exp(lp - max_log);
        }
        return max_log + std::log(sum);
    }

    static double log_sum_exp(double a, double b) {
        if (a == -std::numeric_limits<double>::infinity()) return b;
        if (b == -std::numeric_limits<double>::infinity()) return a;
        if (a > b) {
            return a + std::log1p(std::exp(b - a));
        }
        return b + std::log1p(std::exp(a - b));
    }

    static double calculate_p_value(double score, const std::vector<double>& score_distribution) {
        int count = 0;
        for (double s : score_distribution) {
            if (s >= score) count++;
        }
        return static_cast<double>(count) / score_distribution.size();
    }

    static double calculate_e_value(double p_value, int num_sequences, int seq_length, int motif_width) {
        int num_sites_per_seq = seq_length - motif_width + 1;
        long long total_sites = static_cast<long long>(num_sequences) * num_sites_per_seq;
        return p_value * total_sites;
    }

    static std::vector<double> simulate_score_distribution(
        const PWM& pwm,
        const BackgroundModel& background,
        int num_simulations = 10000
    ) {
        std::vector<double> scores;
        scores.reserve(num_simulations);
        
        std::vector<int> random_seq(pwm.width);
        
        for (int i = 0; i < num_simulations; i++) {
            for (int j = 0; j < pwm.width; j++) {
                double r = static_cast<double>(rand()) / RAND_MAX;
                double cum = 0.0;
                int base = 0;
                for (; base < 4; base++) {
                    cum += background.frequencies[base];
                    if (r <= cum) break;
                }
                random_seq[j] = std::min(base, 3);
            }
            double score = pwm.score_site(random_seq, 0, background.frequencies);
            scores.push_back(score);
        }
        
        std::sort(scores.begin(), scores.end());
        return scores;
    }

    static double p_value_from_distribution(double score, const std::vector<double>& sorted_scores) {
        auto it = std::lower_bound(sorted_scores.begin(), sorted_scores.end(), score);
        int count = sorted_scores.end() - it;
        return static_cast<double>(count) / sorted_scores.size();
    }

    static double compute_gc_content(const std::string& seq) {
        int gc = 0, at = 0;
        for (char c : seq) {
            if (c == 'G' || c == 'C' || c == 'g' || c == 'c') gc++;
            else if (c == 'A' || c == 'T' || c == 'a' || c == 't') at++;
        }
        int total = gc + at;
        return total > 0 ? static_cast<double>(gc) / total : 0.5;
    }

    static std::vector<double> compute_position_prior(int seq_length, int motif_width, double edge_penalty = 0.5) {
        int n_positions = seq_length - motif_width + 1;
        if (n_positions <= 0) {
            return std::vector<double>();
        }

        std::vector<double> prior(n_positions, 1.0);
        
        if (n_positions <= 2 * motif_width) {
            return prior;
        }

        int buffer = motif_width;
        for (int p = 0; p < n_positions; p++) {
            double dist_from_start = static_cast<double>(p);
            double dist_from_end = static_cast<double>(n_positions - 1 - p);
            
            double min_dist = std::min(dist_from_start, dist_from_end);
            double penalty = 1.0;
            
            if (min_dist < buffer) {
                double ratio = min_dist / buffer;
                penalty = edge_penalty + (1.0 - edge_penalty) * ratio * ratio;
            }
            
            prior[p] = penalty;
        }

        double sum = 0.0;
        for (double p : prior) sum += p;
        for (double& p : prior) p /= sum;

        return prior;
    }

    static std::vector<double> compute_position_prior_log(int seq_length, int motif_width, double edge_penalty = 0.5) {
        auto prior = compute_position_prior(seq_length, motif_width, edge_penalty);
        std::vector<double> log_prior(prior.size());
        for (size_t i = 0; i < prior.size(); i++) {
            log_prior[i] = std::log(prior[i]);
        }
        return log_prior;
    }

    static std::vector<std::vector<double>> compute_all_position_priors(
        const std::vector<FastaSequence>& sequences,
        int motif_width,
        double edge_penalty = 0.5
    ) {
        std::vector<std::vector<double>> log_priors(sequences.size());
        for (size_t s = 0; s < sequences.size(); s++) {
            int seq_len = static_cast<int>(sequences[s].encoded.size());
            log_priors[s] = compute_position_prior_log(seq_len, motif_width, edge_penalty);
        }
        return log_priors;
    }
};

#endif
