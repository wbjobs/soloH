#include "plotwidget.h"
#include <QPaintEvent>
#include <QMouseEvent>
#include <QFontMetrics>
#include <QLinearGradient>
#include <cmath>
#include <algorithm>

PlotWidget::PlotWidget(QWidget *parent)
    : QWidget(parent)
    , m_mode(PlotMode::TimeDomain)
    , m_xLabel("X")
    , m_yLabel("Y")
    , m_title("")
    , m_autoScaleX(true)
    , m_autoScaleY(true)
    , m_xMin(0), m_xMax(1)
    , m_yMin(-1), m_yMax(1)
    , m_showGrid(true)
    , m_showLegend(false)
    , m_lineWidth(2)
    , m_mouseInWidget(false)
    , m_marginLeft(60)
    , m_marginRight(20)
    , m_marginTop(40)
    , m_marginBottom(50)
{
    setMinimumHeight(150);
    setMouseTracking(true);

    SeriesData s1;
    s1.color = QColor(255, 100, 100);
    s1.visible = true;
    m_series.push_back(s1);

    SeriesData s2;
    s2.color = QColor(100, 255, 100);
    s2.visible = true;
    m_series.push_back(s2);

    SeriesData s3;
    s3.color = QColor(100, 150, 255);
    s3.visible = true;
    m_series.push_back(s3);
}

void PlotWidget::addSeries(const QColor& color)
{
    SeriesData s;
    s.color = color;
    s.visible = true;
    m_series.push_back(s);
    update();
}

void PlotWidget::setPlotMode(PlotMode mode)
{
    m_mode = mode;
    update();
}

PlotMode PlotWidget::plotMode() const
{
    return m_mode;
}

void PlotWidget::setXLabel(const QString& label)
{
    m_xLabel = label;
    update();
}

void PlotWidget::setYLabel(const QString& label)
{
    m_yLabel = label;
    update();
}

void PlotWidget::setTitle(const QString& title)
{
    m_title = title;
    update();
}

void PlotWidget::setAutoScale(bool enable)
{
    m_autoScaleX = enable;
    m_autoScaleY = enable;
    update();
}

void PlotWidget::setYRange(double min, double max)
{
    m_yMin = min;
    m_yMax = max;
    m_autoScaleY = false;
    update();
}

void PlotWidget::setXRange(double min, double max)
{
    m_xMin = min;
    m_xMax = max;
    m_autoScaleX = false;
    update();
}

void PlotWidget::setShowGrid(bool show)
{
    m_showGrid = show;
    update();
}

void PlotWidget::setShowLegend(bool show)
{
    m_showLegend = show;
    update();
}

void PlotWidget::setLineWidth(int width)
{
    m_lineWidth = width;
    update();
}

void PlotWidget::setData(const std::vector<double>& x, const std::vector<double>& y, int seriesIndex)
{
    if (seriesIndex >= static_cast<int>(m_series.size())) return;
    m_series[seriesIndex].x = x;
    m_series[seriesIndex].y = y;
    computeRanges();
    update();
}

void PlotWidget::setData(const std::vector<double>& y, int seriesIndex)
{
    if (seriesIndex >= static_cast<int>(m_series.size())) return;
    m_series[seriesIndex].x.clear();
    for (size_t i = 0; i < y.size(); ++i) {
        m_series[seriesIndex].x.push_back(static_cast<double>(i));
    }
    m_series[seriesIndex].y = y;
    computeRanges();
    update();
}

void PlotWidget::setXYData(const std::vector<double>& x, const std::vector<double>& y)
{
    m_xyX = x;
    m_xyY = y;

    if (m_autoScaleX || m_autoScaleY) {
        double xMin = x.front(), xMax = x.front();
        double yMin = y.front(), yMax = y.front();
        for (size_t i = 1; i < x.size(); ++i) {
            xMin = std::min(xMin, x[i]);
            xMax = std::max(xMax, x[i]);
            yMin = std::min(yMin, y[i]);
            yMax = std::max(yMax, y[i]);
        }
        if (m_autoScaleX) {
            m_xMin = xMin;
            m_xMax = xMax;
        }
        if (m_autoScaleY) {
            m_yMin = yMin;
            m_yMax = yMax;
        }
    }
    update();
}

void PlotWidget::clearData()
{
    for (auto& s : m_series) {
        s.x.clear();
        s.y.clear();
    }
    m_xyX.clear();
    m_xyY.clear();
    update();
}

void PlotWidget::clearSeries(int seriesIndex)
{
    if (seriesIndex >= static_cast<int>(m_series.size())) return;
    m_series[seriesIndex].x.clear();
    m_series[seriesIndex].y.clear();
    update();
}

