#include "GLWidget.h"
#include <cmath>
#include <QDebug>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

const char* vertexShaderSource = R"(
    #version 330 core
    layout(location = 0) in vec2 position;
    layout(location = 1) in vec2 texCoord;
    out vec2 vTexCoord;
    void main() {
        vTexCoord = texCoord;
        gl_Position = vec4(position, 0.0, 1.0);
    }
)";

const char* fragmentShaderSource = R"(
    #version 330 core
    in vec2 vTexCoord;
    out vec4 fragColor;
    uniform sampler2D dataTexture;
    uniform sampler1D colormapTexture;
    void main() {
        float value = texture(dataTexture, vTexCoord).r;
        vec3 color = texture(colormapTexture, value).rgb;
        fragColor = vec4(color, 1.0);
    }
)";

GLWidget::GLWidget(QWidget* parent)
    : QOpenGLWidget(parent),
      m_vao(0), m_vbo(0),
      m_transferSync(nullptr),
      m_dataWidth(0), m_dataHeight(0),
      m_currentColormap(0),
      m_currentTextureIndex(0),
      m_pboIndex(0),
      m_textureReady(false),
      m_updatePending(false) {
    m_colormapData.resize(COLORMAP_SIZE * 3);
    setUpdateBehavior(QOpenGLWidget::PartialUpdate);
}

GLWidget::~GLWidget() {
    makeCurrent();
    
    if (m_transferSync) {
        glDeleteSync(m_transferSync);
        m_transferSync = nullptr;
    }
    
    glDeleteVertexArrays(1, &m_vao);
    glDeleteBuffers(1, &m_vbo);
    
    m_program.reset();
    m_dataTexture[0].reset();
    m_dataTexture[1].reset();
    m_colormapTexture.reset();
    m_pbo[0].reset();
    m_pbo[1].reset();
    
    doneCurrent();
}

void GLWidget::createTransferFunction(int index) {
    m_colormapData.resize(COLORMAP_SIZE * 3);
    
    switch (index) {
        case 0: {
            for (int i = 0; i < COLORMAP_SIZE; i++) {
                float t = i / 255.0f;
                m_colormapData[i * 3]     = static_cast<unsigned char>(255 * (0.2f + 0.6f * t));
                m_colormapData[i * 3 + 1] = static_cast<unsigned char>(255 * (0.1f + 0.8f * t * t));
                m_colormapData[i * 3 + 2] = static_cast<unsigned char>(255 * (0.5f + 0.5f * std::sin(t * M_PI)));
            }
            break;
        }
        case 1: {
            for (int i = 0; i < COLORMAP_SIZE; i++) {
                float t = i / 255.0f;
                m_colormapData[i * 3]     = static_cast<unsigned char>(255 * t);
                m_colormapData[i * 3 + 1] = static_cast<unsigned char>(255 * std::sqrt(t));
                m_colormapData[i * 3 + 2] = static_cast<unsigned char>(255 * (1.0f - t));
            }
            break;
        }
        case 2: {
            for (int i = 0; i < COLORMAP_SIZE; i++) {
                float t = i / 255.0f;
                m_colormapData[i * 3]     = static_cast<unsigned char>(255 * (0.5f + 0.5f * std::sin(t * 2 * M_PI)));
                m_colormapData[i * 3 + 1] = static_cast<unsigned char>(255 * (0.5f + 0.5f * std::sin(t * 2 * M_PI + 2.094)));
                m_colormapData[i * 3 + 2] = static_cast<unsigned char>(255 * (0.5f + 0.5f * std::sin(t * 2 * M_PI + 4.188)));
            }
            break;
        }
        case 3: {
            for (int i = 0; i < COLORMAP_SIZE; i++) {
                float t = i / 255.0f;
                m_colormapData[i * 3]     = static_cast<unsigned char>(255 * t);
                m_colormapData[i * 3 + 1] = static_cast<unsigned char>(255 * t);
                m_colormapData[i * 3 + 2] = static_cast<unsigned char>(255 * t);
            }
            break;
        }
        case 4: {
            for (int i = 0; i < COLORMAP_SIZE; i++) {
                float t = i / 255.0f;
                if (t < 0.25f) {
                    float s = t / 0.25f;
                    m_colormapData[i * 3]     = static_cast<unsigned char>(68 * (1 - s) + 72 * s);
                    m_colormapData[i * 3 + 1] = static_cast<unsigned char>(1 * (1 - s) + 228 * s);
                    m_colormapData[i * 3 + 2] = static_cast<unsigned char>(84 * (1 - s) + 239 * s);
                } else if (t < 0.5f) {
                    float s = (t - 0.25f) / 0.25f;
                    m_colormapData[i * 3]     = static_cast<unsigned char>(72 * (1 - s) + 246 * s);
                    m_colormapData[i * 3 + 1] = static_cast<unsigned char>(228 * (1 - s) + 233 * s);
                    m_colormapData[i * 3 + 2] = static_cast<unsigned char>(239 * (1 - s) + 148 * s);
                } else if (t < 0.75f) {
                    float s = (t - 0.5f) / 0.25f;
                    m_colormapData[i * 3]     = static_cast<unsigned char>(246 * (1 - s) + 253 * s);
                    m_colormapData[i * 3 + 1] = static_cast<unsigned char>(233 * (1 - s) + 161 * s);
                    m_colormapData[i * 3 + 2] = static_cast<unsigned char>(148 * (1 - s) + 47 * s);
                } else {
                    float s = (t - 0.75f) / 0.25f;
                    m_colormapData[i * 3]     = static_cast<unsigned char>(253 * (1 - s) + 255 * s);
                    m_colormapData[i * 3 + 1] = static_cast<unsigned char>(161 * (1 - s) + 255 * s);
                    m_colormapData[i * 3 + 2] = static_cast<unsigned char>(47 * (1 - s) + 255 * s);
                }
            }
            break;
        }
        default:
            for (int i = 0; i < COLORMAP_SIZE; i++) {
                m_colormapData[i * 3]     = i;
                m_colormapData[i * 3 + 1] = i;
                m_colormapData[i * 3 + 2] = i;
            }
    }
}

