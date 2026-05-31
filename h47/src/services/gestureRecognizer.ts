import { FrameData, RecognizedWord, VocabularyItem } from '@/types';
import { VOCABULARY, getVocabularyMap } from '@/data/vocabulary';

export class GestureRecognizer {
  private vocabularyMap: Map<string, VocabularyItem> = new Map();
  private frameBuffer: FrameData[] = [];
  private lastRecognitionTime: number = 0;
  private minFramesPerWord: number = 20;
  private maxFramesPerWord: number = 80;
  private similarityThreshold: number = 0.7;
  private currentWordFrames: FrameData[] = [];
  private isInitialized: boolean = false;
  private motionHistory: number[] = [];
  private stableFrameCount: number = 0;
  private transitionFrameCount: number = 0;
  private lastStableFeatures: number[] | null = null;
  private minStableFrames: number = 8;
  private maxTransitionFrames: number = 15;
  private gestureStabilityThreshold: number = 0.15;

  async init(): Promise<void> {
    this.vocabularyMap = getVocabularyMap();
    this.isInitialized = true;
  }

  async recognizeSequence(frames: FrameData[]): Promise<RecognizedWord[]> {
    if (!this.isInitialized) {
      await this.init();
    }

    if (frames.length === 0) {
      return [];
    }

    const segments = this.segmentFrames(frames);
    const recognizedWords: RecognizedWord[] = [];

    for (let i = 0; i < segments.length; i++) {
      const segment = segments[i];
      if (segment.length >= this.minFramesPerWord) {
        const word = await this.recognizeWordFromSegment(segment, i);
        if (word && word.confidence >= this.similarityThreshold) {
          recognizedWords.push(word);
        }
      }
    }

    return recognizedWords;
  }

  private segmentFrames(frames: FrameData[]): FrameData[][] {
    const segments: FrameData[][] = [];
    let currentSegment: FrameData[] = [];
    let motionlessFrames = 0;
    let inTransition = false;
    let transitionFrames = 0;
    let stableFramesInSegment = 0;
    const localMotionHistory: number[] = [];

    for (let i = 0; i < frames.length; i++) {
      const frame = frames[i];
      const motionScore = this.calculateMotionScore(frame);
      localMotionHistory.push(motionScore);
      if (localMotionHistory.length > 30) localMotionHistory.shift();

      const isStable = this.isGestureStable(frame, localMotionHistory);
      const isTransition = this.isTransitionFrame(frame, localMotionHistory, motionScore);

      if (isTransition) {
        inTransition = true;
        transitionFrames++;

        if (transitionFrames >= this.maxTransitionFrames && currentSegment.length >= this.minFramesPerWord && stableFramesInSegment >= this.minStableFrames) {
          const filteredSegment = this.filterTransitionFrames(currentSegment);
          if (filteredSegment.length >= this.minFramesPerWord) {
            segments.push(filteredSegment);
          }
          currentSegment = [];
          stableFramesInSegment = 0;
          inTransition = false;
          transitionFrames = 0;
          motionlessFrames = 0;
        } else if (currentSegment.length > 0) {
          currentSegment.push(frame);
        }
      } else {
        inTransition = false;
        transitionFrames = 0;

        if (motionScore > 0.2) {
          currentSegment.push(frame);
          motionlessFrames = 0;
          if (isStable) {
            stableFramesInSegment++;
          }
        } else {
          motionlessFrames++;
          if (motionlessFrames >= 12 && currentSegment.length > 0) {
            if (currentSegment.length >= this.minFramesPerWord && stableFramesInSegment >= this.minStableFrames) {
              const filteredSegment = this.filterTransitionFrames(currentSegment);
              if (filteredSegment.length >= this.minFramesPerWord) {
                segments.push(filteredSegment);
              }
            }
            currentSegment = [];
            stableFramesInSegment = 0;
            motionlessFrames = 0;
          } else if (currentSegment.length > 0) {
            currentSegment.push(frame);
          }
        }
      }

      if (currentSegment.length >= this.maxFramesPerWord) {
        if (stableFramesInSegment >= this.minStableFrames) {
          const filteredSegment = this.filterTransitionFrames(currentSegment);
          if (filteredSegment.length >= this.minFramesPerWord) {
            segments.push(filteredSegment);
          }
        }
        currentSegment = [];
        stableFramesInSegment = 0;
        motionlessFrames = 0;
        inTransition = false;
        transitionFrames = 0;
      }
    }

    if (currentSegment.length >= this.minFramesPerWord && stableFramesInSegment >= this.minStableFrames) {
      const filteredSegment = this.filterTransitionFrames(currentSegment);
      if (filteredSegment.length >= this.minFramesPerWord) {
        segments.push(filteredSegment);
      }
    }

    return this.mergeShortSegments(segments);
  }

