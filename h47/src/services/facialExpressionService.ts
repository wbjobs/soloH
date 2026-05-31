import { FaceLandmark, FacialExpression, MouthShape, NonManualFeatures } from '@/types';

const FACE_LANDMARK_INDICES = {
  LEFT_EYEBROW_INNER: 107,
  LEFT_EYEBROW_OUTER: 105,
  RIGHT_EYEBROW_INNER: 336,
  RIGHT_EYEBROW_OUTER: 334,
  LEFT_EYE_UPPER: 159,
  LEFT_EYE_LOWER: 145,
  RIGHT_EYE_UPPER: 386,
  RIGHT_EYE_LOWER: 374,
  MOUTH_LEFT: 61,
  MOUTH_RIGHT: 291,
  MOUTH_UPPER: 13,
  MOUTH_LOWER: 14,
  MOUTH_UPPER_LIP: 12,
  MOUTH_LOWER_LIP: 15,
  NOSE_TIP: 1,
  FOREHEAD: 10,
  CHIN: 152,
  LEFT_CHEEK: 116,
  RIGHT_CHEEK: 345
};

const EXPRESSION_THRESHOLDS = {
  eyebrowRaise: 0.08,
  mouthOpen: 0.03,
  lipCornerRaise: 0.02,
  eyebrowFurrow: 0.05,
  mouthStretch: 0.05
};

const MOUTH_SHAPES: { [key: string]: { widthRatio: [number, number]; heightRatio: [number, number]; corners: string } } = {
  closed: { widthRatio: [0.4, 0.6], heightRatio: [0, 0.05], corners: 'neutral' },
  open: { widthRatio: [0.3, 0.7], heightRatio: [0.15, 0.5], corners: 'neutral' },
  rounded: { widthRatio: [0.2, 0.45], heightRatio: [0.1, 0.4], corners: 'rounded' },
  spread: { widthRatio: [0.6, 0.9], heightRatio: [0.05, 0.25], corners: 'spread' },
  pursed: { widthRatio: [0.15, 0.35], heightRatio: [0.02, 0.15], corners: 'pursed' }
};

const FACIAL_EXPRESSION_WEIGHTS = {
  question: { eyebrowRaise: 0.4, mouthOpen: 0.3, headTilt: 0.3 },
  affirmative: { eyebrowLower: 0.3, headNod: 0.4, mouthClosed: 0.3 },
  negative: { eyebrowFurrow: 0.3, headShake: 0.4, mouthDown: 0.3 },
  happy: { lipCornerRaise: 0.5, cheekRaise: 0.3, eyeSquint: 0.2 },
  surprised: { eyebrowRaise: 0.4, eyeWiden: 0.3, mouthOpen: 0.3 }
};

export class FacialExpressionService {
  private expressionHistory: FacialExpression[] = [];
  private mouthShapeHistory: MouthShape[] = [];
  private headMotionHistory: { x: number; y: number }[] = [];
  private historySize: number = 30;
  private expressionBuffer: { expression: FacialExpression; timestamp: number }[] = [];
  private bufferDuration: number = 2000;

  constructor(historySize: number = 30) {
    this.historySize = historySize;
  }

  public extractFacialFeatures(
    faceLandmarks: FaceLandmark[],
    timestamp?: number
  ): NonManualFeatures | null {
    if (!faceLandmarks || faceLandmarks.length < 468) {
      return null;
    }

    const facialExpression = this.extractFacialExpression(faceLandmarks, timestamp);
    const mouthShape = this.extractMouthShape(faceLandmarks);
    const headTilt = this.calculateHeadTilt(faceLandmarks);
    const eyeGaze = this.calculateEyeGaze(faceLandmarks);
    const bodyPosture = this.detectPosture(faceLandmarks);

    this.expressionHistory.push(facialExpression);
    this.mouthShapeHistory.push(mouthShape);
    this.headMotionHistory.push(eyeGaze);

    if (this.expressionHistory.length > this.historySize) {
      this.expressionHistory.shift();
      this.mouthShapeHistory.shift();
      this.headMotionHistory.shift();
    }

    this.bufferExpression(facialExpression, timestamp || Date.now());

    return {
      facialExpression,
      mouthShape,
      headTilt,
      eyeGaze,
      bodyPosture
    };
  }

