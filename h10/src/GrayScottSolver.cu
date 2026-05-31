#include "GrayScottSolver.h"
#include <cmath>
#include <stdexcept>
#include <iostream>

__global__ void initCircularSeedKernel(float* U, float* V, int width, int height) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < width * height) {
        int x = idx % width;
        int y = idx / width;
        float cx = width / 2.0f;
        float cy = height / 2.0f;
        float dist = sqrtf((x - cx) * (x - cx) + (y - cy) * (y - cy));
        
        U[idx] = 1.0f;
        V[idx] = 0.0f;
        
        if (dist < 20.0f) {
            U[idx] = 0.5f;
            V[idx] = 0.25f;
        }
    }
}

__global__ void initRandomNoiseKernel(float* U, float* V, int width, int height, float* randVals) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < width * height) {
        U[idx] = 1.0f - 0.1f * randVals[idx];
        V[idx] = 0.0f + 0.1f * randVals[idx + width * height];
    }
}

__global__ void initMultipleSeedsKernel(float* U, float* V, int width, int height) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < width * height) {
        int x = idx % width;
        int y = idx / width;
        
        U[idx] = 1.0f;
        V[idx] = 0.0f;
        
        float seeds[6][3] = {
            {512.0f, 512.0f, 25.0f},
            {1536.0f, 512.0f, 25.0f},
            {512.0f, 1536.0f, 25.0f},
            {1536.0f, 1536.0f, 25.0f},
            {1024.0f, 1024.0f, 30.0f},
            {1024.0f, 512.0f, 20.0f}
        };
        
        for (int i = 0; i < 6; i++) {
            float dx = x - seeds[i][0];
            float dy = y - seeds[i][1];
            float dist = sqrtf(dx * dx + dy * dy);
            if (dist < seeds[i][2]) {
                U[idx] = 0.5f;
                V[idx] = 0.25f;
                break;
            }
        }
    }
}

__global__ void grayScottStepKernel(
    float* U, float* V, float* U2, float* V2,
    int width, int height,
    float F, float k, float Du, float Dv, float dt) {
    
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < width * height) {
        int x = idx % width;
        int y = idx / width;
        
        int left = (x == 0) ? width - 1 : x - 1;
        int right = (x == width - 1) ? 0 : x + 1;
        int up = (y == 0) ? height - 1 : y - 1;
        int down = (y == height - 1) ? 0 : y + 1;
        
        int idx_left = y * width + left;
        int idx_right = y * width + right;
        int idx_up = up * width + x;
        int idx_down = down * width + x;
        
        float u = fminf(fmaxf(U[idx], 0.0f), 1.0f);
        float v = fminf(fmaxf(V[idx], 0.0f), 1.0f);
        
        float uL = fminf(fmaxf(U[idx_left], 0.0f), 1.0f);
        float uR = fminf(fmaxf(U[idx_right], 0.0f), 1.0f);
        float uU = fminf(fmaxf(U[idx_up], 0.0f), 1.0f);
        float uD = fminf(fmaxf(U[idx_down], 0.0f), 1.0f);
        
        float vL = fminf(fmaxf(V[idx_left], 0.0f), 1.0f);
        float vR = fminf(fmaxf(V[idx_right], 0.0f), 1.0f);
        float vU = fminf(fmaxf(V[idx_up], 0.0f), 1.0f);
        float vD = fminf(fmaxf(V[idx_down], 0.0f), 1.0f);
        
        float lapU = 0.25f * (uL + uR + uU + uD) + 0.5f * (uL + uR + uU + uD - 4.0f * u);
        float lapV = 0.25f * (vL + vR + vU + vD) + 0.5f * (vL + vR + vU + vD - 4.0f * v);
        
        float uvv = u * v * v;
        
        float du = Du * lapU - uvv + F * (1.0f - u);
        float dv = Dv * lapV + uvv - (F + k) * v;
        
        float u_new = u + dt * du;
        float v_new = v + dt * dv;
        
        u_new = 0.99f * u_new + 0.01f * u;
        v_new = 0.99f * v_new + 0.01f * v;
        
        U2[idx] = fminf(fmaxf(u_new, 0.0f), 1.0f);
        V2[idx] = fminf(fmaxf(v_new, 0.0f), 1.0f);
    }
}

__global__ void multiplyLaplacianKernel(
    cufftComplex* freqU, cufftComplex* freqV,
    cufftComplex* lapKernel,
    int width, int height) {
    
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int fftSize = (width / 2 + 1) * height;
    
    if (idx < fftSize) {
        float k = lapKernel[idx].x;
        freqU[idx].x *= k;
        freqU[idx].y *= k;
        freqV[idx].x *= k;
        freqV[idx].y *= k;
    }
}

