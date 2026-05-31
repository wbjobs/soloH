#include "mainwindow.h"
#include "ui_mainwindow.h"
#include "phaseplot3d.h"
#include "plotwidget.h"
#include "dataexporter.h"

#include <QFileDialog>
#include <QMessageBox>
#include <QThread>
#include <QDateTime>
#include <QProgressDialog>
#include <QApplication>
#include <cmath>
#include <algorithm>

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , ui(new Ui::MainWindow)
    , m_system(SystemType::Lorenz)
    , m_solver(m_system.getODEFunction(), 0.01, SolverMethod::RK4)
    , m_lyapunovCalc(std::make_unique<LyapunovCalculator>(m_system, SolverMethod::RK4))
    , m_simulationTimer(nullptr)
    , m_currentTime(0.0)
    , m_stepSize(0.01)
    , m_simulationSpeed(10.0)
    , m_isRunning(false)
    , m_maxPoints(20000)
    , m_dataSkip(1)
    , m_sampleCounter(0)
    , m_xyChannelX(0)
    , m_xyChannelY(1)
{
    ui->setupUi(this);
    setupUI();
    setupConnections();
    initializeSystem();

    setStyleSheet("QMainWindow { background-color: #1a1a2e; }"
                  "QGroupBox { "
                  "  background-color: #16213e; "
                  "  border: 1px solid #0f3460; "
                  "  border-radius: 5px; "
                  "  margin-top: 10px; "
                  "  color: #e0e0e0; "
                  "  font-weight: bold;"
                  "}"
                  "QGroupBox::title { "
                  "  subcontrol-origin: margin; "
                  "  left: 10px; "
                  "  padding: 0 5px; "
                  "  color: #00d4ff; "
                  "}"
                  "QLabel { color: #e0e0e0; }"
                  "QComboBox, QDoubleSpinBox, QSpinBox { "
                  "  background-color: #0f3460; "
                  "  color: #e0e0e0; "
                  "  border: 1px solid #1f4287; "
                  "  border-radius: 3px; "
                  "  padding: 3px; "
                  "}"
                  "QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover { "
                  "  border-color: #00d4ff; "
                  "}"
                  "QPushButton { "
                  "  background-color: #1f4287; "
                  "  color: #ffffff; "
                  "  border: none; "
                  "  border-radius: 4px; "
                  "  padding: 8px 16px; "
                  "  font-weight: bold;"
                  "}"
                  "QPushButton:hover { "
                  "  background-color: #278ea5; "
                  "}"
                  "QPushButton:pressed { "
                  "  background-color: #00d4ff; "
                  "  color: #000000;"
                  "}"
                  "QCheckBox { color: #e0e0e0; }"
                  "QSlider::groove:horizontal { "
                  "  border: 1px solid #1f4287; "
                  "  height: 8px; "
                  "  background: #0f3460; "
                  "  border-radius: 4px; "
                  "}"
                  "QSlider::handle:horizontal { "
                  "  background: #00d4ff; "
                  "  width: 16px; "
                  "  margin: -4px 0; "
                  "  border-radius: 8px; "
                  "}");
}

MainWindow::~MainWindow()
{
    if (m_simulationTimer) {
        m_simulationTimer->stop();
    }
    delete ui;
}

void MainWindow::setupUI()
{
    m_phasePlot3D = new PhasePlot3D(this);
    ui->phasePlotLayout->addWidget(m_phasePlot3D);

    m_timePlot = new PlotWidget(this);
    m_timePlot->setPlotMode(PlotMode::TimeDomain);
    m_timePlot->setTitle("时域波形 / Time Domain");
    m_timePlot->setXLabel("时间 t");
    m_timePlot->setYLabel("幅值");
    ui->timePlotLayout->addWidget(m_timePlot);

    m_spectrumPlot = new PlotWidget(this);
    m_spectrumPlot->setPlotMode(PlotMode::Spectrum);
    m_spectrumPlot->setTitle("频谱 / Spectrum (Hann窗)");
    m_spectrumPlot->setXLabel("频率 (Hz)");
    m_spectrumPlot->setYLabel("幅值");
    ui->spectrumPlotLayout->addWidget(m_spectrumPlot);

    m_xyPlot = new PlotWidget(this);
    m_xyPlot->setPlotMode(PlotMode::XYMode);
    m_xyPlot->setTitle("X-Y 模式 / X-Y Mode");
    m_xyPlot->setXLabel("X");
    m_xyPlot->setYLabel("Y");
    ui->xyPlotLayout->addWidget(m_xyPlot);

    m_simulationTimer = new QTimer(this);
    m_simulationTimer->setInterval(16);

    m_fftAnalyzer.setWindowType(WindowType::Hann);
    m_fftAnalyzer.setZeroPadding(true, 8192);
    m_fftAnalyzer.setRemoveDC(true);
    m_fftAnalyzer.setLogScale(false);

    onSystemChanged(0);
    onXYModeChanged(0);
}

