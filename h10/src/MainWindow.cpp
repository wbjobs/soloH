#include "MainWindow.h"
#include "GLWidget.h"
#include "VideoRecorder.h"
#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGridLayout>
#include <QLabel>
#include <QDoubleSpinBox>
#include <QSpinBox>
#include <QPushButton>
#include <QComboBox>
#include <QGroupBox>
#include <QCheckBox>
#include <QTextEdit>
#include <QStatusBar>
#include <QMessageBox>
#include <QFileDialog>
#include <QElapsedTimer>
#include <QDateTime>
#include <sstream>
#include <iomanip>

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent),
      m_solver(nullptr),
      m_recorder(std::make_unique<VideoRecorder>()),
      m_glWidget(nullptr),
      m_timer(nullptr),
      m_isRunning(false),
      m_useFFT(false),
      m_displayChannel(0),
      m_currentStep(0),
      m_stepsPerFrame(10),
      m_statsInterval(100),
      m_autoStats(false),
      m_lastTime(0),
      m_frameCount(0),
      m_fps(0.0f) {
    
    setWindowTitle("Gray-Scott Reaction-Diffusion Simulator");
    resize(1400, 900);

    try {
        m_solver = std::make_unique<GrayScottSolver>(2048, 2048);
        m_solver->initialize();
    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Error", 
            QString("Failed to initialize CUDA solver: %1").arg(e.what()));
    }

    createUI();
    
    m_timer = new QTimer(this);
    connect(m_timer, &QTimer::timeout, this, &MainWindow::updateSimulation);
    m_timer->setInterval(16);

    m_glWidget->updateData(m_solver->getV(), 2048, 2048);
    updateStatusBar();
}

MainWindow::~MainWindow() {
    if (m_timer) {
        m_timer->stop();
    }
    if (m_recorder && m_recorder->isRecording()) {
        m_recorder->stop();
    }
}

