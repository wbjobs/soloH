#ifndef RNA_STRUCTURE_H
#define RNA_STRUCTURE_H

#include "sequence.h"
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <memory>
#include <stdexcept>

enum class NucleotideType {
    A = 0,
    C = 1,
    G = 2,
    U = 3,
    T = 3,
    N = 4
};

enum class StructureType {
    UNPAIRED = 0,
    STEM = 1,
    LOOP = 2,
    BULGE = 3,
    MULTILOOP = 4,
    HAIRPIN = 5
};

struct BasePair {
    int i;
    int j;
    double energy;
    double probability;
};

struct RnaStructure {
    std::vector<StructureType> structure;
    std::vector<int> pair_partner;
    std::vector<double> pairing_probability;
    std::vector<double> accessibility;
    std::vector<BasePair> base_pairs;
    double min_free_energy;
};

class RnaStructurePredictor {
public:
    struct Options {
        double stem_bonus = 2.0;
        double loop_penalty = 0.5;
        double hairpin_loop_bonus = 1.5;
        double bulge_penalty = 1.0;
        int min_stem_length = 3;
        int max_loop_length = 20;
        int min_hairpin_loop = 3;
        bool allow_gu_pairing = true;
        double structure_weight = 1.0;
        double min_accessibility = 0.1;
    };

    static bool is_base_pair(int base1, int base2, bool allow_gu = true) {
        int b1 = base1 % 4;
        int b2 = base2 % 4;
        
        if ((b1 == 0 && b2 == 3) || (b1 == 3 && b2 == 0)) return true;
        if ((b1 == 1 && b2 == 2) || (b1 == 2 && b2 == 1)) return true;
        if (allow_gu && ((b1 == 2 && b2 == 3) || (b1 == 3 && b2 == 2))) return true;
        
        return false;
    }

    static double base_pair_energy(int base1, int base2) {
        int b1 = base1 % 4;
        int b2 = base2 % 4;
        
        if ((b1 == 0 && b2 == 3) || (b1 == 3 && b2 == 0)) return -2.0;
        if ((b1 == 1 && b2 == 2) || (b1 == 2 && b2 == 1)) return -3.0;
        if ((b1 == 2 && b2 == 3) || (b1 == 3 && b2 == 2)) return -1.0;
        
        return 0.0;
    }

    static RnaStructure predict(const FastaSequence& seq, const Options& options) {
        int n = static_cast<int>(seq.encoded.size());
        RnaStructure result;
        
        result.structure.assign(n, StructureType::UNPAIRED);
        result.pair_partner.assign(n, -1);
        result.pairing_probability.assign(n, 0.0);
        result.accessibility.assign(n, 1.0);

        if (n < 6) {
            return result;
        }

        std::vector<std::vector<double>> dp(n, std::vector<double>(n, 0.0));
        std::vector<std::vector<int>> trace(n, std::vector<int>(n, -1));

        for (int len = 1; len < n; len++) {
            for (int i = 0; i + len < n; i++) {
                int j = i + len;
                
                dp[i][j] = dp[i + 1][j];
                trace[i][j] = -1;

                if (is_base_pair(seq.encoded[i], seq.encoded[j], options.allow_gu_pairing) &&
                    len >= options.min_hairpin_loop) {
                    
                    double pair_energy = base_pair_energy(seq.encoded[i], seq.encoded[j]);
                    
                    double score = pair_energy;
                    if (j > i + 1) {
                        score += dp[i + 1][j - 1];
                    }

                    if (score < dp[i][j]) {
                        dp[i][j] = score;
                        trace[i][j] = j;
                    }

                    for (int k = i + 1; k < j; k++) {
                        double split_score = dp[i][k] + dp[k + 1][j];
                        if (split_score < dp[i][j]) {
                            dp[i][j] = split_score;
                            trace[i][j] = -k - 2;
                        }
                    }
                }
            }
        }

        result.min_free_energy = dp[0][n - 1];
        
        std::vector<BasePair> pairs;
        traceback(trace, 0, n - 1, pairs, result.pair_partner);

        std::vector<std::vector<double>> pair_prob(n, std::vector<double>(n, 0.0));
        compute_pairing_probabilities(seq, options, pair_prob);

        for (int i = 0; i < n; i++) {
            double prob = 0.0;
            for (int j = 0; j < n; j++) {
                prob += pair_prob[i][j];
            }
            result.pairing_probability[i] = std::min(1.0, prob);
            result.accessibility[i] = 1.0 - result.pairing_probability[i];
        }

        annotate_structure(seq, result, pairs, options);

        result.base_pairs = pairs;

        return result;
    }