  private calculateMotionScore(frame: FrameData): number {
    const { features } = frame;
    let motionScore = 0;
    let activePoints = 0;

    for (let i = 0; i < features.length; i += 3) {
      const x = features[i];
      const y = features[i + 1];
      const z = features[i + 2];
      const magnitude = Math.sqrt(x * x + y * y + z * z);
      if (magnitude > 0.005) {
        motionScore += magnitude;
        activePoints++;
      }
    }

    return activePoints > 5 ? motionScore / activePoints : 0;
  }

  private isGestureStable(frame: FrameData, motionHistory: number[]): boolean {
    if (motionHistory.length < 10) return false;

    const recentMotions = motionHistory.slice(-10);
    const mean = recentMotions.reduce((a, b) => a + b, 0) / recentMotions.length;
    const variance = recentMotions.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / recentMotions.length;
    const stdDev = Math.sqrt(variance);

    return stdDev < this.gestureStabilityThreshold && mean > 0.1;
  }

  private isTransitionFrame(frame: FrameData, motionHistory: number[], currentMotion: number): boolean {
    if (motionHistory.length < 15) return false;

    const recentMotions = motionHistory.slice(-15);
    const avgMotion = recentMotions.reduce((a, b) => a + b, 0) / recentMotions.length;

    const hasRightHand = frame.rightHand !== null;
    const hasLeftHand = frame.leftHand !== null;

    if (!hasRightHand && !hasLeftHand) return true;

    if (avgMotion > 0 && currentMotion > avgMotion * 2.5) return true;
    if (avgMotion > 0.3 && currentMotion < avgMotion * 0.2) return true;

    if (hasRightHand && frame.rightHand) {
      const wrist = frame.rightHand[0];
      const middleTip = frame.rightHand[12];
      if (wrist && middleTip) {
        const handOpen = this.calculateHandSpread(frame.rightHand) > 0.3;
        const handClosed = this.calculateHandSpread(frame.rightHand) < 0.1;
        if (handOpen || handClosed) return false;
      }
    }

    if (motionHistory.length >= 3) {
      const m1 = motionHistory[motionHistory.length - 1] || 0;
      const m2 = motionHistory[motionHistory.length - 2] || 0;
      const m3 = motionHistory[motionHistory.length - 3] || 0;
      const acceleration = Math.abs(m1 - 2 * m2 + m3);
      if (acceleration > 0.5) return true;
    }

    return false;
  }

  private calculateHandSpread(hand: { x: number; y: number; z: number }[]): number {
    if (!hand || hand.length < 21) return 0;

    const wrist = hand[0];
    let maxDistance = 0;

    const fingerTips = [4, 8, 12, 16, 20];
    for (const tip of fingerTips) {
      const finger = hand[tip];
      if (finger && wrist) {
        const distance = Math.sqrt(
          Math.pow(finger.x - wrist.x, 2) +
          Math.pow(finger.y - wrist.y, 2) +
          Math.pow(finger.z - wrist.z, 2)
        );
        maxDistance = Math.max(maxDistance, distance);
      }
    }

    return maxDistance;
  }

  private filterTransitionFrames(segment: FrameData[]): FrameData[] {
    if (segment.length < 10) return segment;

    const scores: number[] = [];
    for (let i = 0; i < segment.length; i++) {
      let score = 0;
      const frame = segment[i];

      if (frame.rightHand) score += 2;
      if (frame.leftHand) score += 1;

      const motionScore = this.calculateMotionScore(frame);
      score += Math.min(motionScore * 5, 3);

      if (i > 0 && i < segment.length - 1) {
        const prevScore = this.calculateMotionScore(segment[i - 1]);
        const nextScore = this.calculateMotionScore(segment[i + 1]);
        if (motionScore > prevScore * 0.5 && motionScore > nextScore * 0.5) {
          score += 1;
        }
      }

      scores.push(score);
    }

    const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
    const threshold = avgScore * 0.5;

    const filtered: FrameData[] = [];
    for (let i = 0; i < segment.length; i++) {
      if (scores[i] >= threshold) {
        filtered.push(segment[i]);
      }
    }

    if (filtered.length < this.minFramesPerWord) {
      const sortedIndices = scores
        .map((score, index) => ({ score, index }))
        .sort((a, b) => b.score - a.score)
        .slice(0, this.minFramesPerWord)
        .map(item => item.index)
        .sort((a, b) => a - b);

      return sortedIndices.map(i => segment[i]);
    }

    return filtered;
  }

