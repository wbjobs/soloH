import { Stroke, Point, StyleFeatures, CharacterStyle, RenderParameters } from '../types';

class StylePerlinNoise {
  private perm: number[];
  
  constructor(seed: number = 12345) {
    this.perm = this.generatePermutation(seed);
  }
  
  private generatePermutation(seed: number): number[] {
    const p: number[] = [];
    for (let i = 0; i < 256; i++) p[i] = i;
    
    let s = seed;
    for (let i = 255; i > 0; i--) {
      s = (s * 16807) % 2147483647;
      const j = s % (i + 1);
      [p[i], p[j]] = [p[j], p[i]];
    }
    return [...p, ...p];
  }
  
  private fade(t: number): number {
    return t * t * t * (t * (t * 6 - 15) + 10);
  }
  
  private lerp(a: number, b: number, t: number): number {
    return a + t * (b - a);
  }
  
  private grad(hash: number, x: number): number {
    return (hash & 1) === 0 ? x : -x;
  }
  
  noise(x: number): number {
    const X = Math.floor(x) & 255;
    x -= Math.floor(x);
    const u = this.fade(x);
    return this.lerp(
      this.grad(this.perm[X], x),
      this.grad(this.perm[X + 1], x - 1),
      u
    );
  }
  
  octaveNoise(x: number, octaves: number = 2, persistence: number = 0.5): number {
    let total = 0;
    let freq = 1;
    let amp = 1;
    let max = 0;
    for (let i = 0; i < octaves; i++) {
      total += this.noise(x * freq) * amp;
      max += amp;
      amp *= persistence;
      freq *= 2;
    }
    return total / max;
  }
}

const styleNoise = new StylePerlinNoise(98765);

export function extractStyleFeatures(strokes: Stroke[]): StyleFeatures {
  if (strokes.length === 0) {
    return {
      avgThickness: 4,
      thicknessVariance: 1,
      slantAngle: 0,
      speedVariation: 0.5,
      flyingWhite: 0.1,
      smoothness: 0.8,
      strokeLengths: [],
      strokeDirections: []
    };
  }

  const allThickness: number[] = [];
  const strokeLengths: number[] = [];
  const strokeDirections: number[] = [];

  for (const stroke of strokes) {
    for (const t of stroke.thickness) {
      allThickness.push(t);
    }
    
    if (stroke.points.length >= 2) {
      const start = stroke.points[0];
      const end = stroke.points[stroke.points.length - 1];
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      const length = Math.sqrt(dx * dx + dy * dy);
      strokeLengths.push(length);
      strokeDirections.push(Math.atan2(dy, dx));
    }
  }

  const avgThickness = mean(allThickness);
  const thicknessVariance = variance(allThickness);
  
  const slantAngle = mean(strokeDirections);
  
  let totalSpeedVar = 0;
  let count = 0;
  for (const stroke of strokes) {
    for (const point of stroke.points) {
      if (point.speed !== undefined) {
        totalSpeedVar += Math.abs(point.speed - 0.8);
        count++;
      }
    }
  }
  const speedVariation = count > 0 ? totalSpeedVar / count : 0.5;

  let flyingWhite = 0;
  for (const stroke of strokes) {
    for (let i = 1; i < stroke.thickness.length; i++) {
      if (stroke.thickness[i] < avgThickness * 0.3) {
        flyingWhite += 0.1;
      }
    }
  }
  flyingWhite = Math.min(1, flyingWhite / strokes.length);

  const smoothness = calculateSmoothness(strokes);

  return {
    avgThickness,
    thicknessVariance,
    slantAngle,
    speedVariation,
    flyingWhite,
    smoothness,
    strokeLengths,
    strokeDirections
  };
}