    static std::vector<std::vector<double>> compute_structure_weights(
        const std::vector<RnaStructure>& structures,
        int motif_width,
        const Options& options
    ) {
        std::vector<std::vector<double>> weights(structures.size());

        for (size_t s = 0; s < structures.size(); s++) {
            int n = static_cast<int>(structures[s].accessibility.size());
            int n_positions = n - motif_width + 1;
            
            if (n_positions <= 0) {
                weights[s] = std::vector<double>();
                continue;
            }

            weights[s].assign(n_positions, 1.0);

            for (int p = 0; p < n_positions; p++) {
                double avg_accessibility = 0.0;
                double loop_score = 0.0;
                double stem_count = 0.0;
                bool contains_stem = false;
                bool contains_hairpin = false;

                for (int i = 0; i < motif_width; i++) {
                    int pos = p + i;
                    avg_accessibility += structures[s].accessibility[pos];
                    
                    if (structures[s].structure[pos] == StructureType::LOOP ||
                        structures[s].structure[pos] == StructureType::HAIRPIN) {
                        loop_score += 1.0;
                    }
                    if (structures[s].structure[pos] == StructureType::STEM) {
                        stem_count += 1.0;
                        contains_stem = true;
                    }
                    if (structures[s].structure[pos] == StructureType::HAIRPIN) {
                        contains_hairpin = true;
                    }
                }

                avg_accessibility /= motif_width;
                loop_score /= motif_width;
                stem_count /= motif_width;

                double weight = 1.0;
                
                weight *= (options.min_accessibility + avg_accessibility);
                
                weight *= (1.0 + options.hairpin_loop_bonus * loop_score);
                
                if (contains_hairpin) {
                    weight *= (1.0 + options.hairpin_loop_bonus);
                }
                
                if (contains_stem) {
                    weight *= (1.0 - options.stem_bonus * stem_count * 0.5);
                }

                weights[s][p] = std::max(0.1, weight * options.structure_weight);
            }
        }

        return weights;
    }

    static std::vector<std::vector<double>> compute_log_structure_weights(
        const std::vector<RnaStructure>& structures,
        int motif_width,
        const Options& options
    ) {
        auto weights = compute_structure_weights(structures, motif_width, options);
        std::vector<std::vector<double>> log_weights(weights.size());
        
        for (size_t s = 0; s < weights.size(); s++) {
            log_weights[s].resize(weights[s].size());
            for (size_t p = 0; p < weights[s].size(); p++) {
                log_weights[s][p] = std::log(weights[s][p]);
            }
        }
        
        return log_weights;
    }

    static std::vector<RnaStructure> predict_all(
        const std::vector<FastaSequence>& sequences,
        const Options& options
    ) {
        std::vector<RnaStructure> structures(sequences.size());
        
        #ifdef _OPENMP
        #pragma omp parallel for schedule(dynamic)
        #endif
        for (int s = 0; s < static_cast<int>(sequences.size()); s++) {
            structures[s] = predict(sequences[s], options);
        }
        
        return structures;
    }

    static std::vector<std::vector<double>> compute_loop_enrichment_weights(
        const std::vector<RnaStructure>& structures,
        int motif_width
    ) {
        std::vector<std::vector<double>> weights(structures.size());

        for (size_t s = 0; s < structures.size(); s++) {
            int n = static_cast<int>(structures[s].structure.size());
            int n_positions = n - motif_width + 1;
            
            if (n_positions <= 0) {
                weights[s] = std::vector<double>();
                continue;
            }

            weights[s].assign(n_positions, 0.0);

            for (int p = 0; p < n_positions; p++) {
                int loop_count = 0;
                int hairpin_count = 0;
                int stem_count = 0;
                bool spans_loop = false;

                for (int i = 0; i < motif_width; i++) {
                    int pos = p + i;
                    if (structures[s].structure[pos] == StructureType::LOOP) {
                        loop_count++;
                        spans_loop = true;
                    }
                    if (structures[s].structure[pos] == StructureType::HAIRPIN) {
                        hairpin_count++;
                        spans_loop = true;
                    }
                    if (structures[s].structure[pos] == StructureType::STEM) {
                        stem_count++;
                    }
                }

                double score = 0.0;
                if (spans_loop) {
                    score = static_cast<double>(loop_count + hairpin_count * 2) / motif_width;
                }
                
                if (stem_count >= motif_width * 0.8) {
                    score = -1.0;
                }

                weights[s][p] = score;
            }
        }

        return weights;
    }

private:
    static void traceback(
        const std::vector<std::vector<int>>& trace,
        int i, int j,
        std::vector<BasePair>& pairs,
        std::vector<int>& partner
    ) {
        if (i >= j) return;

        int t = trace[i][j];
        if (t == -1) {
            traceback(trace, i + 1, j, pairs, partner);
        } else if (t >= 0) {
            BasePair bp;
            bp.i = i;
            bp.j = j;
            bp.energy = 0.0;
            bp.probability = 1.0;
            pairs.push_back(bp);
            partner[i] = j;
            partner[j] = i;
            traceback(trace, i + 1, j - 1, pairs, partner);
        } else {
            int k = -t - 2;
            traceback(trace, i, k, pairs, partner);
            traceback(trace, k + 1, j, pairs, partner);
        }
    }

