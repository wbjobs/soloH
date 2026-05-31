#include "real_time_plot.h"

#ifdef USE_QT_CHARTS

#include <QChartView>
#include <QScrollArea>
#include <QSplitter>
#include <QColor>
#include <QBrush>
#include <QPen>
#include <QResizeEvent>

static const int MAX_SPIKE_POINTS_PER_NEURON = 5000;
static const int MAX_VOLTAGE_POINTS = 10000;
static const int MAX_DISPLAY_NEURONS_SAFE = 200;

RealTimePlot::RealTimePlot(int max_display_neurons, QWidget *parent)
    : QMainWindow(parent),
      max_display_neurons_(std::min(max_display_neurons, MAX_DISPLAY_NEURONS_SAFE)),
      selected_neuron_(0),
      display_count_(std::min(max_display_neurons, MAX_DISPLAY_NEURONS_SAFE)),
      max_time_(100.0) {
    setupUI();
}

RealTimePlot::~RealTimePlot() {
}

void RealTimePlot::setupUI() {
    setWindowTitle("Izhikevich Network Simulation - Real-time Plot");
    resize(1200, 800);

    auto* central_widget = new QWidget(this);
    setCentralWidget(central_widget);

    auto* main_layout = new QVBoxLayout(central_widget);

    auto* control_layout = new QHBoxLayout();

    auto* neuron_group = new QGroupBox("Neuron Selection");
    auto* neuron_layout = new QHBoxLayout(neuron_group);

    neuron_layout->addWidget(new QLabel("Display Neuron:"));
    neuron_selector_ = new QComboBox();
    neuron_selector_->addItem("Neuron 0 (Excitatory)");
    neuron_layout->addWidget(neuron_selector_);

    neuron_layout->addWidget(new QLabel("Raster Count:"));
    display_count_spin_ = new QSpinBox();
    display_count_spin_->setRange(1, MAX_DISPLAY_NEURONS_SAFE);
    display_count_spin_->setValue(display_count_);
    neuron_layout->addWidget(display_count_spin_);

    info_label_ = new QLabel("Time: 0.0 ms");
    info_label_->setStyleSheet("font-weight: bold; color: #3498db;");
    neuron_layout->addWidget(info_label_);

    control_layout->addWidget(neuron_group);
    main_layout->addLayout(control_layout);

    raster_chart_ = new QtCharts::QChart();
    raster_chart_->setTitle("Spike Raster Plot");
    raster_chart_->setAnimationOptions(QtCharts::QChart::NoAnimation);
    raster_chart_->legend()->hide();

    raster_x_axis_ = new QtCharts::QValueAxis();
    raster_x_axis_->setTitleText("Time (ms)");
    raster_x_axis_->setRange(0, max_time_);
    raster_chart_->addAxis(raster_x_axis_, Qt::AlignBottom);

    raster_y_axis_ = new QtCharts::QValueAxis();
    raster_y_axis_->setTitleText("Neuron ID");
    raster_y_axis_->setRange(0, display_count_);
    raster_chart_->addAxis(raster_y_axis_, Qt::AlignLeft);

    raster_view_ = new QtCharts::QChartView(raster_chart_);
    raster_view_->setRenderHint(QPainter::Antialiasing);

    voltage_chart_ = new QtCharts::QChart();
    voltage_chart_->setTitle("Membrane Potential");
    voltage_chart_->setAnimationOptions(QtCharts::QChart::NoAnimation);

    voltage_x_axis_ = new QtCharts::QValueAxis();
    voltage_x_axis_->setTitleText("Time (ms)");
    voltage_x_axis_->setRange(0, max_time_);
    voltage_chart_->addAxis(voltage_x_axis_, Qt::AlignBottom);

    voltage_y_axis_ = new QtCharts::QValueAxis();
    voltage_y_axis_->setTitleText("Membrane Potential (mV)");
    voltage_y_axis_->setRange(-80, 40);
    voltage_chart_->addAxis(voltage_y_axis_, Qt::AlignLeft);

    voltage_series_ = new QtCharts::QLineSeries();
    voltage_series_->setName("V(t)");
    QPen voltage_pen(QColor(231, 76, 60));
    voltage_pen.setWidth(2);
    voltage_series_->setPen(voltage_pen);
    voltage_chart_->addSeries(voltage_series_);
    voltage_series_->attachAxis(voltage_x_axis_);
    voltage_series_->attachAxis(voltage_y_axis_);

    voltage_view_ = new QtCharts::QChartView(voltage_chart_);
    voltage_view_->setRenderHint(QPainter::Antialiasing);

    auto* splitter = new QSplitter(Qt::Vertical);
    splitter->addWidget(raster_view_);
    splitter->addWidget(voltage_view_);
    splitter->setSizes({400, 400});

    main_layout->addWidget(splitter);

    connect(neuron_selector_, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &RealTimePlot::onNeuronIndexChanged);
    connect(display_count_spin_, QOverload<int>::of(&QSpinBox::valueChanged),
            this, &RealTimePlot::onDisplayCountChanged);
}