  private mergeShortSegments(segments: FrameData[][]): FrameData[][] {
    if (segments.length < 2) return segments;

    const merged: FrameData[][] = [];
    let i = 0;

    while (i < segments.length) {
      let current = segments[i];

      while (i + 1 < segments.length) {
        const next = segments[i + 1];
        const currentFeatures = this.computeAverageFeatures(current);
        const nextFeatures = this.computeAverageFeatures(next);
        const similarity = this.cosineSimilarity(currentFeatures, nextFeatures);

        if (similarity > 0.85 || next.length < this.minFramesPerWord * 0.8) {
          current = [...current, ...next];
          i++;
        } else {
          break;
        }
      }

      merged.push(current);
      i++;
    }

    return merged.filter(s => s.length >= this.minFramesPerWord);
  }

  private hasSignificantMotion(frame: FrameData): boolean {
    const { features } = frame;
    let motionScore = 0;

    for (let i = 0; i < features.length; i += 3) {
      const x = features[i];
      const y = features[i + 1];
      if (x > 0.01 || y > 0.01) {
        motionScore += Math.abs(x) + Math.abs(y);
      }
    }

    return motionScore > 0.5;
  }

  private recognizeWordFromSegment(
    segment: FrameData[],
    segmentIndex: number
  ): RecognizedWord | null {
    if (segment.length === 0) return null;

    const avgFeatures = this.computeAverageFeatures(segment);
    let bestMatch: VocabularyItem | null = null;
    let bestSimilarity = 0;

    for (const item of VOCABULARY) {
      const similarity = this.cosineSimilarity(avgFeatures, item.featureTemplate);
      if (similarity > bestSimilarity && similarity >= this.similarityThreshold) {
        bestSimilarity = similarity;
        bestMatch = item;
      }
    }

    if (!bestMatch) {
      const fallbackMatch = this.recognizeByMotionPattern(segment);
      if (fallbackMatch) {
        return {
          word: fallbackMatch.word,
          pinyin: fallbackMatch.pinyin,
          confidence: 0.7,
          startTime: segment[0].timestamp,
          endTime: segment[segment.length - 1].timestamp,
          frameIndex: segmentIndex,
          category: fallbackMatch.category
        };
      }
      return null;
    }

    return {
      word: bestMatch.word,
      pinyin: bestMatch.pinyin,
      confidence: bestSimilarity,
      startTime: segment[0].timestamp,
      endTime: segment[segment.length - 1].timestamp,
      frameIndex: segmentIndex,
      category: bestMatch.category
    };
  }

  private recognizeByMotionPattern(segment: FrameData[]): VocabularyItem | null {
    const motionPattern = this.extractMotionPattern(segment);
    
    if (motionPattern.isCircular) {
      return VOCABULARY.find(v => v.word === '看') || null;
    }
    if (motionPattern.isVertical) {
      return VOCABULARY.find(v => v.word === '是') || null;
    }
    if (motionPattern.isHorizontal) {
      return VOCABULARY.find(v => v.word === '你') || null;
    }
    if (motionPattern.isPinch) {
      return VOCABULARY.find(v => v.word === '小') || null;
    }
    if (motionPattern.isOpen) {
      return VOCABULARY.find(v => v.word === '大') || null;
    }

    return null;
  }

