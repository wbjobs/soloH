#include "hbsolver/output.h"
#include <fstream>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <cmath>
#include <algorithm>

namespace hbsolver {

bool OutputWriter::writeSpectrumCSV(const HBSolution& solution,
                                     const std::string& filename,
                                     const std::string& separator) {
    std::ofstream file(filename);
    if (!file.is_open()) return false;

    file << "Frequency(Hz)" << separator << "Label" << separator
         << "Magnitude(V)" << separator << "Phase(rad)" << separator
         << "Real(V)" << separator << "Imag(V)" << separator
         << "Power(dBm)" << std::endl;

    for (const auto& line : solution.spectrum) {
        file << std::fixed << std::setprecision(2) << line.frequency << separator
             << line.label << separator
             << std::scientific << std::setprecision(6) << std::abs(line.amplitude) << separator
             << std::fixed << std::setprecision(6) << std::arg(line.amplitude) << separator
             << std::scientific << std::setprecision(6) << std::real(line.amplitude) << separator
             << std::scientific << std::setprecision(6) << std::imag(line.amplitude) << separator
             << std::fixed << std::setprecision(2) << line.power_dBm << std::endl;
    }

    file.close();
    return true;
}

bool OutputWriter::writeSweepCSV(const std::vector<SweepAnalysis::SweepResult>& results,
                                  const std::string& filename,
                                  const std::string& sweep_type,
                                  const std::string& separator) {
    std::ofstream file(filename);
    if (!file.is_open()) return false;

    file << "Parameter" << separator
         << "Fundamental(dBm)" << separator
         << "Harmonic2(dBm)" << separator
         << "Harmonic3(dBm)" << separator
         << "IM3(dBm)" << separator
         << "IM5(dBm)" << separator
         << "Converged" << separator
         << "Iterations" << separator
         << "Residual" << std::endl;

    for (const auto& result : results) {
        file << std::fixed << std::setprecision(3) << result.parameter << separator
             << std::fixed << std::setprecision(2) << result.metrics.fundamental_power << separator
             << std::fixed << std::setprecision(2) << result.metrics.harmonic2_power << separator
             << std::fixed << std::setprecision(2) << result.metrics.harmonic3_power << separator
             << std::fixed << std::setprecision(2) << result.metrics.im3_power << separator
             << std::fixed << std::setprecision(2) << result.metrics.im5_power << separator
             << (result.solution.converged ? "Yes" : "No") << separator
             << result.solution.iterations << separator
             << std::scientific << std::setprecision(6) << result.solution.residual_norm << std::endl;
    }

    file.close();
    return true;
}

bool OutputWriter::writeTimeDomainCSV(const HBSolution& solution,
                                       const std::string& filename,
                                       const std::string& separator) {
    std::ofstream file(filename);
    if (!file.is_open()) return false;

    file << "Time(s)" << separator << "Voltage(V)" << separator << "Current(A)" << std::endl;

    int n = static_cast<int>(std::min(solution.time_voltage.size(), solution.time_current.size()));
    double dt = 1.0 / (solution.time_voltage.size() * 1.0);
    if (n > 1) dt = 1.0 / (solution.time_voltage.size() * 1.0);

    for (int i = 0; i < n; ++i) {
        double t = i * dt;
        file << std::scientific << std::setprecision(8) << t << separator
             << std::scientific << std::setprecision(8) << solution.time_voltage[i] << separator
             << std::scientific << std::setprecision(8) << solution.time_current[i] << std::endl;
    }

    file.close();
    return true;
}

std::string OutputWriter::generateAsciiSpectrum(const HBSolution& solution,
                                                 int width,
                                                 int height,
                                                 double min_dB,
                                                 double max_dB) {
    std::ostringstream oss;
    int num_lines = static_cast<int>(solution.spectrum.size());

    oss << std::string(width, '=') << std::endl;
    oss << "  Frequency Spectrum (ASCII Plot)" << std::endl;
    oss << std::string(width, '-') << std::endl;

    oss << std::right << std::setw(10) << "Freq(Hz)" << " ";
    oss << std::left << std::setw(12) << "Label" << " ";
    oss << std::right << std::setw(8) << "dBm" << " |";

    int bar_width = width - 38;
    for (int h = 0; h < height; ++h) {
        double threshold = max_dB - (max_dB - min_dB) * h / (height - 1);
        if (h == 0) oss << " " << std::fixed << std::setprecision(0) << max_dB << "dB";
        else if (h == height - 1) oss << " " << std::fixed << std::setprecision(0) << min_dB << "dB";
    }
    oss << std::endl;

    for (const auto& line : solution.spectrum) {
        if (line.frequency < 1e-6 && std::abs(line.amplitude) < 1e-9) continue;

        std::string freq_str;
        if (line.frequency < 1e-6) freq_str = "DC";
        else if (line.frequency < 1e3) freq_str = std::to_string(static_cast<int>(line.frequency)) + "Hz";
        else if (line.frequency < 1e6) freq_str = std::to_string(static_cast<int>(line.frequency/1e3)) + "kHz";
        else freq_str = std::to_string(static_cast<int>(line.frequency/1e6)) + "MHz";

        oss << std::right << std::setw(10) << freq_str << " ";
        oss << std::left << std::setw(12) << line.label << " ";
        oss << std::right << std::fixed << std::setprecision(1) << std::setw(7) << line.power_dBm << " |";

        double normalized = (line.power_dBm - min_dB) / (max_dB - min_dB);
        normalized = std::max(0.0, std::min(1.0, normalized));
        int num_chars = static_cast<int>(normalized * bar_width);

        oss << std::string(num_chars, '#');
        oss << std::endl;
    }

    oss << std::string(width, '=') << std::endl;
    return oss.str();
}

std::string OutputWriter::generateAsciiTimeDomain(const HBSolution& solution,
                                                   int width,
                                                   int height) {
    std::ostringstream oss;
    int n = static_cast<int>(solution.time_voltage.size());
    if (n == 0) return "No time domain data available";

    oss << std::string(width, '=') << std::endl;
    oss << "  Time Domain Waveform" << std::endl;
    oss << std::string(width, '-') << std::endl;

    double v_max = *std::max_element(solution.time_voltage.begin(), solution.time_voltage.end());
    double v_min = *std::min_element(solution.time_voltage.begin(), solution.time_voltage.end());
    double v_range = v_max - v_min;
    if (v_range < 1e-12) {
        v_max = 1.0;
        v_min = -1.0;
        v_range = 2.0;
    }

    int step = std::max(1, n / width);
    int num_points = n / step;

    oss << std::string(12, ' ') << "+" << std::string(width - 12, '-') << "+ " << std::fixed << std::setprecision(2) << v_max << "V" << std::endl;

    for (int row = 0; row < height; ++row) {
        double v_threshold = v_max - v_range * row / (height - 1);

        oss << std::string(10, ' ') << std::fixed << std::setprecision(2) << std::setw(6) << v_threshold << "V |";

        for (int col = 0; col < num_points; ++col) {
            int idx = col * step;
            if (idx >= n) break;

            double v = solution.time_voltage[idx];
            if (row == height - 1 && v <= v_threshold) {
                oss << '*';
            } else if (row == 0 && v >= v_threshold) {
                oss << '*';
            } else if (row > 0 && row < height - 1) {
                double v_next = (col + 1 < num_points && (col + 1) * step < n) ?
                                 solution.time_voltage[(col + 1) * step] : v;
                if ((v >= v_threshold && v_next < v_threshold) ||
                    (v < v_threshold && v_next >= v_threshold)) {
                    oss << '*';
                } else {
                    oss << ' ';
                }
            } else {
                oss << ' ';
            }
        }
        oss << "|" << std::endl;
    }

    oss << std::string(12, ' ') << "+" << std::string(width - 12, '-') << "+ " << std::fixed << std::setprecision(2) << v_min << "V" << std::endl;
    oss << std::string(12, ' ') << "0.0s" << std::string(width - 24, ' ')
        << std::fixed << std::setprecision(2) << (1.0 / (solution.time_voltage.size() > 0 ? solution.time_voltage.size() : 1) * n) << "s" << std::endl;
    oss << std::string(width, '=') << std::endl;

    return oss.str();
}

std::string OutputWriter::generateSweepPlot(const std::vector<SweepAnalysis::SweepResult>& results,
                                             const std::string& sweep_type,
                                             int width,
                                             int height) {
    std::ostringstream oss;
    if (results.empty()) return "No sweep data available";

    oss << std::string(width, '=') << std::endl;
    oss << "  " << (sweep_type == "power" ? "Power" : "Frequency") << " Sweep Results" << std::endl;
    oss << std::string(width, '-') << std::endl;

    double min_power = 1e9, max_power = -1e9;
    for (const auto& r : results) {
        min_power = std::min(min_power, r.metrics.fundamental_power);
        max_power = std::max(max_power, r.metrics.fundamental_power);
    }

    double power_range = max_power - min_power;
    if (power_range < 1) power_range = 10;

    int num_points = static_cast<int>(results.size());
    int plot_width = width - 20;

    oss << std::right << std::setw(10) << (sweep_type == "power" ? "Pin(dBm)" : "Freq(Hz)") << " | ";
    oss << std::left << std::setw(plot_width) << "Fundamental Output Power (dBm)";
    oss << " | " << std::setw(8) << "Pout(dBm)" << std::endl;

    for (int i = 0; i < num_points; ++i) {
        const auto& r = results[i];
        double normalized = (r.metrics.fundamental_power - min_power + 2) / (power_range + 4);
        normalized = std::max(0.0, std::min(1.0, normalized));
        int bar_len = static_cast<int>(normalized * plot_width);

        oss << std::right << std::fixed << std::setprecision(2) << std::setw(10) << r.parameter << " | ";
        oss << std::string(bar_len, '#');
        oss << std::string(plot_width - bar_len, ' ');
        oss << " | " << std::fixed << std::setprecision(2) << std::setw(8) << r.metrics.fundamental_power << std::endl;
    }

    oss << std::string(width, '=') << std::endl;
    return oss.str();
}

void OutputWriter::printPowerMetrics(const PowerMetrics& metrics, std::ostream& os) {
    os << std::endl;
    os << "=== Power Metrics ===" << std::endl;
    os << "  Fundamental Power: " << std::fixed << std::setprecision(2) << metrics.fundamental_power << " dBm" << std::endl;
    os << "  2nd Harmonic:      " << std::fixed << std::setprecision(2) << metrics.harmonic2_power << " dBm" << std::endl;
    os << "  3rd Harmonic:      " << std::fixed << std::setprecision(2) << metrics.harmonic3_power << " dBm" << std::endl;
    if (metrics.im3_power > -199) {
        os << "  IM3:               " << std::fixed << std::setprecision(2) << metrics.im3_power << " dBm" << std::endl;
    }
    if (metrics.im5_power > -199) {
        os << "  IM5:               " << std::fixed << std::setprecision(2) << metrics.im5_power << " dBm" << std::endl;
    }
    if (metrics.p1dB_input != 0) {
        os << "  1dB Compression:   " << std::fixed << std::setprecision(2) << metrics.p1dB_input << " dBm (input)" << std::endl;
    }
    if (metrics.ip3_input != 0) {
        os << "  IP3:               " << std::fixed << std::setprecision(2) << metrics.ip3_input << " dBm (input)" << std::endl;
    }
    os << "=====================" << std::endl;
    os << std::endl;
}

void OutputWriter::printSolutionSummary(const HBSolution& solution, std::ostream& os) {
    os << std::endl;
    os << "=== Solution Summary ===" << std::endl;
    os << "  Converged:        " << (solution.converged ? "Yes" : "No") << std::endl;
    os << "  Iterations:       " << solution.iterations << std::endl;
    os << "  Residual Norm:    " << std::scientific << solution.residual_norm << std::endl;
    os << "  Frequency Bins:   " << solution.spectrum.size() << std::endl;
    os << "  Time Samples:     " << solution.time_voltage.size() << std::endl;
    os << "  Aliasing:         " << (solution.is_aliased ? "Yes" : "No") << std::endl;
    if (solution.is_aliased) {
        os << "  Aliased Comps:    " << solution.aliased_components.size() << std::endl;
    }
    os << "========================" << std::endl;
    os << std::endl;
}

void OutputWriter::printSpectrumTable(const HBSolution& solution, std::ostream& os) {
    os << std::endl;
    os << "=== Spectrum Components ===" << std::endl;
    os << std::right << std::setw(15) << "Frequency(Hz)"
       << std::setw(12) << "Label"
       << std::setw(15) << "Magnitude(V)"
       << std::setw(15) << "Power(dBm)" << std::endl;
    os << std::string(57, '-') << std::endl;

    for (const auto& line : solution.spectrum) {
        os << std::right << std::fixed << std::setprecision(2) << std::setw(15) << line.frequency
           << std::setw(12) << line.label
           << std::scientific << std::setprecision(4) << std::setw(15) << std::abs(line.amplitude)
           << std::fixed << std::setprecision(2) << std::setw(15) << line.power_dBm << std::endl;
    }
    os << std::string(57, '-') << std::endl;
    os << std::endl;
}

void OutputWriter::printHysteresisSummary(const SweepAnalysis::HysteresisResult& hysteresis, std::ostream& os) {
    os << std::endl;
    os << "=== Hysteresis Analysis Summary ===" << std::endl;
    os << "  Hysteresis Detected:  " << (hysteresis.has_hysteresis ? "Yes" : "No") << std::endl;
    os << "  Hysteresis Width:     " << std::fixed << std::setprecision(2) << hysteresis.hysteresis_width << " dB" << std::endl;
    os << "  Jump Points Detected: " << hysteresis.jump_points.size() << std::endl;
    if (!hysteresis.jump_points.empty()) {
        os << "  Jump Locations: ";
        for (size_t i = 0; i < hysteresis.jump_points.size(); ++i) {
            if (i > 0) os << ", ";
            os << std::fixed << std::setprecision(2) << hysteresis.jump_points[i] << " dBm";
        }
        os << std::endl;
    }
    os << "  Forward Sweep Points: " << hysteresis.forward_sweep.size() << std::endl;
    os << "  Backward Sweep Points: " << hysteresis.backward_sweep.size() << std::endl;
    os << "===================================" << std::endl;
    os << std::endl;
}

std::string OutputWriter::generateHysteresisPlot(const SweepAnalysis::HysteresisResult& hysteresis,
                                                  int width, int height) {
    std::ostringstream oss;
    oss << std::string(width, '=') << std::endl;
    oss << "  Hysteresis Plot (Forward vs Backward Sweep)" << std::endl;
    oss << "  Legend: 'F' = Forward, 'B' = Backward, '*' = Both" << std::endl;
    oss << std::string(width, '-') << std::endl;

    const auto& forward = hysteresis.forward_sweep;
    const auto& backward = hysteresis.backward_sweep;

    if (forward.empty() || backward.empty()) {
        return "No hysteresis data available";
    }

    double min_p = 1e9, max_p = -1e9;
    double min_pin = 1e9, max_pin = -1e9;
    for (const auto& r : forward) {
        min_p = std::min(min_p, r.metrics.fundamental_power);
        max_p = std::max(max_p, r.metrics.fundamental_power);
        min_pin = std::min(min_pin, r.parameter);
        max_pin = std::max(max_pin, r.parameter);
    }
    for (const auto& r : backward) {
        min_p = std::min(min_p, r.metrics.fundamental_power);
        max_p = std::max(max_p, r.metrics.fundamental_power);
        min_pin = std::min(min_pin, r.parameter);
        max_pin = std::max(max_pin, r.parameter);
    }

    double p_range = max_p - min_p;
    if (p_range < 1) p_range = 10;
    min_p -= 2;
    max_p += 2;
    p_range = max_p - min_p;

    int plot_width = width - 25;
    int n_rows = height;

    oss << std::right << std::setw(12) << "Pout(dBm)" << " |";
    oss << std::string(plot_width, ' ');
    oss << "| Pin(dBm)" << std::endl;

    for (int row = 0; row < n_rows; ++row) {
        double p_threshold = max_p - p_range * row / (n_rows - 1);

        oss << std::right << std::fixed << std::setprecision(1) << std::setw(12) << p_threshold << " |";

        std::vector<char> line_chars(plot_width, ' ');

        for (size_t i = 0; i < forward.size(); ++i) {
            const auto& r = forward[i];
            int col = static_cast<int>((r.parameter - min_pin) / (max_pin - min_pin) * (plot_width - 1));
            col = std::max(0, std::min(plot_width - 1, col));

            double p = r.metrics.fundamental_power;
            double p_next = (i + 1 < forward.size()) ? forward[i+1].metrics.fundamental_power : p;

            if ((p >= p_threshold && p_next < p_threshold) ||
                (p < p_threshold && p_next >= p_threshold)) {
                if (line_chars[col] == ' ') line_chars[col] = 'F';
                else if (line_chars[col] == 'B') line_chars[col] = '*';
            }
        }

        for (size_t i = 0; i < backward.size(); ++i) {
            const auto& r = backward[i];
            int col = static_cast<int>((r.parameter - min_pin) / (max_pin - min_pin) * (plot_width - 1));
            col = std::max(0, std::min(plot_width - 1, col));

            double p = r.metrics.fundamental_power;
            double p_next = (i + 1 < backward.size()) ? backward[i+1].metrics.fundamental_power : p;

            if ((p >= p_threshold && p_next < p_threshold) ||
                (p < p_threshold && p_next >= p_threshold)) {
                if (line_chars[col] == ' ') line_chars[col] = 'B';
                else if (line_chars[col] == 'F') line_chars[col] = '*';
            }
        }

        for (double jump : hysteresis.jump_points) {
            int col = static_cast<int>((jump - min_pin) / (max_pin - min_pin) * (plot_width - 1));
            col = std::max(0, std::min(plot_width - 1, col));
            if (row == n_rows / 2) {
                line_chars[col] = '^';
            }
        }

        oss << std::string(line_chars.begin(), line_chars.end());
        oss << "|" << std::endl;
    }

    oss << std::string(13, ' ') << "+" << std::string(plot_width, '-') << "+" << std::endl;
    oss << std::string(13, ' ') << std::fixed << std::setprecision(1) << std::setw(plot_width / 2 + 4) << min_pin
        << std::string(plot_width - plot_width / 2 - 8, ' ')
        << std::fixed << std::setprecision(1) << max_pin << std::endl;

    if (hysteresis.has_hysteresis) {
        oss << std::endl;
        oss << "  Hysteresis detected! Jump points marked with '^'." << std::endl;
        oss << "  Width = " << std::fixed << std::setprecision(2) << hysteresis.hysteresis_width << " dB" << std::endl;
    }
    oss << std::string(width, '=') << std::endl;

    return oss.str();
}

bool OutputWriter::writeHysteresisCSV(const SweepAnalysis::HysteresisResult& hysteresis,
                                       const std::string& filename,
                                       const std::string& separator) {
    std::ofstream file(filename);
    if (!file.is_open()) return false;

    file << "Direction" << separator
         << "Pin(dBm)" << separator
         << "Pout(dBm)" << separator
         << "IM3(dBm)" << separator
         << "Converged" << separator
         << "Iterations" << std::endl;

    for (const auto& r : hysteresis.forward_sweep) {
        file << "Forward" << separator
             << std::fixed << std::setprecision(3) << r.parameter << separator
             << std::fixed << std::setprecision(2) << r.metrics.fundamental_power << separator
             << std::fixed << std::setprecision(2) << r.metrics.im3_power << separator
             << (r.solution.converged ? "Yes" : "No") << separator
             << r.solution.iterations << std::endl;
    }

    for (const auto& r : hysteresis.backward_sweep) {
        file << "Backward" << separator
             << std::fixed << std::setprecision(3) << r.parameter << separator
             << std::fixed << std::setprecision(2) << r.metrics.fundamental_power << separator
             << std::fixed << std::setprecision(2) << r.metrics.im3_power << separator
             << (r.solution.converged ? "Yes" : "No") << separator
             << r.solution.iterations << std::endl;
    }

    file << std::endl;
    file << "Hysteresis Info" << std::endl;
    file << "Has Hysteresis" << separator << (hysteresis.has_hysteresis ? "Yes" : "No") << std::endl;
    file << "Hysteresis Width (dB)" << separator << std::fixed << std::setprecision(3) << hysteresis.hysteresis_width << std::endl;
    file << "Jump Points" << separator << hysteresis.jump_points.size() << std::endl;
    if (!hysteresis.jump_points.empty()) {
        file << "Jump Locations (dBm)" << separator;
        for (size_t i = 0; i < hysteresis.jump_points.size(); ++i) {
            if (i > 0) file << ";";
            file << std::fixed << std::setprecision(3) << hysteresis.jump_points[i];
        }
        file << std::endl;
    }

    file.close();
    return true;
}

std::string OutputWriter::generateSmithChart(const std::vector<LoadPullResult>& results,
                                              int size) {
    std::ostringstream oss;
    int n = size;
    int center = n / 2;
    double radius = n / 2.0 - 1;

    oss << std::string(n + 10, '=') << std::endl;
    oss << "  Smith Chart - Load Pull Results" << std::endl;
    oss << "  (normalized to Z0=50Ohm)" << std::endl;
    oss << std::string(n + 10, '-') << std::endl;

    std::vector<std::vector<char>> chart(n, std::vector<char>(n, ' '));

    for (int y = 0; y < n; ++y) {
        for (int x = 0; x < n; ++x) {
            double dx = x - center;
            double dy = y - center;
            double dist = std::sqrt(dx * dx + dy * dy);
            
            if (std::abs(dist - radius) < 1.0) {
                chart[y][x] = '.';
            }
            if (std::abs(dy) < 0.5 && dx >= -radius && dx <= radius) {
                chart[y][x] = '-';
            }
            if (std::abs(dx) < 0.5 && dy >= -radius && dy <= radius) {
                chart[y][x] = '|';
            }
        }
    }

    for (const auto& r : results) {
        if (!r.is_stable) continue;
        
        Complex z = r.load_impedance / 50.0;
        Complex gamma = (z - 1.0) / (z + 1.0);
        
        int x = center + static_cast<int>(std::real(gamma) * radius);
        int y = center - static_cast<int>(std::imag(gamma) * radius);
        
        if (x >= 0 && x < n && y >= 0 && y < n) {
            if (r.output_power > 10) chart[y][x] = 'O';
            else if (r.output_power > 5) chart[y][x] = 'o';
            else if (r.output_power > 0) chart[y][x] = '+';
            else chart[y][x] = '.';
        }
    }

    oss << std::string(5, ' ');
    for (int x = 0; x < n; ++x) {
        if (x % 10 == 0) oss << "+";
        else oss << " ";
    }
    oss << std::endl;

    for (int y = 0; y < n; ++y) {
        if (y % 10 == 0) oss << std::setw(4) << (center - y) / radius << " ";
        else oss << "     ";
        
        for (int x = 0; x < n; ++x) {
            oss << chart[y][x];
        }
        
        if (y == center) oss << "  Re(Gamma)";
        oss << std::endl;
    }

    oss << std::string(5, ' ');
    oss << "Im(Gamma) ->" << std::endl;
    oss << std::string(n + 10, '-') << std::endl;
    oss << "  Legend: O=High Pout, o=Med Pout, +=Low Pout" << std::endl;
    oss << std::string(n + 10, '=') << std::endl;

    return oss.str();
}

std::string OutputWriter::generateSmithChartWithContours(
    const std::vector<LoadPullResult>& results,
    const std::vector<ImpedanceContour>& contours,
    int size) {
    
    std::ostringstream oss;
    int n = size;
    int center = n / 2;
    double radius = n / 2.0 - 1;

    oss << std::string(n + 10, '=') << std::endl;
    oss << "  Smith Chart with Contours" << std::endl;
    oss << std::string(n + 10, '-') << std::endl;

    std::vector<std::vector<char>> chart(n, std::vector<char>(n, ' '));

    for (int y = 0; y < n; ++y) {
        for (int x = 0; x < n; ++x) {
            double dx = x - center;
            double dy = y - center;
            double dist = std::sqrt(dx * dx + dy * dy);
            
            if (std::abs(dist - radius) < 1.0) {
                chart[y][x] = '.';
            }
        }
    }

    for (const auto& r : results) {
        if (!r.is_stable) continue;
        
        Complex z = r.load_impedance / 50.0;
        Complex gamma = (z - 1.0) / (z + 1.0);
        
        int x = center + static_cast<int>(std::real(gamma) * radius);
        int y = center - static_cast<int>(std::imag(gamma) * radius);
        
        if (x >= 0 && x < n && y >= 0 && y < n && chart[y][x] == ' ') {
            chart[y][x] = '.';
        }
    }

    std::vector<char> contour_chars = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
    for (size_t c = 0; c < contours.size(); ++c) {
        char ch = contour_chars[c % contour_chars.size()];
        for (const auto& pt : contours[c].points) {
            Complex z = pt.impedance / 50.0;
            Complex gamma = (z - 1.0) / (z + 1.0);
            
            int x = center + static_cast<int>(std::real(gamma) * radius);
            int y = center - static_cast<int>(std::imag(gamma) * radius);
            
            if (x >= 0 && x < n && y >= 0 && y < n) {
                chart[y][x] = ch;
            }
        }
    }

    for (int y = 0; y < n; ++y) {
        for (int x = 0; x < n; ++x) {
            oss << chart[y][x];
        }
        oss << std::endl;
    }

    oss << std::string(n + 10, '-') << std::endl;
    oss << "  Contours:" << std::endl;
    for (size_t c = 0; c < contours.size(); ++c) {
        oss << "    " << contour_chars[c % contour_chars.size()] << " = " 
            << contours[c].name << std::endl;
    }
    oss << std::string(n + 10, '=') << std::endl;

    return oss.str();
}

std::string OutputWriter::generateLoadPullTable(const std::vector<LoadPullResult>& results,
                                                 int top_n) {
    std::ostringstream oss;
    auto sorted = results;
    std::sort(sorted.begin(), sorted.end(),
              [](const LoadPullResult& a, const LoadPullResult& b) {
                  return a.output_power > b.output_power;
              });

    oss << std::string(80, '=') << std::endl;
    oss << "  Top Load Pull Results (by Output Power)" << std::endl;
    oss << std::string(80, '-') << std::endl;
    oss << std::right
        << std::setw(5) << "Rank"
        << std::setw(18) << "Z_load (Ohm)"
        << std::setw(12) << "Pout(dBm)"
        << std::setw(10) << "Gain(dB)"
        << std::setw(10) << "IM3(dBc)"
        << std::setw(10) << "Stable"
        << std::endl;
    oss << std::string(80, '-') << std::endl;

    int count = 0;
    for (const auto& r : sorted) {
        if (!r.is_stable) continue;
        if (count++ >= top_n) break;

        std::ostringstream zs;
        zs << std::fixed << std::setprecision(1) 
           << std::real(r.load_impedance) << "+j" 
           << std::imag(r.load_impedance);

        oss << std::right
            << std::setw(5) << count
            << std::setw(18) << zs.str()
            << std::setw(12) << std::fixed << std::setprecision(2) << r.output_power
            << std::setw(10) << std::fixed << std::setprecision(2) << r.gain
            << std::setw(10) << std::fixed << std::setprecision(2) << r.im3
            << std::setw(10) << (r.is_stable ? "Yes" : "No")
            << std::endl;
    }

    oss << std::string(80, '=') << std::endl;
    return oss.str();
}

std::string OutputWriter::generateSourcePullTable(const std::vector<SourcePullResult>& results,
                                                   int top_n) {
    std::ostringstream oss;
    auto sorted = results;
    std::sort(sorted.begin(), sorted.end(),
              [](const SourcePullResult& a, const SourcePullResult& b) {
                  return a.gain > b.gain;
              });

    oss << std::string(80, '=') << std::endl;
    oss << "  Top Source Pull Results (by Gain)" << std::endl;
    oss << std::string(80, '-') << std::endl;
    oss << std::right
        << std::setw(5) << "Rank"
        << std::setw(18) << "Z_source (Ohm)"
        << std::setw(12) << "Gain(dB)"
        << std::setw(12) << "Pout(dBm)"
        << std::setw(10) << "Stable"
        << std::endl;
    oss << std::string(80, '-') << std::endl;

    int count = 0;
    for (const auto& r : sorted) {
        if (!r.is_stable) continue;
        if (count++ >= top_n) break;

        std::ostringstream zs;
        zs << std::fixed << std::setprecision(1) 
           << std::real(r.source_impedance) << "+j" 
           << std::imag(r.source_impedance);

        oss << std::right
            << std::setw(5) << count
            << std::setw(18) << zs.str()
            << std::setw(12) << std::fixed << std::setprecision(2) << r.gain
            << std::setw(12) << std::fixed << std::setprecision(2) << r.output_power
            << std::setw(10) << (r.is_stable ? "Yes" : "No")
            << std::endl;
    }

    oss << std::string(80, '=') << std::endl;
    return oss.str();
}

bool OutputWriter::writeLoadPullCSV(const std::vector<LoadPullResult>& results,
                                     const std::string& filename,
                                     const std::string& separator) {
    std::ofstream file(filename);
    if (!file.is_open()) return false;

    file << "Z_load_real" << separator << "Z_load_imag" << separator
         << "Pout_dBm" << separator << "Gain_dB" << separator
         << "Efficiency" << separator << "PAE" << separator
         << "IM3_dBc" << separator << "Stable" << std::endl;

    for (const auto& r : results) {
        file << std::fixed << std::setprecision(6) << std::real(r.load_impedance) << separator
             << std::fixed << std::setprecision(6) << std::imag(r.load_impedance) << separator
             << std::fixed << std::setprecision(3) << r.output_power << separator
             << std::fixed << std::setprecision(3) << r.gain << separator
             << std::fixed << std::setprecision(6) << r.efficiency << separator
             << std::fixed << std::setprecision(6) << r.pae << separator
             << std::fixed << std::setprecision(3) << r.im3 << separator
             << (r.is_stable ? "Yes" : "No") << std::endl;
    }

    file.close();
    return true;
}

bool OutputWriter::writeSourcePullCSV(const std::vector<SourcePullResult>& results,
                                       const std::string& filename,
                                       const std::string& separator) {
    std::ofstream file(filename);
    if (!file.is_open()) return false;

    file << "Z_source_real" << separator << "Z_source_imag" << separator
         << "Gain_dB" << separator << "NoiseFigure_dB" << separator
         << "Pout_dBm" << separator << "Stable" << std::endl;

    for (const auto& r : results) {
        file << std::fixed << std::setprecision(6) << std::real(r.source_impedance) << separator
             << std::fixed << std::setprecision(6) << std::imag(r.source_impedance) << separator
             << std::fixed << std::setprecision(3) << r.gain << separator
             << std::fixed << std::setprecision(3) << r.noise_figure << separator
             << std::fixed << std::setprecision(3) << r.output_power << separator
             << (r.is_stable ? "Yes" : "No") << std::endl;
    }

    file.close();
    return true;
}

bool OutputWriter::writeContoursCSV(const std::vector<ImpedanceContour>& contours,
                                     const std::string& filename,
                                     const std::string& separator) {
    std::ofstream file(filename);
    if (!file.is_open()) return false;

    file << "ContourName" << separator << "TargetValue" << separator
         << "Z_real" << separator << "Z_imag" << separator
         << "ActualValue" << std::endl;

    for (const auto& contour : contours) {
        for (const auto& pt : contour.points) {
            file << contour.name << separator
                 << std::fixed << std::setprecision(3) << contour.target_value << separator
                 << std::fixed << std::setprecision(6) << std::real(pt.impedance) << separator
                 << std::fixed << std::setprecision(6) << std::imag(pt.impedance) << separator
                 << std::fixed << std::setprecision(3) << pt.value << std::endl;
        }
    }

    file.close();
    return true;
}

std::string OutputWriter::generateEnvelopeWaveform(const EnvelopeSolution& env,
                                                    int width,
                                                    int height) {
    std::ostringstream oss;
    oss << std::string(width, '=') << std::endl;
    oss << "  Envelope Waveform (Input vs Output)" << std::endl;
    oss << "  Legend: 'I' = Input, 'O' = Output, '*' = Both" << std::endl;
    oss << std::string(width, '-') << std::endl;

    const auto& in_amp = env.input_envelope.amplitude;
    const auto& out_amp = env.output_envelope.amplitude;
    
    int n = static_cast<int>(std::min(in_amp.size(), out_amp.size()));
    if (n == 0) return "No envelope data available";

    double max_amp = 0;
    for (int i = 0; i < n; ++i) {
        max_amp = std::max(max_amp, std::max(in_amp[i], out_amp[i]));
    }
    if (max_amp < 1e-12) max_amp = 1.0;

    int step = std::max(1, n / width);
    int num_points = n / step;
    int plot_width = width - 20;

    oss << std::right << std::setw(10) << "Amp(V)" << " |";
    oss << std::string(plot_width, ' ');
    oss << "| Time" << std::endl;

    for (int row = 0; row < height; ++row) {
        double threshold = max_amp * (1.0 - static_cast<double>(row) / (height - 1));
        
        oss << std::right << std::fixed << std::setprecision(3) << std::setw(10) << threshold << " |";
        
        std::vector<char> line_chars(plot_width, ' ');
        
        for (int col = 0; col < num_points; ++col) {
            int idx = col * step;
            if (idx >= n) break;

            double v_in = in_amp[idx];
            double v_out = out_amp[idx];

            if (std::abs(v_in - threshold) < max_amp / height) {
                line_chars[col] = 'I';
            }
            if (std::abs(v_out - threshold) < max_amp / height) {
                if (line_chars[col] == 'I') line_chars[col] = '*';
                else line_chars[col] = 'O';
            }
        }
        
        oss << std::string(line_chars.begin(), line_chars.end());
        oss << "|" << std::endl;
    }

    oss << std::string(12, ' ') << "+" << std::string(plot_width, '-') << "+" << std::endl;
    oss << std::string(12, ' ') << "0s" << std::string(plot_width - 8, ' ');
    if (!env.input_envelope.time.empty()) {
        oss << std::fixed << std::setprecision(2) << env.input_envelope.time.back() << "s";
    }
    oss << std::endl;

    if (env.evm > 0) {
        oss << std::endl;
        oss << "  EVM: " << std::fixed << std::setprecision(2) << env.evm * 100 << "%" << std::endl;
        oss << "  ACPR: " << std::fixed << std::setprecision(2) << env.acpr << " dBc" << std::endl;
    }
    oss << std::string(width, '=') << std::endl;

    return oss.str();
}

std::string OutputWriter::generateAmAmPlot(const AMAMPMCharacteristics& amam,
                                            int width,
                                            int height) {
    std::ostringstream oss;
    oss << std::string(width, '=') << std::endl;
    oss << "  AM-AM Characteristics" << std::endl;
    oss << std::string(width, '-') << std::endl;

    if (amam.points.empty()) return "No AM-AM data available";

    double min_pin = 1e9, max_pin = -1e9;
    double min_pout = 1e9, max_pout = -1e9;
    
    for (const auto& pt : amam.points) {
        min_pin = std::min(min_pin, pt.input_power);
        max_pin = std::max(max_pin, pt.input_power);
        min_pout = std::min(min_pout, pt.output_power);
        max_pout = std::max(max_pout, pt.output_power);
    }

    double pin_range = max_pin - min_pin;
    double pout_range = max_pout - min_pout;
    if (pin_range < 1) pin_range = 10;
    if (pout_range < 1) pout_range = 10;

    int plot_width = width - 20;

    oss << std::right << std::setw(10) << "Pout(dBm)" << " |";
    oss << std::string(plot_width, ' ');
    oss << "| Pin(dBm)" << std::endl;

    for (int row = 0; row < height; ++row) {
        double pout_thresh = max_pout - pout_range * row / (height - 1);
        
        oss << std::right << std::fixed << std::setprecision(1) << std::setw(10) << pout_thresh << " |";
        
        std::vector<char> line_chars(plot_width, ' ');
        
        for (size_t i = 0; i < amam.points.size(); ++i) {
            const auto& pt = amam.points[i];
            int col = static_cast<int>((pt.input_power - min_pin) / pin_range * (plot_width - 1));
            col = std::max(0, std::min(plot_width - 1, col));

            double pout_next = (i + 1 < amam.points.size()) ? 
                              amam.points[i+1].output_power : pt.output_power;

            if ((pt.output_power >= pout_thresh && pout_next < pout_thresh) ||
                (pt.output_power < pout_thresh && pout_next >= pout_thresh)) {
                line_chars[col] = '*';
            }

            if (std::abs(pt.input_power - amam.p1dB) < pin_range / 20 && row == height / 2) {
                line_chars[col] = '1';
            }
        }

        double ideal_pout = amam.linear_gain + (min_pin + pin_range * row / (height - 1));
        int ideal_col = static_cast<int>((ideal_pout - min_pin) / pin_range * (plot_width - 1));
        if (ideal_col >= 0 && ideal_col < plot_width && line_chars[ideal_col] == ' ') {
            line_chars[ideal_col] = '.';
        }
        
        oss << std::string(line_chars.begin(), line_chars.end());
        oss << "|" << std::endl;
    }

    oss << std::string(12, ' ') << "+" << std::string(plot_width, '-') << "+" << std::endl;
    oss << std::string(12, ' ') << std::fixed << std::setprecision(0) << min_pin
        << std::string(plot_width - 8, ' ')
        << std::fixed << std::setprecision(0) << max_pin << std::endl;

    oss << std::endl;
    oss << "  Linear Gain: " << std::fixed << std::setprecision(2) << amam.linear_gain << " dB" << std::endl;
    oss << "  P1dB: " << std::fixed << std::setprecision(2) << amam.p1dB << " dBm" << std::endl;
    oss << "  Saturation Power: " << std::fixed << std::setprecision(2) << amam.sat_power << " dBm" << std::endl;
    oss << "  Legend: '*' = measured, '.' = ideal, '1' = P1dB point" << std::endl;
    oss << std::string(width, '=') << std::endl;

    return oss.str();
}

std::string OutputWriter::generateAmPmPlot(const AMAMPMCharacteristics& ampm,
                                            int width,
                                            int height) {
    std::ostringstream oss;
    oss << std::string(width, '=') << std::endl;
    oss << "  AM-PM Characteristics" << std::endl;
    oss << std::string(width, '-') << std::endl;

    if (ampm.points.empty()) return "No AM-PM data available";

    double min_pin = 1e9, max_pin = -1e9;
    double min_phase = 1e9, max_phase = -1e9;
    
    for (const auto& pt : ampm.points) {
        min_pin = std::min(min_pin, pt.input_power);
        max_pin = std::max(max_pin, pt.input_power);
        min_phase = std::min(min_phase, pt.phase_shift);
        max_phase = std::max(max_phase, pt.phase_shift);
    }

    double pin_range = max_pin - min_pin;
    double phase_range = max_phase - min_phase;
    if (pin_range < 1) pin_range = 10;
    if (phase_range < 1) phase_range = 10;

    int plot_width = width - 20;

    oss << std::right << std::setw(10) << "Phase(deg)" << " |";
    oss << std::string(plot_width, ' ');
    oss << "| Pin(dBm)" << std::endl;

    for (int row = 0; row < height; ++row) {
        double phase_thresh = max_phase - phase_range * row / (height - 1);
        
        oss << std::right << std::fixed << std::setprecision(1) << std::setw(10) << phase_thresh << " |";
        
        std::vector<char> line_chars(plot_width, ' ');
        
        for (size_t i = 0; i < ampm.points.size(); ++i) {
            const auto& pt = ampm.points[i];
            int col = static_cast<int>((pt.input_power - min_pin) / pin_range * (plot_width - 1));
            col = std::max(0, std::min(plot_width - 1, col));

            double phase_next = (i + 1 < ampm.points.size()) ? 
                               ampm.points[i+1].phase_shift : pt.phase_shift;

            if ((pt.phase_shift >= phase_thresh && phase_next < phase_thresh) ||
                (pt.phase_shift < phase_thresh && phase_next >= phase_thresh)) {
                line_chars[col] = '*';
            }
        }
        
        oss << std::string(line_chars.begin(), line_chars.end());
        oss << "|" << std::endl;
    }

    oss << std::string(12, ' ') << "+" << std::string(plot_width, '-') << "+" << std::endl;
    oss << std::string(12, ' ') << std::fixed << std::setprecision(0) << min_pin
        << std::string(plot_width - 8, ' ')
        << std::fixed << std::setprecision(0) << max_pin << std::endl;

    oss << std::endl;
    oss << "  PM1dB: " << std::fixed << std::setprecision(2) << ampm.pm1dB << " degrees" << std::endl;
    oss << std::string(width, '=') << std::endl;

    return oss.str();
}

bool OutputWriter::writeEnvelopeCSV(const EnvelopeSolution& env,
                                     const std::string& filename,
                                     const std::string& separator) {
    std::ofstream file(filename);
    if (!file.is_open()) return false;

    const auto& in = env.input_envelope;
    const auto& out = env.output_envelope;
    
    int n = static_cast<int>(std::min(in.time.size(), out.time.size()));

    file << "Time(s)" << separator
         << "In_Amplitude(V)" << separator << "In_Phase(rad)" << separator
         << "In_I(V)" << separator << "In_Q(V)" << separator
         << "Out_Amplitude(V)" << separator << "Out_Phase(rad)" << separator
         << "Out_I(V)" << separator << "Out_Q(V)" << std::endl;

    for (int i = 0; i < n; ++i) {
        file << std::scientific << std::setprecision(8) << in.time[i] << separator
             << std::fixed << std::setprecision(6) << in.amplitude[i] << separator
             << std::fixed << std::setprecision(6) << in.phase[i] << separator
             << std::fixed << std::setprecision(6) << std::real(in.envelope[i]) << separator
             << std::fixed << std::setprecision(6) << std::imag(in.envelope[i]) << separator
             << std::fixed << std::setprecision(6) << out.amplitude[i] << separator
             << std::fixed << std::setprecision(6) << out.phase[i] << separator
             << std::fixed << std::setprecision(6) << std::real(out.envelope[i]) << separator
             << std::fixed << std::setprecision(6) << std::imag(out.envelope[i]) << std::endl;
    }

    file << std::endl;
    file << "Performance Metrics" << std::endl;
    file << "EVM(%)" << separator << std::fixed << std::setprecision(4) << env.evm * 100 << std::endl;
    file << "ACPR(dBc)" << separator << std::fixed << std::setprecision(4) << env.acpr << std::endl;
    file << "NPR(dB)" << separator << std::fixed << std::setprecision(4) << env.npr << std::endl;

    file.close();
    return true;
}

bool OutputWriter::writeAmAmPmCSV(const AMAMPMCharacteristics& amam,
                                   const std::string& filename,
                                   const std::string& separator) {
    std::ofstream file(filename);
    if (!file.is_open()) return false;

    file << "Pin(dBm)" << separator << "Pout(dBm)" << separator
         << "Gain(dB)" << separator << "PhaseShift(deg)" << separator
         << "GainCompression(dB)" << std::endl;

    for (const auto& pt : amam.points) {
        file << std::fixed << std::setprecision(3) << pt.input_power << separator
             << std::fixed << std::setprecision(3) << pt.output_power << separator
             << std::fixed << std::setprecision(3) << (pt.output_power - pt.input_power) << separator
             << std::fixed << std::setprecision(3) << pt.phase_shift << separator
             << std::fixed << std::setprecision(3) << pt.gain_compression << std::endl;
    }

    file << std::endl;
    file << "Key Parameters" << std::endl;
    file << "LinearGain(dB)" << separator << std::fixed << std::setprecision(4) << amam.linear_gain << std::endl;
    file << "P1dB(dBm)" << separator << std::fixed << std::setprecision(4) << amam.p1dB << std::endl;
    file << "SatPower(dBm)" << separator << std::fixed << std::setprecision(4) << amam.sat_power << std::endl;
    file << "PM1dB(deg)" << separator << std::fixed << std::setprecision(4) << amam.pm1dB << std::endl;

    file.close();
    return true;
}

void OutputWriter::printLoadPullSummary(const LoadPullResult& optimum,
                                         const std::vector<ImpedanceContour>& contours,
                                         std::ostream& os) {
    os << std::endl;
    os << "=== Load Pull Analysis Summary ===" << std::endl;
    os << "  Optimum Load Impedance: " 
       << std::fixed << std::setprecision(2) << std::real(optimum.load_impedance) 
       << " + j" << std::imag(optimum.load_impedance) << " Ohm" << std::endl;
    os << "  Output Power: " << std::fixed << std::setprecision(2) << optimum.output_power << " dBm" << std::endl;
    os << "  Gain: " << std::fixed << std::setprecision(2) << optimum.gain << " dB" << std::endl;
    os << "  IM3: " << std::fixed << std::setprecision(2) << optimum.im3 << " dBc" << std::endl;
    os << "  Stable: " << (optimum.is_stable ? "Yes" : "No") << std::endl;
    if (!contours.empty()) {
        os << "  Contours Generated: " << contours.size() << std::endl;
    }
    os << "==================================" << std::endl;
    os << std::endl;
}

void OutputWriter::printSourcePullSummary(const SourcePullResult& optimum,
                                           std::ostream& os) {
    os << std::endl;
    os << "=== Source Pull Analysis Summary ===" << std::endl;
    os << "  Optimum Source Impedance: " 
       << std::fixed << std::setprecision(2) << std::real(optimum.source_impedance) 
       << " + j" << std::imag(optimum.source_impedance) << " Ohm" << std::endl;
    os << "  Gain: " << std::fixed << std::setprecision(2) << optimum.gain << " dB" << std::endl;
    os << "  Output Power: " << std::fixed << std::setprecision(2) << optimum.output_power << " dBm" << std::endl;
    os << "  Stable: " << (optimum.is_stable ? "Yes" : "No") << std::endl;
    os << "====================================" << std::endl;
    os << std::endl;
}

void OutputWriter::printEnvelopeSummary(const EnvelopeSolution& env,
                                         std::ostream& os) {
    os << std::endl;
    os << "=== Envelope Simulation Summary ===" << std::endl;
    os << "  Carrier Frequency: " << std::scientific << std::setprecision(2) 
       << env.input_envelope.carrier_freq << " Hz" << std::endl;
    os << "  Samples: " << env.input_envelope.time.size() << std::endl;
    os << "  EVM: " << std::fixed << std::setprecision(2) << env.evm * 100 << " %" << std::endl;
    os << "  ACPR: " << std::fixed << std::setprecision(2) << env.acpr << " dBc" << std::endl;
    os << "  NPR: " << std::fixed << std::setprecision(2) << env.npr << " dB" << std::endl;
    os << "====================================" << std::endl;
    os << std::endl;
}

void OutputWriter::printAmAmPmSummary(const AMAMPMCharacteristics& amam,
                                       std::ostream& os) {
    os << std::endl;
    os << "=== AM-AM/AM-PM Characteristics Summary ===" << std::endl;
    os << "  Linear Gain: " << std::fixed << std::setprecision(2) << amam.linear_gain << " dB" << std::endl;
    os << "  P1dB (Input): " << std::fixed << std::setprecision(2) << amam.p1dB << " dBm" << std::endl;
    os << "  Saturation Power: " << std::fixed << std::setprecision(2) << amam.sat_power << " dBm" << std::endl;
    os << "  PM1dB: " << std::fixed << std::setprecision(2) << amam.pm1dB << " degrees" << std::endl;
    os << "  Data Points: " << amam.points.size() << std::endl;
    os << "============================================" << std::endl;
    os << std::endl;
}

void OutputWriter::printMemoryEffectSummary(const MemoryEffectConfig& config,
                                             std::ostream& os) {
    os << std::endl;
    os << "=== Memory Effect Configuration ===" << std::endl;
    os << "  Nonlinear Capacitor: " << (config.has_nl_capacitor ? "Enabled" : "Disabled") << std::endl;
    if (config.has_nl_capacitor) {
        os << "    Cj0: " << std::scientific << config.nl_cap.cj0 << " F" << std::endl;
        os << "    Vj: " << std::fixed << std::setprecision(2) << config.nl_cap.vj << " V" << std::endl;
        os << "    m: " << std::fixed << std::setprecision(2) << config.nl_cap.m << std::endl;
    }
    os << "  Nonlinear Inductor: " << (config.has_nl_inductor ? "Enabled" : "Disabled") << std::endl;
    if (config.has_nl_inductor) {
        os << "    L0: " << std::scientific << config.nl_ind.l0 << " H" << std::endl;
        os << "    alpha: " << std::fixed << std::setprecision(2) << config.nl_ind.alpha << std::endl;
        os << "    Isat: " << std::scientific << config.nl_ind.i_sat << " A" << std::endl;
    }
    os << "  Thermal Time Constant: " << std::scientific << config.thermal_tau << " s" << std::endl;
    os << "  Trap Time Constant: " << std::scientific << config.trap_tau << " s" << std::endl;
    os << "===================================" << std::endl;
    os << std::endl;
}

}
