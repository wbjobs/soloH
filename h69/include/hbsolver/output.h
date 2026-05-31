#ifndef HBSOLVER_OUTPUT_H
#define HBSOLVER_OUTPUT_H

#include "hbsolver/types.h"
#include "hbsolver/analysis.h"
#include "hbsolver/loadpull.h"
#include "hbsolver/envelope.h"
#include <string>
#include <ostream>
#include <vector>

namespace hbsolver {

class OutputWriter {
public:
    static bool writeSpectrumCSV(const HBSolution& solution,
                                  const std::string& filename,
                                  const std::string& separator = ",");

    static bool writeSweepCSV(const std::vector<SweepAnalysis::SweepResult>& results,
                               const std::string& filename,
                               const std::string& sweep_type = "power",
                               const std::string& separator = ",");

    static bool writeTimeDomainCSV(const HBSolution& solution,
                                    const std::string& filename,
                                    const std::string& separator = ",");

    static std::string generateAsciiSpectrum(const HBSolution& solution,
                                              int width = 80,
                                              int height = 24,
                                              double min_dB = -80.0,
                                              double max_dB = 20.0);

    static std::string generateAsciiTimeDomain(const HBSolution& solution,
                                                int width = 80,
                                                int height = 20);

    static std::string generateSweepPlot(const std::vector<SweepAnalysis::SweepResult>& results,
                                          const std::string& sweep_type = "power",
                                          int width = 80,
                                          int height = 20);

    static std::string generateHysteresisPlot(const SweepAnalysis::HysteresisResult& hysteresis,
                                               int width = 80,
                                               int height = 25);

    static bool writeHysteresisCSV(const SweepAnalysis::HysteresisResult& hysteresis,
                                    const std::string& filename,
                                    const std::string& separator = ",");

    static std::string generateSmithChart(const std::vector<LoadPullResult>& results,
                                           int size = 40);

    static std::string generateSmithChartWithContours(
        const std::vector<LoadPullResult>& results,
        const std::vector<ImpedanceContour>& contours,
        int size = 40);

    static std::string generateLoadPullTable(const std::vector<LoadPullResult>& results,
                                             int top_n = 10);

    static std::string generateSourcePullTable(const std::vector<SourcePullResult>& results,
                                               int top_n = 10);

    static bool writeLoadPullCSV(const std::vector<LoadPullResult>& results,
                                  const std::string& filename,
                                  const std::string& separator = ",");

    static bool writeSourcePullCSV(const std::vector<SourcePullResult>& results,
                                    const std::string& filename,
                                    const std::string& separator = ",");

    static bool writeContoursCSV(const std::vector<ImpedanceContour>& contours,
                                  const std::string& filename,
                                  const std::string& separator = ",");

    static std::string generateEnvelopeWaveform(const EnvelopeSolution& env,
                                                int width = 80,
                                                int height = 20);

    static std::string generateAmAmPlot(const AMAMPMCharacteristics& amam,
                                        int width = 60,
                                        int height = 25);

    static std::string generateAmPmPlot(const AMAMPMCharacteristics& ampm,
                                        int width = 60,
                                        int height = 25);

    static bool writeEnvelopeCSV(const EnvelopeSolution& env,
                                  const std::string& filename,
                                  const std::string& separator = ",");

    static bool writeAmAmPmCSV(const AMAMPMCharacteristics& amam,
                                const std::string& filename,
                                const std::string& separator = ",");

    static void printLoadPullSummary(const LoadPullResult& optimum,
                                     const std::vector<ImpedanceContour>& contours,
                                     std::ostream& os = std::cout);

    static void printSourcePullSummary(const SourcePullResult& optimum,
                                       std::ostream& os = std::cout);

    static void printEnvelopeSummary(const EnvelopeSolution& env,
                                     std::ostream& os = std::cout);

    static void printAmAmPmSummary(const AMAMPMCharacteristics& amam,
                                   std::ostream& os = std::cout);

    static void printMemoryEffectSummary(const MemoryEffectConfig& config,
                                         std::ostream& os = std::cout);

    static void printHysteresisSummary(const SweepAnalysis::HysteresisResult& hysteresis,
                                        std::ostream& os = std::cout);
    static void printPowerMetrics(const PowerMetrics& metrics, std::ostream& os = std::cout);
    static void printSolutionSummary(const HBSolution& solution, std::ostream& os = std::cout);
    static void printSpectrumTable(const HBSolution& solution, std::ostream& os = std::cout);
};

}

#endif
