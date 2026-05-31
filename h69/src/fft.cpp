#include "hbsolver/fft.h"
#include <stdexcept>
#include <algorithm>

namespace hbsolver {

FFT::FFT() {}

bool FFT::isPowerOfTwo(int n) {
    return n > 0 && (n & (n - 1)) == 0;
}

int FFT::nextPowerOfTwo(int n) {
    int result = 1;
    while (result < n) result <<= 1;
    return result;
}

int FFT::reverseBits(int n, int bits) {
    int reversed = 0;
    for (int i = 0; i < bits; ++i) {
        if (n & (1 << i)) {
            reversed |= 1 << (bits - 1 - i);
        }
    }
    return reversed;
}

void FFT::transform(ComplexVec& data, bool inverse) {
    int n = static_cast<int>(data.size());
    if (!isPowerOfTwo(n)) {
        throw std::invalid_argument("FFT size must be power of two");
    }

    int bits = 0;
    while ((1 << bits) < n) bits++;

    for (int i = 0; i < n; ++i) {
        int j = reverseBits(i, bits);
        if (i < j) {
            std::swap(data[i], data[j]);
        }
    }

    for (int len = 2; len <= n; len <<= 1) {
        double ang = 2.0 * PI / len * (inverse ? -1.0 : 1.0);
        Complex wlen(std::cos(ang), std::sin(ang));
        for (int i = 0; i < n; i += len) {
            Complex w(1.0);
            for (int j = 0; j < len / 2; ++j) {
                Complex u = data[i + j];
                Complex v = data[i + j + len / 2] * w;
                data[i + j] = u + v;
                data[i + j + len / 2] = u - v;
                w *= wlen;
            }
        }
    }

    if (inverse) {
        for (int i = 0; i < n; ++i) {
            data[i] /= static_cast<double>(n);
        }
    }
}

ComplexVec FFT::timeToFrequency(const RealVec& time) {
    int n = static_cast<int>(time.size());
    int nfft = nextPowerOfTwo(n);
    ComplexVec freq(nfft, Complex(0.0, 0.0));

    for (int i = 0; i < n; ++i) {
        freq[i] = Complex(time[i], 0.0);
    }

    transform(freq, false);
    return freq;
}

ComplexVec FFT::frequencyToTime(const ComplexVec& freq) {
    ComplexVec time = freq;
    transform(time, true);
    return time;
}

ComplexVec FFT::timeToFrequencyN(const RealVec& time, int n_freq) {
    int n = static_cast<int>(time.size());
    int nfft = nextPowerOfTwo(n);
    ComplexVec freq(nfft, Complex(0.0, 0.0));

    for (int i = 0; i < n; ++i) {
        freq[i] = Complex(time[i], 0.0);
    }

    transform(freq, false);

    if (n_freq > nfft) n_freq = nfft;
    freq.resize(n_freq);
    return freq;
}

ComplexVec FFT::frequencyToTimeN(const ComplexVec& freq, int n_samples) {
    int n = static_cast<int>(freq.size());
    int nfft = nextPowerOfTwo(std::max(n, n_samples));
    ComplexVec time(nfft, Complex(0.0, 0.0));

    int half = (n + 1) / 2;
    for (int i = 0; i < half && i < nfft; ++i) {
        time[i] = freq[i];
    }
    for (int i = 1; i < half && (nfft - i) > 0; ++i) {
        time[nfft - i] = std::conj(freq[i]);
    }

    transform(time, true);
    time.resize(n_samples);
    return time;
}

}