void MainWindow::createUI() {
    QWidget* centralWidget = new QWidget(this);
    QHBoxLayout* mainLayout = new QHBoxLayout(centralWidget);

    m_glWidget = new GLWidget(this);
    mainLayout->addWidget(m_glWidget, 3);

    QWidget* controlPanel = new QWidget(this);
    QVBoxLayout* controlLayout = new QVBoxLayout(controlPanel);
    controlPanel->setFixedWidth(360);

    QGroupBox* paramGroup = new QGroupBox("Reaction Parameters", controlPanel);
    QGridLayout* paramLayout = new QGridLayout(paramGroup);

    paramLayout->addWidget(new QLabel("F (feed rate):"), 0, 0);
    m_spinF = new QDoubleSpinBox(paramGroup);
    m_spinF->setRange(0.001, 0.1);
    m_spinF->setSingleStep(0.001);
    m_spinF->setDecimals(4);
    m_spinF->setValue(0.035);
    paramLayout->addWidget(m_spinF, 0, 1);

    paramLayout->addWidget(new QLabel("k (kill rate):"), 1, 0);
    m_spinK = new QDoubleSpinBox(paramGroup);
    m_spinK->setRange(0.01, 0.1);
    m_spinK->setSingleStep(0.001);
    m_spinK->setDecimals(4);
    m_spinK->setValue(0.065);
    paramLayout->addWidget(m_spinK, 1, 1);

    paramLayout->addWidget(new QLabel("Du:"), 2, 0);
    m_spinDu = new QDoubleSpinBox(paramGroup);
    m_spinDu->setRange(0.01, 0.5);
    m_spinDu->setSingleStep(0.01);
    m_spinDu->setDecimals(3);
    m_spinDu->setValue(0.16);
    paramLayout->addWidget(m_spinDu, 2, 1);

    paramLayout->addWidget(new QLabel("Dv:"), 3, 0);
    m_spinDv = new QDoubleSpinBox(paramGroup);
    m_spinDv->setRange(0.01, 0.5);
    m_spinDv->setSingleStep(0.01);
    m_spinDv->setDecimals(3);
    m_spinDv->setValue(0.08);
    paramLayout->addWidget(m_spinDv, 3, 1);

    paramLayout->addWidget(new QLabel("Steps/Frame:"), 4, 0);
    m_spinStepsPerFrame = new QSpinBox(paramGroup);
    m_spinStepsPerFrame->setRange(1, 100);
    m_spinStepsPerFrame->setValue(10);
    paramLayout->addWidget(m_spinStepsPerFrame, 4, 1);

    controlLayout->addWidget(paramGroup);

    QGroupBox* solverGroup = new QGroupBox("Solver Settings", controlPanel);
    QVBoxLayout* solverLayout = new QVBoxLayout(solverGroup);

    solverLayout->addWidget(new QLabel("Solver Method:"));
    m_comboSolverMethod = new QComboBox(solverGroup);
    m_comboSolverMethod->addItem("Finite Difference");
    m_comboSolverMethod->addItem("cuFFT Accelerated");
    solverLayout->addWidget(m_comboSolverMethod);

    solverLayout->addWidget(new QLabel("Initial Condition:"));
    m_comboInitialCondition = new QComboBox(solverGroup);
    m_comboInitialCondition->addItem("Circular Seed");
    m_comboInitialCondition->addItem("Random Noise");
    m_comboInitialCondition->addItem("Multiple Seeds");
    solverLayout->addWidget(m_comboInitialCondition);

    solverLayout->addWidget(new QLabel("Display Channel:"));
    m_comboDisplayChannel = new QComboBox(solverGroup);
    m_comboDisplayChannel->addItem("V (activator)");
    m_comboDisplayChannel->addItem("U (substrate)");
    solverLayout->addWidget(m_comboDisplayChannel);

    solverLayout->addWidget(new QLabel("Colormap:"));
    m_comboColormap = new QComboBox(solverGroup);
    m_comboColormap->addItem("Thermal");
    m_comboColormap->addItem("Gradient");
    m_comboColormap->addItem("Rainbow");
    m_comboColormap->addItem("Grayscale");
    m_comboColormap->addItem("Viridis");
    solverLayout->addWidget(m_comboColormap);

    controlLayout->addWidget(solverGroup);

    QGroupBox* controlGroup = new QGroupBox("Controls", controlPanel);
    QGridLayout* controlBtnsLayout = new QGridLayout(controlGroup);

    m_btnStart = new QPushButton("Start", controlGroup);
    m_btnPause = new QPushButton("Pause", controlGroup);
    m_btnReset = new QPushButton("Reset", controlGroup);
    m_btnStep = new QPushButton("Single Step", controlGroup);
    m_btnRecord = new QPushButton("Record", controlGroup);

    m_btnPause->setEnabled(false);

    controlBtnsLayout->addWidget(m_btnStart, 0, 0);
    controlBtnsLayout->addWidget(m_btnPause, 0, 1);
    controlBtnsLayout->addWidget(m_btnReset, 1, 0);
    controlBtnsLayout->addWidget(m_btnStep, 1, 1);
    controlBtnsLayout->addWidget(m_btnRecord, 2, 0, 1, 2);

    controlLayout->addWidget(controlGroup);

    QGroupBox* statsGroup = new QGroupBox("Statistics", controlPanel);
    QVBoxLayout* statsLayout = new QVBoxLayout(statsGroup);

    QHBoxLayout* statsBtnLayout = new QHBoxLayout();
    m_checkAutoStats = new QCheckBox("Auto Stats", statsGroup);
    m_spinStatsInterval = new QSpinBox(statsGroup);
    m_spinStatsInterval->setRange(10, 1000);
    m_spinStatsInterval->setValue(100);
    m_spinStatsInterval->setSuffix(" steps");
    m_btnComputeStats = new QPushButton("Compute Now", statsGroup);

    statsBtnLayout->addWidget(m_checkAutoStats);
    statsBtnLayout->addWidget(m_spinStatsInterval);
    statsLayout->addLayout(statsBtnLayout);
    statsLayout->addWidget(m_btnComputeStats);

    m_statsDisplay = new QTextEdit(statsGroup);
    m_statsDisplay->setReadOnly(true);
    m_statsDisplay->setMinimumHeight(200);
    statsLayout->addWidget(m_statsDisplay);

    controlLayout->addWidget(statsGroup);
    controlLayout->addStretch();

    mainLayout->addWidget(controlPanel, 1);
    setCentralWidget(centralWidget);

    m_labelFps = new QLabel("FPS: 0.0", this);
    m_labelStep = new QLabel("Step: 0", this);
    m_labelRecording = new QLabel("", this);

    statusBar()->addWidget(m_labelFps);
    statusBar()->addWidget(m_labelStep);
    statusBar()->addPermanentWidget(m_labelRecording);

    connect(m_spinF, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onParameterChanged);
    connect(m_spinK, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onParameterChanged);
    connect(m_spinDu, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onParameterChanged);
    connect(m_spinDv, QOverload<double>::of(&QDoubleSpinBox::valueChanged),
            this, &MainWindow::onParameterChanged);
    connect(m_spinStepsPerFrame, QOverload<int>::of(&QSpinBox::valueChanged),
            this, [this](int val) { m_stepsPerFrame = val; });

    connect(m_comboSolverMethod, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &MainWindow::onSolverMethodChanged);
    connect(m_comboInitialCondition, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &MainWindow::onInitialConditionChanged);
    connect(m_comboDisplayChannel, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &MainWindow::onDisplayChannelChanged);
    connect(m_comboColormap, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &MainWindow::onColormapChanged);

    connect(m_btnStart, &QPushButton::clicked, this, &MainWindow::onStart);
    connect(m_btnPause, &QPushButton::clicked, this, &MainWindow::onPause);
    connect(m_btnReset, &QPushButton::clicked, this, &MainWindow::onReset);
    connect(m_btnStep, &QPushButton::clicked, this, &MainWindow::onStep);
    connect(m_btnRecord, &QPushButton::clicked, this, &MainWindow::onRecord);
    connect(m_btnComputeStats, &QPushButton::clicked, this, &MainWindow::onComputeStats);
    connect(m_checkAutoStats, &QCheckBox::stateChanged,
            this, &MainWindow::onAutoStatsChanged);
}

