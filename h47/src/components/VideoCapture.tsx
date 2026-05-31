import { useEffect, useRef, useState } from 'react';
import { cameraService } from '@/services/cameraService';
import { keypointExtractor } from '@/services/keypointExtractor';
import { useAppStore } from '@/store/appStore';
import { Loader2, Eye, EyeOff, AlertCircle } from 'lucide-react';

const VideoCapture = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);
  const [isLoading, setIsLoading] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);

  const {
    isRecording,
    isPaused,
    showOverlay,
    isCameraActive,
    isModelLoaded,
    setCameraActive,
    setModelLoaded,
    addFrame,
    processFrameForRecognition,
    setError,
    setProcessingStatus,
    latestFrame,
    enableFaceDetection,
    latestNonManualFeatures
  } = useAppStore();

  useEffect(() => {
    const initCamera = async () => {
      setIsLoading(true);
      setInitError(null);
      setProcessingStatus('正在启动摄像头...');

      try {
        await cameraService.start();
        setCameraActive(true);

        if (videoRef.current) {
          videoRef.current.srcObject = cameraService.getStream();
          await videoRef.current.play();
        }

        setProcessingStatus('正在加载手势识别模型...');
        await keypointExtractor.init(enableFaceDetection);
        setModelLoaded(true);
        setProcessingStatus('');

        startProcessing();
      } catch (err) {
        const message = err instanceof Error ? err.message : '启动摄像头失败';
        setInitError(message);
        setError(message);
        setProcessingStatus('');
      } finally {
        setIsLoading(false);
      }
    };

    initCamera();

    return () => {
      stopProcessing();
      cameraService.stop();
      keypointExtractor.close();
      setCameraActive(false);
      setModelLoaded(false);
    };
  }, []);

  const startProcessing = () => {
    const processFrame = async () => {
      if (!videoRef.current || !canvasRef.current) {
        animationRef.current = requestAnimationFrame(processFrame);
        return;
      }

      const video = videoRef.current;
      const canvas = canvasRef.current;

      if (video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        try {
          const frameData = await keypointExtractor.processFrame(video);
          addFrame(frameData);

          if (isRecording && !isPaused) {
            processFrameForRecognition(frameData);
          }

          if (showOverlay) {
            keypointExtractor.drawOverlay(canvas, frameData, enableFaceDetection);
          } else {
            const ctx = canvas.getContext('2d');
            if (ctx) {
              ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
          }
        } catch (e) {
          console.error('Frame processing error:', e);
        }
      }

      animationRef.current = requestAnimationFrame(processFrame);
    };

    animationRef.current = requestAnimationFrame(processFrame);
  };

  const stopProcessing = () => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }
  };

  const toggleOverlay = () => {
    useAppStore.getState().setShowOverlay(!showOverlay);
  };

  if (initError) {
    return (
      <div className="relative w-full aspect-video bg-slate-800 rounded-2xl overflow-hidden flex items-center justify-center">
        <div className="text-center p-8">
          <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-8 h-8 text-red-400" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">摄像头访问失败</h3>
          <p className="text-slate-400 text-sm max-w-md">{initError}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-6 py-2 bg-teal-500 hover:bg-teal-600 text-white rounded-lg transition-colors"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full aspect-video bg-slate-900 rounded-2xl overflow-hidden">
      {isLoading && (
        <div className="absolute inset-0 z-20 bg-slate-900/90 flex flex-col items-center justify-center">
          <Loader2 className="w-12 h-12 text-teal-400 animate-spin mb-4" />
          <p className="text-slate-300 text-sm">
            {isCameraActive ? '正在加载手势识别模型...' : '正在启动摄像头...'}
          </p>
        </div>
      )}

      <video
        ref={videoRef}
        className="absolute inset-0 w-full h-full object-cover transform scale-x-[-1]"
        playsInline
        muted
      />

      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full object-cover pointer-events-none"
      />

      <div className="absolute top-4 left-4 flex items-center gap-2">
        <div
          className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-2 ${
            isRecording
              ? 'bg-red-500/90 text-white'
              : isPaused
              ? 'bg-amber-500/90 text-white'
              : 'bg-slate-800/80 text-slate-300'
          }`}
        >
          {isRecording && (
            <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
          )}
          {isRecording ? '录制中' : isPaused ? '已暂停' : '准备就绪'}
        </div>

        {isModelLoaded && (
          <div className="px-3 py-1.5 rounded-full text-xs font-medium bg-green-500/20 text-green-400 border border-green-500/30">
            模型已加载
          </div>
        )}
      </div>

      <div className="absolute top-4 right-4">
        <button
          onClick={toggleOverlay}
          className={`p-2 rounded-lg transition-all duration-200 ${
            showOverlay
              ? 'bg-teal-500/30 text-teal-400 border border-teal-500/30'
              : 'bg-slate-800/80 text-slate-400 hover:text-white'
          }`}
          title={showOverlay ? '隐藏关键点' : '显示关键点'}
        >
          {showOverlay ? <Eye className="w-5 h-5" /> : <EyeOff className="w-5 h-5" />}
        </button>
      </div>

      {isPaused && (
        <div className="absolute inset-0 bg-slate-900/50 flex items-center justify-center">
          <div className="px-6 py-3 bg-slate-800/90 rounded-xl text-white font-medium">
            已暂停
          </div>
        </div>
      )}

      <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between text-xs text-slate-400">
        <span>
          {latestFrame
            ? `左手: ${latestFrame.leftHand ? '检测中' : '未检测'} | 右手: ${
                latestFrame.rightHand ? '检测中' : '未检测'
              }`
            : '等待手势...'}
        </span>
        <span>
          MediaPipe Hands + Pose
          {enableFaceDetection && (
            <span className="ml-2">
              {latestNonManualFeatures ? (
                <span className="text-pink-400">+ 面部检测中</span>
              ) : (
                <span className="text-slate-600">+ 面部待检测</span>
              )}
            </span>
          )}
        </span>
      </div>
    </div>
  );
};

export default VideoCapture;
