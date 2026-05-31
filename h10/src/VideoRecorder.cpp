#include "VideoRecorder.h"
#include <algorithm>
#include <stdexcept>

VideoRecorder::VideoRecorder()
    : m_isRecording(false), m_width(0), m_height(0), m_frameCount(0), m_fps(30.0) {
}

VideoRecorder::~VideoRecorder() {
    stop();
}

bool VideoRecorder::start(const std::string& filename, int width, int height, double fps) {
    if (m_isRecording) {
        stop();
    }

    m_width = width;
    m_height = height;
    m_fps = fps;
    m_frameCount = 0;

    int fourcc = cv::VideoWriter::fourcc('M', 'J', 'P', 'G');
    m_writer.open(filename, fourcc, fps, cv::Size(width, height), true);

    if (!m_writer.isOpened()) {
        int fourcc2 = cv::VideoWriter::fourcc('a', 'v', 'c', '1');
        m_writer.open(filename, fourcc2, fps, cv::Size(width, height), true);
    }

    if (!m_writer.isOpened()) {
        int fourcc3 = cv::VideoWriter::fourcc('X', 'V', 'I', 'D');
        m_writer.open(filename, fourcc3, fps, cv::Size(width, height), true);
    }

    m_isRecording = m_writer.isOpened();
    return m_isRecording;
}

void VideoRecorder::stop() {
    if (m_isRecording && m_writer.isOpened()) {
        m_writer.release();
    }
    m_isRecording = false;
    m_frameCount = 0;
}

void VideoRecorder::addFrame(const std::vector<float>& data, int width, int height) {
    if (!m_isRecording || !m_writer.isOpened()) {
        return;
    }

    if (data.size() != static_cast<size_t>(width * height)) {
        throw std::invalid_argument("Data size mismatch");
    }

    cv::Mat frame;
    applyColormap(data, width, height, frame);

    if (frame.cols != m_width || frame.rows != m_height) {
        cv::resize(frame, frame, cv::Size(m_width, m_height));
    }

    m_writer.write(frame);
    m_frameCount++;
}

void VideoRecorder::applyColormap(const std::vector<float>& data, int width, int height, cv::Mat& output) {
    cv::Mat gray(height, width, CV_32F, const_cast<float*>(data.data()));
    
    double minVal, maxVal;
    cv::minMaxLoc(gray, &minVal, &maxVal);
    
    if (maxVal > minVal) {
        gray.convertTo(gray, CV_8U, 255.0 / (maxVal - minVal), -255.0 * minVal / (maxVal - minVal));
    } else {
        gray.convertTo(gray, CV_8U, 0, 0);
    }

    cv::Mat colored;
    cv::applyColorMap(gray, colored, cv::COLORMAP_VIRIDIS);
    
    cv::Mat flipped;
    cv::flip(colored, output, 0);
}
