#include "fftanalyzer.h"
#include <cmath>
#include <algorithm>
#include <numeric>

const double PI = 3.14159265358979323846;

FFTAnalyzer::FFTAnalyzer()
    : m_windowType(WindowType::Hann)
    , m_useZeroPadding(true)
    , m_targetSize(0)
    , m_logScale(false)
    , m_removeDC(true)
{
}

int FFTAnalyzer::nextPowerOfTwo(int n)
{
    int power = 1;
    while (power < n) {
        power <<= 1;
    }
    return power;
}

void FFTAnalyzer::fftInternal(std::vector<std::complex<double>>& data, bool invert)
{
    int n = data.size();
    if (n <= 1) return;

    for (int i = 1, j = 0; i < n; ++i) {
        int bit = n >> 1;
        for (; j & bit; bit >>= 1) {
            j ^= bit;
        }
        j ^= bit;

        if (i < j) {
            std::swap(data[i], data[j]);
        }
    }

    for (int len = 2; len <= n; len <<= 1) {
        double ang = 2 * PI / len * (invert ? -1 : 1);
        std::complex<double> wlen(cos(ang), sin(ang));
        for (int i = 0; i < n; i += len) {
            std::complex<double> w(1);
            for (int j = 0; j < len / 2; ++j) {
                std::complex<double> u = data[i + j];
                std::complex<double> v = data[i + j + len / 2] * w;
                data[i + j] = u + v;
                data[i + j + len / 2] = u - v;
                w *= wlen;
            }
        }
    }

    if (invert) {
        for (std::complex<double>& x : data) {
            x /= n;
        }
    }
}

std::vector<double> FFTAnalyzer::generateWindow(int size, WindowType type)
{
    std::vector<double> window(size);

    switch (type) {
    case WindowType::Rectangular:
        for (int i = 0; i < size; ++i) {
            window[i] = 1.0;
        }
        break;

    case WindowType::Hann:
        for (int i = 0; i < size; ++i) {
            window[i] = 0.5 * (1.0 - cos(2.0 * PI * i / (size - 1)));
        }
        break;

    case WindowType::Hamming:
        for (int i = 0; i < size; ++i) {
            window[i] = 0.54 - 0.46 * cos(2.0 * PI * i / (size - 1));
        }
        break;

    case WindowType::Blackman:
        for (int i = 0; i < size; ++i) {
            window[i] = 0.42 - 0.5 * cos(2.0 * PI * i / (size - 1))
                       + 0.08 * cos(4.0 * PI * i / (size - 1));
        }
        break;

    case WindowType::Nuttall:
        for (int i = 0; i < size; ++i) {
            window[i] = 0.355768
                       - 0.487396 * cos(2.0 * PI * i / (size - 1))
                       + 0.144232 * cos(4.0 * PI * i / (size - 1))
                       - 0.012604 * cos(6.0 * PI * i / (size - 1));
        }
        break;
    }

    return window;
}

double FFTAnalyzer::getWindowCoherentGain(WindowType type)
{
    switch (type) {
    case WindowType::Rectangular: return 1.0;
    case WindowType::Hann:        return 0.5;
    case WindowType::Hamming:     return 0.54;
    case WindowType::Blackman:    return 0.42;
    case WindowType::Nuttall:     return 0.355768;
    }
    return 1.0;
}

double FFTAnalyzer::getWindowENBW(WindowType type)
{
    switch (type) {
    case WindowType::Rectangular: return 1.0;
    case WindowType::Hann:        return 1.5;
    case WindowType::Hamming:     return 1.36;
    case WindowType::Blackman:    return 1.73;
    case WindowType::Nuttall:     return 1.98;
    }
    return 1.0;
}

std::vector<std::complex<double>> FFTAnalyzer::fft(const std::vector<double>& input)
{
    int n = input.size();
    int nfft = nextPowerOfTwo(n);

    std::vector<std::complex<double>> data(nfft, 0.0);
    for (int i = 0; i < n; ++i) {
        data[i] = input[i];
    }

    fftInternal(data, false);
    return data;
}