void PlotWidget::computeRanges()
{
    if (!m_autoScaleX && !m_autoScaleY) return;

    bool hasData = false;
    double xMin = 0, xMax = 1;
    double yMin = 0, yMax = 1;

    for (const auto& s : m_series) {
        if (s.y.empty()) continue;
        hasData = true;

        double localXMin = s.x.empty() ? 0 : *std::min_element(s.x.begin(), s.x.end());
        double localXMax = s.x.empty() ? s.y.size() : *std::max_element(s.x.begin(), s.x.end());
        double localYMin = *std::min_element(s.y.begin(), s.y.end());
        double localYMax = *std::max_element(s.y.begin(), s.y.end());

        if (!hasData) {
            xMin = localXMin;
            xMax = localXMax;
            yMin = localYMin;
            yMax = localYMax;
        } else {
            xMin = std::min(xMin, localXMin);
            xMax = std::max(xMax, localXMax);
            yMin = std::min(yMin, localYMin);
            yMax = std::max(yMax, localYMax);
        }
    }

    if (!hasData) {
        xMin = 0; xMax = 1;
        yMin = -1; yMax = 1;
    } else {
        double yRange = yMax - yMin;
        if (yRange < 1e-10) yRange = 1.0;
        double xRange = xMax - xMin;
        if (xRange < 1e-10) xRange = 1.0;

        yMin -= yRange * 0.1;
        yMax += yRange * 0.1;
        xMax += xRange * 0.02;
    }

    if (m_autoScaleX) {
        m_xMin = xMin;
        m_xMax = xMax;
    }
    if (m_autoScaleY) {
        m_yMin = yMin;
        m_yMax = yMax;
    }
}

QPointF PlotWidget::mapToScreen(double x, double y) const
{
    double xNorm = (x - m_xMin) / (m_xMax - m_xMin);
    double yNorm = (m_yMax - y) / (m_yMax - m_yMin);

    double sx = m_plotRect.left() + xNorm * m_plotRect.width();
    double sy = m_plotRect.top() + yNorm * m_plotRect.height();

    return QPointF(sx, sy);
}

void PlotWidget::mapFromScreen(const QPointF& pos, double& x, double& y) const
{
    double xNorm = (pos.x() - m_plotRect.left()) / m_plotRect.width();
    double yNorm = (m_plotRect.bottom() - pos.y()) / m_plotRect.height();

    x = m_xMin + xNorm * (m_xMax - m_xMin);
    y = m_yMin + yNorm * (m_yMax - m_yMin);
}

QString PlotWidget::formatValue(double value, int precision) const
{
    if (std::abs(value) < 1e-10) {
        return QString("0");
    }
    if (std::abs(value) >= 1e4 || std::abs(value) < 1e-3) {
        return QString::number(value, 'e', precision);
    }
    return QString::number(value, 'g', precision + 2);
}

void PlotWidget::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event);
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);

    m_plotRect = QRectF(m_marginLeft, m_marginTop,
                        width() - m_marginLeft - m_marginRight,
                        height() - m_marginTop - m_marginBottom);

    drawBackground(painter);

    if (m_showGrid) {
        drawGrid(painter);
    }

    drawAxes(painter);
    drawData(painter);
    drawLabels(painter);

    if (m_mouseInWidget && m_plotRect.contains(m_mousePos)) {
        double x, y;
        mapFromScreen(m_mousePos, x, y);
        QString text = QString("(%1, %2)").arg(formatValue(x)).arg(formatValue(y));

        painter.setPen(QPen(QColor(255, 255, 255, 200)));
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)));
        QRectF textRect(m_mousePos.x() + 10, m_mousePos.y() - 25, 120, 20);
        painter.drawRoundedRect(textRect, 4, 4);
        painter.setPen(QColor(255, 255, 255));
        painter.drawText(textRect, Qt::AlignCenter, text);

        painter.setPen(QPen(QColor(255, 255, 255, 150), 1, Qt::DashLine));
        painter.drawLine(QPointF(m_mousePos.x(), m_plotRect.top()),
                        QPointF(m_mousePos.x(), m_plotRect.bottom()));
        painter.drawLine(QPointF(m_plotRect.left(), m_mousePos.y()),
                        QPointF(m_plotRect.right(), m_mousePos.y()));
    }
}

void PlotWidget::drawBackground(QPainter& painter)
{
    QLinearGradient grad(0, 0, 0, height());
    grad.setColorAt(0, QColor(30, 30, 40));
    grad.setColorAt(1, QColor(15, 15, 25));
    painter.fillRect(rect(), grad);

    painter.setPen(QPen(QColor(60, 60, 80)));
    painter.setBrush(Qt::NoBrush);
    painter.drawRect(m_plotRect);
}

void PlotWidget::drawGrid(QPainter& painter)
{
    painter.setPen(QPen(QColor(80, 80, 100, 100), 1, Qt::DotLine));

    int numXTicks = 5;
    for (int i = 0; i <= numXTicks; ++i) {
        double xVal = m_xMin + (m_xMax - m_xMin) * i / numXTicks;
        QPointF p = mapToScreen(xVal, m_yMin);
        painter.drawLine(QPointF(p.x(), m_plotRect.top()),
                        QPointF(p.x(), m_plotRect.bottom()));
    }

    int numYTicks = 5;
    for (int i = 0; i <= numYTicks; ++i) {
        double yVal = m_yMin + (m_yMax - m_yMin) * i / numYTicks;
        QPointF p = mapToScreen(m_xMin, yVal);
        painter.drawLine(QPointF(m_plotRect.left(), p.y()),
                        QPointF(m_plotRect.right(), p.y()));
    }
}

