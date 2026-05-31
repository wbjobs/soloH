#ifndef GRAYSCOTTSOLVER_H
#define GRAYSCOTTSOLVER_H

#include <cuda_runtime.h>
#include <cufft.h>
#include <vector>
#include <random>

class GrayScottSolver {
public:
    enum InitialCondition {
        CIRCULAR_SEED,
        RANDOM_NOISE,
        MULTIPLE_SEEDS
    };

    GrayScottSolver(int width = 2048, int height = 2048);
    ~GrayScottSolver();

    void setParameters(float F, float k, float Du, float Dv);
    void setInitialCondition(InitialCondition cond);
    void initialize();
    void step(int numSteps = 1);
    void stepFFT(int numSteps = 1);
    void setAdaptiveTimeStep(bool enable) { m_adaptiveDt = enable; }
    float computeStableDt() const;

    const std::vector<float>& getU() const { return m_hostU; }
    const std::vector<float>& getV() const { return m_hostV; }
    int width() const { return m_width; }
    int height() const { return m_height; }

    float getF() const { return m_F; }
    float getK() const { return m_k; }
    float getDu() const { return m_Du; }
    float getDv() const { return m_Dv; }

    void copyToHost();

private:
    int m_width;
    int m_height;
    float m_dt;

    float m_F;
    float m_k;
    float m_Du;
    float m_Dv;

    float* m_dU;
    float* m_dV;
    float* m_dU2;
    float* m_dV2;

    cufftComplex* m_dFreqU;
    cufftComplex* m_dFreqV;
    cufftComplex* m_dLaplacianKernel;

    cufftHandle m_planForwardU;
    cufftHandle m_planForwardV;
    cufftHandle m_planInverseU;
    cufftHandle m_planInverseV;

    std::vector<float> m_hostU;
    std::vector<float> m_hostV;

    InitialCondition m_initialCondition;
    std::mt19937 m_rng;
    bool m_adaptiveDt;

    void initCUDA();
    void cleanupCUDA();
    void initFFT();
    void cleanupFFT();
    void computeLaplacianKernelFFT();
};

#endif