  private bufferExpression(expression: FacialExpression, timestamp: number): void {
    this.expressionBuffer.push({ expression, timestamp });
    const cutoff = timestamp - this.bufferDuration;
    this.expressionBuffer = this.expressionBuffer.filter(e => e.timestamp >= cutoff);
  }

  private extractFacialExpression(
    faceLandmarks: FaceLandmark[],
    timestamp?: number
  ): FacialExpression {
    const eyebrowRaise = this.calculateEyebrowRaise(faceLandmarks);
    const mouthOpen = this.calculateMouthOpenness(faceLandmarks);
    const lipCornerRaise = this.calculateLipCornerRaise(faceLandmarks);
    const eyebrowFurrow = this.calculateEyebrowFurrow(faceLandmarks);

    let expressionType: FacialExpression['type'] = 'neutral';
    let confidence = 0.5;

    const scores: { type: FacialExpression['type']; score: number }[] = [];

    const questionScore = eyebrowRaise * 0.4 + mouthOpen * 0.3 + this.detectHeadTiltQuestion(faceLandmarks) * 0.3;
    if (questionScore > 0.5) {
      scores.push({ type: 'questioning', score: questionScore });
    }

    const happyScore = lipCornerRaise * 0.5 + this.calculateCheekRaise(faceLandmarks) * 0.3 + this.calculateEyeSquint(faceLandmarks) * 0.2;
    if (happyScore > 0.3) {
      scores.push({ type: 'happy', score: happyScore });
    }

    const negativeScore = eyebrowFurrow * 0.3 + this.detectMouthDown(faceLandmarks) * 0.4 + this.detectHeadShake() * 0.3;
    if (negativeScore > 0.4) {
      scores.push({ type: 'negative', score: negativeScore });
    }

    const affirmativeScore = this.detectHeadNod() * 0.5 + (1 - mouthOpen) * 0.3 + (1 - eyebrowRaise) * 0.2;
    if (affirmativeScore > 0.6) {
      scores.push({ type: 'affirmative', score: affirmativeScore });
    }

    const surprisedScore = eyebrowRaise * 0.4 + this.calculateEyeWiden(faceLandmarks) * 0.3 + mouthOpen * 0.3;
    if (surprisedScore > 0.5) {
      scores.push({ type: 'surprised', score: surprisedScore });
    }

    const angryScore = eyebrowFurrow * 0.5 + this.detectLipPress(faceLandmarks) * 0.3 + (1 - lipCornerRaise) * 0.2;
    if (angryScore > 0.5) {
      scores.push({ type: 'angry', score: angryScore });
    }

    if (scores.length > 0) {
      scores.sort((a, b) => b.score - a.score);
      expressionType = scores[0].type;
      confidence = Math.min(0.95, scores[0].score);
    }

    return {
      type: expressionType,
      confidence,
      eyebrowRaise,
      mouthOpen,
      lipCornerRaise
    };
  }

  private extractMouthShape(faceLandmarks: FaceLandmark[]): MouthShape {
    const leftMouth = faceLandmarks[FACE_LANDMARK_INDICES.MOUTH_LEFT];
    const rightMouth = faceLandmarks[FACE_LANDMARK_INDICES.MOUTH_RIGHT];
    const upperMouth = faceLandmarks[FACE_LANDMARK_INDICES.MOUTH_UPPER];
    const lowerMouth = faceLandmarks[FACE_LANDMARK_INDICES.MOUTH_LOWER];

    const faceWidth = Math.abs(faceLandmarks[234].x - faceLandmarks[454].x);
    const faceHeight = Math.abs(faceLandmarks[10].y - faceLandmarks[152].y);

    const mouthWidth = Math.abs(rightMouth.x - leftMouth.x) / faceWidth;
    const mouthHeight = Math.abs(lowerMouth.y - upperMouth.y) / faceHeight;
    const aspectRatio = mouthHeight / (mouthWidth + 0.001);

    let mouthType: MouthShape['type'] = 'closed';
    let bestMatchScore = Infinity;

    for (const [type, params] of Object.entries(MOUTH_SHAPES)) {
      const widthInRange = mouthWidth >= params.widthRatio[0] && mouthWidth <= params.widthRatio[1];
      const heightInRange = mouthHeight >= params.heightRatio[0] && mouthHeight <= params.heightRatio[1];
      
      if (widthInRange && heightInRange) {
        const widthCenter = (params.widthRatio[0] + params.widthRatio[1]) / 2;
        const heightCenter = (params.heightRatio[0] + params.heightRatio[1]) / 2;
        const distance = Math.sqrt(
          Math.pow(mouthWidth - widthCenter, 2) + Math.pow(mouthHeight - heightCenter, 2)
        );
        
        if (distance < bestMatchScore) {
          bestMatchScore = distance;
          mouthType = type as MouthShape['type'];
        }
      }
    }

    if (mouthHeight > 0.05 && mouthType === 'closed') {
      mouthType = 'open';
    }

    return {
      type: mouthType,
      width: mouthWidth,
      height: mouthHeight,
      aspectRatio
    };
  }

