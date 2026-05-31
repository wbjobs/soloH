#ifndef VIDEORECORDER_H
#define VIDEORECORDER_H

#include <string>
#include <vector>
#include <opencv2/opencv.hpp>

class VideoRecorder {
public:
    VideoRecorder();
    ~VideoRecorder();

    bool start(const std::string& filename, int width, int height, double fps = 30.0);
    void stop();
    void addFrame(const std::vector<float>& data, int width, int height);
    bool isRecording() const { return m_isRecording; }
    int getFrameCount() const { return m_frameCount; }

    static void applyColormap(const std::vector<float>& data, int width, int height, cv::Mat& output);

private:
    cv::VideoWriter m_writer;
    bool m_isRecording;
    int m_width;
    int m_height;
    int m_frameCount;
    double m_fps;
};

#endif
