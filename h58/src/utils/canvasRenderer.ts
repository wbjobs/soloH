import { Stroke, Point, RenderParameters, StyleFeatures } from '../types';

class PerlinNoise1D {
  private permutation: number[];
  
  constructor(seed: number = Math.random() * 10000) {
    this.permutation = this.generatePermutation(seed);
  }
  
  private generatePermutation(seed: number): number[] {
    const p: number[] = [];
    for (let i = 0; i < 256; i++) {
      p[i] = i;
    }
    
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
    
    const A = this.permutation[X];
    const B = this.permutation[X + 1];
    
    return this.lerp(
      this.grad(this.permutation[A], x),
      this.grad(this.permutation[B], x - 1),
      u
    );
  }
  
  octaveNoise(x: number, octaves: number, persistence: number): number {
    let total = 0;
    let frequency = 1;
    let amplitude = 1;
    let maxValue = 0;
    
    for (let i = 0; i < octaves; i++) {
      total += this.noise(x * frequency) * amplitude;
      maxValue += amplitude;
      amplitude *= persistence;
      frequency *= 2;
    }
    
    return total / maxValue;
  }
}

const noiseCache = new Map<string, PerlinNoise1D>();

function getNoise(strokeId: string): PerlinNoise1D {
  if (!noiseCache.has(strokeId)) {
    noiseCache.set(strokeId, new PerlinNoise1D());
  }
  return noiseCache.get(strokeId)!;
}

function directionalFlyingWhite(
  strokeId: string,
  progress: number,
  positionAlongStroke: number,
  strokeDirection: number,
  intensity: number
): number {
  const noise = getNoise(strokeId);
  
  const axialNoise = noise.octaveNoise(positionAlongStroke * 0.15, 2, 0.6);
  const transverseNoise = noise.octaveNoise(positionAlongStroke * 0.4 + 100, 1, 0.5);
  
  const axialComponent = (axialNoise + 1) / 2;
  const transverseComponent = (transverseNoise + 1) / 2;
  
  const baseValue = axialComponent * 0.7 + transverseComponent * 0.3;
  
  const threshold = 1 - intensity * 0.6;
  if (baseValue > threshold) {
    const sharpness = Math.pow((baseValue - threshold) / (1 - threshold), 2);
    return sharpness * intensity;
  }
  
  return 0;
}

export function clearCanvas(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  bgColor: string = '#f5f0e6'
): void {
  ctx.fillStyle = bgColor;
  ctx.fillRect(0, 0, width, height);
}

export function drawStroke(
  ctx: CanvasRenderingContext2D,
  stroke: Stroke,
  parameters: RenderParameters,
  styleFeatures: StyleFeatures,
  color: string = '#1a1a1a',
  progress: number = 1
): void {
  if (stroke.points.length < 2) return;
  
  const points = stroke.points;
  const thickness = stroke.thickness;
  const totalPoints = Math.floor(points.length * progress);
  
  if (totalPoints < 2) return;
  
  const flyingWhiteIntensity = (parameters.flyingWhite / 100) * (0.5 + styleFeatures.flyingWhite);
  
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  
  let strokeLength = 0;
  const segmentLengths: number[] = [0];
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x;
    const dy = points[i].y - points[i - 1].y;
    strokeLength += Math.sqrt(dx * dx + dy * dy);
    segmentLengths.push(strokeLength);
  }
  
  let currentPathStart = 0;
  
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  
  for (let i = 1; i < totalPoints; i++) {
    const p0 = points[i - 1];
    const p1 = points[i];
    
    const t0 = thickness[i - 1] * (parameters.thickness / 50);
    const t1 = thickness[i] * (parameters.thickness / 50);
    
    if (flyingWhiteIntensity > 0.1) {
      const positionAlongStroke = segmentLengths[i] / Math.max(strokeLength, 1);
      const strokeDirection = Math.atan2(
        points[points.length - 1].y - points[0].y,
        points[points.length - 1].x - points[0].x
      );
      
      const gapAmount = directionalFlyingWhite(
        stroke.id,
        progress,
        positionAlongStroke * 50,
        strokeDirection,
        flyingWhiteIntensity
      );
      
      if (gapAmount > 0.5) {
        ctx.stroke();
        currentPathStart = i;
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        continue;
      }
      
      if (gapAmount > 0.2) {
        ctx.globalAlpha = 1 - gapAmount * 0.6;
      } else {
        ctx.globalAlpha = 1;
      }
    }
    
    const xc = (p0.x + p1.x) / 2;
    const yc = (p0.y + p1.y) / 2;
    
    ctx.quadraticCurveTo(p0.x, p0.y, xc, yc);
    ctx.lineWidth = (t0 + t1) / 2;
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(xc, yc);
  }
  
  if (totalPoints === points.length) {
    const last = points[points.length - 1];
    ctx.lineTo(last.x, last.y);
    ctx.lineWidth = thickness[thickness.length - 1] * (parameters.thickness / 50);
    ctx.stroke();
  }
  
  ctx.restore();
}

