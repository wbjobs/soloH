#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QTimer>
#include <QThread>
#include <memory>
#include <vector>
#include "odesolver.h"
#include "chaoticsystems.h"
#include "lyapunovcalculator.h"
#include "fftanalyzer.h"

namespace Ui {
class MainWindow;
}

class PhasePlot3D;
class PlotWidget;

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

private slots:
    void onStartSimulation();
    void onStopSimulation();
    void onResetSimulation();
    void onSimulationStep();

    void onSystemChanged(int index);
    void onSolverChanged(int index);
    void onStepSizeChanged(double value);
    void onMaxPointsChanged(int value);
    void onSpeedChanged(int value);

    void onLorenzSigmaChanged(double value);
    void onLorenzRhoChanged(double value);
    void onLorenzBetaChanged(double value);

    void onChuaAlphaChanged(double value);
    void onChuaBetaChanged(double value);
    void onChuaM0Changed(double value);
    void onChuaM1Changed(double value);

    void onInitialXChanged(double value);
    void onInitialYChanged(double value);
    void onInitialZChanged(double value);

    void onAutoRotateToggled(bool checked);
    void onShowAxesToggled(bool checked);
    void onResetView();

    void onXYModeChanged(int index);
    void onCalculateLyapunov();
    void onExportCSV();

    void onUpdateFFT();

private:
    void setupUI();
    void setupConnections();
    void initializeSystem();

    void updateTimeDomainPlots();
    void updateSpectrumPlot();
    void updateXYPlot();
    void updateLyapunovDisplay(const std::vector<double>& exponents);
    void updateStatusInfo();

    void collectDataPoint();
    void runTransient(int steps);

    std::unique_ptr<Ui::MainWindow> ui;

    PhasePlot3D* m_phasePlot3D;
    PlotWidget* m_timePlot;
    PlotWidget* m_spectrumPlot;
    PlotWidget* m_xyPlot;

    ChaoticSystem m_system;
    ODESolver m_solver;
    std::unique_ptr<LyapunovCalculator> m_lyapunovCalc;
    FFTAnalyzer m_fftAnalyzer;

    QTimer* m_simulationTimer;

    State m_currentState;
    double m_currentTime;
    double m_stepSize;
    double m_simulationSpeed;
    bool m_isRunning;

    int m_maxPoints;
    int m_dataSkip;
    int m_sampleCounter;

    std::vector<double> m_timeData;
    std::vector<double> m_xData;
    std::vector<double> m_yData;
    std::vector<double> m_zData;

    int m_xyChannelX;
    int m_xyChannelY;

    std::vector<double> m_spectrumFreqs;
    std::vector<double> m_spectrumMagn;
};

#endif