void GLWidget::initPBO() {
    int dataSize = m_dataWidth * m_dataHeight * sizeof(float);
    
    for (int i = 0; i < 2; i++) {
        if (!m_pbo[i]) {
            m_pbo[i] = std::make_unique<QOpenGLBuffer>(QOpenGLBuffer::PixelUnpackBuffer);
            m_pbo[i]->create();
        }
        m_pbo[i]->bind();
        m_pbo[i]->allocate(dataSize);
        m_pbo[i]->release();
    }
}

void GLWidget::swapBuffers() {
    if (m_transferSync) {
        GLenum status = glClientWaitSync(m_transferSync, GL_SYNC_FLUSH_COMMANDS_BIT, 1000000000);
        if (status == GL_TIMEOUT_EXPIRED || status == GL_WAIT_FAILED) {
            qDebug() << "Sync wait failed, status:" << status;
        }
        glDeleteSync(m_transferSync);
        m_transferSync = nullptr;
    }
    
    m_currentTextureIndex = 1 - m_currentTextureIndex;
    m_pboIndex = 1 - m_pboIndex;
    m_textureReady.store(true);
}

void GLWidget::initializeGL() {
    initializeOpenGLFunctions();
    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
    
    glEnable(GL_TEXTURE_2D);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);

    m_program = std::make_unique<QOpenGLShaderProgram>();
    m_program->addShaderFromSourceCode(QOpenGLShader::Vertex, vertexShaderSource);
    m_program->addShaderFromSourceCode(QOpenGLShader::Fragment, fragmentShaderSource);
    m_program->link();
    m_program->bind();

    float vertices[] = {
        -1.0f, -1.0f,  0.0f, 1.0f,
         1.0f, -1.0f,  1.0f, 1.0f,
         1.0f,  1.0f,  1.0f, 0.0f,
        -1.0f,  1.0f,  0.0f, 0.0f
    };

    glGenVertexArrays(1, &m_vao);
    glGenBuffers(1, &m_vbo);
    
    glBindVertexArray(m_vao);
    glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(vertices), vertices, GL_STATIC_DRAW);

    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)(2 * sizeof(float)));
    glEnableVertexAttribArray(1);

    initColormapTexture();

    m_program->release();
    
    glBindVertexArray(0);
    glBindBuffer(GL_ARRAY_BUFFER, 0);
}

void GLWidget::initColormapTexture() {
    createTransferFunction(m_currentColormap);
    
    m_colormapTexture = std::make_unique<QOpenGLTexture>(QOpenGLTexture::Target1D);
    m_colormapTexture->create();
    m_colormapTexture->bind();
    m_colormapTexture->setSize(COLORMAP_SIZE);
    m_colormapTexture->setFormat(QOpenGLTexture::RGB8_UNorm);
    m_colormapTexture->allocateStorage();
    m_colormapTexture->setData(QOpenGLTexture::RGB, QOpenGLTexture::UInt8, m_colormapData.data());
    m_colormapTexture->setWrapMode(QOpenGLTexture::ClampToEdge);
    m_colormapTexture->setMinificationFilter(QOpenGLTexture::Linear);
    m_colormapTexture->setMagnificationFilter(QOpenGLTexture::Linear);
    m_colormapTexture->release();
}

