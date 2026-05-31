#ifndef PWM_H
#define PWM_H

#include <vector>
#include <cmath>
#include <string>
#include <iomanip>
#include <sstream>
#include <algorithm>

class PWM {
public:
    int width;
    std::vector<std::vector<double>> matrix;

    PWM() : width(0) {}
    
    PWM(int w) : width(w), matrix(w, std::vector<double>(4, 0.0)) {}

    void initialize_pseudocount(double pseudocount = 0.1) {
        for (int i = 0; i < width; i++) {
            for (int j = 0; j < 4; j++) {
                matrix[i][j] = pseudocount;
            }
        }
    }

    void initialize_pseudocount_with_background(const std::vector<double>& background, 
                                                 double pseudo_strength = 0.05) {
        for (int i = 0; i < width; i++) {
            for (int j = 0; j < 4; j++) {
                matrix[i][j] = pseudo_strength * background[j];
            }
        }
    }

    void normalize() {
        for (int i = 0; i < width; i++) {
            double sum = 0.0;
            for (int j = 0; j < 4; j++) sum += matrix[i][j];
            if (sum > 0) {
                for (int j = 0; j < 4; j++) matrix[i][j] /= sum;
            }
        }
    }

    double score_site(const std::vector<int>& seq, int pos, const std::vector<double>& background) const {
        double score = 0.0;
        for (int i = 0; i < width; i++) {
            int base = seq[pos + i];
            if (base < 0 || base > 3) continue;
            if (matrix[i][base] > 0 && background[base] > 0) {
                score += std::log2(matrix[i][base] / background[base]);
            }
        }
        return score;
    }

    double information_content(const std::vector<double>& background) const {
        double ic = 0.0;
        for (int i = 0; i < width; i++) {
            for (int j = 0; j < 4; j++) {
                if (matrix[i][j] > 0) {
                    ic += matrix[i][j] * std::log2(matrix[i][j] / background[j]);
                }
            }
        }
        return ic;
    }

    std::string consensus() const {
        std::string result;
        for (int i = 0; i < width; i++) {
            int max_base = 0;
            double max_val = matrix[i][0];
            for (int j = 1; j < 4; j++) {
                if (matrix[i][j] > max_val) {
                    max_val = matrix[i][j];
                    max_base = j;
                }
            }
            result += "ACGT"[max_base];
        }
        return result;
    }

    std::string to_string() const {
        std::ostringstream oss;
        oss << std::fixed << std::setprecision(4);
        for (int j = 0; j < 4; j++) {
            oss << (j == 0 ? "A:" : j == 1 ? "C:" : j == 2 ? "G:" : "T:");
            for (int i = 0; i < width; i++) {
                oss << " " << std::setw(7) << matrix[i][j];
            }
            oss << "\n";
        }
        return oss.str();
    }
};

class BackgroundModel {
public:
    std::vector<double> frequencies;
    double gc_content;

    BackgroundModel() : frequencies(4, 0.25), gc_content(0.5) {}

    void estimate(const std::vector<FastaSequence>& sequences) {
        double counts[4] = {0, 0, 0, 0};
        double total = 0;
        
        for (const auto& seq : sequences) {
            for (int base : seq.encoded) {
                if (base >= 0 && base < 4) {
                    counts[base]++;
                    total++;
                }
            }
        }

        for (int i = 0; i < 4; i++) {
            frequencies[i] = (counts[i] + 0.25) / (total + 1.0);
        }
        gc_content = frequencies[1] + frequencies[2];
    }

    double log_background(int base) const {
        if (base >= 0 && base < 4 && frequencies[base] > 0) {
            return std::log(frequencies[base]);
        }
        return std::log(0.25);
    }
};

struct MotifSite {
    int seq_index;
    int position;
    std::string sequence;
    double score;
    double p_value;
    double e_value;
    int strand;
};

struct MotifResult {
    PWM pwm;
    int width;
    double information_content;
    double e_value;
    std::string consensus;
    std::vector<MotifSite> sites;
    std::string algorithm;
    std::string model;
};

#endif
