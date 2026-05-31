#include "phaseplot3d.h"
#include <QMouseEvent>
#include <QWheelEvent>
#include <GL/glu.h>
#include <cmath>
#include <algorithm>

PhasePlot3D::PhasePlot3D(QWidget *parent)
    : QOpenGLWidget(parent)
    , m_maxPoints(20000)
    , m_autoRotate(false)
    , m_showAxes(true)
    , m_showGrid(true)
    , m_rotationX(30.0f)
    , m_rotationY(-45.0f)
    , m_rotationZ(0.0f)
    , m_zoom(1.0f)
    , m_distance(5.0f)
    , m_leftButtonPressed(false)
    , m_rightButtonPressed(false)
    , m_rotateTimer(nullptr)
    , m_minX(-1), m_maxX(1)
    , m_minY(-1), m_maxY(1)
    , m_minZ(-1), m_maxZ(1)
    , m_scaleX(1), m_scaleY(1), m_scaleZ(1)
    , m_centerX(0), m_centerY(0), m_centerZ(0)
{
    setFocusPolicy(Qt::StrongFocus);

    m_rotateTimer = new QTimer(this);
    connect(m_rotateTimer, &QTimer::timeout, this, &PhasePlot3D::onAutoRotate);
    m_rotateTimer->start(30);
}

PhasePlot3D::~PhasePlot3D()
{
}

void PhasePlot3D::setMaxPoints(int maxPoints)
{
    m_maxPoints = maxPoints;
    while (static_cast<int>(m_xData.size()) > m_maxPoints) {
        m_xData.erase(m_xData.begin());
        m_yData.erase(m_yData.begin());
        m_zData.erase(m_zData.begin());
    }
}

void PhasePlot3D::setAutoRotate(bool enable)
{
    m_autoRotate = enable;
}

void PhasePlot3D::setShowAxes(bool show)
{
    m_showAxes = show;
    update();
}

void PhasePlot3D::setGridEnabled(bool enable)
{
    m_showGrid = enable;
    update();
}

void PhasePlot3D::setTrajectoryData(const std::vector<double>& x,
                                    const std::vector<double>& y,
                                    const std::vector<double>& z)
{
    m_xData = x;
    m_yData = y;
    m_zData = z;

    while (static_cast<int>(m_xData.size()) > m_maxPoints) {
        m_xData.erase(m_xData.begin());
        m_yData.erase(m_yData.begin());
        m_zData.erase(m_zData.begin());
    }

    computeBounds();
    update();
}

void PhasePlot3D::appendPoint(double x, double y, double z)
{
    m_xData.push_back(x);
    m_yData.push_back(y);
    m_zData.push_back(z);

    while (static_cast<int>(m_xData.size()) > m_maxPoints) {
        m_xData.erase(m_xData.begin());
        m_yData.erase(m_yData.begin());
        m_zData.erase(m_zData.begin());
    }

    if (m_xData.size() % 100 == 0) {
        computeBounds();
    }
    update();
}

void PhasePlot3D::clearTrajectory()
{
    m_xData.clear();
    m_yData.clear();
    m_zData.clear();
    computeBounds();
    update();
}

void PhasePlot3D::resetView()
{
    m_rotationX = 30.0f;
    m_rotationY = -45.0f;
    m_rotationZ = 0.0f;
    m_zoom = 1.0f;
    m_distance = 5.0f;
    update();
}

void PhasePlot3D::computeBounds()
{
    if (m_xData.empty()) {
        m_minX = m_minY = m_minZ = -1;
        m_maxX = m_maxY = m_maxZ = 1;
        m_centerX = m_centerY = m_centerZ = 0;
        m_scaleX = m_scaleY = m_scaleZ = 1;
        return;
    }

    m_minX = m_maxX = m_xData[0];
    m_minY = m_maxY = m_yData[0];
    m_minZ = m_maxZ = m_zData[0];

    for (size_t i = 1; i < m_xData.size(); ++i) {
        m_minX = std::min(m_minX, m_xData[i]);
        m_maxX = std::max(m_maxX, m_xData[i]);
        m_minY = std::min(m_minY, m_yData[i]);
        m_maxY = std::max(m_maxY, m_yData[i]);
        m_minZ = std::min(m_minZ, m_zData[i]);
        m_maxZ = std::max(m_maxZ, m_zData[i]);
    }

    m_centerX = (m_minX + m_maxX) / 2.0;
    m_centerY = (m_minY + m_maxY) / 2.0;
    m_centerZ = (m_minZ + m_maxZ) / 2.0;

    double rangeX = std::max(m_maxX - m_minX, 1e-6);
    double rangeY = std::max(m_maxY - m_minY, 1e-6);
    double rangeZ = std::max(m_maxZ - m_minZ, 1e-6);

    double maxRange = std::max({rangeX, rangeY, rangeZ});
    m_scaleX = 2.0 / maxRange;
    m_scaleY = 2.0 / maxRange;
    m_scaleZ = 2.0 / maxRange;
}

void PhasePlot3D::initializeGL()
{
    initializeOpenGLFunctions();
    glClearColor(0.05f, 0.05f, 0.08f, 1.0f);

    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LESS);
    glDepthMask(GL_TRUE);

    glEnable(GL_LINE_SMOOTH);
    glEnable(GL_POINT_SMOOTH);

    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);

    glEnable(GL_POLYGON_OFFSET_FILL);
    glPolygonOffset(1.0f, 1.0f);
}

void PhasePlot3D::resizeGL(int w, int h)
{
    glViewport(0, 0, w, h);
    setupProjection();
}

void PhasePlot3D::setupProjection()
{
    m_projectionMatrix.setToIdentity();
    m_projectionMatrix.perspective(45.0f, float(width()) / float(height()), 0.1f, 100.0f);
}

