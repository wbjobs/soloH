#ifndef OUTPUT_FORMATTER_H
#define OUTPUT_FORMATTER_H

#include "sequence.h"
#include "pwm.h"
#include "tcm_model.h"
#include <vector>
#include <string>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <cmath>
#include <algorithm>

class OutputFormatter {
public:
    static std::string generate_weblogo(const PWM& pwm, const BackgroundModel& background, int height = 10) {
        std::ostringstream oss;
        int width = pwm.width;
        
        std::vector<std::vector<double>> height_per_base(width, std::vector<double>(4, 0.0));
        
        for (int i = 0; i < width; i++) {
            double ic_total = 0.0;
            for (int j = 0; j < 4; j++) {
                if (pwm.matrix[i][j] > 0 && background.frequencies[j] > 0) {
                    double ic = pwm.matrix[i][j] * std::log2(pwm.matrix[i][j] / background.frequencies[j]);
                    height_per_base[i][j] = std::max(0.0, ic);
                    ic_total += height_per_base[i][j];
                }
            }
            
            if (ic_total > 0) {
                for (int j = 0; j < 4; j++) {
                    height_per_base[i][j] = (height_per_base[i][j] / ic_total) * std::min(2.0, ic_total);
                }
            }
        }

        std::vector<int> order(width);
        for (int i = 0; i < width; i++) order[i] = i;

        char bases[4] = {'A', 'C', 'G', 'T'};
        std::string colors[4] = {"\033[32m", "\033[34m", "\033[33m", "\033[31m"};
        std::string reset = "\033[0m";

        oss << "\n  +";
        for (int i = 0; i < width; i++) oss << "---";
        oss << "+\n";

        for (int h = height; h >= 1; h--) {
            double threshold = (h - 0.5) / height * 2.0;
            oss << std::fixed << std::setprecision(1) << std::setw(5) << threshold << " |";
            
            for (int i = 0; i < width; i++) {
                double cum = 0.0;
                char shown = ' ';
                
                std::vector<std::pair<double, char>> sorted;
                for (int j = 0; j < 4; j++) {
                    sorted.push_back({height_per_base[i][j], bases[j]});
                }
                std::sort(sorted.begin(), sorted.end(), std::greater<std::pair<double, char>>());
                
                for (auto& p : sorted) {
                    cum += p.first;
                    if (cum >= threshold) {
                        shown = p.second;
                        break;
                    }
                }
                
                if (shown != ' ') {
                    int color_idx = 0;
                    for (int j = 0; j < 4; j++) {
                        if (bases[j] == shown) color_idx = j;
                    }
                    oss << " " << colors[color_idx] << shown << reset << " ";
                } else {
                    oss << "   ";
                }
            }
            oss << "|\n";
        }

        oss << "  +";
        for (int i = 0; i < width; i++) oss << "---";
        oss << "+\n";
        
        oss << "      ";
        for (int i = 0; i < width; i++) {
            oss << " " << std::setw(2) << (i + 1);
        }
        oss << "\n\n";

        oss << "  Legend: " << colors[0] << "A (green)" << reset << " | " 
            << colors[1] << "C (blue)" << reset << " | " 
            << colors[2] << "G (yellow)" << reset << " | " 
            << colors[3] << "T (red)" << reset << "\n";
        oss << "  Y-axis: Information Content (bits)\n\n";

        return oss.str();
    }

    static std::string generate_weblogo_plain(const PWM& pwm, const BackgroundModel& background, int height = 10) {
        std::ostringstream oss;
        int width = pwm.width;
        
        std::vector<std::vector<double>> height_per_base(width, std::vector<double>(4, 0.0));
        
        for (int i = 0; i < width; i++) {
            double ic_total = 0.0;
            for (int j = 0; j < 4; j++) {
                if (pwm.matrix[i][j] > 0 && background.frequencies[j] > 0) {
                    double ic = pwm.matrix[i][j] * std::log2(pwm.matrix[i][j] / background.frequencies[j]);
                    height_per_base[i][j] = std::max(0.0, ic);
                    ic_total += height_per_base[i][j];
                }
            }
            
            if (ic_total > 0) {
                for (int j = 0; j < 4; j++) {
                    height_per_base[i][j] = (height_per_base[i][j] / ic_total) * std::min(2.0, ic_total);
                }
            }
        }

        char bases[4] = {'A', 'C', 'G', 'T'};

        oss << "\n  +";
        for (int i = 0; i < width; i++) oss << "---";
        oss << "+\n";

        for (int h = height; h >= 1; h--) {
            double threshold = (h - 0.5) / height * 2.0;
            oss << std::fixed << std::setprecision(1) << std::setw(5) << threshold << " |";
            
            for (int i = 0; i < width; i++) {
                double cum = 0.0;
                char shown = ' ';
                
                std::vector<std::pair<double, char>> sorted;
                for (int j = 0; j < 4; j++) {
                    sorted.push_back({height_per_base[i][j], bases[j]});
                }
                std::sort(sorted.begin(), sorted.end(), std::greater<std::pair<double, char>>());
                
                for (auto& p : sorted) {
                    cum += p.first;
                    if (cum >= threshold) {
                        shown = p.second;
                        break;
                    }
                }
                
                oss << " " << shown << " ";
            }
            oss << "|\n";
        }

        oss << "  +";
        for (int i = 0; i < width; i++) oss << "---";
        oss << "+\n";
        
        oss << "      ";
        for (int i = 0; i < width; i++) {
            oss << " " << std::setw(2) << (i + 1);
        }
        oss << "\n\n";

        oss << "  Legend: A (Adenine) | C (Cytosine) | G (Guanine) | T (Thymine)\n";
        oss << "  Y-axis: Information Content (bits)\n\n";

        return oss.str();
    }

