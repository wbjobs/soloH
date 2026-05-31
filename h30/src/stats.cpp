#include "../include/stats.h"
#include "../include/utils.h"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <cmath>
#include <stdexcept>
#include <chrono>
#include <ctime>

namespace bb84 {

Statistics::Statistics() {}

void Statistics::addRun(const RunResult& result) {
    results_.push_back(result);
}

const std::vector<RunResult>& Statistics::getResults() const {
    return results_;
}

void Statistics::clear() {
    results_.clear();
}

double Statistics::calculateMean(const std::vector<double>& values) const {
    if (values.empty()) return 0.0;
    double sum = 0.0;
    for (double v : values) sum += v;
    return sum / values.size();
}

double Statistics::calculateStdDev(const std::vector<double>& values, double mean) const {
    if (values.size() < 2) return 0.0;
    double sum_sq = 0.0;
    for (double v : values) {
        double diff = v - mean;
        sum_sq += diff * diff;
    }
    return std::sqrt(sum_sq / (values.size() - 1));
}

std::string Statistics::formatDouble(double value, int precision) const {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(precision) << value;
    return oss.str();
}

StatsSummary Statistics::computeSummary() const {
    StatsSummary summary;
    summary.total_runs = static_cast<int>(results_.size());
    summary.successful_runs = 0;
    summary.avg_pulse_broadening = 0.0;
    summary.avg_nonlinear_phase = 0.0;
    summary.avg_fiber_qber = 0.0;
    summary.avg_decoy_yield_signal = 0.0;
    summary.avg_single_photon_fraction = 0.0;
    summary.avg_mdi_visibility = 0.0;
    summary.avg_mdi_coincidence_rate = 0.0;
    
    if (results_.empty()) {
        summary.avg_qber = 0.0;
        summary.std_qber = 0.0;
        summary.avg_key_rate = 0.0;
        summary.std_key_rate = 0.0;
        summary.eavesdropping_detection_probability = 0.0;
        summary.avg_final_key_length = 0.0;
        summary.avg_sifted_key_length = 0.0;
        summary.avg_photon_loss_rate = 0.0;
        summary.avg_dark_count_rate = 0.0;
        return summary;
    }
    
    std::vector<double> qber_values;
    std::vector<double> key_rate_values;
    std::vector<double> final_key_lengths;
    std::vector<double> sifted_key_lengths;
    std::vector<double> loss_rates;
    std::vector<double> dark_count_rates;
    std::vector<double> pulse_broadening;
    std::vector<double> nonlinear_phase;
    std::vector<double> fiber_qber;
    std::vector<double> decoy_yield_signal;
    std::vector<double> single_photon_fraction;
    std::vector<double> mdi_visibility;
    std::vector<double> mdi_coincidence;
    
    int detections = 0;
    int fiber_count = 0;
    int decoy_count = 0;
    int mdi_count = 0;
    
    for (const auto& result : results_) {
        if (result.final_key_length > 0) {
            summary.successful_runs++;
        }
        
        qber_values.push_back(result.qber);
        key_rate_values.push_back(result.key_generation_rate);
        final_key_lengths.push_back(static_cast<double>(result.final_key_length));
        sifted_key_lengths.push_back(static_cast<double>(result.sifted_key_length));
        
        if (result.total_photons_sent > 0) {
            loss_rates.push_back(static_cast<double>(result.photons_lost) / 
                                static_cast<double>(result.total_photons_sent));
            dark_count_rates.push_back(static_cast<double>(result.dark_count_events) / 
                                      static_cast<double>(result.total_photons_sent));
        } else {
            loss_rates.push_back(0.0);
            dark_count_rates.push_back(0.0);
        }
        
        if (result.eavesdropping_detected) {
            detections++;
        }
        
        if (result.fiber_params.length_km > 0) {
            pulse_broadening.push_back(result.avg_fiber_effects.pulse_broadening_factor);
            nonlinear_phase.push_back(result.avg_fiber_effects.nonlinear_phase_shift);
            fiber_qber.push_back(result.avg_fiber_effects.additional_qber);
            fiber_count++;
        }
        
        if (result.decoy_result.decoy_enabled) {
            decoy_yield_signal.push_back(result.decoy_result.signal_yield);
            single_photon_fraction.push_back(
                result.decoy_result.estimated_single_photon_count / 
                std::max(1.0, static_cast<double>(result.sifted_key_length))
            );
            decoy_count++;
        }
        
        if (result.protocol_type == ProtocolType::MDI_QKD) {
            mdi_visibility.push_back(result.mdi_result.interference_visibility);
            mdi_coincidence.push_back(static_cast<double>(result.mdi_result.bell_state_count) / 
                                      std::max(1, result.total_photons_sent));
            mdi_count++;
        }
    }
    
    summary.avg_qber = calculateMean(qber_values);
    summary.std_qber = calculateStdDev(qber_values, summary.avg_qber);
    summary.avg_key_rate = calculateMean(key_rate_values);
    summary.std_key_rate = calculateStdDev(key_rate_values, summary.avg_key_rate);
    summary.avg_final_key_length = calculateMean(final_key_lengths);
    summary.avg_sifted_key_length = calculateMean(sifted_key_lengths);
    summary.avg_photon_loss_rate = calculateMean(loss_rates);
    summary.avg_dark_count_rate = calculateMean(dark_count_rates);
    
    if (fiber_count > 0) {
        summary.avg_pulse_broadening = calculateMean(pulse_broadening);
        summary.avg_nonlinear_phase = calculateMean(nonlinear_phase);
        summary.avg_fiber_qber = calculateMean(fiber_qber);
    }
    if (decoy_count > 0) {
        summary.avg_decoy_yield_signal = calculateMean(decoy_yield_signal);
        summary.avg_single_photon_fraction = calculateMean(single_photon_fraction);
    }
    if (mdi_count > 0) {
        summary.avg_mdi_visibility = calculateMean(mdi_visibility);
        summary.avg_mdi_coincidence_rate = calculateMean(mdi_coincidence);
    }
    
    summary.eavesdropping_detection_probability = 
        static_cast<double>(detections) / static_cast<double>(results_.size());
    
    return summary;
}

void Statistics::printTableHeader() const {
    std::cout << std::string(200, '=') << std::endl;
    std::cout << std::setw(6) << "Run" 
              << std::setw(8) << "Proto"
              << std::setw(10) << "Photons" 
              << std::setw(8) << "Lost"
              << std::setw(10) << "Sifted"
              << std::setw(10) << "TestSize"
              << std::setw(10) << "QBER"
              << std::setw(8) << "Passes"
              << std::setw(8) << "Errors"
              << std::setw(10) << "Final"
              << std::setw(12) << "Key Rate"
              << std::setw(8) << "Eve?"
              << std::setw(8) << "Decoy"
              << std::setw(10) << "Visibility"
              << std::endl;
    std::cout << std::string(200, '-') << std::endl;
}

void Statistics::printTableRow(const RunResult& result) const {
    std::cout << std::setw(6) << result.run_id
              << std::setw(8) << utils::protocolTypeToString(result.protocol_type)
              << std::setw(10) << result.total_photons_sent
              << std::setw(8) << result.photons_lost
              << std::setw(10) << result.sifted_key_length
              << std::setw(10) << result.test_sample_size
              << std::setw(10) << formatDouble(result.qber, 4)
              << std::setw(8) << result.cascade_passes_completed
              << std::setw(8) << result.cascade_errors_corrected
              << std::setw(10) << result.final_key_length
              << std::setw(12) << formatDouble(result.key_generation_rate, 4)
              << std::setw(8) << (result.eavesdropping_detected ? "YES" : "no")
              << std::setw(8) << (result.decoy_result.decoy_enabled ? "YES" : "no")
              << std::setw(10);
    
    if (result.protocol_type == ProtocolType::MDI_QKD) {
        std::cout << formatDouble(result.mdi_result.interference_visibility, 3);
    } else {
        std::cout << "-";
    }
    std::cout << std::endl;
}

void Statistics::printTerminalTable(const Config& config) const {
    if (results_.empty()) {
        std::cout << "No results to display." << std::endl;
        return;
    }
    
    std::cout << "\n" << std::string(200, '=') << std::endl;
    std::cout << "QKD Protocol Simulation Results - Per Run Details" << std::endl;
    std::cout << "Protocol: " << utils::protocolTypeToString(config.protocol_type)
              << " | Attack: " << utils::attackTypeToString(config.attack_type)
              << " | Eavesdropping: " << formatDouble(config.eavesdropping_strength, 2);
    if (config.fiber_length_km > 0 && config.use_fiber_model) {
        std::cout << " | Fiber: " << config.fiber_length_km << " km";
    }
    if (config.use_decoy_states) {
        std::cout << " | Decoy: Enabled";
    }
    std::cout << std::endl;
    printTableHeader();
    
    size_t display_count = std::min(results_.size(), static_cast<size_t>(20));
    for (size_t i = 0; i < display_count; ++i) {
        printTableRow(results_[i]);
    }
    
    if (results_.size() > 20) {
        std::cout << "... (" << (results_.size() - 20) << " more runs)" << std::endl;
    }
    
    std::cout << std::string(200, '=') << "\n" << std::endl;
}

void Statistics::printSummaryTable(const Config& config) const {
    StatsSummary summary = computeSummary();
    
    std::cout << "\n" << std::string(90, '=') << std::endl;
    std::cout << "QKD Protocol Simulation - Statistical Summary" << std::endl;
    std::cout << std::string(90, '=') << std::endl;
    std::cout << "Configuration:" << std::endl;
    std::cout << "  Protocol:             " << utils::protocolTypeToString(config.protocol_type) << std::endl;
    std::cout << "  Attack Type:          " << utils::attackTypeToString(config.attack_type) << std::endl;
    std::cout << "  Eavesdropping Strength: " << formatDouble(config.eavesdropping_strength, 4) << std::endl;
    std::cout << "  Channel Loss Rate:    " << formatDouble(config.channel_loss_rate, 4) << std::endl;
    std::cout << "  Dark Count Prob:      " << formatDouble(config.dark_count_prob, 6) << std::endl;
    std::cout << "  QBER Threshold:       " << formatDouble(config.qber_threshold, 4) << std::endl;
    std::cout << "  Photons per Run:      " << config.num_photons << std::endl;
    std::cout << "  Number of Runs:       " << config.num_runs << std::endl;
    std::cout << "  Decoy States:         " << (config.use_decoy_states ? "Enabled" : "Disabled") << std::endl;
    if (config.fiber_length_km > 0 && config.use_fiber_model) {
        std::cout << "  Fiber Length:         " << config.fiber_length_km << " km" << std::endl;
        std::cout << "  Fiber Attenuation:    " << formatDouble(config.fiber_attenuation, 3) << " dB/km" << std::endl;
        std::cout << "  Fiber Dispersion:     " << formatDouble(config.fiber_dispersion, 2) << " ps/nm/km" << std::endl;
    }
    std::cout << std::string(90, '-') << std::endl;
    std::cout << "Statistical Results:" << std::endl;
    std::cout << "  Total Runs:           " << summary.total_runs << std::endl;
    std::cout << "  Successful Runs:      " << summary.successful_runs 
              << " (" << formatDouble(100.0 * summary.successful_runs / summary.total_runs, 2) << "%)" << std::endl;
    std::cout << "  Average QBER:         " << formatDouble(summary.avg_qber, 6) 
              << " ± " << formatDouble(summary.std_qber, 6) << std::endl;
    std::cout << "  Average Key Rate:     " << formatDouble(summary.avg_key_rate, 6)
              << " ± " << formatDouble(summary.std_key_rate, 6) << std::endl;
    std::cout << "  Eve Detection Prob:   " << formatDouble(summary.eavesdropping_detection_probability, 4)
              << " (" << formatDouble(100.0 * summary.eavesdropping_detection_probability, 2) << "%)" << std::endl;
    std::cout << "  Avg Sifted Key Len:   " << formatDouble(summary.avg_sifted_key_length, 2) << std::endl;
    std::cout << "  Avg Final Key Len:    " << formatDouble(summary.avg_final_key_length, 2) << std::endl;
    std::cout << "  Avg Photon Loss Rate: " << formatDouble(summary.avg_photon_loss_rate, 4) << std::endl;
    std::cout << "  Avg Dark Count Rate:  " << formatDouble(summary.avg_dark_count_rate, 6) << std::endl;
    
    if (summary.avg_fiber_qber > 0) {
        std::cout << std::string(90, '-') << std::endl;
        std::cout << "Fiber Effects:" << std::endl;
        std::cout << "  Avg Pulse Broadening: " << formatDouble(summary.avg_pulse_broadening, 4) << std::endl;
        std::cout << "  Avg Nonlinear Phase:  " << formatDouble(summary.avg_nonlinear_phase, 6) << std::endl;
        std::cout << "  Avg Fiber QBER:       " << formatDouble(summary.avg_fiber_qber, 6) << std::endl;
    }
    
    if (summary.avg_single_photon_fraction > 0) {
        std::cout << std::string(90, '-') << std::endl;
        std::cout << "Decoy State Results:" << std::endl;
        std::cout << "  Avg Signal Yield:     " << formatDouble(summary.avg_decoy_yield_signal, 6) << std::endl;
        std::cout << "  Avg Single Photon:    " << formatDouble(summary.avg_single_photon_fraction, 6) << std::endl;
    }
    
    if (summary.avg_mdi_visibility > 0) {
        std::cout << std::string(90, '-') << std::endl;
        std::cout << "MDI-QKD Results:" << std::endl;
        std::cout << "  Avg Visibility:       " << formatDouble(summary.avg_mdi_visibility, 4) << std::endl;
        std::cout << "  Avg Coincidence Rate: " << formatDouble(summary.avg_mdi_coincidence_rate, 6) << std::endl;
    }
    
    std::cout << std::string(90, '=') << "\n" << std::endl;
}

bool Statistics::exportToCSV(const std::string& filename, const Config& config) const {
    std::ofstream file(filename);
    if (!file.is_open()) {
        return false;
    }
    
    file << "run_id,protocol,total_photons,photons_lost,sifted_key_length,test_sample_size,"
         << "qber,qber_after_basis,cascade_passes,cascade_errors_corrected,"
         << "final_key_length,security_parameter,collision_probability,"
         << "eavesdropping_detected,eavesdropping_strength,attack_type,"
         << "key_generation_rate,dark_count_events,decoy_enabled,signal_yield,"
         << "single_photon_count,estimated_single_photon_error,fiber_length_km,"
         << "pulse_broadening,nonlinear_phase,additional_fiber_qber,"
         << "mdi_visibility,bell_state_count" << std::endl;
    
    for (const auto& result : results_) {
        file << result.run_id << ","
             << utils::protocolTypeToString(result.protocol_type) << ","
             << result.total_photons_sent << ","
             << result.photons_lost << ","
             << result.sifted_key_length << ","
             << result.test_sample_size << ","
             << formatDouble(result.qber, 8) << ","
             << formatDouble(result.qber_after_basis_reconciliation, 8) << ","
             << result.cascade_passes_completed << ","
             << result.cascade_errors_corrected << ","
             << result.final_key_length << ","
             << result.security_parameter << ","
             << formatDouble(result.collision_probability, 12) << ","
             << (result.eavesdropping_detected ? "1" : "0") << ","
             << formatDouble(result.eavesdropping_strength_used, 6) << ","
             << utils::attackTypeToString(result.attack_type) << ","
             << formatDouble(result.key_generation_rate, 8) << ","
             << result.dark_count_events << ","
             << (result.decoy_result.decoy_enabled ? "1" : "0") << ","
             << formatDouble(result.decoy_result.signal_yield, 8) << ","
             << result.decoy_result.estimated_single_photon_count << ","
             << formatDouble(result.decoy_result.estimated_single_photon_error, 8) << ","
             << result.fiber_params.length_km << ","
             << formatDouble(result.avg_fiber_effects.pulse_broadening_factor, 8) << ","
             << formatDouble(result.avg_fiber_effects.nonlinear_phase_shift, 10) << ","
             << formatDouble(result.avg_fiber_effects.additional_qber, 8) << ","
             << formatDouble(result.mdi_result.interference_visibility, 6) << ","
             << result.mdi_result.bell_state_count << std::endl;
    }
    
    file.close();
    return true;
}

bool Statistics::exportSummaryToCSV(const std::string& filename, const Config& config) const {
    StatsSummary summary = computeSummary();
    std::ofstream file(filename, std::ios::app);
    if (!file.is_open()) {
        return false;
    }
    
    if (file.tellp() == 0) {
        file << "timestamp,protocol,attack_type,eavesdropping_strength,channel_loss_rate,"
             << "dark_count_prob,qber_threshold,num_photons,num_runs,"
             << "total_runs,successful_runs,avg_qber,std_qber,"
             << "avg_key_rate,std_key_rate,eavesdropping_detection_probability,"
             << "avg_final_key_length,avg_sifted_key_length,"
             << "avg_photon_loss_rate,avg_dark_count_rate,"
             << "fiber_length_km,avg_pulse_broadening,avg_nonlinear_phase,avg_fiber_qber,"
             << "decoy_enabled,avg_signal_yield,avg_single_photon_fraction,"
             << "avg_mdi_visibility,avg_mdi_coincidence_rate" << std::endl;
    }
    
    auto now = std::chrono::system_clock::now();
    std::time_t now_c = std::chrono::system_clock::to_time_t(now);
    std::string timestamp = std::ctime(&now_c);
    if (!timestamp.empty() && timestamp.back() == '\n') {
        timestamp.pop_back();
    }
    
    file << "\"" << timestamp << "\","
         << utils::protocolTypeToString(config.protocol_type) << ","
         << utils::attackTypeToString(config.attack_type) << ","
         << formatDouble(config.eavesdropping_strength, 6) << ","
         << formatDouble(config.channel_loss_rate, 6) << ","
         << formatDouble(config.dark_count_prob, 8) << ","
         << formatDouble(config.qber_threshold, 4) << ","
         << config.num_photons << ","
         << config.num_runs << ","
         << summary.total_runs << ","
         << summary.successful_runs << ","
         << formatDouble(summary.avg_qber, 8) << ","
         << formatDouble(summary.std_qber, 8) << ","
         << formatDouble(summary.avg_key_rate, 8) << ","
         << formatDouble(summary.std_key_rate, 8) << ","
         << formatDouble(summary.eavesdropping_detection_probability, 8) << ","
         << formatDouble(summary.avg_final_key_length, 4) << ","
         << formatDouble(summary.avg_sifted_key_length, 4) << ","
         << formatDouble(summary.avg_photon_loss_rate, 6) << ","
         << formatDouble(summary.avg_dark_count_rate, 8) << ","
         << config.fiber_length_km << ","
         << formatDouble(summary.avg_pulse_broadening, 8) << ","
         << formatDouble(summary.avg_nonlinear_phase, 10) << ","
         << formatDouble(summary.avg_fiber_qber, 8) << ","
         << (config.use_decoy_states ? "1" : "0") << ","
         << formatDouble(summary.avg_decoy_yield_signal, 8) << ","
         << formatDouble(summary.avg_single_photon_fraction, 8) << ","
         << formatDouble(summary.avg_mdi_visibility, 6) << ","
         << formatDouble(summary.avg_mdi_coincidence_rate, 8) << std::endl;
    
    file.close();
    return true;
}

} // namespace bb84