void PhasePlot3D::paintGL()
{
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

    m_modelViewMatrix.setToIdentity();
    m_modelViewMatrix.translate(0.0f, 0.0f, -m_distance * m_zoom);
    m_modelViewMatrix.rotate(m_rotationX, 1.0f, 0.0f, 0.0f);
    m_modelViewMatrix.rotate(m_rotationY, 0.0f, 1.0f, 0.0f);
    m_modelViewMatrix.rotate(m_rotationZ, 0.0f, 0.0f, 1.0f);

    glMatrixMode(GL_PROJECTION);
    glLoadMatrixf(m_projectionMatrix.constData());

    glMatrixMode(GL_MODELVIEW);
    glLoadMatrixf(m_modelViewMatrix.constData());

    if (m_showGrid) {
        drawGrid();
    }

    if (m_showAxes) {
        drawAxes();
    }

    drawTrajectory();
}

void PhasePlot3D::drawGrid()
{
    glDepthMask(GL_FALSE);
    glDisable(GL_DEPTH_TEST);

    glColor4f(0.2f, 0.2f, 0.3f, 0.25f);
    glLineWidth(1.0f);

    int gridSize = 10;
    float step = 2.0f / static_cast<float>(gridSize);

    glBegin(GL_LINES);
    for (int i = 0; i <= gridSize; ++i) {
        float pos = -1.0f + static_cast<float>(i) * step;

        glVertex3f(pos, -1.0f, -1.0f);
        glVertex3f(pos, -1.0f, 1.0f);

        glVertex3f(-1.0f, -1.0f, pos);
        glVertex3f(1.0f, -1.0f, pos);
    }
    glEnd();

    glEnable(GL_DEPTH_TEST);
    glDepthMask(GL_TRUE);
}

void PhasePlot3D::drawAxes()
{
    glDepthMask(GL_TRUE);
    glEnable(GL_DEPTH_TEST);
    glDisable(GL_BLEND);

    glLineWidth(2.0f);

    glBegin(GL_LINES);
    glColor3f(1.0f, 0.3f, 0.3f);
    glVertex3f(-1.2f, -1.0f, -1.0f);
    glVertex3f(1.2f, -1.0f, -1.0f);
    glEnd();

    glBegin(GL_LINES);
    glColor3f(0.3f, 1.0f, 0.3f);
    glVertex3f(-1.0f, -1.2f, -1.0f);
    glVertex3f(-1.0f, 1.2f, -1.0f);
    glEnd();

    glBegin(GL_LINES);
    glColor3f(0.3f, 0.5f, 1.0f);
    glVertex3f(-1.0f, -1.0f, -1.2f);
    glVertex3f(-1.0f, -1.0f, 1.2f);
    glEnd();

    glEnable(GL_BLEND);
}

void PhasePlot3D::drawTrajectory()
{
    if (m_xData.size() < 2) return;

    glDepthMask(GL_TRUE);
    glEnable(GL_DEPTH_TEST);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);

    glLineWidth(1.5f);
    glBegin(GL_LINE_STRIP);

    for (size_t i = 0; i < m_xData.size(); ++i) {
        float t = static_cast<float>(i) / static_cast<float>(m_xData.size());

        float sx = (m_xData[i] - m_centerX) * m_scaleX;
        float sy = (m_yData[i] - m_centerY) * m_scaleY;
        float sz = (m_zData[i] - m_centerZ) * m_scaleZ;

        float r = 0.2f + 0.8f * t;
        float g = 0.3f + 0.5f * sinf(t * 3.14159f);
        float b = 1.0f - 0.8f * t;
        float a = 0.6f + 0.4f * t;

        glColor4f(r, g, b, a);
        glVertex3f(sx, sy, sz);
    }

    glEnd();

    if (!m_xData.empty()) {
        glDisable(GL_BLEND);
        glPointSize(6.0f);
        glBegin(GL_POINTS);
        glColor3f(1.0f, 1.0f, 0.5f);
        int idx = static_cast<int>(m_xData.size()) - 1;
        float sx = (m_xData[idx] - m_centerX) * m_scaleX;
        float sy = (m_yData[idx] - m_centerY) * m_scaleY;
        float sz = (m_zData[idx] - m_centerZ) * m_scaleZ;
        glVertex3f(sx, sy, sz);
        glEnd();
        glEnable(GL_BLEND);
    }
}

void PhasePlot3D::mousePressEvent(QMouseEvent *event)
{
    m_lastMousePos = event->pos();
    if (event->button() == Qt::LeftButton) {
        m_leftButtonPressed = true;
    }
    if (event->button() == Qt::RightButton) {
        m_rightButtonPressed = true;
    }
}

void PhasePlot3D::mouseMoveEvent(QMouseEvent *event)
{
    int dx = event->x() - m_lastMousePos.x();
    int dy = event->y() - m_lastMousePos.y();

    if (m_leftButtonPressed) {
        m_rotationY += dx * 0.5f;
        m_rotationX += dy * 0.5f;
        update();
    }

    if (m_rightButtonPressed) {
        m_distance -= dy * 0.02f;
        m_distance = std::max(1.0f, std::min(20.0f, m_distance));
        update();
    }

    m_lastMousePos = event->pos();
}

void PhasePlot3D::wheelEvent(QWheelEvent *event)
{
    int delta = event->angleDelta().y();
    m_zoom *= (1.0f - delta * 0.001f);
    m_zoom = std::max(0.1f, std::min(10.0f, m_zoom));
    update();
}

void PhasePlot3D::onAutoRotate()
{
    if (m_autoRotate && !m_leftButtonPressed) {
        m_rotationY += 0.3f;
        update();
    }
}