void RealTimePlot::onNeuronIndexChanged(int index) {
    selected_neuron_ = index;
    voltage_series_->clear();
}

void RealTimePlot::onDisplayCountChanged(int count) {
    display_count_ = std::min(count, MAX_DISPLAY_NEURONS_SAFE);
    raster_y_axis_->setRange(0, display_count_);

    raster_chart_->removeAllSeries();
    for (auto* series : raster_series_) {
        delete series;
    }
    raster_series_.clear();
}

void RealTimePlot::updateData(const IzhikevichNetwork& network, double current_time) {
    info_label_->setText(QString("Time: %1 ms").arg(current_time, 0, 'f', 1));

    if (current_time > max_time_) {
        max_time_ = current_time + 50.0;
        raster_x_axis_->setMax(max_time_);
        voltage_x_axis_->setMax(max_time_);
    }

    updateRasterPlot(network);
    updateVoltagePlot(network);
}

void RealTimePlot::updateRasterPlot(const IzhikevichNetwork& network) {
    const auto& spike_times = network.getSpikeTimes();
    const auto& neurons = network.getNeurons();

    int effective_display = std::min(display_count_, static_cast<int>(spike_times.size()));
    effective_display = std::min(effective_display, MAX_DISPLAY_NEURONS_SAFE);

    for (int i = 0; i < effective_display; ++i) {
        if (i >= static_cast<int>(raster_series_.size())) {
            auto* series = new QtCharts::QScatterSeries();
            series->setMarkerSize(3.0);
            series->setUseOpenGL(true);

            if (neurons[i].isExcitatory()) {
                series->setColor(QColor(52, 152, 219));
            } else {
                series->setColor(QColor(231, 76, 60));
            }

            raster_series_.push_back(series);
            raster_chart_->addSeries(series);
            series->attachAxis(raster_x_axis_);
            series->attachAxis(raster_y_axis_);
        }

        const auto& times = spike_times[i];

        if (static_cast<int>(raster_series_[i]->count()) != static_cast<int>(times.size())) {
            raster_series_[i]->removePoints(0, raster_series_[i]->count());

            int points_to_add = static_cast<int>(times.size());
            if (points_to_add > MAX_SPIKE_POINTS_PER_NEURON) {
                int skip = points_to_add / MAX_SPIKE_POINTS_PER_NEURON;
                for (int j = 0; j < points_to_add; j += skip) {
                    raster_series_[i]->append(times[j], i);
                }
            } else {
                for (double t : times) {
                    raster_series_[i]->append(t, i);
                }
            }
        }
    }
}

void RealTimePlot::updateVoltagePlot(const IzhikevichNetwork& network) {
    const auto& voltage_traces = network.getVoltageTraces();
    const auto& time_array = network.getTimeArray();

    if (selected_neuron_ >= static_cast<int>(voltage_traces.size())) {
        return;
    }

    const auto& trace = voltage_traces[selected_neuron_];

    int current_count = voltage_series_->count();
    int target_count = static_cast<int>(trace.size());

    if (target_count <= MAX_VOLTAGE_POINTS) {
        if (current_count != target_count) {
            voltage_series_->removePoints(0, current_count);

            for (int t = 0; t < target_count; ++t) {
                voltage_series_->append(time_array[t], trace[t]);
            }
        }
    } else {
        voltage_series_->removePoints(0, current_count);

        int stride = target_count / MAX_VOLTAGE_POINTS;
        if (stride < 1) stride = 1;

        for (int t = 0; t < target_count; t += stride) {
            if (t < static_cast<int>(time_array.size()) && t < static_cast<int>(trace.size())) {
                voltage_series_->append(time_array[t], trace[t]);
            }
        }
    }
}

#endif
