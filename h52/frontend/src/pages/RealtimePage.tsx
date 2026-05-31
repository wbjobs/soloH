import { useEffect, useRef } from 'react';
import { useEmotionStream } from '@/hooks/useEmotionStream';
import { EmotionDisplay } from '@/components/emotion/EmotionDisplay';
import { EmotionTimeSeries } from '@/components/charts/EmotionTimeSeries';
import { EmotionBadge } from '@/components/emotion/EmotionDisplay';
import { Play, Pause, Power, Camera } from 'lucide-react';
import { generateMockEmotionResult, formatPercent, getDominantEmotion } from '@/utils';
import { useAppStore } from '@/store';
import type { EmotionProbabilities } from '@/types';
import { EMOTION_LABELS, EMOTION_COLORS } from '@/types';

export function RealtimePage() {
  const {
    videoRef,
    canvasRef,
    stream,
    isCameraActive,
    startCamera,
    stopCamera,
    startStreaming,
    stopStreaming,
    disconnect,
  } = useEmotionStream();

  const mockDataRef = useRef<number | null>(null);

  useEffect(() => {
    if (stream.isStreaming && !stream.isConnected) {
      mockDataRef.current = window.setInterval(() => {
        const mock = generateMockEmotionResult();
        const { addStreamResult } = useAppStore.getState();
        addStreamResult({
          timestamp: Date.now(),
          emotion: getDominantEmotion(mock.emotion.probabilities).category,
          confidence: getDominantEmotion(mock.emotion.probabilities).confidence,
          valence: mock.valenceArousal.valence,
          arousal: mock.valenceArousal.arousal,
          probabilities: mock.emotion.probabilities,
          modalityContributions: {
            audio: Math.random() * 0.5 + 0.2,
            video: Math.random() * 0.5 + 0.2,
            text: Math.random() * 0.5 + 0.2,
          },
        });
      }, 1000);
    }

    return () => {
      if (mockDataRef.current) {
        clearInterval(mockDataRef.current);
      }
    };
  }, [stream.isStreaming, stream.isConnected]);

  useEffect(() => {
    return () => {
      disconnect();
      if (mockDataRef.current) {
        clearInterval(mockDataRef.current);
      }
    };
  }, [disconnect]);

  const currentProbabilities = stream.results.length > 0
    ? stream.results[stream.results.length - 1].probabilities
    : { anger: 0, joy: 0, sadness: 0, surprise: 0, disgust: 0, fear: 0, neutral: 1 };

  const currentEmotion = stream.results.length > 0
    ? stream.results[stream.results.length - 1]
    : null;

  const timeSeriesData = stream.results.map((r, i) => ({
    time: i,
    emotion: r.emotion,
    valence: r.valence,
    arousal: r.arousal,
    probabilities: r.probabilities,
  }));

  const avgContributions = stream.results.length > 0
    ? stream.results.reduce(
        (acc, r) => {
          acc.audio += r.modalityContributions.audio;
          acc.video += r.modalityContributions.video;
          acc.text += r.modalityContributions.text;
          return acc;
        },
        { audio: 0, video: 0, text: 0 }
      )
    : { audio: 0, video: 0, text: 0 };

  if (stream.results.length > 0) {
    avgContributions.audio /= stream.results.length;
    avgContributions.video /= stream.results.length;
    avgContributions.text /= stream.results.length;
  }

  return (
    <div className="min-h-screen pt-24 pb-12">
      <div className="container mx-auto px-4">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold font-display mb-4">
            实时<span className="text-gradient">情感分析</span>
          </h1>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            通过WebSocket实时传输音视频数据，动态展示情感变化过程
          </p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-6">
            <div className="glass-card p-6">
              <div className="relative aspect-video rounded-2xl overflow-hidden bg-black/50 border border-white/10 mb-6">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-cover"
                  style={{ transform: 'scaleX(-1)' }}
                />
                <canvas ref={canvasRef} className="hidden" />

                {!isCameraActive && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                    <div className="text-center">
                      <Camera className="w-16 h-16 mx-auto mb-4 text-white/50" />
                      <p className="text-white/70">点击下方按钮开启摄像头</p>
                    </div>
                  </div>
                )}

                {stream.isStreaming && (
                  <div className="absolute top-4 left-4 flex items-center gap-2 bg-black/60 backdrop-blur-sm px-3 py-2 rounded-full">
                    <div className="recording-indicator" />
                    <span className="text-white font-mono text-sm">实时分析中</span>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-center gap-4">
                {!isCameraActive ? (
                  <button
                    onClick={startCamera}
                    className="btn-primary flex items-center gap-2"
                  >
                    <Power className="w-5 h-5" />
                    开启摄像头
                  </button>
                ) : (
                  <>
                    {!stream.isStreaming ? (
                      <button
                        onClick={startStreaming}
                        className="btn-primary flex items-center gap-2"
                      >
                        <Play className="w-5 h-5" />
                        开始分析
                      </button>
                    ) : (
                      <button
                        onClick={stopStreaming}
                        className="btn-danger flex items-center gap-2"
                      >
                        <Pause className="w-5 h-5" />
                        暂停分析
                      </button>
                    )}
                    <button
                      onClick={stopCamera}
                      className="btn-secondary flex items-center gap-2"
                    >
                      <Power className="w-5 h-5" />
                      关闭
                    </button>
                  </>
                )}
              </div>

              <div className="mt-4 flex items-center justify-center gap-4">
                <div className="flex items-center gap-2">
                  <span className={`status-dot ${stream.isConnected ? 'bg-green-500 animate-pulse-fast' : 'bg-red-500'}`} />
                  <span className="text-sm text-muted-foreground">
                    {stream.isConnected ? '已连接' : '未连接'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`status-dot ${stream.isStreaming ? 'bg-green-500 animate-pulse-fast' : 'bg-gray-500'}`} />
                  <span className="text-sm text-muted-foreground">
                    {stream.isStreaming ? '分析中' : '已停止'}
                  </span>
                </div>
              </div>
            </div>

            {currentEmotion && (
              <div className="glass-card p-6">
                <h2 className="text-xl font-bold mb-4 text-center">当前情感</h2>
                <EmotionDisplay
                  probabilities={currentEmotion.probabilities}
                  size="md"
                />
              </div>
            )}

            {stream.results.length > 0 && (
              <div className="glass-card p-6">
                <h2 className="text-lg font-bold mb-4">平均模态贡献</h2>
                <div className="space-y-4">
                  {(['audio', 'video', 'text'] as const).map((modality) => (
                    <div key={modality}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm text-muted-foreground">
                          {modality === 'audio' ? '语音' : modality === 'video' ? '视频' : '文本'}
                        </span>
                        <span className="text-sm font-mono" style={{ color: `var(--modality-${modality})` }}>
                          {formatPercent(avgContributions[modality] / (Object.values(avgContributions).reduce((a, b) => a + b, 0) || 1), 0)}
                        </span>
                      </div>
                      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${(avgContributions[modality] / Math.max(...Object.values(avgContributions), 0.01)) * 100}%`,
                            backgroundColor: `var(--modality-${modality})`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="lg:col-span-2 space-y-6">
            {stream.results.length > 0 && (
              <>
                <div className="glass-card p-6">
                  <h2 className="text-xl font-bold mb-4">实时情感概率</h2>
                  <div className="grid grid-cols-7 gap-2">
                    {(Object.entries(currentEmotion?.probabilities || {}) as [string, number][]).map(([emotion, prob]) => (
                      <div key={emotion} className="text-center">
                        <div
                          className="h-24 rounded-lg mb-2 flex items-end justify-center p-2 overflow-hidden"
                          style={{
                            backgroundColor: `${EMOTION_COLORS[emotion as keyof typeof EMOTION_COLORS]}20`,
                            border: `1px solid ${EMOTION_COLORS[emotion as keyof typeof EMOTION_COLORS]}30`,
                          }}
                        >
                          <div
                            className="w-full rounded transition-all duration-500"
                            style={{
                              height: `${prob * 100}%`,
                              backgroundColor: EMOTION_COLORS[emotion as keyof typeof EMOTION_COLORS],
                            }}
                          />
                        </div>
                        <p className="text-[10px] text-muted-foreground truncate">
                          {EMOTION_LABELS[emotion as keyof typeof EMOTION_LABELS]}
                        </p>
                        <p className="text-[10px] font-mono" style={{ color: EMOTION_COLORS[emotion as keyof typeof EMOTION_COLORS] }}>
                          {formatPercent(prob, 0)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="glass-card p-6">
                  <h2 className="text-xl font-bold mb-4">情感时序变化</h2>
                  <EmotionTimeSeries
                    data={timeSeriesData}
                    height={300}
                    showValenceArousal={true}
                  />
                </div>

                <div className="glass-card p-6">
                  <h2 className="text-xl font-bold mb-4">最近情感状态</h2>
                  <div className="flex flex-wrap gap-2">
                    {stream.results.slice(-10).reverse().map((result, index) => (
                      <EmotionBadge
                        key={index}
                        emotion={result.emotion}
                        probability={result.confidence}
                      />
                    ))}
                  </div>
                </div>
              </>
            )}

            {!stream.isStreaming && (
              <div className="glass-card p-12 text-center">
                <div className="w-20 h-20 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-6">
                  <Play className="w-10 h-10 text-primary" />
                </div>
                <h3 className="text-xl font-bold mb-2">开始实时分析</h3>
                <p className="text-muted-foreground max-w-md mx-auto">
                  开启摄像头并点击开始分析按钮，系统将实时分析您的情感变化
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default RealtimePage;