function mean(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function variance(values: number[]): number {
  if (values.length === 0) return 0;
  const m = mean(values);
  return Math.sqrt(values.reduce((a, b) => a + (b - m) ** 2, 0) / values.length);
}

function calculateSmoothness(strokes: Stroke[]): number {
  let totalAngleChanges = 0;
  let totalSegments = 0;

  for (const stroke of strokes) {
    for (let i = 2; i < stroke.points.length; i++) {
      const p0 = stroke.points[i - 2];
      const p1 = stroke.points[i - 1];
      const p2 = stroke.points[i];
      
      const v1 = { dx: p1.x - p0.x, dy: p1.y - p0.y };
      const v2 = { dx: p2.x - p1.x, dy: p2.y - p1.y };
      
      const dot = v1.dx * v2.dx + v1.dy * v2.dy;
      const mag1 = Math.sqrt(v1.dx * v1.dx + v1.dy * v1.dy);
      const mag2 = Math.sqrt(v2.dx * v2.dx + v2.dy * v2.dy);
      
      if (mag1 > 0 && mag2 > 0) {
        const cos = Math.max(-1, Math.min(1, dot / (mag1 * mag2)));
        totalAngleChanges += Math.acos(cos);
        totalSegments++;
      }
    }
  }

  if (totalSegments === 0) return 1;
  const avgAngle = totalAngleChanges / totalSegments;
  return Math.max(0, Math.min(1, 1 - avgAngle / Math.PI));
}

export function fuseStyles(samples: CharacterStyle[]): StyleFeatures {
  const validSamples = samples.filter(s => s.weight > 0);
  if (validSamples.length === 0) {
    return {
      avgThickness: 4,
      thicknessVariance: 1,
      slantAngle: 0,
      speedVariation: 0.5,
      flyingWhite: 0.1,
      smoothness: 0.8,
      strokeLengths: [],
      strokeDirections: []
    };
  }

  const totalWeight = validSamples.reduce((sum, s) => sum + s.weight, 0);
  
  let avgThickness = 0;
  let thicknessVariance = 0;
  let slantAngle = 0;
  let speedVariation = 0;
  let flyingWhite = 0;
  let smoothness = 0;

  const allLengths: number[] = [];
  const allDirections: number[] = [];

  for (const sample of validSamples) {
    const w = sample.weight / totalWeight;
    const f = sample.features;
    
    avgThickness += f.avgThickness * w;
    thicknessVariance += f.thicknessVariance * w;
    slantAngle += f.slantAngle * w;
    speedVariation += f.speedVariation * w;
    flyingWhite += f.flyingWhite * w;
    smoothness += f.smoothness * w;
    
    allLengths.push(...f.strokeLengths.map(l => l * w));
    allDirections.push(...f.strokeDirections.map(d => d * w));
  }

  return {
    avgThickness,
    thicknessVariance,
    slantAngle,
    speedVariation,
    flyingWhite,
    smoothness,
    strokeLengths: allLengths,
    strokeDirections: allDirections
  };
}

export function applyParameters(
  stroke: Stroke,
  parameters: RenderParameters,
  styleFeatures: StyleFeatures
): Stroke {
  const thicknessScale = parameters.thickness / 50;
  const speedScale = parameters.speed / 50;
  const flyingWhiteIntensity = (parameters.flyingWhite / 100) * (0.5 + styleFeatures.flyingWhite);

  let strokeLength = 0;
  const segmentLengths: number[] = [0];
  const points = stroke.points;
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x;
    const dy = points[i].y - points[i - 1].y;
    strokeLength += Math.sqrt(dx * dx + dy * dy);
    segmentLengths.push(strokeLength);
  }

  const strokeDirection = points.length >= 2 
    ? Math.atan2(
        points[points.length - 1].y - points[0].y,
        points[points.length - 1].x - points[0].x
      )
    : 0;

  const strokeIdNum = parseInt(stroke.id.replace(/\D/g, '').slice(0, 6)) || 0;

  const newThickness = stroke.thickness.map((t, i) => {
    let newT = t * thicknessScale;
    
    if (styleFeatures.thicknessVariance > 0) {
      const variation = (Math.random() - 0.5) * styleFeatures.thicknessVariance;
      newT += variation;
    }
    
    if (flyingWhiteIntensity > 0.1) {
      const positionAlongStroke = segmentLengths[i] / Math.max(strokeLength, 1);
      
      const axialNoise = styleNoise.octaveNoise(positionAlongStroke * 40 + strokeIdNum * 0.001, 2, 0.6);
      const transverseNoise = styleNoise.octaveNoise(positionAlongStroke * 80 + strokeIdNum * 0.001 + 50, 1, 0.5);
      
      const axialComponent = (axialNoise + 1) / 2;
      const transverseComponent = (transverseNoise + 1) / 2;
      const baseValue = axialComponent * 0.75 + transverseComponent * 0.25;
      
      const threshold = 1 - flyingWhiteIntensity * 0.55;
      if (baseValue > threshold) {
        const gapAmount = Math.pow((baseValue - threshold) / (1 - threshold), 2);
        newT *= Math.max(0.15, 1 - gapAmount * 0.85);
      }
    }
    
    return Math.max(0.5, newT);
  });

  const newPoints = stroke.points.map((p, i) => {
    const baseSpeed = p.speed ?? 0.8;
    const adjustedSpeed = baseSpeed * speedScale * (1 + styleFeatures.speedVariation * (Math.random() - 0.5));
    
    let newX = p.x;
    let newY = p.y;
    
    if (styleFeatures.slantAngle !== 0) {
      const slant = styleFeatures.slantAngle * 0.1;
      newX = p.x + (p.y * Math.sin(slant));
    }
    
    if (styleFeatures.smoothness < 0.7) {
      const jitter = (1 - styleFeatures.smoothness) * 2;
      newX += (Math.random() - 0.5) * jitter;
      newY += (Math.random() - 0.5) * jitter;
    }
    
    return {
      ...p,
      x: newX,
      y: newY,
      speed: Math.max(0.1, Math.min(2, adjustedSpeed))
    };
  });

  return {
    ...stroke,
    points: newPoints,
    thickness: newThickness
  };
}