void MainWindow::setupConnections()
{
    connect(m_simulationTimer, &QTimer::timeout, this, &MainWindow::onSimulationStep);

    connect(ui->systemCombo, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &MainWindow::onSystemChanged);
    connect(ui->solverCombo, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &MainWindow::onSolverChanged);
    connect(ui->stepSizeSpin, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onStepSizeChanged);
    connect(ui->speedSlider, &QSlider::valueChanged,
            this, &MainWindow::onSpeedChanged);
    connect(ui->maxPointsSpin, QOverload<int>::of(&QSpinBox::valueChanged),
            this, &MainWindow::onMaxPointsChanged);

    connect(ui->sigmaSpin, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onLorenzSigmaChanged);
    connect(ui->rhoSpin, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onLorenzRhoChanged);
    connect(ui->betaSpin, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onLorenzBetaChanged);

    connect(ui->chuaAlphaSpin, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onChuaAlphaChanged);
    connect(ui->chuaBetaSpin, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onChuaBetaChanged);
    connect(ui->m0Spin, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onChuaM0Changed);
    connect(ui->m1Spin, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onChuaM1Changed);

    connect(ui->initXSpin, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onInitialXChanged);
    connect(ui->initYSpin, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onInitialYChanged);
    connect(ui->initZSpin, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onInitialZChanged);

    connect(ui->autoRotateCheck, &QCheckBox::toggled,
            this, &MainWindow::onAutoRotateToggled);
    connect(ui->showAxesCheck, &QCheckBox::toggled,
            this, &MainWindow::onShowAxesToggled);
    connect(ui->resetViewBtn, &QPushButton::clicked,
            this, &MainWindow::onResetView);

    connect(ui->xyModeCombo, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &MainWindow::onXYModeChanged);

    connect(ui->startBtn, &QPushButton::clicked,
            this, &MainWindow::onStartSimulation);
    connect(ui->stopBtn, &QPushButton::clicked,
            this, &MainWindow::onStopSimulation);
    connect(ui->resetBtn, &QPushButton::clicked,
            this, &MainWindow::onResetSimulation);
    connect(ui->lyapunovBtn, &QPushButton::clicked,
            this, &MainWindow::onCalculateLyapunov);
    connect(ui->exportBtn, &QPushButton::clicked,
            this, &MainWindow::onExportCSV);
}

void MainWindow::initializeSystem()
{
    m_currentState = m_system.getInitialState();
    m_currentTime = 0.0;
    m_stepSize = ui->stepSizeSpin->value();
    m_dataSkip = 1;
    m_sampleCounter = 0;

    m_timeData.clear();
    m_xData.clear();
    m_yData.clear();
    m_zData.clear();

    m_phasePlot3D->clearTrajectory();
    m_phasePlot3D->setMaxPoints(m_maxPoints);

    updateTimeDomainPlots();
    updateSpectrumPlot();
    updateXYPlot();
    updateStatusInfo();

    updateLyapunovDisplay(std::vector<double>());
}