void GLWidget::setColormap(int index) {
    m_currentColormap = index;
    makeCurrent();
    createTransferFunction(index);
    if (m_colormapTexture) {
        m_colormapTexture->bind();
        m_colormapTexture->setData(QOpenGLTexture::RGB, QOpenGLTexture::UInt8, m_colormapData.data());
        m_colormapTexture->release();
    }
    doneCurrent();
    update();
}

void GLWidget::resizeGL(int w, int h) {
    glViewport(0, 0, w, h);
}

void GLWidget::paintGL() {
    glClear(GL_COLOR_BUFFER_BIT);

    if (!m_program || !m_dataTexture[m_currentTextureIndex] || !m_colormapTexture) {
        return;
    }

    if (m_updatePending.load() && m_textureReady.load()) {
        m_updatePending.store(false);
    }

    m_program->bind();

    m_dataTexture[m_currentTextureIndex]->bind(0);
    m_colormapTexture->bind(1);

    m_program->setUniformValue("dataTexture", 0);
    m_program->setUniformValue("colormapTexture", 1);

    glBindVertexArray(m_vao);
    glDrawArrays(GL_TRIANGLE_FAN, 0, 4);
    glBindVertexArray(0);

    m_dataTexture[m_currentTextureIndex]->release(0);
    m_colormapTexture->release(1);
    m_program->release();
    
    glFlush();
}

void GLWidget::updateData(const std::vector<float>& data, int width, int height) {
    if (data.empty()) return;
    
    m_floatData = data;
    m_dataWidth = width;
    m_dataHeight = height;

    makeCurrent();

    bool needRecreate = false;
    for (int i = 0; i < 2; i++) {
        if (!m_dataTexture[i] || 
            m_dataTexture[i]->width() != width || 
            m_dataTexture[i]->height() != height) {
            needRecreate = true;
            break;
        }
    }

    if (needRecreate) {
        for (int i = 0; i < 2; i++) {
            m_dataTexture[i] = std::make_unique<QOpenGLTexture>(QOpenGLTexture::Target2D);
            m_dataTexture[i]->create();
            m_dataTexture[i]->bind();
            m_dataTexture[i]->setSize(width, height);
            m_dataTexture[i]->setFormat(QOpenGLTexture::R32F);
            m_dataTexture[i]->allocateStorage();
            m_dataTexture[i]->setWrapMode(QOpenGLTexture::ClampToEdge);
            m_dataTexture[i]->setMinificationFilter(QOpenGLTexture::Linear);
            m_dataTexture[i]->setMagnificationFilter(QOpenGLTexture::Linear);
            m_dataTexture[i]->release();
        }
        initPBO();
        
        for (int i = 0; i < 2; i++) {
            m_pbo[i]->bind();
            void* ptr = m_pbo[i]->map(QOpenGLBuffer::WriteOnly);
            if (ptr) {
                memcpy(ptr, m_floatData.data(), width * height * sizeof(float));
                m_pbo[i]->unmap();
            }
            m_pbo[i]->release();
            
            m_dataTexture[i]->bind();
            m_pbo[i]->bind();
            m_dataTexture[i]->setData(QOpenGLTexture::Red, QOpenGLTexture::Float32, nullptr);
            m_pbo[i]->release();
            m_dataTexture[i]->release();
        }
        m_textureReady.store(true);
    } else {
        int uploadIndex = 1 - m_currentTextureIndex;
        
        if (m_pbo[m_pboIndex]->isCreated()) {
            m_pbo[m_pboIndex]->bind();
            
            GLint pboSize = 0;
            glGetBufferParameteriv(GL_PIXEL_UNPACK_BUFFER, GL_BUFFER_SIZE, &pboSize);
            if (pboSize != width * height * sizeof(float)) {
                m_pbo[m_pboIndex]->allocate(width * height * sizeof(float));
            }
            
            void* ptr = m_pbo[m_pboIndex]->map(QOpenGLBuffer::WriteOnly);
            if (ptr) {
                memcpy(ptr, m_floatData.data(), width * height * sizeof(float));
                m_pbo[m_pboIndex]->unmap();
            }
            
            m_dataTexture[uploadIndex]->bind();
            m_pbo[m_pboIndex]->release();
            
            if (m_transferSync) {
                glDeleteSync(m_transferSync);
            }
            
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, width, height, 
                           GL_RED, GL_FLOAT, nullptr);
            
            m_transferSync = glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE, 0);
            
            m_dataTexture[uploadIndex]->release();
            
            GLenum waitStatus = glClientWaitSync(m_transferSync, 
                                                 GL_SYNC_FLUSH_COMMANDS_BIT, 
                                                 50000000);
            if (waitStatus == GL_ALREADY_SIGNALED || waitStatus == GL_CONDITION_SATISFIED) {
                swapBuffers();
            }
        }
    }

    glFinish();
    doneCurrent();
    m_updatePending.store(true);
    update();
}