export function interpolateStrokes(
  strokeA: Stroke,
  strokeB: Stroke,
  t: number
): Stroke {
  const targetLength = Math.round(
    strokeA.points.length * (1 - t) + strokeB.points.length * t
  );
  
  const resampledA = resampleStroke(strokeA, targetLength);
  const resampledB = resampleStroke(strokeB, targetLength);
  
  const points: Point[] = [];
  const thickness: number[] = [];
  
  for (let i = 0; i < targetLength; i++) {
    const pA = resampledA.points[i];
    const pB = resampledB.points[i];
    
    points.push({
      x: pA.x * (1 - t) + pB.x * t,
      y: pA.y * (1 - t) + pB.y * t,
      pressure: (pA.pressure ?? 0.8) * (1 - t) + (pB.pressure ?? 0.8) * t,
      speed: (pA.speed ?? 0.8) * (1 - t) + (pB.speed ?? 0.8) * t
    });
    
    thickness.push(
      resampledA.thickness[i] * (1 - t) + resampledB.thickness[i] * t
    );
  }
  
  return {
    id: `stroke-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    points,
    thickness,
    order: strokeA.order,
    type: strokeA.type
  };
}

function resampleStroke(stroke: Stroke, targetLength: number): Stroke {
  if (stroke.points.length === targetLength) return stroke;
  if (stroke.points.length < 2) return stroke;
  
  const points: Point[] = [];
  const thickness: number[] = [];
  
  const totalLength = getStrokeLength(stroke.points);
  const step = totalLength / (targetLength - 1);
  
  let accumulated = 0;
  let currentIndex = 0;
  
  points.push({ ...stroke.points[0] });
  thickness.push(stroke.thickness[0]);
  
  for (let i = 1; i < targetLength - 1; i++) {
    const targetDist = step * i;
    
    while (currentIndex < stroke.points.length - 1) {
      const p1 = stroke.points[currentIndex];
      const p2 = stroke.points[currentIndex + 1];
      const segLength = distance(p1, p2);
      
      if (accumulated + segLength >= targetDist) {
        const t = (targetDist - accumulated) / segLength;
        points.push({
          x: p1.x + (p2.x - p1.x) * t,
          y: p1.y + (p2.y - p1.y) * t,
          pressure: ((p1.pressure ?? 0.8) + (p2.pressure ?? 0.8)) / 2,
          speed: ((p1.speed ?? 0.8) + (p2.speed ?? 0.8)) / 2
        });
        thickness.push(
          stroke.thickness[currentIndex] * (1 - t) + 
          stroke.thickness[currentIndex + 1] * t
        );
        break;
      }
      
      accumulated += segLength;
      currentIndex++;
    }
  }
  
  points.push({ ...stroke.points[stroke.points.length - 1] });
  thickness.push(stroke.thickness[stroke.thickness.length - 1]);
  
  return {
    ...stroke,
    points,
    thickness
  };
}

function getStrokeLength(points: Point[]): number {
  let length = 0;
  for (let i = 1; i < points.length; i++) {
    length += distance(points[i - 1], points[i]);
  }
  return length;
}

function distance(p1: Point, p2: Point): number {
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  return Math.sqrt(dx * dx + dy * dy);
}

export function normalizeStrokeBounds(
  stroke: Stroke,
  targetWidth: number,
  targetHeight: number
): Stroke {
  if (stroke.points.length === 0) return stroke;
  
  let minX = Infinity, maxX = -Infinity;
  let minY = Infinity, maxY = -Infinity;
  
  for (const p of stroke.points) {
    minX = Math.min(minX, p.x);
    maxX = Math.max(maxX, p.x);
    minY = Math.min(minY, p.y);
    maxY = Math.max(maxY, p.y);
  }
  
  const width = maxX - minX;
  const height = maxY - minY;
  
  const scaleX = width > 0 ? targetWidth * 0.8 / width : 1;
  const scaleY = height > 0 ? targetHeight * 0.8 / height : 1;
  const scale = Math.min(scaleX, scaleY);
  
  const offsetX = (targetWidth - width * scale) / 2 - minX * scale;
  const offsetY = (targetHeight - height * scale) / 2 - minY * scale;
  
  return {
    ...stroke,
    points: stroke.points.map(p => ({
      ...p,
      x: p.x * scale + offsetX,
      y: p.y * scale + offsetY
    })),
    thickness: stroke.thickness.map(t => t * scale)
  };
}

export function buildCharacterStyle(
  character: string,
  originalImage: string,
  strokes: Stroke[],
  name: string = '风格'
): CharacterStyle {
  const strokesWithSpeed = strokes.map(addSpeedAndPressureToStroke);
  const features = extractStyleFeatures(strokesWithSpeed);
  
  return {
    id: `style-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    name,
    character,
    originalImage,
    strokes: strokesWithSpeed,
    features,
    weight: 1
  };
}

