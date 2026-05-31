import { useState, useRef, useEffect, useCallback } from 'react';
import { useAppStore } from '@/store';
import { uploadVideo, startAnalysis, getAnalysisStatus, getAnalysisResult } from '@/services/api';

const RECORDING_DURATION = 60;
const CONSTRAINTS: MediaStreamConstraints = {
  video: {
    width: { ideal: 1280 },
    height: { ideal: 720 },
    frameRate: { ideal: 30 },
    facingMode: 'user',
  },
  audio: {
    sampleRate: 48000,
    channelCount: 2,
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  },
};

export const useVideoRecorder = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const pollingRef = useRef<number | null>(null);

  const {
    recording,
    analysis,
    setRecordingStatus,
    setRecordingDuration,
    setVideoUrl,
    setVideoId,
    setRecordingError,
    resetRecording,
    setAnalysisTaskId,
    setAnalysisStatus,
    setAnalysisProgress,
    setAnalysisResult,
    setAnalysisError,
    resetAnalysis,
  } = useAppStore();

  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);

  const enumerateDevices = useCallback(async () => {
    try {
      const allDevices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = allDevices.filter((d) => d.kind === 'videoinput');
      setDevices(videoDevices);
    } catch (error) {
      console.error('Failed to enumerate devices:', error);
    }
  }, []);

  const stopMediaStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  const requestCamera = useCallback(async (deviceId?: string) => {
    try {
      setRecordingStatus('requesting');
      stopMediaStream();

      const constraints: MediaStreamConstraints = {
        ...CONSTRAINTS,
        video: deviceId
          ? { ...(CONSTRAINTS.video as MediaTrackConstraints), deviceId: { exact: deviceId } }
          : CONSTRAINTS.video,
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.muted = true;
      }

      setRecordingStatus('idle');
      enumerateDevices();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : '无法访问摄像头';
      setRecordingError(message);
      setRecordingStatus('error');
      return false;
    }
  }, [setRecordingStatus, setRecordingError, stopMediaStream, enumerateDevices]);

  const startRecording = useCallback(async () => {
    if (!streamRef.current) {
      const success = await requestCamera();
      if (!success) return;
    }

    try {
      resetAnalysis();
      recordedChunksRef.current = [];

      const mimeTypes = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];
      const mimeType = mimeTypes.find((type) => MediaRecorder.isTypeSupported(type)) || 'video/webm';

      const mediaRecorder = new MediaRecorder(streamRef.current!, {
        mimeType,
        videoBitsPerSecond: 2500000,
        audioBitsPerSecond: 128000,
      });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordedChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(recordedChunksRef.current, { type: mimeType });
        const url = URL.createObjectURL(blob);
        setVideoUrl(url);
        setRecordingStatus('stopped');
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(1000);

      setRecordingDuration(0);
      setRecordingStatus('recording');

      let seconds = 0;
      timerRef.current = window.setInterval(() => {
        seconds++;
        setRecordingDuration(seconds);

        if (seconds >= RECORDING_DURATION) {
          stopRecording();
        }
      }, 1000);
    } catch (error) {
      const message = error instanceof Error ? error.message : '录制失败';
      setRecordingError(message);
      setRecordingStatus('error');
    }
  }, [requestCamera, resetAnalysis, setRecordingDuration, setRecordingStatus, setRecordingError, setVideoUrl]);

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }

    stopMediaStream();
  }, [stopMediaStream]);

  const uploadAndAnalyze = useCallback(async () => {
    if (!recordedChunksRef.current.length) {
      setRecordingError('没有录制数据');
      return;
    }

    try {
      setRecordingStatus('uploading');
      setAnalysisStatus('queued');

      const mimeType = mediaRecorderRef.current?.mimeType || 'video/webm';
      const blob = new Blob(recordedChunksRef.current, { type: mimeType });
      const file = new File([blob], `recording_${Date.now()}.webm`, { type: mimeType });

      const uploadProgress = (progress: number) => {
        setAnalysisProgress(progress * 0.4);
      };

      const uploadResponse = await uploadVideo(file, uploadProgress);
      setVideoId(uploadResponse.videoId);
      setAnalysisProgress(40);

      setRecordingStatus('analyzing');
      setAnalysisStatus('processing');

      const analyzeResponse = await startAnalysis(uploadResponse.videoId, {
        includeAttention: true,
        timeStep: 1.0,
      });
      setAnalysisTaskId(analyzeResponse.taskId);
      setAnalysisProgress(50);

      const pollStatus = async () => {
        try {
          const status = await getAnalysisStatus(analyzeResponse.taskId);
          setAnalysisProgress(50 + status.progress * 0.5);

          if (status.status === 'completed') {
            const result = await getAnalysisResult(analyzeResponse.taskId);
            setAnalysisResult(result.result);
            setRecordingStatus('completed');
            setAnalysisProgress(100);
            return;
          }

          if (status.status === 'failed') {
            setAnalysisError('分析失败');
            setRecordingStatus('error');
            return;
          }

          pollingRef.current = window.setTimeout(pollStatus, 1000);
        } catch (error) {
          const message = error instanceof Error ? error.message : '状态查询失败';
          setAnalysisError(message);
          setRecordingStatus('error');
        }
      };

      pollingRef.current = window.setTimeout(pollStatus, 1000);
    } catch (error) {
      const message = error instanceof Error ? error.message : '上传失败';
      setRecordingError(message);
      setRecordingStatus('error');
      setAnalysisError(message);
    }
  }, [setRecordingStatus, setRecordingError, setVideoId, setAnalysisStatus, setAnalysisProgress, setAnalysisTaskId, setAnalysisResult, setAnalysisError]);

  const reset = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (pollingRef.current) {
      clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
    if (recording.videoUrl) {
      URL.revokeObjectURL(recording.videoUrl);
    }
    stopMediaStream();
    recordedChunksRef.current = [];
    resetRecording();
    resetAnalysis();
  }, [recording.videoUrl, stopMediaStream, resetRecording, resetAnalysis]);

  useEffect(() => {
    enumerateDevices();
    return () => {
      reset();
    };
  }, [enumerateDevices, reset]);

  return {
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
  };
};

export default useVideoRecorder;
