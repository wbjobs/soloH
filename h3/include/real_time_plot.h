#ifndef REAL_TIME_PLOT_H
#define REAL_TIME_PLOT_H

#ifdef USE_QT_CHARTS

#include <QMainWindow>
#include <QtCharts/QChart>
#include <QtCharts/QLineSeries>
#include <QtCharts/QScatterSeries>
#include <QtCharts/QValueAxis>
#include <QTimer>
#include <QComboBox>
#include <QSpinBox>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QLabel>
#include "izhikevich_neuron.h"

class RealTimePlot : public QMainWindow {
    Q_OBJECT

public:
    explicit RealTimePlot(int max_display_neurons = 10, QWidget *parent = nullptr);
    ~RealTimePlot();

    void updateData(const IzhikevichNetwork& network, double current_time);
    void setMaxDisplayNeurons(int count) { max_display_neurons_ = count; }

private slots:
    void onNeuronIndexChanged(int index);
    void onDisplayCountChanged(int count);

private:
    void setupUI();
    void updateRasterPlot(const IzhikevichNetwork& network);
    void updateVoltagePlot(const IzhikevichNetwork& network);

    int max_display_neurons_;
    int selected_neuron_;
    int display_count_;
    double max_time_;

    QtCharts::QChart* raster_chart_;
    QtCharts::QChart* voltage_chart_;
    QtCharts::QChartView* raster_view_;
    QtCharts::QChartView* voltage_view_;

    QtCharts::QValueAxis* raster_x_axis_;
    QtCharts::QValueAxis* raster_y_axis_;
    QtCharts::QValueAxis* voltage_x_axis_;
    QtCharts::QValueAxis* voltage_y_axis_;

    std::vector<QtCharts::QScatterSeries*> raster_series_;
    QtCharts::QLineSeries* voltage_series_;

    QComboBox* neuron_selector_;
    QSpinBox* display_count_spin_;
    QLabel* info_label_;
};

#endif

#endif
