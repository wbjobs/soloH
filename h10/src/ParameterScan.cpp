#include "ParameterScan.h"
#include "GrayScottSolver.h"
#include "Statistics.h"
#include <fstream>
#include <iostream>
#include <opencv2/opencv.hpp>
#include <iomanip>
#include <algorithm>

ParameterScan::ParameterScan()
    : m_Du(0.16f), m_Dv(0.08f),
      m_simSteps(5000), m_convThreshold(1e-4f),
      m_stopFlag(false), m_running(false), m_completed(0), m_totalPoints(0) {
    
    m_rangeF = {0.02f, 0.06f, 20};
    m_rangeK = {0.05f, 0.07f, 20};
}

ParameterScan::~ParameterScan() {
    stopScan();
}

void ParameterScan::setScanRanges(const ScanRange& F_range, const ScanRange& K_range) {
    m_rangeF = F_range;
    m_rangeK = K_range;
}

void ParameterScan::setFixedParameters(float Du, float Dv) {
    m_Du = Du;
    m_Dv = Dv;
}

ParameterScan::PhasePoint ParameterScan::simulatePoint(float F, float k, float Du, float Dv) {
    PhasePoint point;
    point.F = F;
    point.k = k;
    point.Du = Du;
    point.Dv = Dv;
    point.avgV = 0.0f;
    point.varV = 0.0f;
    point.numClusters = 0;
    point.fractalDim = 0.0f;
    point.maxClusterSize = 0;
    point.convergenceSteps = 0;
    point.converged = false;

    try {
        GrayScottSolver solver(512, 512);
        solver.setParameters(F, k, Du, Dv);
        solver.setAdaptiveTimeStep(true);
        solver.initialize();

        float prevAvg = 0.0f;
        int stableCount = 0;
        
        for (int step = 0; step < m_simSteps; step++) {
            if (m_stopFlag.load()) break;

            solver.step(10);
            solver.copyToHost();

            if (step % 50 == 0) {
                float avgV = Statistics::computeAverageConcentration(solver.getV());
                
                if (std::abs(avgV - prevAvg) < m_convThreshold) {
                    stableCount++;
                    if (stableCount >= 3) {
                        point.converged = true;
                        point.convergenceSteps = step;
                        break;
                    }
                } else {
                    stableCount = 0;
                }
                prevAvg = avgV;
            }
        }

        solver.copyToHost();
        const auto& V = solver.getV();
        
        point.avgV = Statistics::computeAverageConcentration(V);
        point.varV = Statistics::computeVariance(V);
        
        auto clusterStats = Statistics::computeClusterSizeDistribution(V, 512, 512, 0.3f);
        point.numClusters = clusterStats.numClusters;
        point.maxClusterSize = static_cast<float>(clusterStats.maxClusterSize);
        
        auto fractal = Statistics::computeFractalDimension(V, 512, 512, 0.3f);
        point.fractalDim = static_cast<float>(fractal.dimension);
        
        if (!point.converged) {
            point.convergenceSteps = m_simSteps;
        }

    } catch (const std::exception& e) {
        std::cerr << "Error simulating point (F=" << F << ", k=" << k << "): " << e.what() << std::endl;
    }

    return point;
}

ParameterScan::PhaseDiagram ParameterScan::startScan(int numThreads) {
    m_running.store(true);
    m_stopFlag.store(false);
    m_completed.store(0);

    std::vector<float> F_values;
    std::vector<float> K_values;

    for (int i = 0; i < m_rangeF.steps; i++) {
        float F = m_rangeF.start + (m_rangeF.end - m_rangeF.start) * i / (m_rangeF.steps - 1);
        F_values.push_back(F);
    }

    for (int j = 0; j < m_rangeK.steps; j++) {
        float k = m_rangeK.start + (m_rangeK.end - m_rangeK.start) * j / (m_rangeK.steps - 1);
        K_values.push_back(k);
    }

    m_totalPoints = F_values.size() * K_values.size();
    PhaseDiagram diagram;
    diagram.rangeF = m_rangeF;
    diagram.rangeK = m_rangeK;
    diagram.F_values = F_values;
    diagram.K_values = K_values;
    diagram.data.resize(m_totalPoints);

    std::vector<std::pair<int, int>> jobs;
    for (int i = 0; i < m_rangeF.steps; i++) {
        for (int j = 0; j < m_rangeK.steps; j++) {
            jobs.push_back({i, j});
        }
    }

    std::atomic<int> jobIndex(0);
    std::mutex resultMutex;

    auto worker = [&]() {
        while (!m_stopFlag.load()) {
            int idx = jobIndex.fetch_add(1);
            if (idx >= jobs.size()) break;

            int i = jobs[idx].first;
            int j = jobs[idx].second;
            int dataIdx = i * m_rangeK.steps + j;

            float F = F_values[i];
            float k = K_values[j];

            PhasePoint point = simulatePoint(F, k, m_Du, m_Dv);

            {
                std::lock_guard<std::mutex> lock(resultMutex);
                diagram.data[dataIdx] = point;
            }

            int completed = m_completed.fetch_add(1) + 1;
            if (m_callback) {
                m_callback(completed, m_totalPoints, point);
            }
        }
    };

    if (numThreads <= 0) numThreads = 1;
    std::vector<std::thread> threads;
    for (int t = 0; t < numThreads; t++) {
        threads.emplace_back(worker);
    }

    for (auto& t : threads) {
        if (t.joinable()) {
            t.join();
        }
    }

    m_running.store(false);
    return diagram;
}

