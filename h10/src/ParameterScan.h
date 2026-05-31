#ifndef PARAMETERSCAN_H
#define PARAMETERSCAN_H

#include <vector>
#include <string>
#include <functional>
#include <thread>
#include <atomic>
#include <mutex>
#include <future>

class GrayScottSolver;

class ParameterScan {
public:
    struct ScanRange {
        float start;
        float end;
        int steps;
    };

    struct PhasePoint {
        float F;
        float k;
        float Du;
        float Dv;
        float avgV;
        float varV;
        int numClusters;
        float fractalDim;
        float maxClusterSize;
        int convergenceSteps;
        bool converged;
    };

    struct PhaseDiagram {
        ScanRange rangeF;
        ScanRange rangeK;
        std::vector<PhasePoint> data;
        std::vector<float> F_values;
        std::vector<float> K_values;
    };

    using ProgressCallback = std::function<void(int current, int total, const PhasePoint& point)>;

    ParameterScan();
    ~ParameterScan();

    void setScanRanges(const ScanRange& F_range, const ScanRange& K_range);
    void setFixedParameters(float Du, float Dv);
    void setSimulationSteps(int steps) { m_simSteps = steps; }
    void setConvergenceThreshold(float threshold) { m_convThreshold = threshold; }
    void setProgressCallback(ProgressCallback callback) { m_callback = callback; }

    PhaseDiagram startScan(int numThreads = 1);
    void stopScan() { m_stopFlag.store(true); }
    bool isRunning() const { return m_running.load(); }
    void savePhaseDiagram(const PhaseDiagram& diagram, const std::string& filename);
    void savePhaseDiagramCSV(const PhaseDiagram& diagram, const std::string& filename);
    void savePhaseDiagramImage(const PhaseDiagram& diagram, const std::string& filename, 
                               const std::string& metric = "avgV");

private:
    PhasePoint simulatePoint(float F, float k, float Du, float Dv);

    ScanRange m_rangeF;
    ScanRange m_rangeK;
    float m_Du;
    float m_Dv;
    int m_simSteps;
    float m_convThreshold;
    ProgressCallback m_callback;
    std::atomic<bool> m_stopFlag;
    std::atomic<bool> m_running;
    std::atomic<int> m_completed;
    int m_totalPoints;
};

#endif
