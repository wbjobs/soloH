import { useCallback } from 'react';
import { Video, Camera, StopCircle, Upload, RotateCcw, Settings, AlertCircle } from 'lucide-react';
import { useVideoRecorder } from '@/hooks/useVideoRecorder';
import { cn, formatTime } from '@/utils';

interface VideoRecorderProps {
  onComplete?: (resultId: string) => void;
}

export function VideoRecorder({ onComplete }: VideoRecorderProps) {
  const {
    videoRef,
    devices,
    recording,
    analysis,
    requestCamera,
    startRecording,
    stopRecording,
    uploadAndAnalyze,
    reset,
    RECORDING_DURATION,
  } = useVideoRecorder();

  const progress = (recording.duration / RECORDING_DURATION) * 100;
  const isRecording = recording.status === 'recording';
  const isProcessing = recording.status === 'uploading' || recording.status === 'analyzing';

  const handleRecordClick = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else if (recording.status === 'idle' || recording.status === 'stopped') {
      if (recording.status === 'stopped') {
        reset();
      }
      startRecording();
    }
  }, [isRecording, recording.status, startRecording, stopRecording, reset]);

  const handleUpload = useCallback(() => {
    uploadAndAnalyze();
  }, [uploadAndAnalyze]);

  const handleReset = useCallback(() => {
    reset();
  }, [reset]);

  const circumference = 2 * Math.PI * 56;
  const strokeDashoffset = circumference - (progress / 100) * circumference;

  const getStatusText = () => {
    switch (recording.status) {
      case 'requesting':
        return '正在请求摄像头权限...';
      case 'recording':
        return `录制中 ${formatTime(recording.duration)} / ${formatTime(RECORDING_DURATION)}`;
      case 'stopped':
        return '录制完成，点击上传分析';
      case 'uploading':
        return `上传中 ${Math.round(analysis.progress)}%`;
      case 'analyzing':
        return `分析中 ${Math.round(analysis.progress)}%`;
      case 'completed':
        return '分析完成！';
      case 'error':
        return recording.error || '发生错误';
      default:
        return '点击开始录制';
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto">
      <div className="glass-card p-6 relative overflow-hidden">
        <div className="absolute inset-0 grid-overlay opacity-30 pointer-events-none" />

        <div className="relative">
          <div className="relative aspect-video rounded-2xl overflow-hidden bg-black/50 border border-white/10">
            {recording.status === 'stopped' && recording.videoUrl ? (
              <video
                ref={videoRef}
                src={recording.videoUrl}
                controls
                className="w-full h-full object-cover"
                playsInline
              />
            ) : (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className={cn(
                  'w-full h-full object-cover transition-all duration-300',
                  isRecording && 'scale-[1.01]'
                )}
                style={{ transform: 'scaleX(-1)' }}
              />
            )}

            {recording.status === 'idle' && !recording.videoUrl && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                <div className="text-center">
                  <Camera className="w-16 h-16 mx-auto mb-4 text-white/50" />
                  <p className="text-white/70">点击下方按钮开始录制</p>
                </div>
              </div>
            )}

            {isRecording && (
              <div className="absolute top-4 left-4 flex items-center gap-2 bg-black/60 backdrop-blur-sm px-3 py-2 rounded-full">
                <div className="recording-indicator" />
                <span className="text-white font-mono text-sm">
                  {formatTime(recording.duration)}
                </span>
              </div>
            )}

            {isRecording && (
              <div className="absolute inset-0 border-4 border-red-500/30 rounded-2xl pointer-events-none animate-pulse-fast" />
            )}

            {isProcessing && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                <div className="text-center">
                  <div className="relative w-24 h-24 mx-auto mb-4">
                    <svg className="w-24 h-24 progress-ring" viewBox="0 0 120 120">
                      <circle
                        cx="60"
                        cy="60"
                        r="56"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="8"
                        className="text-white/10"
                      />
                      <circle
                        cx="60"
                        cy="60"
                        r="56"
                        fill="none"
                        stroke="url(#gradient)"
                        strokeWidth="8"
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        className="transition-all duration-300"
                      />
                      <defs>
                        <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                          <stop offset="0%" stopColor="#667eea" />
                          <stop offset="100%" stopColor="#764ba2" />
                        </linearGradient>
                      </defs>
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-2xl font-bold text-white font-mono">
                        {Math.round(analysis.progress)}%
                      </span>
                    </div>
                  </div>
                  <p className="text-white/90 font-medium">{getStatusText()}</p>
                </div>
              </div>
            )}

            {recording.status === 'error' && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                <div className="text-center text-red-400">
                  <AlertCircle className="w-16 h-16 mx-auto mb-4" />
                  <p className="text-lg font-medium">{recording.error}</p>
                </div>
              </div>
            )}
          </div>

          <div className="mt-6 flex items-center justify-between">
            <div className="flex items-center gap-2">
              {devices.length > 1 && (
                <select
                  className="bg-card border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                  onChange={(e) => requestCamera(e.target.value)}
                  disabled={isRecording || isProcessing}
                >
                  {devices.map((device, index) => (
                    <option key={device.deviceId} value={device.deviceId}>
                      {device.label || `摄像头 ${index + 1}`}
                    </option>
                  ))}
                </select>
              )}
              <button
                className="p-2 rounded-lg bg-card border border-white/10 hover:bg-white/5 transition-colors"
                title="设置"
                disabled={isRecording || isProcessing}
              >
                <Settings className="w-5 h-5" />
              </button>
            </div>

            <p className="text-muted-foreground text-sm">{getStatusText()}</p>
          </div>

          <div className="mt-6 flex items-center justify-center gap-4">
            {recording.status === 'stopped' && (
              <>
                <button
                  onClick={handleReset}
                  className="btn-secondary flex items-center gap-2"
                  disabled={isProcessing}
                >
                  <RotateCcw className="w-5 h-5" />
                  重新录制
                </button>
                <button
                  onClick={handleUpload}
                  className="btn-primary flex items-center gap-2"
                  disabled={isProcessing}
                >
                  <Upload className="w-5 h-5" />
                  上传并分析
                </button>
              </>
            )}

            {recording.status === 'completed' && (
              <button onClick={handleReset} className="btn-primary flex items-center gap-2">
                <RotateCcw className="w-5 h-5" />
                新的录制
              </button>
            )}

            {(recording.status === 'idle' || isRecording) && (
              <button
                onClick={handleRecordClick}
                className={cn(
                  'relative w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300',
                  isRecording
                    ? 'bg-red-500 hover:bg-red-600 shadow-[0_0_40px_rgba(239,68,68,0.5)]'
                    : 'bg-gradient-primary hover:shadow-[0_0_40px_rgba(102,126,234,0.5)] hover:scale-105',
                  isProcessing && 'opacity-50 cursor-not-allowed'
                )}
                disabled={isProcessing || recording.status === 'requesting'}
              >
                {isRecording ? (
                  <StopCircle className="w-10 h-10 text-white" />
                ) : (
                  <Video className="w-10 h-10 text-white" />
                )}

                {isRecording && (
                  <>
                    <span className="absolute inset-0 rounded-full bg-red-500/30 animate-ripple" style={{ animationDelay: '0s' }} />
                    <span className="absolute inset-0 rounded-full bg-red-500/30 animate-ripple" style={{ animationDelay: '0.5s' }} />
                    <span className="absolute inset-0 rounded-full bg-red-500/30 animate-ripple" style={{ animationDelay: '1s' }} />
                  </>
                )}
              </button>
            )}
          </div>

          {!isProcessing && recording.status !== 'error' && (
            <div className="mt-6">
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-300',
                    isRecording
                      ? 'bg-gradient-to-r from-red-500 to-orange-500'
                      : 'bg-gradient-primary'
                  )}
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="mt-2 flex justify-between text-xs text-muted-foreground">
                <span>{formatTime(0)}</span>
                <span>{formatTime(RECORDING_DURATION / 2)}</span>
                <span>{formatTime(RECORDING_DURATION)}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {analysis.result && onComplete && (
        <div className="mt-6 text-center animate-slide-up">
          <button
            onClick={() => onComplete(analysis.result!.id)}
            className="btn-primary"
          >
            查看分析结果
          </button>
        </div>
      )}
    </div>
  );
}

export default VideoRecorder;
