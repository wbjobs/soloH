#include "Statistics.h"
#include <queue>
#include <algorithm>
#include <numeric>
#include <stdexcept>

Statistics::ClusterStats Statistics::computeClusterSizeDistribution(
    const std::vector<float>& data,
    int width, int height,
    float threshold) {
    
    ClusterStats stats;
    stats.numClusters = 0;
    stats.maxClusterSize = 0;
    stats.avgClusterSize = 0.0;

    if (data.size() != static_cast<size_t>(width * height)) {
        throw std::invalid_argument("Data size mismatch");
    }

    std::vector<bool> visited(width * height, false);

    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int idx = y * width + x;
            if (!visited[idx] && data[idx] > threshold) {
                int clusterSize = 0;
                floodFill(data, visited, x, y, width, height, threshold, clusterSize);
                
                if (clusterSize > 0) {
                    stats.clusterSizes.push_back(clusterSize);
                    stats.sizeDistribution[clusterSize]++;
                    stats.numClusters++;
                    stats.maxClusterSize = std::max(stats.maxClusterSize, clusterSize);
                }
            }
        }
    }

    if (!stats.clusterSizes.empty()) {
        stats.avgClusterSize = std::accumulate(
            stats.clusterSizes.begin(),
            stats.clusterSizes.end(),
            0.0) / stats.clusterSizes.size();
    }

    return stats;
}

void Statistics::floodFill(
    const std::vector<float>& data,
    std::vector<bool>& visited,
    int startX, int startY,
    int width, int height,
    float threshold,
    int& clusterSize) {
    
    std::queue<std::pair<int, int>> q;
    q.push({startX, startY});
    visited[startY * width + startX] = true;

    int dx[] = {-1, 1, 0, 0};
    int dy[] = {0, 0, -1, 1};

    while (!q.empty()) {
        std::pair<int, int> current = q.front();
        q.pop();
        int x = current.first;
        int y = current.second;
        clusterSize++;

        for (int i = 0; i < 4; i++) {
            int nx = x + dx[i];
            int ny = y + dy[i];
            
            if (nx >= 0 && nx < width && ny >= 0 && ny < height) {
                int nidx = ny * width + nx;
                if (!visited[nidx] && data[nidx] > threshold) {
                    visited[nidx] = true;
                    q.push({nx, ny});
                }
            }
        }
    }
}

std::vector<int> Statistics::generateBoxSizes(int maxSize, int minSize) {
    std::vector<int> sizes;
    int startSize = 1;
    while (startSize < minSize) startSize *= 2;
    
    for (int size = startSize; size <= maxSize / 4; size *= 2) {
        sizes.push_back(size);
    }
    
    if (sizes.size() < 4) {
        sizes.clear();
        for (int size = minSize; size <= maxSize / 4; size *= 2) {
            sizes.push_back(size);
        }
    }
    
    return sizes;
}

int Statistics::boxCount(
    const std::vector<float>& data,
    int width, int height,
    int boxSize,
    int offsetX, int offsetY,
    float threshold) {
    
    int count = 0;
    int effectiveWidth = width - offsetX;
    int effectiveHeight = height - offsetY;
    
    if (effectiveWidth <= 0 || effectiveHeight <= 0) {
        return 0;
    }
    
    int boxesX = effectiveWidth / boxSize;
    int boxesY = effectiveHeight / boxSize;
    
    if (boxesX == 0 || boxesY == 0) {
        return 0;
    }

    for (int by = 0; by < boxesY; by++) {
        for (int bx = 0; bx < boxesX; bx++) {
            bool hasPoint = false;
            int startX = offsetX + bx * boxSize;
            int startY = offsetY + by * boxSize;
            int endX = startX + boxSize;
            int endY = startY + boxSize;

            for (int y = startY; y < endY && !hasPoint; y++) {
                for (int x = startX; x < endX && !hasPoint; x++) {
                    int idx = y * width + x;
                    if (data[idx] > threshold) {
                        hasPoint = true;
                    }
                }
            }

            if (hasPoint) {
                count++;
            }
        }
    }

    return count;
}

double Statistics::differentialBoxCount(
    const std::vector<float>& data,
    int width, int height,
    int boxSize) {
    
    int boxesX = width / boxSize;
    int boxesY = height / boxSize;
    
    if (boxesX == 0 || boxesY == 0) {
        return 0.0;
    }
    
    double totalBoxes = 0.0;
    int grayLevels = 256;
    int boxHeight = std::max(1, grayLevels / (height / boxSize));
    
    for (int by = 0; by < boxesY; by++) {
        for (int bx = 0; bx < boxesX; bx++) {
            float minVal = 1.0f;
            float maxVal = 0.0f;
            
            for (int y = by * boxSize; y < (by + 1) * boxSize; y++) {
                for (int x = bx * boxSize; x < (bx + 1) * boxSize; x++) {
                    int idx = y * width + x;
                    float val = data[idx];
                    minVal = std::min(minVal, val);
                    maxVal = std::max(maxVal, val);
                }
            }
            
            int minBox = static_cast<int>(minVal * (grayLevels - 1)) / boxHeight;
            int maxBox = static_cast<int>(maxVal * (grayLevels - 1)) / boxHeight;
            int numBoxes = maxBox - minBox + 1;
            
            totalBoxes += static_cast<double>(numBoxes);
        }
    }
    
    return totalBoxes;
}