function addSpeedAndPressureToStroke(stroke: Stroke): Stroke {
  const points = stroke.points.map((p, i) => {
    let speed = 0.8;
    let pressure = 0.8;
    
    if (i === 0 || i === stroke.points.length - 1) {
      pressure = 0.5;
      speed = 0.6;
    } else if (stroke.points.length > 2) {
      const prev = stroke.points[i - 1];
      const next = stroke.points[i + 1];
      
      const v1 = { dx: p.x - prev.x, dy: p.y - prev.y };
      const v2 = { dx: next.x - p.x, dy: next.y - p.y };
      
      const dot = v1.dx * v2.dx + v1.dy * v2.dy;
      const mag1 = Math.sqrt(v1.dx * v1.dx + v1.dy * v1.dy);
      const mag2 = Math.sqrt(v2.dx * v2.dx + v2.dy * v2.dy);
      
      if (mag1 > 0 && mag2 > 0) {
        const cos = Math.max(-1, Math.min(1, dot / (mag1 * mag2)));
        const angle = Math.acos(cos);
        speed = 1 - (angle / Math.PI) * 0.6;
        pressure = 0.6 + (angle / Math.PI) * 0.4;
      }
    }
    
    return { ...p, speed, pressure };
  });
  
  return { ...stroke, points };
}