void MainWindow::onSystemChanged(int index)
{
    SystemType type = (index == 0) ? SystemType::Lorenz : SystemType::Chua;
    m_system.setType(type);

    bool isLorenz = (type == SystemType::Lorenz);
    ui->lorenzGroup->setVisible(isLorenz);
    ui->chuaGroup->setVisible(!isLorenz);

    auto params = m_system.getDefaultParameters(type);
    auto initState = m_system.getDefaultInitialState(type);

    if (isLorenz) {
        ui->sigmaSpin->setValue(params.sigma);
        ui->rhoSpin->setValue(params.rho);
        ui->betaSpin->setValue(params.beta);
    } else {
        ui->chuaAlphaSpin->setValue(params.alpha);
        ui->chuaBetaSpin->setValue(params.beta);
        ui->m0Spin->setValue(params.m0);
        ui->m1Spin->setValue(params.m1);
    }

    ui->initXSpin->setValue(initState[0]);
    ui->initYSpin->setValue(initState[1]);
    ui->initZSpin->setValue(initState[2]);

    m_system.setInitialState(initState);
    m_solver = ODESolver(m_system.getODEFunction(), m_stepSize,
                         static_cast<SolverMethod>(ui->solverCombo->currentIndex()));

    onResetSimulation();
}

void MainWindow::onSolverChanged(int index)
{
    SolverMethod method = (index == 0) ? SolverMethod::RK4 : SolverMethod::AdaptiveRK45;
    m_solver.setMethod(method);
    m_solver.setStepSize(m_stepSize);
    m_lyapunovCalc = std::make_unique<LyapunovCalculator>(m_system, method);
    m_lyapunovCalc->setStepSize(m_stepSize);
}

void MainWindow::onStepSizeChanged(double value)
{
    m_stepSize = value;
    m_solver.setStepSize(value);
    m_lyapunovCalc->setStepSize(value);
}

void MainWindow::onMaxPointsChanged(int value)
{
    m_maxPoints = value;
    m_phasePlot3D->setMaxPoints(value);
}

void MainWindow::onSpeedChanged(int value)
{
    m_simulationSpeed = static_cast<double>(value);
    ui->speedValueLabel->setText(QString("%1x").arg(value));
    int interval = qMax(1, static_cast<int>(1000.0 / (60.0 * m_simulationSpeed / 10.0)));
    m_simulationTimer->setInterval(interval);
}

void MainWindow::onLorenzSigmaChanged(double value)
{
    SystemParameters params = m_system.getParameters();
    params.sigma = value;
    m_system.setParameters(params);
}

void MainWindow::onLorenzRhoChanged(double value)
{
    SystemParameters params = m_system.getParameters();
    params.rho = value;
    m_system.setParameters(params);
}

void MainWindow::onLorenzBetaChanged(double value)
{
    SystemParameters params = m_system.getParameters();
    params.beta = value;
    m_system.setParameters(params);
}

void MainWindow::onChuaAlphaChanged(double value)
{
    SystemParameters params = m_system.getParameters();
    params.alpha = value;
    m_system.setParameters(params);
}

void MainWindow::onChuaBetaChanged(double value)
{
    SystemParameters params = m_system.getParameters();
    params.beta = value;
    m_system.setParameters(params);
}

void MainWindow::onChuaM0Changed(double value)
{
    SystemParameters params = m_system.getParameters();
    params.m0 = value;
    m_system.setParameters(params);
}

void MainWindow::onChuaM1Changed(double value)
{
    SystemParameters params = m_system.getParameters();
    params.m1 = value;
    m_system.setParameters(params);
}

void MainWindow::onInitialXChanged(double value)
{
    State state = m_system.getInitialState();
    state[0] = value;
    m_system.setInitialState(state);
}

void MainWindow::onInitialYChanged(double value)
{
    State state = m_system.getInitialState();
    state[1] = value;
    m_system.setInitialState(state);
}

void MainWindow::onInitialZChanged(double value)
{
    State state = m_system.getInitialState();
    state[2] = value;
    m_system.setInitialState(state);
}

void MainWindow::onAutoRotateToggled(bool checked)
{
    m_phasePlot3D->setAutoRotate(checked);
}

void MainWindow::onShowAxesToggled(bool checked)
{
    m_phasePlot3D->setShowAxes(checked);
}

void MainWindow::onResetView()
{
    m_phasePlot3D->resetView();
}