Statistics::FractalResult Statistics::computeFractalDimension(
    const std::vector<float>& data,
    int width, int height,
    float threshold) {
    
    FractalResult result;
    result.dimension = 0.0;
    result.correlation = 0.0;
    result.rSquared = 0.0;
    result.intercept = 0.0;
    result.isReliable = false;

    int minDim = std::min(width, height);
    auto boxSizes = generateBoxSizes(minDim, 4);
    
    if (boxSizes.size() < 4) {
        return result;
    }
    
    result.boxSizes.reserve(boxSizes.size());
    result.logR.reserve(boxSizes.size());
    result.logN.reserve(boxSizes.size());

    int offsets[4][2] = {{0, 0}, {1, 0}, {0, 1}, {1, 1}};
    
    for (size_t s = 0; s < boxSizes.size(); s++) {
        int boxSize = boxSizes[s];
        double avgCount = 0.0;
        int validOffsets = 0;
        
        for (int o = 0; o < 4; o++) {
            int count = boxCount(data, width, height, boxSize, 
                                 offsets[o][0] * boxSize / 2, 
                                 offsets[o][1] * boxSize / 2, 
                                 threshold);
            if (count > 0) {
                avgCount += static_cast<double>(count);
                validOffsets++;
            }
        }
        
        if (validOffsets > 0) {
            avgCount /= static_cast<double>(validOffsets);
            
            double r = static_cast<double>(boxSize) / static_cast<double>(minDim);
            
            result.boxSizes.push_back(boxSize);
            result.logR.push_back(std::log(1.0 / r));
            result.logN.push_back(std::log(avgCount));
        }
    }

    if (result.logR.size() < 4) {
        return result;
    }

    double n = static_cast<double>(result.logR.size());
    double sumX = 0.0, sumY = 0.0, sumXY = 0.0, sumX2 = 0.0, sumY2 = 0.0;

    for (size_t i = 0; i < result.logR.size(); i++) {
        double x = result.logR[i];
        double y = result.logN[i];
        sumX += x;
        sumY += y;
        sumXY += x * y;
        sumX2 += x * x;
        sumY2 += y * y;
    }

    double denominator = n * sumX2 - sumX * sumX;
    if (std::abs(denominator) < 1e-10) {
        return result;
    }

    double slope = (n * sumXY - sumX * sumY) / denominator;
    double intercept = (sumY - slope * sumX) / n;
    
    result.dimension = slope;
    result.intercept = intercept;

    double ssTotal = 0.0, ssResidual = 0.0;
    double yMean = sumY / n;
    
    for (size_t i = 0; i < result.logR.size(); i++) {
        double x = result.logR[i];
        double y = result.logN[i];
        double yPred = slope * x + intercept;
        ssResidual += (y - yPred) * (y - yPred);
        ssTotal += (y - yMean) * (y - yMean);
    }
    
    if (ssTotal > 1e-10) {
        result.rSquared = 1.0 - ssResidual / ssTotal;
    }
    
    double numerator = n * sumXY - sumX * sumY;
    double denominator1 = n * sumX2 - sumX * sumX;
    double denominator2 = n * sumY2 - sumY * sumY;
    
    if (denominator1 > 1e-10 && denominator2 > 1e-10) {
        result.correlation = numerator / std::sqrt(denominator1 * denominator2);
    }
    
    result.isReliable = (result.rSquared >= 0.95) && 
                        (result.dimension >= 1.0) && 
                        (result.dimension <= 2.0);

    return result;
}

float Statistics::computeAverageConcentration(const std::vector<float>& data) {
    if (data.empty()) return 0.0f;
    double sum = std::accumulate(data.begin(), data.end(), 0.0);
    return static_cast<float>(sum / data.size());
}

float Statistics::computeVariance(const std::vector<float>& data) {
    if (data.size() < 2) return 0.0f;
    float mean = computeAverageConcentration(data);
    double sumSq = 0.0;
    for (float v : data) {
        double diff = v - mean;
        sumSq += diff * diff;
    }
    return static_cast<float>(sumSq / (data.size() - 1));
}

std::pair<float, float> Statistics::computeMinMax(const std::vector<float>& data) {
    if (data.empty()) return {0.0f, 0.0f};
    auto result = std::minmax_element(data.begin(), data.end());
    return {*result.first, *result.second};
}