  private extractMotionPattern(segment: FrameData[]): {
    isCircular: boolean;
    isVertical: boolean;
    isHorizontal: boolean;
    isPinch: boolean;
    isOpen: boolean;
  } {
    let sumX = 0, sumY = 0;
    let prevX = 0, prevY = 0;
    let verticalMoves = 0, horizontalMoves = 0;
    let directionChanges = 0;
    let lastDirection = '';

    for (const frame of segment) {
      if (frame.rightHand && frame.rightHand[0]) {
        const x = frame.rightHand[0].x;
        const y = frame.rightHand[0].y;
        sumX += x;
        sumY += y;

        if (prevX > 0) {
          const dx = x - prevX;
          const dy = y - prevY;

          if (Math.abs(dy) > Math.abs(dx)) {
            verticalMoves++;
            const direction = dy > 0 ? 'down' : 'up';
            if (lastDirection && lastDirection !== direction) {
              directionChanges++;
            }
            lastDirection = direction;
          } else if (Math.abs(dx) > 0.01) {
            horizontalMoves++;
            const direction = dx > 0 ? 'right' : 'left';
            if (lastDirection && lastDirection !== direction) {
              directionChanges++;
            }
            lastDirection = direction;
          }
        }

        prevX = x;
        prevY = y;
      }
    }

    let isPinch = false;
    let isOpen = false;

    for (const frame of segment) {
      if (frame.rightHand && frame.rightHand.length >= 21) {
        const thumbTip = frame.rightHand[4];
        const indexTip = frame.rightHand[8];
        const distance = Math.sqrt(
          Math.pow(thumbTip.x - indexTip.x, 2) +
          Math.pow(thumbTip.y - indexTip.y, 2)
        );
        if (distance < 0.05) {
          isPinch = true;
        }
        if (distance > 0.15) {
          isOpen = true;
        }
      }
    }

    const totalMoves = verticalMoves + horizontalMoves;
    const isCircular = directionChanges >= 3 && totalMoves > 5;
    const isVertical = verticalMoves > horizontalMoves * 1.5 && !isCircular;
    const isHorizontal = horizontalMoves > verticalMoves * 1.5 && !isCircular;

    return { isCircular, isVertical, isHorizontal, isPinch, isOpen };
  }

  private computeAverageFeatures(frames: FrameData[]): number[] {
    if (frames.length === 0) return [];

    const featureLength = frames[0].features.length;
    const avgFeatures = new Array(featureLength).fill(0);

    for (const frame of frames) {
      for (let i = 0; i < featureLength; i++) {
        avgFeatures[i] += frame.features[i];
      }
    }

    for (let i = 0; i < featureLength; i++) {
      avgFeatures[i] /= frames.length;
    }

    return avgFeatures;
  }

  private cosineSimilarity(vecA: number[], vecB: number[]): number {
    if (vecA.length !== vecB.length) return 0;

    let dotProduct = 0;
    let normA = 0;
    let normB = 0;

    for (let i = 0; i < vecA.length; i++) {
      dotProduct += vecA[i] * vecB[i];
      normA += Math.pow(vecA[i], 2);
      normB += Math.pow(vecB[i], 2);
    }

    normA = Math.sqrt(normA);
    normB = Math.sqrt(normB);

    if (normA === 0 || normB === 0) return 0;

    return dotProduct / (normA * normB);
  }

  extractFeatures(frame: FrameData): number[] {
    return frame.features;
  }

  addFrame(frame: FrameData): RecognizedWord | null {
    this.frameBuffer.push(frame);
    this.currentWordFrames.push(frame);

    if (this.frameBuffer.length > 120) {
      this.frameBuffer.shift();
    }

    const now = Date.now();
    if (now - this.lastRecognitionTime < 500) {
      return null;
    }

    const hasMotion = this.hasSignificantMotion(frame);
    if (!hasMotion && this.currentWordFrames.length >= this.minFramesPerWord) {
      const segment = [...this.currentWordFrames];
      this.currentWordFrames = [];
      this.lastRecognitionTime = now;

      const word = this.recognizeWordFromSegment(segment, 0);
      return word;
    }

    if (this.currentWordFrames.length >= this.maxFramesPerWord) {
      const segment = [...this.currentWordFrames];
      this.currentWordFrames = [];
      this.lastRecognitionTime = now;

      const word = this.recognizeWordFromSegment(segment, 0);
      return word;
    }

    return null;
  }

  flush(): RecognizedWord[] {
    const words: RecognizedWord[] = [];
    if (this.currentWordFrames.length >= this.minFramesPerWord) {
      const word = this.recognizeWordFromSegment(this.currentWordFrames, 0);
      if (word) {
        words.push(word);
      }
    }
    this.currentWordFrames = [];
    this.frameBuffer = [];
    return words;
  }

  reset(): void {
    this.frameBuffer = [];
    this.currentWordFrames = [];
    this.lastRecognitionTime = 0;
  }
}

export const gestureRecognizer = new GestureRecognizer();
