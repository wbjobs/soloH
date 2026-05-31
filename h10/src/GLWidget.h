#ifndef GLWIDGET_H
#define GLWIDGET_H

#include <QOpenGLWidget>
#include <QOpenGLFunctions>
#include <QOpenGLShaderProgram>
#include <QOpenGLTexture>
#include <QOpenGLBuffer>
#include <vector>
#include <memory>
#include <atomic>

class GLWidget : public QOpenGLWidget, protected QOpenGLFunctions {
    Q_OBJECT

public:
    explicit GLWidget(QWidget* parent = nullptr);
    ~GLWidget() override;

    void updateData(const std::vector<float>& data, int width, int height);

public slots:
    void setColormap(int index);

protected:
    void initializeGL() override;
    void resizeGL(int w, int h) override;
    void paintGL() override;

private:
    void initColormapTexture();
    void createTransferFunction(int index);
    void initPBO();
    void swapBuffers();

    std::unique_ptr<QOpenGLShaderProgram> m_program;
    std::unique_ptr<QOpenGLTexture> m_dataTexture[2];
    std::unique_ptr<QOpenGLTexture> m_colormapTexture;
    std::unique_ptr<QOpenGLBuffer> m_pbo[2];

    GLuint m_vao;
    GLuint m_vbo;
    GLsync m_transferSync;

    std::vector<unsigned char> m_colormapData;
    std::vector<float> m_floatData;
    int m_dataWidth;
    int m_dataHeight;
    int m_currentColormap;
    int m_currentTextureIndex;
    int m_pboIndex;
    std::atomic<bool> m_textureReady;
    std::atomic<bool> m_updatePending;

    static const int COLORMAP_SIZE = 256;
};

#endif