void MainWindow::applyParameters() {
    if (m_solver) {
        m_solver->setParameters(
            static_cast<float>(m_spinF->value()),
            static_cast<float>(m_spinK->value()),
            static_cast<float>(m_spinDu->value()),
            static_cast<float>(m_spinDv->value())
        );
    }
}

void MainWindow::onParameterChanged() {
    applyParameters();
}

void MainWindow::onSolverMethodChanged(int index) {
    m_useFFT = (index == 1);
}

void MainWindow::onInitialConditionChanged(int index) {
    if (m_solver) {
        GrayScottSolver::InitialCondition cond;
        switch (index) {
            case 0: cond = GrayScottSolver::CIRCULAR_SEED; break;
            case 1: cond = GrayScottSolver::RANDOM_NOISE; break;
            case 2: cond = GrayScottSolver::MULTIPLE_SEEDS; break;
            default: cond = GrayScottSolver::CIRCULAR_SEED;
        }
        m_solver->setInitialCondition(cond);
    }
}

void MainWindow::onDisplayChannelChanged(int index) {
    m_displayChannel = index;
    if (m_solver) {
        if (m_displayChannel == 0) {
            m_glWidget->updateData(m_solver->getV(), 2048, 2048);
        } else {
            m_glWidget->updateData(m_solver->getU(), 2048, 2048);
        }
    }
}

void MainWindow::onColormapChanged(int index) {
    m_glWidget->setColormap(index);
}

void MainWindow::onStart() {
    m_isRunning = true;
    m_btnStart->setEnabled(false);
    m_btnPause->setEnabled(true);
    m_timer->start();
    m_lastTime = QDateTime::currentMSecsSinceEpoch();
    m_frameCount = 0;
}

void MainWindow::onPause() {
    m_isRunning = false;
    m_timer->stop();
    m_btnStart->setEnabled(true);
    m_btnPause->setEnabled(false);
}

void MainWindow::onReset() {
    m_isRunning = false;
    m_timer->stop();
    m_currentStep = 0;
    m_btnStart->setEnabled(true);
    m_btnPause->setEnabled(false);

    if (m_solver) {
        applyParameters();
        m_solver->initialize();
        if (m_displayChannel == 0) {
            m_glWidget->updateData(m_solver->getV(), 2048, 2048);
        } else {
            m_glWidget->updateData(m_solver->getU(), 2048, 2048);
        }
    }
    m_statsDisplay->clear();
    updateStatusBar();
}

void MainWindow::onStep() {
    if (m_solver) {
        if (m_useFFT) {
            m_solver->stepFFT(m_stepsPerFrame);
        } else {
            m_solver->step(m_stepsPerFrame);
        }
        m_solver->copyToHost();
        m_currentStep += m_stepsPerFrame;

        if (m_displayChannel == 0) {
            m_glWidget->updateData(m_solver->getV(), 2048, 2048);
        } else {
            m_glWidget->updateData(m_solver->getU(), 2048, 2048);
        }

        if (m_recorder && m_recorder->isRecording()) {
            m_recorder->addFrame(m_solver->getV(), 2048, 2048);
        }

        if (m_autoStats && (m_currentStep % m_statsInterval == 0)) {
            onComputeStats();
        }
    }
    updateStatusBar();
}

