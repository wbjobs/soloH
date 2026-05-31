#ifndef HBSOLVER_FFT_H
#define HBSOLVER_FFT_H

#include "hbsolver/types.h"

namespace hbsolver {

class FFT {
public:
    FFT();
    ~FFT() = default;

    static void transform(ComplexVec& data, bool inverse = false);
    static ComplexVec frequencyToTime(const ComplexVec& freq);
    static ComplexVec timeToFrequency(const RealVec& time);

    static ComplexVec frequencyToTimeN(const ComplexVec& freq, int n_samples);
    static ComplexVec timeToFrequencyN(const RealVec& time, int n_freq);

private:
    static int reverseBits(int n, int bits);
    static bool isPowerOfTwo(int n);
    static int nextPowerOfTwo(int n);
};

}

#endif