export function drawStrokeWithVariableWidth(
  ctx: CanvasRenderingContext2D,
  stroke: Stroke,
  parameters: RenderParameters,
  styleFeatures: StyleFeatures,
  color: string = '#1a1a1a',
  progress: number = 1
): void {
  if (stroke.points.length < 2) return;
  
  const points = stroke.points;
  const thickness = stroke.thickness;
  const totalPoints = Math.floor(points.length * progress);
  
  if (totalPoints < 2) return;
  
  const flyingWhiteIntensity = (parameters.flyingWhite / 100) * (0.5 + styleFeatures.flyingWhite);
  
  ctx.save();
  ctx.fillStyle = color;
  
  let strokeLength = 0;
  const segmentLengths: number[] = [0];
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x;
    const dy = points[i].y - points[i - 1].y;
    strokeLength += Math.sqrt(dx * dx + dy * dy);
    segmentLengths.push(strokeLength);
  }
  
  const strokeDirection = Math.atan2(
    points[points.length - 1].y - points[0].y,
    points[points.length - 1].x - points[0].x
  );
  
  const leftPoints: Point[] = [];
  const rightPoints: Point[] = [];
  const gapFlags: boolean[] = [];
  const alphaValues: number[] = [];
  
  for (let i = 0; i < totalPoints; i++) {
    const p = points[i];
    const t = thickness[i] * (parameters.thickness / 50) * 0.5;
    
    let angle: number;
    if (i === 0) {
      const next = points[i + 1];
      angle = Math.atan2(next.y - p.y, next.x - p.x);
    } else if (i === totalPoints - 1) {
      const prev = points[i - 1];
      angle = Math.atan2(p.y - prev.y, p.x - prev.x);
    } else {
      const prev = points[i - 1];
      const next = points[i + 1];
      angle = Math.atan2(next.y - prev.y, next.x - prev.x);
    }
    
    const perpAngle = angle + Math.PI / 2;
    const cos = Math.cos(perpAngle);
    const sin = Math.sin(perpAngle);
    
    let actualThickness = t;
    let alpha = 1;
    let hasGap = false;
    
    if (flyingWhiteIntensity > 0.1) {
      const positionAlongStroke = segmentLengths[i] / Math.max(strokeLength, 1);
      
      const gapAmount = directionalFlyingWhite(
        stroke.id,
        progress,
        positionAlongStroke * 50,
        strokeDirection,
        flyingWhiteIntensity
      );
      
      if (gapAmount > 0.6) {
        hasGap = true;
      } else if (gapAmount > 0.3) {
        actualThickness = t * (1 - gapAmount * 0.7);
        alpha = 1 - gapAmount * 0.5;
      }
    }
    
    leftPoints.push({
      x: p.x + cos * actualThickness,
      y: p.y + sin * actualThickness
    });
    rightPoints.unshift({
      x: p.x - cos * actualThickness,
      y: p.y - sin * actualThickness
    });
    gapFlags.push(hasGap);
    alphaValues.push(alpha);
  }
  
  let pathStart = 0;
  
  for (let i = 0; i < leftPoints.length; i++) {
    if (gapFlags[i] || i === leftPoints.length - 1) {
      if (i - pathStart > 2) {
        const avgAlpha = alphaValues.slice(pathStart, i).reduce((a, b) => a + b, 0) / (i - pathStart);
        ctx.globalAlpha = avgAlpha;
        
        ctx.beginPath();
        ctx.moveTo(leftPoints[pathStart].x, leftPoints[pathStart].y);
        
        for (let j = pathStart + 1; j < i - 1; j++) {
          const xc = (leftPoints[j].x + leftPoints[j + 1].x) / 2;
          const yc = (leftPoints[j].y + leftPoints[j + 1].y) / 2;
          ctx.quadraticCurveTo(leftPoints[j].x, leftPoints[j].y, xc, yc);
        }
        
        ctx.lineTo(leftPoints[i - 1].x, leftPoints[i - 1].y);
        
        const rightStart = rightPoints.length - i + 1;
        const rightEnd = rightPoints.length - pathStart;
        for (let j = rightStart; j < rightEnd - 1; j++) {
          const xc = (rightPoints[j].x + rightPoints[j + 1].x) / 2;
          const yc = (rightPoints[j].y + rightPoints[j + 1].y) / 2;
          ctx.quadraticCurveTo(rightPoints[j].x, rightPoints[j].y, xc, yc);
        }
        
        if (rightEnd > rightStart) {
          ctx.lineTo(rightPoints[rightEnd - 1].x, rightPoints[rightEnd - 1].y);
        }
        
        ctx.closePath();
        ctx.fill();
      }
      pathStart = i + 1;
    }
  }
  
  if (pathStart < leftPoints.length - 2) {
    const avgAlpha = alphaValues.slice(pathStart).reduce((a, b) => a + b, 0) / (leftPoints.length - pathStart);
    ctx.globalAlpha = avgAlpha;
    
    ctx.beginPath();
    ctx.moveTo(leftPoints[pathStart].x, leftPoints[pathStart].y);
    
    for (let j = pathStart + 1; j < leftPoints.length - 1; j++) {
      const xc = (leftPoints[j].x + leftPoints[j + 1].x) / 2;
      const yc = (leftPoints[j].y + leftPoints[j + 1].y) / 2;
      ctx.quadraticCurveTo(leftPoints[j].x, leftPoints[j].y, xc, yc);
    }
    
    ctx.lineTo(leftPoints[leftPoints.length - 1].x, leftPoints[leftPoints.length - 1].y);
    
    const rightEnd = rightPoints.length - pathStart;
    for (let j = 1; j < rightEnd - 1; j++) {
      const xc = (rightPoints[j].x + rightPoints[j + 1].x) / 2;
      const yc = (rightPoints[j].y + rightPoints[j + 1].y) / 2;
      ctx.quadraticCurveTo(rightPoints[j].x, rightPoints[j].y, xc, yc);
    }
    
    if (rightEnd > 1) {
      ctx.lineTo(rightPoints[rightEnd - 1].x, rightPoints[rightEnd - 1].y);
    }
    
    ctx.closePath();
    ctx.fill();
  }
  
  ctx.restore();
}