void MainWindow::onXYModeChanged(int index)
{
    m_xyChannelX = 0;
    m_xyChannelY = 1;

    switch (index) {
    case 0:
        m_xyChannelX = 0; m_xyChannelY = 1;
        m_xyPlot->setXLabel("X");
        m_xyPlot->setYLabel("Y");
        break;
    case 1:
        m_xyChannelX = 0; m_xyChannelY = 2;
        m_xyPlot->setXLabel("X");
        m_xyPlot->setYLabel("Z");
        break;
    case 2:
        m_xyChannelX = 1; m_xyChannelY = 2;
        m_xyPlot->setXLabel("Y");
        m_xyPlot->setYLabel("Z");
        break;
    }
    updateXYPlot();
}

void MainWindow::onStartSimulation()
{
    if (m_timeData.empty()) {
        initializeSystem();
        runTransient(500);
    }
    m_isRunning = true;
    m_simulationTimer->start();
    ui->startBtn->setEnabled(false);
    ui->stopBtn->setEnabled(true);
}

void MainWindow::onStopSimulation()
{
    m_isRunning = false;
    m_simulationTimer->stop();
    ui->startBtn->setEnabled(true);
    ui->stopBtn->setEnabled(false);
    onUpdateFFT();
}

void MainWindow::onResetSimulation()
{
    m_simulationTimer->stop();
    m_isRunning = false;
    ui->startBtn->setEnabled(true);
    ui->stopBtn->setEnabled(false);
    initializeSystem();
}

void MainWindow::runTransient(int steps)
{
    double dt = m_stepSize;
    for (int i = 0; i < steps; ++i) {
        m_currentState = m_solver.step(m_currentState, m_currentTime, dt);
        m_currentTime += dt;
    }
}

void MainWindow::onSimulationStep()
{
    if (!m_isRunning) return;

    int stepsPerFrame = qMax(1, static_cast<int>(m_simulationSpeed));
    double dt = m_stepSize;

    for (int i = 0; i < stepsPerFrame; ++i) {
        m_currentState = m_solver.step(m_currentState, m_currentTime, dt);
        m_currentTime += dt;
        m_sampleCounter++;

        if (m_sampleCounter >= m_dataSkip) {
            collectDataPoint();
            m_sampleCounter = 0;
        }
    }

    m_phasePlot3D->appendPoint(m_currentState[0], m_currentState[1], m_currentState[2]);

    if (m_timeData.size() % 50 == 0) {
        updateTimeDomainPlots();
        updateXYPlot();
    }

    updateStatusInfo();
}

void MainWindow::collectDataPoint()
{
    if (static_cast<int>(m_timeData.size()) >= m_maxPoints) {
        m_timeData.erase(m_timeData.begin());
        m_xData.erase(m_xData.begin());
        m_yData.erase(m_yData.begin());
        m_zData.erase(m_zData.begin());
    }

    m_timeData.push_back(m_currentTime);
    m_xData.push_back(m_currentState[0]);
    m_yData.push_back(m_currentState[1]);
    m_zData.push_back(m_currentState[2]);
}

void MainWindow::updateTimeDomainPlots()
{
    if (m_xData.empty()) return;

    int displayPoints = qMin(5000, static_cast<int>(m_xData.size()));
    int start = m_xData.size() - displayPoints;

    std::vector<double> t(m_timeData.begin() + start, m_timeData.end());
    std::vector<double> x(m_xData.begin() + start, m_xData.end());
    std::vector<double> y(m_yData.begin() + start, m_yData.end());
    std::vector<double> z(m_zData.begin() + start, m_zData.end());

    m_timePlot->setData(t, x, 0);
    m_timePlot->setData(t, y, 1);
    m_timePlot->setData(t, z, 2);
}

void MainWindow::updateSpectrumPlot()
{
    if (m_spectrumMagn.empty() || m_spectrumFreqs.empty()) return;
    m_spectrumPlot->setData(m_spectrumFreqs, m_spectrumMagn, 0);
    m_spectrumPlot->clearSeries(1);
    m_spectrumPlot->clearSeries(2);
}

void MainWindow::updateXYPlot()
{
    if (m_xData.empty()) return;

    int displayPoints = qMin(10000, static_cast<int>(m_xData.size()));
    int start = m_xData.size() - displayPoints;

    std::vector<double> xData, yData;

    const std::vector<double>& sourceX = (m_xyChannelX == 0) ? m_xData :
                                         (m_xyChannelX == 1) ? m_yData : m_zData;
    const std::vector<double>& sourceY = (m_xyChannelY == 0) ? m_xData :
                                         (m_xyChannelY == 1) ? m_yData : m_zData;

    xData.assign(sourceX.begin() + start, sourceX.end());
    yData.assign(sourceY.begin() + start, sourceY.end());

    m_xyPlot->setXYData(xData, yData);
}

