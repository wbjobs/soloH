#ifndef BB84_MDI_QKD_H
#define BB84_MDI_QKD_H

#include "types.h"
#include "config.h"
#include <vector>

namespace bb84 {

enum class BellState {
    PHI_PLUS = 0,
    PHI_MINUS = 1,
    PSI_PLUS = 2,
    PSI_MINUS = 3
};

struct TimeBinPhoton {
    Photon photon;
    int time_bin;
    Basis basis;
    double phase;
};

struct CharlieResult {
    BellState bell_state;
    bool detection_success;
    int detector_clicks[4];
    double coincidence_window_ps;
    double arrival_time_diff_ps;
    double interference_visibility;
};

class MDIProtocol {
public:
    MDIProtocol();
    explicit MDIProtocol(const Config& config);
    
    std::vector<TimeBinPhoton> prepareTimeBinPhotons(
        const std::vector<bool>& bits,
        const std::vector<Basis>& bases,
        bool is_alice
    );
    
    CharlieResult performBellStateMeasurement(
        const TimeBinPhoton& alice_photon,
        const TimeBinPhoton& bob_photon
    );
    
    std::vector<CharlieResult> performBellStateMeasurements(
        const std::vector<TimeBinPhoton>& alice_photons,
        const std::vector<TimeBinPhoton>& bob_photons,
        MDIResult& mdi_stats
    );
    
    std::vector<bool> extractSiftedKey(
        const std::vector<bool>& alice_bits,
        const std::vector<Basis>& alice_bases,
        const std::vector<bool>& bob_bits,
        const std::vector<Basis>& bob_bases,
        const std::vector<CharlieResult>& charlie_results,
        bool is_alice
    );
    
    double calculateMDIQBER(
        const std::vector<bool>& alice_key,
        const std::vector<bool>& bob_key,
        const std::vector<CharlieResult>& charlie_results
    );
    
    double estimateSecureKeyRate(
        double sifted_key_rate,
        double qber,
        double interference_visibility,
        double dark_count_prob,
        double loss_alice,
        double loss_bob
    );
    
    double calculateInterferenceVisibility(
        const std::vector<CharlieResult>& results,
        Basis basis
    );
    
    void setConfig(const Config& config);
    
private:
    Config config_;
    
    BellState simulateBellStateMeasurement(
        double phase_alice,
        double phase_bob,
        Basis alice_basis,
        Basis bob_basis,
        double loss_alice,
        double loss_bob,
        double& visibility
    );
    
    double calculateCoincidenceProbability(
        double time_diff_ps,
        double coincidence_window_ps
    );
    
    double estimateEveInformationMDI(
        double qber,
        double visibility,
        double loss
    );
    
    BellState mapDetectionToBellState(
        int detector1, 
        int detector2,
        double phase_diff
    );
};

class CharlieServer {
public:
    CharlieServer(double coincidence_window_ps = 200.0);
    
    CharlieResult measure(
        const TimeBinPhoton& alice,
        const TimeBinPhoton& bob
    );
    
    void announceResult(const CharlieResult& result);
    
    double getCoincidenceWindow() const { return coincidence_window_ps_; }
    void setCoincidenceWindow(double ps) { coincidence_window_ps_ = ps; }
    
private:
    double coincidence_window_ps_;
    double dark_count_prob_;
    double detector_efficiency_;
};

} // namespace bb84

#endif