export function drawAllStrokes(
  ctx: CanvasRenderingContext2D,
  strokes: Stroke[],
  parameters: RenderParameters,
  styleFeatures: StyleFeatures,
  color: string = '#1a1a1a',
  useVariableWidth: boolean = true
): void {
  for (const stroke of strokes) {
    if (useVariableWidth) {
      drawStrokeWithVariableWidth(ctx, stroke, parameters, styleFeatures, color);
    } else {
      drawStroke(ctx, stroke, parameters, styleFeatures, color);
    }
  }
}

export function drawStrokesAnimated(
  ctx: CanvasRenderingContext2D,
  strokes: Stroke[],
  parameters: RenderParameters,
  styleFeatures: StyleFeatures,
  currentStrokeIndex: number,
  strokeProgress: number,
  color: string = '#1a1a1a',
  useVariableWidth: boolean = true
): void {
  for (let i = 0; i < strokes.length; i++) {
    const stroke = strokes[i];
    let progress = 1;
    
    if (i === currentStrokeIndex) {
      progress = strokeProgress;
    } else if (i > currentStrokeIndex) {
      continue;
    }
    
    if (useVariableWidth) {
      drawStrokeWithVariableWidth(ctx, stroke, parameters, styleFeatures, color, progress);
    } else {
      drawStroke(ctx, stroke, parameters, styleFeatures, color, progress);
    }
  }
}

export function drawStrokeOrderLabels(
  ctx: CanvasRenderingContext2D,
  strokes: Stroke[],
  color: string = '#c41e3a'
): void {
  ctx.save();
  ctx.fillStyle = color;
  ctx.font = 'bold 14px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  
  for (const stroke of strokes) {
    if (stroke.points.length === 0) continue;
    
    const startPoint = stroke.points[0];
    const label = (stroke.order + 1).toString();
    
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    ctx.beginPath();
    ctx.arc(startPoint.x, startPoint.y, 12, 0, Math.PI * 2);
    ctx.fill();
    
    ctx.fillStyle = color;
    ctx.fillText(label, startPoint.x, startPoint.y);
  }
  
  ctx.restore();
}

export function drawSkeleton(
  ctx: CanvasRenderingContext2D,
  skeletonData: Uint8ClampedArray,
  width: number,
  height: number,
  color: string = '#1a1a1a'
): void {
  const imageData = ctx.createImageData(width, height);
  const data = imageData.data;
  
  const rgb = hexToRgb(color);
  
  for (let i = 0; i < skeletonData.length; i++) {
    const isForeground = skeletonData[i] > 0;
    data[i * 4] = isForeground ? rgb.r : 245;
    data[i * 4 + 1] = isForeground ? rgb.g : 240;
    data[i * 4 + 2] = isForeground ? rgb.b : 230;
    data[i * 4 + 3] = 255;
  }
  
  ctx.putImageData(imageData, 0, 0);
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : { r: 0, g: 0, b: 0 };
}

export function drawGrid(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  color: string = 'rgba(0, 0, 0, 0.1)'
): void {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  
  const gridSize = 50;
  
  for (let x = 0; x <= width; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  
  for (let y = 0; y <= height; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  
  ctx.restore();
}