void MainWindow::updateLyapunovDisplay(const std::vector<double>& exponents)
{
    if (exponents.empty() || exponents.size() < 3) {
        ui->lyapunovLabel1->setText("λ₁: --");
        ui->lyapunovLabel2->setText("λ₂: --");
        ui->lyapunovLabel3->setText("λ₃: --");
        ui->sumLabel->setText("∑λ: --");
        return;
    }

    auto format = [](double v) {
        if (std::abs(v) < 0.01) return QString::number(v, 'e', 3);
        return QString::number(v, 'f', 4);
    };

    ui->lyapunovLabel1->setText(QString("λ₁: %1").arg(format(exponents[0])));
    ui->lyapunovLabel2->setText(QString("λ₂: %1").arg(format(exponents[1])));
    ui->lyapunovLabel3->setText(QString("λ₃: %1").arg(format(exponents[2])));

    double sum = exponents[0] + exponents[1] + exponents[2];
    ui->sumLabel->setText(QString("∑λ: %1").arg(format(sum)));
}

void MainWindow::updateStatusInfo()
{
    ui->timeLabel->setText(QString("时间 t: %1").arg(m_currentTime, 0, 'f', 3));
    ui->stateLabel->setText(QString("X: %1, Y: %2, Z: %3")
                           .arg(m_currentState[0], 0, 'f', 3)
                           .arg(m_currentState[1], 0, 'f', 3)
                           .arg(m_currentState[2], 0, 'f', 3));
    ui->pointsLabel->setText(QString("数据点数: %1").arg(m_xData.size()));
}

void MainWindow::onCalculateLyapunov()
{
    QProgressDialog progress("计算李雅普诺夫指数...", "取消", 0, 100, this);
    progress.setWindowModality(Qt::WindowModal);
    progress.setMinimumDuration(0);
    progress.show();

    QApplication::processEvents();

    m_lyapunovCalc->setTransientSteps(1000);
    m_lyapunovCalc->setOrthSteps(10);

    std::vector<double> exponents;
    const int totalSteps = 3000;

    for (int step = 0; step < totalSteps; step += 100) {
        if (progress.wasCanceled()) return;
        progress.setValue(static_cast<int>((step * 100.0) / totalSteps));
        QApplication::processEvents();
    }

    exponents = m_lyapunovCalc->computeSpectrum(totalSteps);
    progress.setValue(100);

    updateLyapunovDisplay(exponents);
}

void MainWindow::onUpdateFFT()
{
    if (m_xData.size() < 256) return;

    int fftSize = qMin(4096, static_cast<int>(m_xData.size()));
    int start = m_xData.size() - fftSize;

    std::vector<double> signal(m_xData.begin() + start, m_xData.end());
    double sampleRate = 1.0 / m_stepSize;

    m_spectrumMagn = m_fftAnalyzer.analyze(signal, sampleRate);
    m_spectrumFreqs = m_fftAnalyzer.getFrequencies();

    updateSpectrumPlot();
}

void MainWindow::onExportCSV()
{
    if (m_timeData.empty()) {
        QMessageBox::warning(this, "导出失败", "没有数据可导出！请先运行模拟。");
        return;
    }

    QString defaultName = QString("chaos_data_%1.csv")
        .arg(QDateTime::currentDateTime().toString("yyyyMMdd_hhmmss"));

    QString filename = QFileDialog::getSaveFileName(
        this, "导出CSV", defaultName,
        "CSV Files (*.csv);;All Files (*.*)");

    if (filename.isEmpty()) return;

    bool success = DataExporter::exportToCSV(filename, m_timeData, m_xData, m_yData, m_zData);

    if (success) {
        QMessageBox::information(this, "导出成功",
            QString("数据已成功导出到:\n%1\n共 %2 个数据点")
                .arg(filename).arg(m_timeData.size()));
    } else {
        QMessageBox::critical(this, "导出失败", "保存文件时发生错误！");
    }
}