__global__ void grayScottStepFFTKernel(
    float* U, float* V, float* lapU, float* lapV,
    float* U2, float* V2,
    int width, int height,
    float F, float k, float Du, float Dv, float dt) {
    
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < width * height) {
        float u = fminf(fmaxf(U[idx], 0.0f), 1.0f);
        float v = fminf(fmaxf(V[idx], 0.0f), 1.0f);
        
        float invN = 1.0f / (width * height);
        float lapU_val = lapU[idx] * invN;
        float lapV_val = lapV[idx] * invN;
        
        float uvv = u * v * v;
        
        float du = Du * lapU_val - uvv + F * (1.0f - u);
        float dv = Dv * lapV_val + uvv - (F + k) * v;
        
        float u_new = u + dt * du;
        float v_new = v + dt * dv;
        
        u_new = 0.99f * u_new + 0.01f * u;
        v_new = 0.99f * v_new + 0.01f * v;
        
        U2[idx] = fminf(fmaxf(u_new, 0.0f), 1.0f);
        V2[idx] = fminf(fmaxf(v_new, 0.0f), 1.0f);
    }
}

GrayScottSolver::GrayScottSolver(int width, int height)
    : m_width(width), m_height(height),
      m_dt(1.0f), m_F(0.035f), m_k(0.065f),
      m_Du(0.16f), m_Dv(0.08f),
      m_dU(nullptr), m_dV(nullptr), m_dU2(nullptr), m_dV2(nullptr),
      m_dFreqU(nullptr), m_dFreqV(nullptr), m_dLaplacianKernel(nullptr),
      m_initialCondition(CIRCULAR_SEED),
      m_rng(std::random_device{}()),
      m_adaptiveDt(true) {
    
    m_hostU.resize(width * height);
    m_hostV.resize(width * height);
    
    initCUDA();
    initFFT();
}

GrayScottSolver::~GrayScottSolver() {
    cleanupFFT();
    cleanupCUDA();
}

void GrayScottSolver::initCUDA() {
    size_t size = m_width * m_height * sizeof(float);
    
    cudaMalloc(&m_dU, size);
    cudaMalloc(&m_dV, size);
    cudaMalloc(&m_dU2, size);
    cudaMalloc(&m_dV2, size);
    
    int fftSize = (m_width / 2 + 1) * m_height;
    cudaMalloc(&m_dFreqU, fftSize * sizeof(cufftComplex));
    cudaMalloc(&m_dFreqV, fftSize * sizeof(cufftComplex));
    cudaMalloc(&m_dLaplacianKernel, fftSize * sizeof(cufftComplex));
}

void GrayScottSolver::cleanupCUDA() {
    cudaFree(m_dU);
    cudaFree(m_dV);
    cudaFree(m_dU2);
    cudaFree(m_dV2);
    cudaFree(m_dFreqU);
    cudaFree(m_dFreqV);
    cudaFree(m_dLaplacianKernel);
}

void GrayScottSolver::initFFT() {
    cufftPlan2d(&m_planForwardU, m_height, m_width, CUFFT_R2C);
    cufftPlan2d(&m_planForwardV, m_height, m_width, CUFFT_R2C);
    cufftPlan2d(&m_planInverseU, m_height, m_width, CUFFT_C2R);
    cufftPlan2d(&m_planInverseV, m_height, m_width, CUFFT_C2R);
    
    computeLaplacianKernelFFT();
}

void GrayScottSolver::cleanupFFT() {
    cufftDestroy(m_planForwardU);
    cufftDestroy(m_planForwardV);
    cufftDestroy(m_planInverseU);
    cufftDestroy(m_planInverseV);
}

void GrayScottSolver::computeLaplacianKernelFFT() {
    int fftWidth = m_width / 2 + 1;
    int fftHeight = m_height;
    std::vector<cufftComplex> hostKernel(fftWidth * fftHeight);
    
    for (int y = 0; y < fftHeight; y++) {
        for (int x = 0; x < fftWidth; x++) {
            float kx = 2.0f * M_PI * x / m_width;
            float ky = 2.0f * M_PI * (y > m_height / 2 ? y - m_height : y) / m_height;
            float laplacian = -(kx * kx + ky * ky);
            
            int idx = y * fftWidth + x;
            hostKernel[idx].x = laplacian;
            hostKernel[idx].y = 0.0f;
        }
    }
    
    cudaMemcpy(m_dLaplacianKernel, hostKernel.data(),
               fftWidth * fftHeight * sizeof(cufftComplex),
               cudaMemcpyHostToDevice);
}

