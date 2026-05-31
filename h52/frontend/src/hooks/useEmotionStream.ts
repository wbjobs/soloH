import { useState, useRef, useEffect, useCallback } from 'react';
import { useAppStore } from '@/store';
import { createStreamClient, type EmotionStreamClient } from '@/services/websocket';
import type { StreamFrame } from '@/types';

const FRAME_INTERVAL = 500;
const VIDEO_CONSTRAINTS: MediaStreamConstraints = {
  video: {
    width: { ideal: 640 },
    height: { ideal: 480 },
    frameRate: { ideal: 15 },
    facingMode: 'user',
  },
  audio: {
    sampleRate: 16000,
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: true,
  },
};

export const useEmotionStream = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const clientRef = useRef<EmotionStreamClient | null>(null);
  const frameTimerRef = useRef<number | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const {
    stream,
    setStreamConnected,
    setStreamActive,
    addStreamResult,
    clearStreamResults,
    setStreamError,
    resetStream,
  } = useAppStore();

  const [isCameraActive, setIsCameraActive] = useState(false);

  const captureFrame = useCallback((): string | null => {
    if (!videoRef.current || !canvasRef.current || !streamRef.current) {
      return null;
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    if (!ctx) return null;

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    return canvas.toDataURL('image/jpeg', 0.6).split(',')[1];
  }, []);

  const sendFrame = useCallback(() => {
    if (!clientRef.current?.isConnected() || !stream.isStreaming) return;

    const frameData = captureFrame();
    if (!frameData) return;

    const frame: StreamFrame = {
      frame: frameData,
      timestamp: Date.now(),
    };

    clientRef.current.sendFrame(frame);
  }, [captureFrame, stream.isStreaming]);

  const stopCamera = useCallback(() => {
    if (mediaRecorderRef.current) {
      if (mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      mediaRecorderRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    if (frameTimerRef.current) {
      clearInterval(frameTimerRef.current);
      frameTimerRef.current = null;
    }

    audioChunksRef.current = [];
    setIsCameraActive(false);
  }, []);

  const startCamera = useCallback(async () => {
    try {
      stopCamera();
      clearStreamResults();
      setStreamError(null);

      const stream = await navigator.mediaDevices.getUserMedia(VIDEO_CONSTRAINTS);
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.muted = true;
      }

      const audioTrack = stream.getAudioTracks()[0];
      if (audioTrack) {
        const audioStream = new MediaStream([audioTrack]);
        const mediaRecorder = new MediaRecorder(audioStream, {
          mimeType: 'audio/webm;codecs=opus',
          audioBitsPerSecond: 16000,
        });

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };

        mediaRecorder.start(1000);
        mediaRecorderRef.current = mediaRecorder;
      }

      setIsCameraActive(true);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : '无法访问摄像头';
      setStreamError(message);
      return false;
    }
  }, [stopCamera, clearStreamResults, setStreamError]);

  const connect = useCallback(async () => {
    try {
      if (clientRef.current) {
        clientRef.current.close();
      }

      const client = createStreamClient();
      clientRef.current = client;

      client.onOpen(() => {
        setStreamConnected(true);
        setStreamError(null);
      });

      client.onClose(() => {
        setStreamConnected(false);
        setStreamActive(false);
      });

      client.onError((error) => {
        setStreamError(error);
      });

      client.onResult((result) => {
        addStreamResult(result);
      });

      await client.connect();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : '连接失败';
      setStreamError(message);
      return false;
    }
  }, [setStreamConnected, setStreamActive, setStreamError, addStreamResult]);

  const startStreaming = useCallback(async () => {
    if (!isCameraActive) {
      const cameraStarted = await startCamera();
      if (!cameraStarted) return;
    }

    if (!clientRef.current?.isConnected()) {
      const connected = await connect();
      if (!connected) return;
    }

    clientRef.current?.startStream();
    setStreamActive(true);

    frameTimerRef.current = window.setInterval(sendFrame, FRAME_INTERVAL);
  }, [isCameraActive, startCamera, connect, sendFrame, setStreamActive]);

  const stopStreaming = useCallback(() => {
    if (frameTimerRef.current) {
      clearInterval(frameTimerRef.current);
      frameTimerRef.current = null;
    }

    if (clientRef.current?.isConnected()) {
      clientRef.current.stopStream();
    }

    setStreamActive(false);
  }, [setStreamActive]);

  const disconnect = useCallback(() => {
    stopStreaming();
    stopCamera();

    if (clientRef.current) {
      clientRef.current.close();
      clientRef.current = null;
    }

    resetStream();
  }, [stopStreaming, stopCamera, resetStream]);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    videoRef,
    canvasRef,
    stream,
    isCameraActive,
    startCamera,
    stopCamera,
    connect,
    startStreaming,
    stopStreaming,
    disconnect,
  };
};

export default useEmotionStream;