  private calculateEyebrowRaise(faceLandmarks: FaceLandmark[]): number {
    const leftEyebrow = faceLandmarks[FACE_LANDMARK_INDICES.LEFT_EYEBROW_INNER];
    const rightEyebrow = faceLandmarks[FACE_LANDMARK_INDICES.RIGHT_EYEBROW_INNER];
    const leftEye = faceLandmarks[FACE_LANDMARK_INDICES.LEFT_EYE_UPPER];
    const rightEye = faceLandmarks[FACE_LANDMARK_INDICES.RIGHT_EYE_UPPER];

    const leftDistance = Math.abs(leftEyebrow.y - leftEye.y);
    const rightDistance = Math.abs(rightEyebrow.y - rightEye.y);
    const avgDistance = (leftDistance + rightDistance) / 2;

    const faceHeight = Math.abs(faceLandmarks[10].y - faceLandmarks[152].y);
    const normalizedDistance = avgDistance / faceHeight;

    return Math.min(1.0, Math.max(0, normalizedDistance / EXPRESSION_THRESHOLDS.eyebrowRaise));
  }

  private calculateEyebrowFurrow(faceLandmarks: FaceLandmark[]): number {
    const leftInner = faceLandmarks[FACE_LANDMARK_INDICES.LEFT_EYEBROW_INNER];
    const rightInner = faceLandmarks[FACE_LANDMARK_INDICES.RIGHT_EYEBROW_INNER];
    const noseTip = faceLandmarks[FACE_LANDMARK_INDICES.NOSE_TIP];

    const eyebrowDistance = Math.abs(rightInner.x - leftInner.x);
    const faceWidth = Math.abs(faceLandmarks[234].x - faceLandmarks[454].x);
    const normalizedDistance = eyebrowDistance / faceWidth;

    const baseDistance = 0.08;
    const furrowAmount = Math.max(0, (baseDistance - normalizedDistance) / baseDistance);

    return Math.min(1.0, furrowAmount);
  }

  private calculateMouthOpenness(faceLandmarks: FaceLandmark[]): number {
    const upperLip = faceLandmarks[FACE_LANDMARK_INDICES.MOUTH_UPPER];
    const lowerLip = faceLandmarks[FACE_LANDMARK_INDICES.MOUTH_LOWER];
    const mouthDistance = Math.abs(lowerLip.y - upperLip.y);
    const faceHeight = Math.abs(faceLandmarks[10].y - faceLandmarks[152].y);
    const normalizedDistance = mouthDistance / faceHeight;
    return Math.min(1.0, normalizedDistance / EXPRESSION_THRESHOLDS.mouthOpen);
  }

  private calculateLipCornerRaise(faceLandmarks: FaceLandmark[]): number {
    const leftCorner = faceLandmarks[FACE_LANDMARK_INDICES.MOUTH_LEFT];
    const rightCorner = faceLandmarks[FACE_LANDMARK_INDICES.MOUTH_RIGHT];
    const mouthCenter = faceLandmarks[FACE_LANDMARK_INDICES.MOUTH_UPPER];

    const leftRaise = mouthCenter.y - leftCorner.y;
    const rightRaise = mouthCenter.y - rightCorner.y;
    const avgRaise = (leftRaise + rightRaise) / 2;

    const faceHeight = Math.abs(faceLandmarks[10].y - faceLandmarks[152].y);
    const normalizedRaise = avgRaise / faceHeight;

    return Math.min(1.0, Math.max(0, normalizedRaise / EXPRESSION_THRESHOLDS.lipCornerRaise));
  }

