#ifndef BB84_STATS_H
#define BB84_STATS_H

#include "types.h"
#include "config.h"
#include <vector>
#include <string>
#include <fstream>

namespace bb84 {

class Statistics {
public:
    Statistics();
    
    void addRun(const RunResult& result);
    StatsSummary computeSummary() const;
    
    void printTerminalTable(const Config& config) const;
    void printSummaryTable(const Config& config) const;
    
    bool exportToCSV(const std::string& filename, const Config& config) const;
    bool exportSummaryToCSV(const std::string& filename, const Config& config) const;
    
    const std::vector<RunResult>& getResults() const;
    void clear();
    
private:
    std::vector<RunResult> results_;
    
    double calculateMean(const std::vector<double>& values) const;
    double calculateStdDev(const std::vector<double>& values, double mean) const;
    void printTableHeader() const;
    void printTableRow(const RunResult& result) const;
    std::string formatDouble(double value, int precision = 4) const;
};

} // namespace bb84

#endif