    static std::string to_meme_format(const std::vector<MotifResult>& results, 
                                      const BackgroundModel& background,
                                      const std::string& command = "") {
        std::ostringstream oss;
        
        oss << "MEME version 5.5.0\n\n";
        oss << "ALPHABET= ACGT\n\n";
        oss << "strands: + -\n\n";
        oss << "Background letter frequencies\n";
        oss << std::fixed << std::setprecision(4);
        oss << "A " << background.frequencies[0] 
            << " C " << background.frequencies[1]
            << " G " << background.frequencies[2]
            << " T " << background.frequencies[3] << "\n\n";

        for (size_t idx = 0; idx < results.size(); idx++) {
            const auto& result = results[idx];
            
            oss << "MOTIF " << result.consensus << " motif_" << (idx + 1) << "\n";
            oss << "letter-probability matrix: alength= 4 w= " << result.width 
                << " nsites= " << result.sites.size() 
                << " E= " << std::scientific << result.e_value << "\n";
            
            oss << std::fixed << std::setprecision(4);
            for (int i = 0; i < result.width; i++) {
                oss << "  " << result.pwm.matrix[i][0]
                    << "  " << result.pwm.matrix[i][1]
                    << "  " << result.pwm.matrix[i][2]
                    << "  " << result.pwm.matrix[i][3] << "\n";
            }
            oss << "\n";
            
            if (!result.sites.empty()) {
                oss << "Motif " << (idx + 1) << " sites sorted by position p-value\n";
                oss << "--------------------------------------------------------------------------------\n";
                oss << "Sequence name\tStart\tStrand\tP-value\t\tSite\n";
                oss << "--------------------------------------------------------------------------------\n";
                
                for (const auto& site : result.sites) {
                    oss << "seq_" << site.seq_index << "\t"
                        << (site.position + 1) << "\t"
                        << (site.strand > 0 ? "+" : "-") << "\t"
                        << std::scientific << site.p_value << "\t"
                        << site.sequence << "\n";
                }
                oss << "--------------------------------------------------------------------------------\n\n";
            }
        }

        return oss.str();
    }

    static std::string format_result_summary(const MotifResult& result, 
                                             const std::vector<FastaSequence>& sequences,
                                             int motif_num = 1) {
        std::ostringstream oss;
        
        oss << "=============================================================================\n";
        oss << "Motif " << motif_num << ": " << result.consensus << "\n";
        oss << "=============================================================================\n";
        oss << "Algorithm: " << result.algorithm << "\n";
        oss << "Model: " << result.model << "\n";
        oss << "Width: " << result.width << " bp\n";
        oss << "Information Content: " << std::fixed << std::setprecision(4) 
            << result.information_content << " bits\n";
        oss << "E-value: " << std::scientific << result.e_value << "\n";
        oss << "Number of sites: " << result.sites.size() << "\n\n";
        
        oss << "Position Weight Matrix (PWM):\n";
        oss << result.pwm.to_string() << "\n";
        
        if (!result.sites.empty()) {
            oss << "Matching sites:\n";
            oss << std::fixed << std::setprecision(4);
            oss << std::left << std::setw(10) << "Sequence" 
                << std::setw(8) << "Start" 
                << std::setw(10) << "Score"
                << std::setw(14) << "P-value"
                << std::setw(14) << "E-value"
                << "Site" << "\n";
            oss << std::string(70, '-') << "\n";
            
            for (const auto& site : result.sites) {
                std::string seq_name = site.seq_index < static_cast<int>(sequences.size()) ? 
                    sequences[site.seq_index].name : ("seq_" + std::to_string(site.seq_index));
                if (seq_name.length() > 8) seq_name = seq_name.substr(0, 8);
                
                oss << std::left << std::setw(10) << seq_name
                    << std::setw(8) << (site.position + 1)
                    << std::setw(10) << site.score
                    << std::scientific << std::setw(14) << site.p_value
                    << std::setw(14) << site.e_value
                    << site.sequence << "\n";
            }
            oss << "\n";
        }
        
        return oss.str();
    }

    static std::string format_tcm_summary(const TCMResult& result,
                                          const std::vector<FastaSequence>& sequences) {
        std::ostringstream oss;
        
        oss << "=============================================================================\n";
        oss << "TCM (Two Component Model) Analysis Results\n";
        oss << "=============================================================================\n";
        oss << "Log Likelihood: " << std::fixed << std::setprecision(4) << result.log_likelihood << "\n";
        oss << "Motif Correlation: " << std::fixed << std::setprecision(4) << result.correlation << "\n\n";
        
        oss << format_result_summary(result.motif1, sequences, 1);
        oss << format_result_summary(result.motif2, sequences, 2);
        
        return oss.str();
    }

    static void write_meme_file(const std::string& filename, 
                                const std::vector<MotifResult>& results,
                                const BackgroundModel& background,
                                const std::string& command = "") {
        std::ofstream file(filename);
        if (!file.is_open()) {
            throw std::runtime_error("Cannot open file for writing: " + filename);
        }
        file << to_meme_format(results, background, command);
        file.close();
    }
};

#endif