  private calculateCheekRaise(faceLandmarks: FaceLandmark[]): number {
    const leftCheek = faceLandmarks[FACE_LANDMARK_INDICES.LEFT_CHEEK];
    const rightCheek = faceLandmarks[FACE_LANDMARK_INDICES.RIGHT_CHEEK];
    const leftEye = faceLandmarks[FACE_LANDMARK_INDICES.LEFT_EYE_LOWER];
    const rightEye = faceLandmarks[FACE_LANDMARK_INDICES.RIGHT_EYE_LOWER];

    const leftDistance = Math.abs(leftCheek.y - leftEye.y);
    const rightDistance = Math.abs(rightCheek.y - rightEye.y);
    const avgDistance = (leftDistance + rightDistance) / 2;

    const faceHeight = Math.abs(faceLandmarks[10].y - faceLandmarks[152].y);
    const normalized = avgDistance / faceHeight;

    return Math.min(1.0, Math.max(0, 1 - normalized / 0.15));
  }

  private calculateEyeSquint(faceLandmarks: FaceLandmark[]): number {
    const leftUpper = faceLandmarks[FACE_LANDMARK_INDICES.LEFT_EYE_UPPER];
    const leftLower = faceLandmarks[FACE_LANDMARK_INDICES.LEFT_EYE_LOWER];
    const rightUpper = faceLandmarks[FACE_LANDMARK_INDICES.RIGHT_EYE_UPPER];
    const rightLower = faceLandmarks[FACE_LANDMARK_INDICES.RIGHT_EYE_LOWER];

    const leftOpen = Math.abs(leftUpper.y - leftLower.y);
    const rightOpen = Math.abs(rightUpper.y - rightLower.y);
    const avgOpen = (leftOpen + rightOpen) / 2;

    const faceHeight = Math.abs(faceLandmarks[10].y - faceLandmarks[152].y);
    const normalized = avgOpen / faceHeight;

    return Math.min(1.0, Math.max(0, 1 - normalized / 0.08));
  }

  private calculateEyeWiden(faceLandmarks: FaceLandmark[]): number {
    const leftUpper = faceLandmarks[FACE_LANDMARK_INDICES.LEFT_EYE_UPPER];
    const leftLower = faceLandmarks[FACE_LANDMARK_INDICES.LEFT_EYE_LOWER];
    const rightUpper = faceLandmarks[FACE_LANDMARK_INDICES.RIGHT_EYE_UPPER];
    const rightLower = faceLandmarks[FACE_LANDMARK_INDICES.RIGHT_EYE_LOWER];

    const leftOpen = Math.abs(leftUpper.y - leftLower.y);
    const rightOpen = Math.abs(rightUpper.y - rightLower.y);
    const avgOpen = (leftOpen + rightOpen) / 2;

    const faceHeight = Math.abs(faceLandmarks[10].y - faceLandmarks[152].y);
    const normalized = avgOpen / faceHeight;

    return Math.min(1.0, normalized / 0.1);
  }

  private calculateHeadTilt(faceLandmarks: FaceLandmark[]): number {
    const leftEye = faceLandmarks[FACE_LANDMARK_INDICES.LEFT_EYE_UPPER];
    const rightEye = faceLandmarks[FACE_LANDMARK_INDICES.RIGHT_EYE_UPPER];
    const deltaY = rightEye.y - leftEye.y;
    const deltaX = rightEye.x - leftEye.x;
    const tiltAngle = Math.atan2(deltaY, deltaX) * (180 / Math.PI);
    return tiltAngle;
  }

  private calculateEyeGaze(faceLandmarks: FaceLandmark[]): { x: number; y: number } {
    const noseTip = faceLandmarks[FACE_LANDMARK_INDICES.NOSE_TIP];
    const faceCenterX = (faceLandmarks[234].x + faceLandmarks[454].x) / 2;
    const faceCenterY = (faceLandmarks[10].y + faceLandmarks[152].y) / 2;

    return {
      x: (noseTip.x - faceCenterX) * 2,
      y: (noseTip.y - faceCenterY) * 2
    };
  }

