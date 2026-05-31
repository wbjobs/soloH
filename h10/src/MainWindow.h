#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QTimer>
#include <memory>
#include "GrayScottSolver.h"
#include "Statistics.h"

class GLWidget;
class QLabel;
class QSlider;
class QDoubleSpinBox;
class QPushButton;
class QComboBox;
class QGroupBox;
class QCheckBox;
class QTextEdit;
class VideoRecorder;

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget* parent = nullptr);
    ~MainWindow() override;

private slots:
    void onStart();
    void onPause();
    void onReset();
    void onStep();
    void onRecord();
    void onParameterChanged();
    void onSolverMethodChanged(int index);
    void onInitialConditionChanged(int index);
    void onDisplayChannelChanged(int index);
    void onColormapChanged(int index);
    void onComputeStats();
    void onAutoStatsChanged(int state);
    void updateSimulation();

private:
    void createUI();
    void updateStatusBar();
    void updateStatsDisplay();
    void applyParameters();

    std::unique_ptr<GrayScottSolver> m_solver;
    std::unique_ptr<VideoRecorder> m_recorder;
    GLWidget* m_glWidget;
    QTimer* m_timer;

    QDoubleSpinBox* m_spinF;
    QDoubleSpinBox* m_spinK;
    QDoubleSpinBox* m_spinDu;
    QDoubleSpinBox* m_spinDv;
    QSpinBox* m_spinStepsPerFrame;
    QSpinBox* m_spinStatsInterval;

    QComboBox* m_comboSolverMethod;
    QComboBox* m_comboInitialCondition;
    QComboBox* m_comboDisplayChannel;
    QComboBox* m_comboColormap;

    QPushButton* m_btnStart;
    QPushButton* m_btnPause;
    QPushButton* m_btnReset;
    QPushButton* m_btnStep;
    QPushButton* m_btnRecord;
    QPushButton* m_btnComputeStats;

    QCheckBox* m_checkAutoStats;
    QCheckBox* m_checkShowStats;

    QLabel* m_labelFps;
    QLabel* m_labelStep;
    QLabel* m_labelRecording;

    QTextEdit* m_statsDisplay;

    bool m_isRunning;
    bool m_useFFT;
    int m_displayChannel;
    int m_currentStep;
    int m_stepsPerFrame;
    int m_statsInterval;
    bool m_autoStats;
    qint64 m_lastTime;
    int m_frameCount;
    float m_fps;
};

#endif
