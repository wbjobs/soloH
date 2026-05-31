#ifndef STATISTICS_H
#define STATISTICS_H

#include <vector>
#include <map>
#include <cmath>

class Statistics {
public:
    struct ClusterStats {
        std::vector<int> clusterSizes;
        std::map<int, int> sizeDistribution;
        int numClusters;
        int maxClusterSize;
        double avgClusterSize;
    };

    struct FractalResult {
        double dimension;
        double correlation;
        double rSquared;
        double intercept;
        std::vector<double> logR;
        std::vector<double> logN;
        std::vector<double> boxSizes;
        bool isReliable;
    };

    static ClusterStats computeClusterSizeDistribution(
        const std::vector<float>& data,
        int width, int height,
        float threshold = 0.5f);

    static FractalResult computeFractalDimension(
        const std::vector<float>& data,
        int width, int height,
        float threshold = 0.5f);

    static float computeAverageConcentration(const std::vector<float>& data);
    static float computeVariance(const std::vector<float>& data);
    static std::pair<float, float> computeMinMax(const std::vector<float>& data);

private:
    static void floodFill(
        const std::vector<float>& data,
        std::vector<bool>& visited,
        int x, int y,
        int width, int height,
        float threshold,
        int& clusterSize);

    static int boxCount(
        const std::vector<float>& data,
        int width, int height,
        int boxSize,
        int offsetX, int offsetY,
        float threshold);

    static double differentialBoxCount(
        const std::vector<float>& data,
        int width, int height,
        int boxSize);

    static std::vector<int> generateBoxSizes(int maxSize, int minSize = 4);
};

#endif