    static void compute_pairing_probabilities(
        const FastaSequence& seq,
        const Options& options,
        std::vector<std::vector<double>>& pair_prob
    ) {
        int n = static_cast<int>(seq.encoded.size());
        if (n < 2) return;

        double temperature = 310.15;
        double kT = 0.001987 * temperature;

        std::vector<std::vector<double>> Q(n, std::vector<double>(n, 0.0));
        std::vector<std::vector<double>> Qb(n, std::vector<double>(n, 0.0));

        for (int i = 0; i < n; i++) {
            Q[i][i] = 1.0;
            if (i > 0) Q[i][i - 1] = 1.0;
        }

        for (int len = 1; len < n; len++) {
            for (int i = 0; i + len < n; i++) {
                int j = i + len;
                
                Q[i][j] = Q[i + 1][j];
                
                if (is_base_pair(seq.encoded[i], seq.encoded[j], options.allow_gu_pairing) &&
                    len >= options.min_hairpin_loop) {
                    
                    double energy = base_pair_energy(seq.encoded[i], seq.encoded[j]);
                    double boltzmann = std::exp(-energy / kT);
                    
                    Qb[i][j] = boltzmann * Q[i + 1][j - 1];
                    
                    for (int k = i + 1; k < j; k++) {
                        Q[i][j] += Q[i][k - 1] * Qb[k][j];
                    }
                }

                for (int k = i; k < j; k++) {
                    for (int l = k + 1; l <= j; l++) {
                        if (is_base_pair(seq.encoded[k], seq.encoded[l], options.allow_gu_pairing) &&
                            (l - k) >= options.min_hairpin_loop) {
                            
                            double energy = base_pair_energy(seq.encoded[k], seq.encoded[l]);
                            double boltzmann = std::exp(-energy / kT);
                            
                            double q_outer = Q[i][k - 1] * Q[l + 1][j];
                            double q_inner = 1.0;
                            if (k + 1 < l - 1) {
                                q_inner = Q[k + 1][l - 1];
                            }
                            
                            pair_prob[k][l] += boltzmann * q_outer * q_inner;
                        }
                    }
                }
            }
        }

        double Z = Q[0][n - 1];
        if (Z > 0) {
            for (int i = 0; i < n; i++) {
                for (int j = 0; j < n; j++) {
                    pair_prob[i][j] /= Z;
                }
            }
        }
    }

    static void annotate_structure(
        const FastaSequence& seq,
        RnaStructure& result,
        const std::vector<BasePair>& pairs,
        const Options& options
    ) {
        int n = static_cast<int>(seq.encoded.size());
        
        std::vector<bool> is_stem(n, false);
        for (const auto& bp : pairs) {
            is_stem[bp.i] = true;
            is_stem[bp.j] = true;
        }

        for (int i = 0; i < n; i++) {
            if (is_stem[i]) {
                result.structure[i] = StructureType::STEM;
            } else {
                int left_stem = -1;
                int right_stem = -1;
                
                for (int k = i - 1; k >= 0; k--) {
                    if (is_stem[k]) {
                        left_stem = k;
                        break;
                    }
                }
                for (int k = i + 1; k < n; k++) {
                    if (is_stem[k]) {
                        right_stem = k;
                        break;
                    }
                }

                if (left_stem >= 0 && right_stem >= 0) {
                    int loop_size = right_stem - left_stem - 1;
                    
                    if (result.pair_partner[left_stem] == right_stem) {
                        result.structure[i] = StructureType::HAIRPIN;
                    } else if (loop_size <= 2) {
                        result.structure[i] = StructureType::BULGE;
                    } else {
                        result.structure[i] = StructureType::LOOP;
                    }
                } else {
                    result.structure[i] = StructureType::LOOP;
                }
            }
        }

        for (int i = 0; i < n; i++) {
            if (is_stem[i]) {
                continue;
            }
            
            int j = i;
            while (j < n && !is_stem[j]) j++;
            int unpaired_len = j - i;
            
            if (unpaired_len <= 2) {
                bool adjacent_to_stem = (i > 0 && is_stem[i - 1]) || (j < n && is_stem[j]);
                if (adjacent_to_stem) {
                    for (int k = i; k < j; k++) {
                        result.structure[k] = StructureType::BULGE;
                    }
                }
            }
            
            i = j - 1;
        }
    }
};

#endif