void ParameterScan::savePhaseDiagram(const PhaseDiagram& diagram, const std::string& filename) {
    std::ofstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("Could not open file for writing: " + filename);
    }

    file.write(reinterpret_cast<const char*>(&diagram.rangeF), sizeof(ScanRange));
    file.write(reinterpret_cast<const char*>(&diagram.rangeK), sizeof(ScanRange));

    size_t dataSize = diagram.data.size();
    file.write(reinterpret_cast<const char*>(&dataSize), sizeof(size_t));
    file.write(reinterpret_cast<const char*>(diagram.data.data()), 
               static_cast<std::streamsize>(dataSize * sizeof(PhasePoint)));
}

void ParameterScan::savePhaseDiagramCSV(const PhaseDiagram& diagram, const std::string& filename) {
    std::ofstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Could not open file for writing: " + filename);
    }

    file << "F,k,Du,Dv,avgV,varV,numClusters,fractalDim,maxClusterSize,convergenceSteps,converged\n";

    for (const auto& point : diagram.data) {
        file << std::fixed << std::setprecision(6)
             << point.F << ","
             << point.k << ","
             << point.Du << ","
             << point.Dv << ","
             << point.avgV << ","
             << point.varV << ","
             << point.numClusters << ","
             << point.fractalDim << ","
             << point.maxClusterSize << ","
             << point.convergenceSteps << ","
             << (point.converged ? "1" : "0") << "\n";
    }
}

void ParameterScan::savePhaseDiagramImage(const PhaseDiagram& diagram, const std::string& filename, 
                                           const std::string& metric) {
    int w = diagram.rangeF.steps;
    int h = diagram.rangeK.steps;
    
    cv::Mat image(h, w, CV_8UC3);
    
    std::vector<float> values(diagram.data.size());
    for (size_t i = 0; i < diagram.data.size(); i++) {
        if (metric == "avgV") {
            values[i] = diagram.data[i].avgV;
        } else if (metric == "varV") {
            values[i] = diagram.data[i].varV;
        } else if (metric == "numClusters") {
            values[i] = static_cast<float>(diagram.data[i].numClusters);
        } else if (metric == "fractalDim") {
            values[i] = diagram.data[i].fractalDim;
        } else if (metric == "convergenceSteps") {
            values[i] = static_cast<float>(diagram.data[i].convergenceSteps);
        } else {
            values[i] = diagram.data[i].avgV;
        }
    }

    float minVal = *std::min_element(values.begin(), values.end());
    float maxVal = *std::max_element(values.begin(), values.end());

    for (int i = 0; i < w; i++) {
        for (int j = 0; j < h; j++) {
            int idx = i * h + j;
            float val = values[idx];
            
            float normalized = (maxVal > minVal) ? (val - minVal) / (maxVal - minVal) : 0.5f;
            
            cv::Vec3b color;
            if (diagram.data[idx].converged) {
                color[0] = static_cast<unsigned char>(255 * (0.5f + 0.5f * std::sin(normalized * M_PI)));
                color[1] = static_cast<unsigned char>(255 * (0.3f + 0.7f * normalized));
                color[2] = static_cast<unsigned char>(255 * normalized);
            } else {
                color[0] = 100;
                color[1] = 100;
                color[2] = 100;
            }
            
            image.at<cv::Vec3b>(h - 1 - j, i) = color;
        }
    }

    cv::resize(image, image, cv::Size(w * 20, h * 20), 0, 0, cv::INTER_NEAREST);
    
    cv::cvtColor(image, image, cv::COLOR_RGB2BGR);
    cv::imwrite(filename, image);
}