void GrayScottSolver::setParameters(float F, float k, float Du, float Dv) {
    m_F = F;
    m_k = k;
    m_Du = Du;
    m_Dv = Dv;
}

void GrayScottSolver::setInitialCondition(InitialCondition cond) {
    m_initialCondition = cond;
}

void GrayScottSolver::initialize() {
    dim3 blockDim(256);
    dim3 gridDim((m_width * m_height + blockDim.x - 1) / blockDim.x);
    
    switch (m_initialCondition) {
        case CIRCULAR_SEED:
            initCircularSeedKernel<<<gridDim, blockDim>>>(m_dU, m_dV, m_width, m_height);
            break;
        case RANDOM_NOISE: {
            std::uniform_real_distribution<float> dist(0.0f, 1.0f);
            std::vector<float> randVals(m_width * m_height * 2);
            for (auto& v : randVals) v = dist(m_rng);
            
            float* dRand;
            cudaMalloc(&dRand, randVals.size() * sizeof(float));
            cudaMemcpy(dRand, randVals.data(), randVals.size() * sizeof(float), cudaMemcpyHostToDevice);
            
            initRandomNoiseKernel<<<gridDim, blockDim>>>(m_dU, m_dV, m_width, m_height, dRand);
            cudaFree(dRand);
            break;
        }
        case MULTIPLE_SEEDS:
            initMultipleSeedsKernel<<<gridDim, blockDim>>>(m_dU, m_dV, m_width, m_height);
            break;
    }
    
    cudaDeviceSynchronize();
    copyToHost();
}

void GrayScottSolver::step(int numSteps) {
    dim3 blockDim(256);
    dim3 gridDim((m_width * m_height + blockDim.x - 1) / blockDim.x);
    
    float effectiveDt = m_dt;
    if (m_adaptiveDt) {
        effectiveDt = computeStableDt();
    }
    
    for (int i = 0; i < numSteps; i++) {
        grayScottStepKernel<<<gridDim, blockDim>>>(
            m_dU, m_dV, m_dU2, m_dV2,
            m_width, m_height, m_F, m_k, m_Du, m_Dv, effectiveDt
        );
        
        float* tmpU = m_dU;
        float* tmpV = m_dV;
        m_dU = m_dU2;
        m_dV = m_dV2;
        m_dU2 = tmpU;
        m_dV2 = tmpV;
    }
    
    cudaDeviceSynchronize();
}

void GrayScottSolver::stepFFT(int numSteps) {
    int fftSize = (m_width / 2 + 1) * m_height;
    dim3 blockDim(256);
    dim3 gridDim((m_width * m_height + blockDim.x - 1) / blockDim.x);
    dim3 gridDimFFT((fftSize + blockDim.x - 1) / blockDim.x);
    
    float effectiveDt = m_dt;
    if (m_adaptiveDt) {
        effectiveDt = computeStableDt();
    }
    
    for (int i = 0; i < numSteps; i++) {
        cufftExecR2C(m_planForwardU, m_dU, m_dFreqU);
        cufftExecR2C(m_planForwardV, m_dV, m_dFreqV);
        
        multiplyLaplacianKernel<<<gridDimFFT, blockDim>>>(
            m_dFreqU, m_dFreqV, m_dLaplacianKernel, m_width, m_height
        );
        
        cufftExecC2R(m_planInverseU, m_dFreqU, m_dU2);
        cufftExecC2R(m_planInverseV, m_dFreqV, m_dV2);
        
        grayScottStepFFTKernel<<<gridDim, blockDim>>>(
            m_dU, m_dV, m_dU2, m_dV2,
            m_dU, m_dV,
            m_width, m_height, m_F, m_k, m_Du, m_Dv, effectiveDt
        );
    }
    
    cudaDeviceSynchronize();
}

float GrayScottSolver::computeStableDt() const {
    float maxDiff = fmaxf(m_Du, m_Dv);
    float dt_diffusion = 0.5f / (4.0f * maxDiff);
    float maxReaction = m_F + m_k + 0.25f;
    float dt_reaction = 0.5f / maxReaction;
    return fminf(dt_diffusion, dt_reaction);
}

void GrayScottSolver::copyToHost() {
    size_t size = m_width * m_height * sizeof(float);
    cudaMemcpy(m_hostU.data(), m_dU, size, cudaMemcpyDeviceToHost);
    cudaMemcpy(m_hostV.data(), m_dV, size, cudaMemcpyDeviceToHost);
}
