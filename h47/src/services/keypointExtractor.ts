import { FrameData, HandLandmark, PoseLandmark, Handedness, FaceLandmark, NonManualFeatures } from '@/types';
import { facialExpressionService } from './facialExpressionService';

declare global {
  interface Window {
    Hands: any;
    Pose: any;
    FaceMesh: any;
    Camera: any;
    drawConnectors: any;
    drawLandmarks: any;
    POSE_CONNECTIONS: any;
    HAND_CONNECTIONS: any;
    FACE_MESH_TESSELATION: any;
    FACE_MESH_RIGHT_EYE: any;
    FACE_MESH_LEFT_EYE: any;
    FACE_MESH_RIGHT_IRIS: any;
    FACE_MESH_LEFT_IRIS: any;
    FACE_MESH_LIPS: any;
  }
}

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17]
];

export class KeypointExtractor {
  private hands: any = null;
  private pose: any = null;
  private faceMesh: any = null;
  private isInitialized = false;
  private enableFaceDetection = true;
  private onResultsCallback: ((results: any) => void) | null = null;

  async init(enableFaceDetection: boolean = true): Promise<void> {
    if (this.isInitialized) return;
    this.enableFaceDetection = enableFaceDetection;

    await this.loadMediaPipeScripts();

    this.hands = new window.Hands({
      locateFile: (file: string) => {
        return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
      }
    });

    this.hands.setOptions({
      maxNumHands: 2,
      modelComplexity: 1,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5
    });

    this.hands.onResults((results: any) => this.handleHandResults(results));

    this.pose = new window.Pose({
      locateFile: (file: string) => {
        return `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`;
      }
    });

    this.pose.setOptions({
      modelComplexity: 1,
      smoothLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5
    });

    this.pose.onResults((results: any) => this.handlePoseResults(results));

    if (this.enableFaceDetection) {
      this.faceMesh = new window.FaceMesh({
        locateFile: (file: string) => {
          return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`;
        }
      });

      this.faceMesh.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
      });

      this.faceMesh.onResults((results: any) => this.handleFaceResults(results));
    }

    this.isInitialized = true;
  }

  private async loadMediaPipeScripts(): Promise<void> {
    const scripts = [
      'https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js',
      'https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils/drawing_utils.js',
      'https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js',
      'https://cdn.jsdelivr.net/npm/@mediapipe/pose/pose.js'
    ];

    for (const src of scripts) {
      await this.loadScript(src);
    }
  }

  private loadScript(src: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[src="${src}"]`)) {
        resolve();
        return;
      }

      const script = document.createElement('script');
      script.src = src;
      script.crossOrigin = 'anonymous';
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`Failed to load ${src}`));
      document.head.appendChild(script);
    });
  }

  private lastHandResults: any = null;
  private lastPoseResults: any = null;
  private lastFaceResults: any = null;
  private pendingFrameData: FrameData | null = null;

  private handleHandResults(results: any): void {
    this.lastHandResults = results;
    this.tryCombineResults();
  }

  private handlePoseResults(results: any): void {
    this.lastPoseResults = results;
    this.tryCombineResults();
  }

  private handleFaceResults(results: any): void {
    this.lastFaceResults = results;
    this.tryCombineResults();
  }

  private tryCombineResults(): void {
    const haveHandResults = !!this.lastHandResults;
    const havePoseResults = !!this.lastPoseResults;
    const haveFaceResults = !this.enableFaceDetection || !!this.lastFaceResults;

    if (haveHandResults && havePoseResults && haveFaceResults) {
      this.pendingFrameData = this.convertToFrameData(
        this.lastHandResults, 
        this.lastPoseResults,
        this.lastFaceResults
      );
      this.lastHandResults = null;
      this.lastPoseResults = null;
      this.lastFaceResults = null;
    }
  }

  async processFrame(videoElement: HTMLVideoElement): Promise<FrameData> {
    if (!this.isInitialized) {
      await this.init();
    }

    this.pendingFrameData = null;

    const sendPromises = [
      this.hands.send({ image: videoElement }),
      this.pose.send({ image: videoElement })
    ];

    if (this.enableFaceDetection && this.faceMesh) {
      sendPromises.push(this.faceMesh.send({ image: videoElement }));
    }

    await Promise.all(sendPromises);

    const timeout = Date.now() + 150;
    while (!this.pendingFrameData && Date.now() < timeout) {
      await new Promise(resolve => setTimeout(resolve, 10));
    }

    return this.pendingFrameData || this.createEmptyFrameData();
  }

  private convertToFrameData(handResults: any, poseResults: any, faceResults?: any): FrameData {
    const timestamp = Date.now();
    let leftHand: HandLandmark[] | null = null;
    let rightHand: HandLandmark[] | null = null;

    if (handResults.multiHandLandmarks && handResults.multiHandedness) {
      handResults.multiHandLandmarks.forEach((landmarks: any[], index: number) => {
        const handedness = handResults.multiHandedness[index]?.classification?.[0]?.label as Handedness;
        const convertedLandmarks = landmarks.map(lm => ({
          x: lm.x,
          y: lm.y,
          z: lm.z,
          visibility: lm.visibility ?? 1.0
        }));

        if (handedness === 'Left') {
          leftHand = convertedLandmarks;
        } else {
          rightHand = convertedLandmarks;
        }
      });
    }

    let pose: PoseLandmark[] = [];
    if (poseResults.poseLandmarks) {
      pose = poseResults.poseLandmarks.map((lm: any) => ({
        x: lm.x,
        y: lm.y,
        z: lm.z,
        visibility: lm.visibility ?? 0
      }));
    }

    let face: FaceLandmark[] | null = null;
    let nonManualFeatures: NonManualFeatures | null = null;

    if (this.enableFaceDetection && faceResults?.multiFaceLandmarks?.[0]) {
      face = faceResults.multiFaceLandmarks[0].map((lm: any) => ({
        x: lm.x,
        y: lm.y,
        z: lm.z,
        visibility: lm.visibility ?? 1.0
      }));

      nonManualFeatures = facialExpressionService.extractFacialFeatures(face, timestamp);
    }

    const features = this.extractFeatures(leftHand, rightHand, pose, face);

    return {
      timestamp,
      leftHand,
      rightHand,
      pose,
      face,
      nonManualFeatures,
      features
    };
  }

  private extractFeatures(
    leftHand: HandLandmark[] | null,
    rightHand: HandLandmark[] | null,
    pose: PoseLandmark[],
    face?: FaceLandmark[] | null
  ): number[] {
    const features: number[] = [];

    if (rightHand) {
      for (const lm of rightHand) {
        features.push(lm.x, lm.y, lm.z);
      }
    } else {
      for (let i = 0; i < 21 * 3; i++) {
        features.push(0);
      }
    }

    if (leftHand) {
      for (const lm of leftHand) {
        features.push(lm.x, lm.y, lm.z);
      }
    } else {
      for (let i = 0; i < 21 * 3; i++) {
        features.push(0);
      }
    }

    if (pose.length >= 33) {
      for (let i = 11; i <= 22; i++) {
        const lm = pose[i];
        features.push(lm.x, lm.y, lm.z, lm.visibility);
      }
    } else {
      for (let i = 0; i < 12 * 4; i++) {
        features.push(0);
      }
    }

    return features;
  }

  private createEmptyFrameData(): FrameData {
    return {
      timestamp: Date.now(),
      leftHand: null,
      rightHand: null,
      pose: [],
      face: null,
      nonManualFeatures: null,
      features: new Array(21 * 3 * 2 + 12 * 4 + 11 * 3).fill(0)
    };
  }

  drawOverlay(canvas: HTMLCanvasElement, frameData: FrameData, drawFace: boolean = true): void {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);

    ctx.save();
    ctx.translate(width, 0);
    ctx.scale(-1, 1);

    if (frameData.rightHand) {
      this.drawHand(ctx, frameData.rightHand, width, height, '#4ECDC4');
    }

    if (frameData.leftHand) {
      this.drawHand(ctx, frameData.leftHand, width, height, '#FF6B6B');
    }

    if (frameData.pose.length > 0) {
      this.drawPose(ctx, frameData.pose, width, height);
    }

    if (drawFace && frameData.face) {
      this.drawFace(ctx, frameData.face, width, height);
    }

    ctx.restore();
  }

  private drawHand(
    ctx: CanvasRenderingContext2D,
    landmarks: HandLandmark[],
    width: number,
    height: number,
    color: string
  ): void {
    ctx.fillStyle = color;
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;

    HAND_CONNECTIONS.forEach(([start, end]) => {
      const startLm = landmarks[start];
      const endLm = landmarks[end];
      if (startLm && endLm) {
        ctx.beginPath();
        ctx.moveTo(startLm.x * width, startLm.y * height);
        ctx.lineTo(endLm.x * width, endLm.y * height);
        ctx.stroke();
      }
    });

    landmarks.forEach(lm => {
      ctx.beginPath();
      ctx.arc(lm.x * width, lm.y * height, 5, 0, 2 * Math.PI);
      ctx.fill();
    });
  }

  private drawPose(
    ctx: CanvasRenderingContext2D,
    landmarks: PoseLandmark[],
    width: number,
    height: number
  ): void {
    ctx.fillStyle = '#0F3460';
    ctx.strokeStyle = '#0F3460';
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.6;

    for (let i = 11; i <= 22; i++) {
      const lm = landmarks[i];
      if (lm && lm.visibility > 0.5) {
        ctx.beginPath();
        ctx.arc(lm.x * width, lm.y * height, 4, 0, 2 * Math.PI);
        ctx.fill();
      }
    }

    const poseConnections = [
      [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
      [15, 17], [15, 19], [15, 21], [17, 19],
      [16, 18], [16, 20], [16, 22], [18, 20],
      [11, 23], [12, 24]
    ];

    poseConnections.forEach(([start, end]) => {
      const startLm = landmarks[start];
      const endLm = landmarks[end];
      if (startLm && endLm && startLm.visibility > 0.5 && endLm.visibility > 0.5) {
        ctx.beginPath();
        ctx.moveTo(startLm.x * width, startLm.y * height);
        ctx.lineTo(endLm.x * width, endLm.y * height);
        ctx.stroke();
      }
    });

    ctx.globalAlpha = 1;
  }

  private drawFace(
    ctx: CanvasRenderingContext2D,
    landmarks: FaceLandmark[],
    width: number,
    height: number
  ): void {
    const faceIndices = {
      eyebrow: [107, 105, 336, 334],
      eyes: [159, 145, 386, 374],
      mouth: [61, 291, 13, 14],
      outline: [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    };

    ctx.strokeStyle = '#9333EA';
    ctx.fillStyle = '#9333EA';
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.4;

    const drawConnections = (indices: number[], closed: boolean = true) => {
      ctx.beginPath();
      for (let i = 0; i < indices.length; i++) {
        const lm = landmarks[indices[i]];
        if (lm) {
          if (i === 0) {
            ctx.moveTo(lm.x * width, lm.y * height);
          } else {
            ctx.lineTo(lm.x * width, lm.y * height);
          }
        }
      }
      if (closed) {
        ctx.closePath();
      }
      ctx.stroke();
    };

    drawConnections(faceIndices.outline, true);

    ctx.globalAlpha = 0.6;
    ctx.fillStyle = '#F472B6';
    faceIndices.mouth.forEach(idx => {
      const lm = landmarks[idx];
      if (lm) {
        ctx.beginPath();
        ctx.arc(lm.x * width, lm.y * height, 2, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    ctx.fillStyle = '#60A5FA';
    faceIndices.eyebrow.forEach(idx => {
      const lm = landmarks[idx];
      if (lm) {
        ctx.beginPath();
        ctx.arc(lm.x * width, lm.y * height, 2, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    ctx.fillStyle = '#34D399';
    faceIndices.eyes.forEach(idx => {
      const lm = landmarks[idx];
      if (lm) {
        ctx.beginPath();
        ctx.arc(lm.x * width, lm.y * height, 2, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    ctx.globalAlpha = 1;
  }

  close(): void {
    if (this.hands) {
      this.hands.close();
      this.hands = null;
    }
    if (this.pose) {
      this.pose.close();
      this.pose = null;
    }
    if (this.faceMesh) {
      this.faceMesh.close();
      this.faceMesh = null;
    }
    this.isInitialized = false;
  }

  isReady(): boolean {
    return this.isInitialized;
  }
}

export const keypointExtractor = new KeypointExtractor();