  private detectPosture(faceLandmarks: FaceLandmark[]): string {
    const forehead = faceLandmarks[FACE_LANDMARK_INDICES.FOREHEAD];
    const chin = faceLandmarks[FACE_LANDMARK_INDICES.CHIN];
    const noseTip = faceLandmarks[FACE_LANDMARK_INDICES.NOSE_TIP];

    const faceVertical = Math.abs(chin.y - forehead.y);
    const faceCenterX = (forehead.x + chin.x) / 2;
    const noseOffset = Math.abs(noseTip.x - faceCenterX);

    if (noseOffset > faceVertical * 0.3) {
      return 'turned_sideways';
    }

    if (noseTip.y < forehead.y + faceVertical * 0.4) {
      return 'head_down';
    }

    if (noseTip.y > forehead.y + faceVertical * 0.6) {
      return 'head_up';
    }

    return 'upright';
  }

  private detectHeadTiltQuestion(faceLandmarks: FaceLandmark[]): number {
    const tilt = Math.abs(this.calculateHeadTilt(faceLandmarks));
    return Math.min(1.0, tilt / 15);
  }

  private detectMouthDown(faceLandmarks: FaceLandmark[]): number {
    const raise = this.calculateLipCornerRaise(faceLandmarks);
    return Math.max(0, 1 - raise * 2);
  }

  private detectLipPress(faceLandmarks: FaceLandmark[]): number {
    const upperLip = faceLandmarks[FACE_LANDMARK_INDICES.MOUTH_UPPER_LIP];
    const lowerLip = faceLandmarks[FACE_LANDMARK_INDICES.MOUTH_LOWER_LIP];
    const distance = Math.abs(lowerLip.y - upperLip.y);
    const faceHeight = Math.abs(faceLandmarks[10].y - faceLandmarks[152].y);
    const normalized = distance / faceHeight;
    return Math.min(1.0, Math.max(0, 1 - normalized / 0.03));
  }

  private detectHeadNod(): number {
    if (this.headMotionHistory.length < 5) return 0;

    const recentY = this.headMotionHistory.slice(-5).map(m => m.y);
    const minY = Math.min(...recentY);
    const maxY = Math.max(...recentY);
    const range = maxY - minY;

    return Math.min(1.0, range / 0.1);
  }

  private detectHeadShake(): number {
    if (this.headMotionHistory.length < 5) return 0;

    const recentX = this.headMotionHistory.slice(-5).map(m => m.x);
    const minX = Math.min(...recentX);
    const maxX = Math.max(...recentX);
    const range = maxX - minX;

    return Math.min(1.0, range / 0.1);
  }

  public getDominantExpression(windowMs: number = 1000): { expression: FacialExpression['type']; confidence: number; duration: number } {
    const now = Date.now();
    const cutoff = now - windowMs;
    const recent = this.expressionBuffer.filter(e => e.timestamp >= cutoff);

    if (recent.length === 0) {
      return { expression: 'neutral', confidence: 0.5, duration: 0 };
    }

    const expressionCounts: Map<string, { count: number; totalConfidence: number }> = new Map();
    
    for (const item of recent) {
      const type = item.expression.type;
      if (!expressionCounts.has(type)) {
        expressionCounts.set(type, { count: 0, totalConfidence: 0 });
      }
      const entry = expressionCounts.get(type)!;
      entry.count++;
      entry.totalConfidence += item.expression.confidence;
    }

    let bestType = 'neutral';
    let bestScore = 0;

    expressionCounts.forEach((data, type) => {
      const avgConfidence = data.totalConfidence / data.count;
      const proportion = data.count / recent.length;
      const score = avgConfidence * proportion;
      
      if (score > bestScore) {
        bestScore = score;
        bestType = type;
      }
    });

    const duration = recent.length > 0 ? now - recent[0].timestamp : 0;

    return {
      expression: bestType as FacialExpression['type'],
      confidence: bestScore,
      duration
    };
  }

  public getExpressionSequence(): FacialExpression[] {
    return [...this.expressionHistory];
  }

  public getMouthShapeSequence(): MouthShape[] {
    return [...this.mouthShapeHistory];
  }

