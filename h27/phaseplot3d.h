#ifndef PHASEPLOT3D_H
#define PHASEPLOT3D_H

#include <QOpenGLWidget>
#include <QOpenGLFunctions>
#include <QMatrix4x4>
#include <QVector3D>
#include <QPoint>
#include <QTimer>
#include <vector>

class PhasePlot3D : public QOpenGLWidget, protected QOpenGLFunctions
{
    Q_OBJECT
public:
    explicit PhasePlot3D(QWidget *parent = nullptr);
    ~PhasePlot3D();

    void setTrajectoryData(const std::vector<double>& x,
                          const std::vector<double>& y,
                          const std::vector<double>& z);

    void appendPoint(double x, double y, double z);
    void clearTrajectory();

    void setMaxPoints(int maxPoints);
    void setAutoRotate(bool enable);
    void setShowAxes(bool show);
    void setGridEnabled(bool enable);

    void resetView();

signals:

protected:
    void initializeGL() override;
    void resizeGL(int w, int h) override;
    void paintGL() override;

    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void wheelEvent(QWheelEvent *event) override;

private slots:
    void onAutoRotate();

private:
    void drawAxes();
    void drawGrid();
    void drawTrajectory();

    void computeBounds();
    void setupProjection();

    std::vector<double> m_xData;
    std::vector<double> m_yData;
    std::vector<double> m_zData;

    int m_maxPoints;
    bool m_autoRotate;
    bool m_showAxes;
    bool m_showGrid;

    float m_rotationX;
    float m_rotationY;
    float m_rotationZ;
    float m_zoom;
    float m_distance;

    QPoint m_lastMousePos;
    bool m_leftButtonPressed;
    bool m_rightButtonPressed;

    QMatrix4x4 m_projectionMatrix;
    QMatrix4x4 m_modelViewMatrix;

    QTimer* m_rotateTimer;

    double m_minX, m_maxX;
    double m_minY, m_maxY;
    double m_minZ, m_maxZ;
    double m_scaleX, m_scaleY, m_scaleZ;
    double m_centerX, m_centerY, m_centerZ;
};

#endif
