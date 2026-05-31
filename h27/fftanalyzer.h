#ifndef FFTANALYZER_H
#define FFTANALYZER_H

#include <vector>
#include <complex>

enum class WindowType {
    Rectangular,
    Hann,
    Hamming,
    Blackman,
    Nuttall
};

class FFTAnalyzer {
public:
    FFTAnalyzer();

    static std::vector<std::complex<double>> fft(const std::vector<double>& input);
    static std::vector<double> computeMagnitudeSpectrum(const std::vector<double>& input, double sampleRate,
                                                       WindowType window = WindowType::Hann);
    static std::vector<double> computeFrequencies(int size, double sampleRate);
    static std::vector<double> generateWindow(int size, WindowType type);
    static double getWindowCoherentGain(WindowType type);
    static double getWindowENBW(WindowType type);

    void setWindowType(WindowType type);
    void setZeroPadding(bool enable, int targetSize = 0);
    void setLogScale(bool enable);
    void setRemoveDC(bool enable);

    std::vector<double> analyze(const std::vector<double>& signal, double sampleRate);
    std::vector<double> getFrequencies() const;
    std::vector<double> getMagnitudeDB() const;

private:
    WindowType m_windowType;
    bool m_useZeroPadding;
    int m_targetSize;
    bool m_logScale;
    bool m_removeDC;
    std::vector<double> m_lastFrequencies;
    std::vector<double> m_lastMagnitude;

    static void fftInternal(std::vector<std::complex<double>>& data, bool invert);
    static int nextPowerOfTwo(int n);
};

#endif