  public calculateNonManualScore(
    features: NonManualFeatures,
    expectedSentenceType: 'question' | 'affirmative' | 'negative' | 'neutral'
  ): { score: number; matchingFeatures: string[]; mismatchingFeatures: string[] } {
    const { facialExpression, mouthShape, headTilt } = features;
    let score = 0.5;
    const matching: string[] = [];
    const mismatching: string[] = [];

    switch (expectedSentenceType) {
      case 'question':
        if (facialExpression.type === 'questioning' || facialExpression.type === 'surprised') {
          score += 0.3;
          matching.push('疑问表情');
        } else {
          score -= 0.2;
          mismatching.push('缺少疑问表情（抬眉、歪头）');
        }
        if (facialExpression.eyebrowRaise > 0.5) {
          score += 0.1;
          matching.push('抬眉');
        }
        if (Math.abs(headTilt) > 5) {
          score += 0.1;
          matching.push('头部倾斜');
        }
        break;

      case 'affirmative':
        if (facialExpression.type === 'affirmative' || facialExpression.type === 'happy') {
          score += 0.2;
          matching.push('肯定表情');
        }
        if (this.detectHeadNod() > 0.5) {
          score += 0.2;
          matching.push('点头');
        }
        if (mouthShape.type === 'closed') {
          score += 0.1;
          matching.push('嘴部闭合');
        }
        break;

      case 'negative':
        if (facialExpression.type === 'negative' || facialExpression.type === 'angry' || facialExpression.type === 'sad') {
          score += 0.3;
          matching.push('否定表情');
        }
        if (this.detectHeadShake() > 0.5) {
          score += 0.2;
          matching.push('摇头');
        }
        if (facialExpression.eyebrowRaise < 0.3) {
          score += 0.1;
          matching.push('皱眉');
        }
        break;

      case 'neutral':
      default:
        if (facialExpression.type === 'neutral') {
          score += 0.2;
          matching.push('中性表情');
        }
        break;
    }

    if (mouthShape.type === 'open' && expectedSentenceType === 'question') {
      score += 0.1;
      matching.push('嘴部张开');
    }

    return {
      score: Math.max(0.1, Math.min(1.0, score)),
      matchingFeatures: matching,
      mismatchingFeatures: mismatching
    };
  }

  public detectSentenceTypeFromExpression(): { type: 'question' | 'affirmative' | 'negative' | 'neutral'; confidence: number } {
    const dominant = this.getDominantExpression(1500);

    switch (dominant.expression) {
      case 'questioning':
      case 'surprised':
        return { type: 'question', confidence: dominant.confidence };
      case 'affirmative':
      case 'happy':
        return { type: 'affirmative', confidence: dominant.confidence };
      case 'negative':
      case 'angry':
      case 'sad':
        return { type: 'negative', confidence: dominant.confidence };
      default:
        return { type: 'neutral', confidence: dominant.confidence };
    }
  }

  public reset(): void {
    this.expressionHistory = [];
    this.mouthShapeHistory = [];
    this.headMotionHistory = [];
    this.expressionBuffer = [];
  }

  public getFacialFeaturesSummary(features: NonManualFeatures): string {
    const parts: string[] = [];
    
    const expressionNames: Record<string, string> = {
      'neutral': '中性',
      'happy': '开心',
      'sad': '悲伤',
      'angry': '生气',
      'surprised': '惊讶',
      'questioning': '疑问',
      'affirmative': '肯定',
      'negative': '否定'
    };
    
    parts.push(`表情: ${expressionNames[features.facialExpression.type]} (${Math.round(features.facialExpression.confidence * 100)}%)`);
    
    const mouthNames: Record<string, string> = {
      'closed': '闭合',
      'open': '张开',
      'rounded': '圆形',
      'spread': '展开',
      'pursed': '噘嘴'
    };
    parts.push(`嘴型: ${mouthNames[features.mouthShape.type]}`);
    
    if (Math.abs(features.headTilt) > 5) {
      parts.push(`歪头: ${features.headTilt > 0 ? '右' : '左'}${Math.round(Math.abs(features.headTilt))}°`);
    }
    
    return parts.join(' | ');
  }
}

export const facialExpressionService = new FacialExpressionService(30);
