#include <QApplication>
#include <QSurfaceFormat>
#include <QMessageBox>
#include <cuda_runtime.h>
#include "MainWindow.h"

int main(int argc, char* argv[]) {
    QSurfaceFormat format;
    format.setVersion(3, 3);
    format.setProfile(QSurfaceFormat::CoreProfile);
    format.setDepthBufferSize(24);
    format.setStencilBufferSize(8);
    format.setSamples(4);
    QSurfaceFormat::setDefaultFormat(format);

    QApplication app(argc, argv);
    app.setApplicationName("Gray-Scott Reaction-Diffusion Simulator");
    app.setOrganizationName("CUDA-Apps");

    int cudaDeviceCount = 0;
    cudaError_t cudaStatus = cudaGetDeviceCount(&cudaDeviceCount);
    
    if (cudaStatus != cudaSuccess || cudaDeviceCount == 0) {
        QMessageBox::critical(nullptr, "CUDA Error",
            "No CUDA-capable device found. Please check your CUDA installation.");
        return 1;
    }

    cudaDeviceProp deviceProp;
    cudaGetDeviceProperties(&deviceProp, 0);
    
    qDebug() << "Using CUDA Device:" << deviceProp.name;
    qDebug() << "Compute Capability:" << deviceProp.major << "." << deviceProp.minor;
    qDebug() << "Total Global Memory:" << deviceProp.totalGlobalMem / (1024 * 1024) << "MB";

    MainWindow window;
    window.show();

    return app.exec();
}