void PlotWidget::drawAxes(QPainter& painter)
{
    painter.setPen(QPen(QColor(200, 200, 200), 2));

    int numXTicks = 5;
    for (int i = 0; i <= numXTicks; ++i) {
        double xVal = m_xMin + (m_xMax - m_xMin) * i / numXTicks;
        QPointF p = mapToScreen(xVal, m_yMin);

        painter.drawLine(QPointF(p.x(), m_plotRect.bottom()),
                        QPointF(p.x(), m_plotRect.bottom() + 5));

        painter.setPen(QColor(200, 200, 200));
        painter.drawText(QRectF(p.x() - 40, m_plotRect.bottom() + 8, 80, 20),
                        Qt::AlignCenter, formatValue(xVal));
        painter.setPen(QPen(QColor(200, 200, 200), 2));
    }

    int numYTicks = 5;
    for (int i = 0; i <= numYTicks; ++i) {
        double yVal = m_yMin + (m_yMax - m_yMin) * i / numYTicks;
        QPointF p = mapToScreen(m_xMin, yVal);

        painter.drawLine(QPointF(m_plotRect.left() - 5, p.y()),
                        QPointF(m_plotRect.left(), p.y()));

        painter.setPen(QColor(200, 200, 200));
        painter.drawText(QRectF(m_marginLeft - 55, p.y() - 10, 50, 20),
                        Qt::AlignRight | Qt::AlignVCenter, formatValue(yVal));
        painter.setPen(QPen(QColor(200, 200, 200), 2));
    }
}

void PlotWidget::drawData(QPainter& painter)
{
    if (m_mode == PlotMode::XYMode) {
        if (m_xyX.size() < 2) return;

        painter.setPen(QPen(QColor(255, 200, 100), m_lineWidth));
        painter.setBrush(Qt::NoBrush);

        QPainterPath path;
        QPointF first = mapToScreen(m_xyX[0], m_xyY[0]);
        path.moveTo(first);

        for (size_t i = 1; i < m_xyX.size(); ++i) {
            QPointF p = mapToScreen(m_xyX[i], m_xyY[i]);
            path.lineTo(p);
        }
        painter.drawPath(path);

        if (!m_xyX.empty()) {
            painter.setPen(Qt::NoPen);
            painter.setBrush(QBrush(QColor(255, 255, 100)));
            QPointF last = mapToScreen(m_xyX.back(), m_xyY.back());
            painter.drawEllipse(last, 4, 4);
        }
    } else {
        for (size_t s = 0; s < m_series.size(); ++s) {
            if (!m_series[s].visible || m_series[s].y.empty()) continue;

            painter.setPen(QPen(m_series[s].color, m_lineWidth));
            painter.setBrush(Qt::NoBrush);

            const auto& yData = m_series[s].y;
            const auto& xData = m_series[s].x;

            if (yData.size() < 2) continue;

            QPainterPath path;
            double x0 = xData.empty() ? 0 : xData[0];
            QPointF first = mapToScreen(x0, yData[0]);
            path.moveTo(first);

            for (size_t i = 1; i < yData.size(); ++i) {
                double x = xData.empty() ? static_cast<double>(i) : xData[i];
                QPointF p = mapToScreen(x, yData[i]);
                path.lineTo(p);
            }
            painter.drawPath(path);

            if (!yData.empty() && m_mode == PlotMode::TimeDomain) {
                painter.setPen(Qt::NoPen);
                painter.setBrush(QBrush(m_series[s].color));
                double x = xData.empty() ? yData.size() - 1 : xData.back();
                QPointF last = mapToScreen(x, yData.back());
                painter.drawEllipse(last, 3, 3);
            }
        }
    }
}

void PlotWidget::drawLabels(QPainter& painter)
{
    painter.setPen(QColor(200, 200, 200));
    QFont font = painter.font();
    font.setPointSize(9);
    painter.setFont(font);

    painter.drawText(QRectF(m_plotRect.left(), 5, m_plotRect.width(), 30),
                    Qt::AlignCenter, m_title);

    painter.save();
    painter.translate(m_marginLeft - 40, m_plotRect.center().y());
    painter.rotate(-90);
    painter.drawText(QRectF(-50, -15, 100, 30), Qt::AlignCenter, m_yLabel);
    painter.restore();

    painter.drawText(QRectF(m_plotRect.left(), height() - 25, m_plotRect.width(), 20),
                    Qt::AlignCenter, m_xLabel);
}

void PlotWidget::mouseMoveEvent(QMouseEvent *event)
{
    m_mousePos = event->pos();
    m_mouseInWidget = true;
    update();
}

void PlotWidget::leaveEvent(QEvent *event)
{
    Q_UNUSED(event);
    m_mouseInWidget = false;
    update();
}