std::vector<double> FFTAnalyzer::computeFrequencies(int size, double sampleRate)
{
    std::vector<double> freqs(size / 2 + 1);
    double df = sampleRate / size;

    for (int i = 0; i <= size / 2; ++i) {
        freqs[i] = i * df;
    }

    return freqs;
}

std::vector<double> FFTAnalyzer::computeMagnitudeSpectrum(const std::vector<double>& input,
                                                         double sampleRate,
                                                         WindowType window)
{
    FFTAnalyzer analyzer;
    analyzer.setWindowType(window);
    analyzer.setRemoveDC(true);
    return analyzer.analyze(input, sampleRate);
}

std::vector<double> FFTAnalyzer::analyze(const std::vector<double>& signal, double sampleRate)
{
    if (signal.size() < 2) {
        m_lastFrequencies.clear();
        m_lastMagnitude.clear();
        return std::vector<double>();
    }

    std::vector<double> processed = signal;
    int originalSize = static_cast<int>(processed.size());

    if (m_removeDC) {
        double mean = std::accumulate(processed.begin(), processed.end(), 0.0) / processed.size();
        for (auto& x : processed) {
            x -= mean;
        }
    }

    std::vector<double> window = generateWindow(originalSize, m_windowType);
    double coherentGain = getWindowCoherentGain(m_windowType);

    double windowSum = 0.0;
    for (auto w : window) windowSum += w;
    double windowAmpCorrection = 1.0 / (windowSum / originalSize);

    for (int i = 0; i < originalSize; ++i) {
        processed[i] *= window[i];
    }

    int targetSize = originalSize;
    if (m_useZeroPadding) {
        targetSize = m_targetSize > 0 ? m_targetSize : nextPowerOfTwo(originalSize * 2);
    }

    if (targetSize > originalSize) {
        processed.resize(targetSize, 0.0);
    }

    std::vector<std::complex<double>> data(targetSize);
    for (int i = 0; i < targetSize; ++i) {
        data[i] = processed[i];
    }

    fftInternal(data, false);

    int n = targetSize;
    int halfN = n / 2 + 1;
    std::vector<double> magnitude(halfN);

    double ampScale = 2.0 * windowAmpCorrection / n;

    magnitude[0] = std::abs(data[0]) * windowAmpCorrection / n;

    for (int i = 1; i < halfN - 1; ++i) {
        magnitude[i] = std::abs(data[i]) * ampScale;
    }

    if (n % 2 == 0) {
        magnitude[halfN - 1] = std::abs(data[n / 2]) * windowAmpCorrection / n;
    } else {
        magnitude[halfN - 1] = std::abs(data[n / 2]) * ampScale;
    }

    m_lastMagnitude = magnitude;
    m_lastFrequencies = computeFrequencies(n, sampleRate);

    if (m_logScale) {
        return getMagnitudeDB();
    }

    return magnitude;
}

std::vector<double> FFTAnalyzer::getMagnitudeDB() const
{
    std::vector<double> db(m_lastMagnitude.size());
    for (size_t i = 0; i < m_lastMagnitude.size(); ++i) {
        double mag = std::max(m_lastMagnitude[i], 1e-12);
        db[i] = 20.0 * log10(mag);
    }
    return db;
}

std::vector<double> FFTAnalyzer::getFrequencies() const
{
    return m_lastFrequencies;
}

void FFTAnalyzer::setWindowType(WindowType type)
{
    m_windowType = type;
}

void FFTAnalyzer::setZeroPadding(bool enable, int targetSize)
{
    m_useZeroPadding = enable;
    m_targetSize = targetSize;
}

void FFTAnalyzer::setLogScale(bool enable)
{
    m_logScale = enable;
}

void FFTAnalyzer::setRemoveDC(bool enable)
{
    m_removeDC = enable;
}
