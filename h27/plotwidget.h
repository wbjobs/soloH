#ifndef PLOTWIDGET_H
#define PLOTWIDGET_H

#include <QWidget>
#include <QPainter>
#include <QPen>
#include <vector>
#include <QPointF>
#include <QRectF>

enum class PlotMode {
    TimeDomain,
    Spectrum,
    XYMode
};

class PlotWidget : public QWidget
{
    Q_OBJECT
public:
    explicit PlotWidget(QWidget *parent = nullptr);

    void setData(const std::vector<double>& x, const std::vector<double>& y, int seriesIndex = 0);
    void setData(const std::vector<double>& y, int seriesIndex = 0);
    void setXYData(const std::vector<double>& x, const std::vector<double>& y);

    void addSeries(const QColor& color);
    void clearData();
    void clearSeries(int seriesIndex);

    void setPlotMode(PlotMode mode);
    PlotMode plotMode() const;

    void setXLabel(const QString& label);
    void setYLabel(const QString& label);
    void setTitle(const QString& title);

    void setAutoScale(bool enable);
    void setYRange(double min, double max);
    void setXRange(double min, double max);

    void setShowGrid(bool show);
    void setShowLegend(bool show);

    void setLineWidth(int width);

    QString formatValue(double value, int precision = 4) const;

protected:
    void paintEvent(QPaintEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void leaveEvent(QEvent *event) override;

private:
    void drawBackground(QPainter& painter);
    void drawGrid(QPainter& painter);
    void drawData(QPainter& painter);
    void drawAxes(QPainter& painter);
    void drawLabels(QPainter& painter);

    void computeRanges();
    QPointF mapToScreen(double x, double y) const;
    void mapFromScreen(const QPointF& pos, double& x, double& y) const;

    struct SeriesData {
        std::vector<double> x;
        std::vector<double> y;
        QColor color;
        bool visible;
    };

    std::vector<SeriesData> m_series;
    std::vector<double> m_xyX;
    std::vector<double> m_xyY;

    PlotMode m_mode;
    QString m_xLabel;
    QString m_yLabel;
    QString m_title;

    bool m_autoScaleX;
    bool m_autoScaleY;
    double m_xMin, m_xMax;
    double m_yMin, m_yMax;

    bool m_showGrid;
    bool m_showLegend;
    int m_lineWidth;

    QRectF m_plotRect;
    QPoint m_mousePos;
    bool m_mouseInWidget;

    int m_marginLeft;
    int m_marginRight;
    int m_marginTop;
    int m_marginBottom;
};

#endif