void MainWindow::onRecord() {
    if (!m_recorder) return;

    if (m_recorder->isRecording()) {
        m_recorder->stop();
        m_btnRecord->setText("Record");
        m_labelRecording->setText("");
        QMessageBox::information(this, "Recording Complete",
            QString("Saved %1 frames").arg(m_recorder->getFrameCount()));
    } else {
        QString filename = QFileDialog::getSaveFileName(
            this, "Save Video",
            QString("grayscott_%1.avi").arg(QDateTime::currentDateTime().toString("yyyyMMdd_hhmmss")),
            "Video Files (*.avi *.mp4)");
        
        if (!filename.isEmpty()) {
            if (m_recorder->start(filename.toStdString(), 1024, 1024, 30.0)) {
                m_btnRecord->setText("Stop Recording");
                m_labelRecording->setText("● REC");
            } else {
                QMessageBox::warning(this, "Error", "Failed to start video recording");
            }
        }
    }
}

void MainWindow::onComputeStats() {
    if (!m_solver) return;

    const auto& dataV = m_solver->getV();
    
    auto clusterStats = Statistics::computeClusterSizeDistribution(dataV, 2048, 2048, 0.3f);
    auto fractal = Statistics::computeFractalDimension(dataV, 2048, 2048, 0.3f);
    float avgV = Statistics::computeAverageConcentration(dataV);
    float varV = Statistics::computeVariance(dataV);
    auto minmax = Statistics::computeMinMax(dataV);

    std::ostringstream oss;
    oss << "=== Step " << m_currentStep << " ===\n\n";
    oss << "Parameters:\n";
    oss << "  F = " << std::fixed << std::setprecision(4) << m_solver->getF() << "\n";
    oss << "  k = " << std::fixed << std::setprecision(4) << m_solver->getK() << "\n";
    oss << "  Du = " << std::fixed << std::setprecision(3) << m_solver->getDu() << "\n";
    oss << "  Dv = " << std::fixed << std::setprecision(3) << m_solver->getDv() << "\n\n";
    
    oss << "Concentration (V):\n";
    oss << "  Average: " << std::fixed << std::setprecision(4) << avgV << "\n";
    oss << "  Variance: " << std::fixed << std::setprecision(6) << varV << "\n";
    oss << "  Min/Max: [" << std::fixed << std::setprecision(4) 
        << minmax.first << ", " << minmax.second << "]\n\n";
    
    oss << "Cluster Statistics:\n";
    oss << "  Number of clusters: " << clusterStats.numClusters << "\n";
    oss << "  Max cluster size: " << clusterStats.maxClusterSize << "\n";
    oss << "  Average cluster size: " << std::fixed << std::setprecision(1) 
        << clusterStats.avgClusterSize << "\n\n";
    
    oss << "Fractal Dimension:\n";
    oss << "  Box-counting dimension: " << std::fixed << std::setprecision(4) 
        << fractal.dimension << "\n";
    oss << "  Correlation coefficient: " << std::fixed << std::setprecision(4) 
        << fractal.correlation << "\n";
    oss << "  R-squared: " << std::fixed << std::setprecision(4) 
        << fractal.rSquared << "\n";
    oss << "  Reliable: " << (fractal.isReliable ? "Yes" : "No") << "\n\n";

    if (!clusterStats.sizeDistribution.empty()) {
        oss << "Cluster Size Distribution (top 10):\n";
        int count = 0;
        for (auto it = clusterStats.sizeDistribution.rbegin(); 
             it != clusterStats.sizeDistribution.rend() && count < 10; ++it, ++count) {
            oss << "  Size " << it->first << ": " << it->second << " clusters\n";
        }
    }

    m_statsDisplay->append(QString::fromStdString(oss.str()));
}

void MainWindow::onAutoStatsChanged(int state) {
    m_autoStats = (state == Qt::Checked);
    m_statsInterval = m_spinStatsInterval->value();
}

void MainWindow::updateSimulation() {
    if (!m_isRunning || !m_solver) return;

    onStep();

    m_frameCount++;
    qint64 currentTime = QDateTime::currentMSecsSinceEpoch();
    if (currentTime - m_lastTime >= 1000) {
        m_fps = static_cast<float>(m_frameCount * 1000.0) / (currentTime - m_lastTime);
        m_frameCount = 0;
        m_lastTime = currentTime;
        updateStatusBar();
    }
}

void MainWindow::updateStatusBar() {
    m_labelFps->setText(QString("FPS: %1").arg(m_fps, 0, 'f', 1));
    m_labelStep->setText(QString("Step: %1").arg(m_currentStep));
}
