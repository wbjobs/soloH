import { Stroke, CharacterStyle, GeneratedCharacter, RenderParameters, StyleFeatures } from '../types';
import { processImage } from './imageProcessor';
import { buildGraph, extractStrokes } from './strokeExtractor';
import { buildCharacterStyle, fuseStyles, applyParameters, normalizeStrokeBounds } from './styleModel';
import { generateStaticSVG } from './svgGenerator';

const strokeDatabase: Record<string, string[]> = {
  '一': ['horizontal'],
  '二': ['horizontal', 'horizontal'],
  '三': ['horizontal', 'horizontal', 'horizontal'],
  '十': ['horizontal', 'vertical'],
  '人': ['diagonal-down', 'diagonal-up'],
  '大': ['horizontal', 'diagonal-down', 'diagonal-up'],
  '天': ['horizontal', 'horizontal', 'diagonal-down', 'diagonal-up'],
  '中': ['vertical', 'horizontal', 'vertical', 'horizontal'],
  '国': ['horizontal', 'vertical', 'horizontal', 'vertical', 'horizontal', 'dot', 'horizontal', 'vertical', 'horizontal'],
  '水': ['diagonal-down', 'dot', 'dot', 'diagonal-down', 'horizontal'],
  '火': ['dot', 'dot', 'diagonal-up', 'diagonal-down'],
  '山': ['vertical', 'vertical', 'horizontal', 'vertical'],
  '木': ['horizontal', 'vertical', 'diagonal-down', 'diagonal-up'],
  '日': ['horizontal', 'vertical', 'horizontal', 'vertical', 'horizontal'],
  '月': ['diagonal-down', 'horizontal', 'horizontal', 'horizontal', 'vertical'],
  '金': ['dot', 'diagonal-down', 'diagonal-up', 'horizontal', 'diagonal-down', 'diagonal-up', 'horizontal'],
  '土': ['horizontal', 'vertical', 'horizontal'],
  '口': ['horizontal', 'vertical', 'vertical', 'horizontal'],
  '田': ['horizontal', 'vertical', 'horizontal', 'vertical', 'horizontal', 'vertical', 'horizontal'],
  '王': ['horizontal', 'horizontal', 'vertical', 'horizontal'],
  '心': ['dot', 'dot', 'horizontal', 'diagonal-down', 'dot'],
  '永': ['dot', 'horizontal', 'vertical', 'diagonal-down', 'diagonal-up', 'horizontal', 'diagonal-down', 'diagonal-up'],
};

function generateStrokeByType(
  type: string,
  index: number,
  totalStrokes: number,
  bounds: { width: number; height: number },
  styleFeatures: StyleFeatures
): Stroke {
  const width = bounds.width * 0.8;
  const height = bounds.height * 0.8;
  const offsetX = bounds.width * 0.1;
  const offsetY = bounds.height * 0.1;
  
  const strokeSpacing = height / (totalStrokes + 1);
  const baseY = offsetY + strokeSpacing * (index + 1);
  
  let points: { x: number; y: number }[] = [];
  const thickness: number[] = [];
  const baseThickness = styleFeatures.avgThickness;
  
  const strokeLength = width * 0.8;
  const startX = offsetX + width * 0.1;
  const endX = offsetX + width * 0.9;
  
  const segments = 20;
  
  switch (type) {
    case 'horizontal':
      for (let i = 0; i <= segments; i++) {
        const t = i / segments;
        const x = startX + t * strokeLength;
        const y = baseY + Math.sin(t * Math.PI) * 2;
        points.push({ x, y });
        const thickVar = Math.sin(t * Math.PI) * styleFeatures.thicknessVariance;
        thickness.push(baseThickness + thickVar);
      }
      break;
      
    case 'vertical':
      const vStartY = offsetY + height * 0.1;
      const vEndY = offsetY + height * 0.9;
      const vX = offsetX + width * (0.3 + (index % 3) * 0.2);
      for (let i = 0; i <= segments; i++) {
        const t = i / segments;
        const x = vX + Math.sin(t * Math.PI) * 1;
        const y = vStartY + t * (vEndY - vStartY);
        points.push({ x, y });
        const thickVar = Math.sin(t * Math.PI) * styleFeatures.thicknessVariance;
        thickness.push(baseThickness + thickVar);
      }
      break;
      
    case 'diagonal-down':
      const ddStartX = offsetX + width * 0.2;
      const ddStartY = offsetY + height * 0.15 + index * 10;
      const ddEndX = offsetX + width * 0.8;
      const ddEndY = offsetY + height * 0.85 + index * 10;
      for (let i = 0; i <= segments; i++) {
        const t = i / segments;
        const x = ddStartX + t * (ddEndX - ddStartX);
        const y = ddStartY + t * (ddEndY - ddStartY) + Math.sin(t * Math.PI * 2) * 3;
        points.push({ x, y });
        const thickVar = Math.sin(t * Math.PI) * styleFeatures.thicknessVariance;
        thickness.push(baseThickness * (1 + t * 0.3) + thickVar);
      }
      break;
      
    case 'diagonal-up':
      const duStartX = offsetX + width * 0.8;
      const duStartY = offsetY + height * 0.15 + index * 10;
      const duEndX = offsetX + width * 0.2;
      const duEndY = offsetY + height * 0.85 + index * 10;
      for (let i = 0; i <= segments; i++) {
        const t = i / segments;
        const x = duStartX + t * (duEndX - duStartX);
        const y = duStartY + t * (duEndY - duStartY) + Math.sin(t * Math.PI * 2) * 3;
        points.push({ x, y });
        const thickVar = Math.sin(t * Math.PI) * styleFeatures.thicknessVariance;
        thickness.push(baseThickness * (1 + (1 - t) * 0.3) + thickVar);
      }
      break;
      
    case 'dot':
      const dotX = offsetX + width * (0.2 + Math.random() * 0.6);
      const dotY = offsetY + height * (0.2 + index * 0.1);
      for (let i = 0; i <= 5; i++) {
        const t = i / 5;
        points.push({
          x: dotX + Math.sin(t * Math.PI) * 5,
          y: dotY + t * 10
        });
        thickness.push(baseThickness * (0.5 + t * 0.8));
      }
      break;
      
    case 'turn':
      const tStartX = offsetX + width * 0.15;
      const tStartY = offsetY + height * 0.2 + index * 15;
      const turnX = offsetX + width * 0.7;
      const turnY = offsetY + height * 0.2 + index * 15;
      const tEndX = offsetX + width * 0.7;
      const tEndY = offsetY + height * 0.8 + index * 15;
      
      for (let i = 0; i <= segments / 2; i++) {
        const t = i / (segments / 2);
        points.push({
          x: tStartX + t * (turnX - tStartX),
          y: tStartY + Math.sin(t * Math.PI) * 2
        });
        thickness.push(baseThickness + Math.sin(t * Math.PI) * styleFeatures.thicknessVariance);
      }
      for (let i = 1; i <= segments / 2; i++) {
        const t = i / (segments / 2);
        points.push({
          x: turnX + Math.sin(t * Math.PI) * 2,
          y: turnY + t * (tEndY - turnY)
        });
        thickness.push(baseThickness + Math.sin(t * Math.PI) * styleFeatures.thicknessVariance);
      }
      break;
      
    case 'curve':
      const cStartX = offsetX + width * 0.15;
      const cStartY = offsetY + height * 0.3 + index * 10;
      const cMidX = offsetX + width * 0.5;
      const cMidY = offsetY + height * 0.1 + index * 10;
      const cEndX = offsetX + width * 0.85;
      const cEndY = offsetY + height * 0.3 + index * 10;
      
      for (let i = 0; i <= segments; i++) {
        const t = i / segments;
        const x = (1 - t) ** 2 * cStartX + 2 * (1 - t) * t * cMidX + t ** 2 * cEndX;
        const y = (1 - t) ** 2 * cStartY + 2 * (1 - t) * t * cMidY + t ** 2 * cEndY;
        points.push({ x, y });
        thickness.push(baseThickness + Math.sin(t * Math.PI) * styleFeatures.thicknessVariance);
      }
      break;
      
    default:
      for (let i = 0; i <= segments; i++) {
        const t = i / segments;
        points.push({
          x: startX + t * strokeLength,
          y: baseY
        });
        thickness.push(baseThickness);
      }
  }
  
  const pointsWithMeta = points.map((p, i) => {
    const speed = 0.6 + Math.random() * 0.4;
    const pressure = 0.5 + Math.random() * 0.5;
    return { ...p, speed, pressure };
  });
  
  return {
    id: `stroke-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    points: pointsWithMeta,
    thickness,
    order: index,
    type
  };
}

export async function processSampleImage(
  imageData: string,
  character: string,
  name: string
): Promise<CharacterStyle> {
  const processed = await processImage(imageData);
  
  const graph = buildGraph(processed.skeletonData, processed.width, processed.height);
  let strokes = extractStrokes(graph, processed.distanceMap, processed.width);
  
  strokes = strokes.map(s => normalizeStrokeBounds(s, processed.width, processed.height));
  
  return buildCharacterStyle(character, imageData, strokes, name);
}

export function generateCharacter(
  character: string,
  samples: CharacterStyle[],
  parameters: RenderParameters,
  bounds: { width: number; height: number } = { width: 200, height: 200 }
): GeneratedCharacter {
  const styleFeatures = fuseStyles(samples);
  
  let strokes: Stroke[] = [];
  
  const strokeTypes = strokeDatabase[character] || generateDefaultStrokeTypes(character);
  
  for (let i = 0; i < strokeTypes.length; i++) {
    let stroke: Stroke;
    
    const sampleStrokes = findMatchingStrokes(samples, strokeTypes[i], i, strokeTypes.length, bounds);
    
    if (sampleStrokes.length > 0) {
      stroke = interpolateSampleStrokes(sampleStrokes, i, bounds, styleFeatures);
    } else {
      stroke = generateStrokeByType(strokeTypes[i], i, strokeTypes.length, bounds, styleFeatures);
    }
    
    stroke = applyParameters(stroke, parameters, styleFeatures);
    strokes.push(stroke);
  }
  
  const svg = generateStaticSVG(strokes, bounds.width, bounds.height);
  
  return {
    character,
    strokes,
    styleId: samples.length > 0 ? samples[0].id : 'default',
    svg
  };
}

function generateDefaultStrokeTypes(character: string): string[] {
  const code = character.charCodeAt(0);
  const strokeCount = Math.max(3, Math.min(12, (code % 10) + 3));
  const types: string[] = [];
  
  const allTypes = ['horizontal', 'vertical', 'diagonal-down', 'diagonal-up', 'dot', 'turn', 'curve'];
  
  for (let i = 0; i < strokeCount; i++) {
    types.push(allTypes[(code + i) % allTypes.length]);
  }
  
  return types;
}

interface StrokeFeature {
  centerX: number;
  centerY: number;
  direction: number;
  length: number;
  type: string;
  boundingBox: { minX: number; maxX: number; minY: number; maxY: number };
}

function extractStrokeFeature(stroke: Stroke): StrokeFeature {
  const points = stroke.points;
  if (points.length === 0) {
    return {
      centerX: 0, centerY: 0, direction: 0, length: 0, type: stroke.type,
      boundingBox: { minX: 0, maxX: 0, minY: 0, maxY: 0 }
    };
  }
  
  let minX = Infinity, maxX = -Infinity;
  let minY = Infinity, maxY = -Infinity;
  
  for (const p of points) {
    minX = Math.min(minX, p.x);
    maxX = Math.max(maxX, p.x);
    minY = Math.min(minY, p.y);
    maxY = Math.max(maxY, p.y);
  }
  
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  
  const start = points[0];
  const end = points[points.length - 1];
  const direction = Math.atan2(end.y - start.y, end.x - start.x);
  
  let length = 0;
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x;
    const dy = points[i].y - points[i - 1].y;
    length += Math.sqrt(dx * dx + dy * dy);
  }
  
  return {
    centerX,
    centerY,
    direction,
    length,
    type: stroke.type,
    boundingBox: { minX, maxX, minY, maxY }
  };
}

function computeStrokeSimilarity(f1: StrokeFeature, f2: StrokeFeature, bounds: { width: number; height: number }): number {
  const typeWeight = 2.0;
  const positionWeight = 1.5;
  const directionWeight = 1.0;
  const lengthWeight = 0.8;
  
  let typeScore = 0;
  if (f1.type === f2.type) {
    typeScore = 1.0;
  } else if (
    (f1.type === 'horizontal' && f2.type === 'line') ||
    (f1.type === 'line' && f2.type === 'horizontal') ||
    (f1.type === 'diagonal-down' && f2.type === 'curve') ||
    (f1.type === 'curve' && f2.type === 'diagonal-down') ||
    (f1.type === 'diagonal-up' && f2.type === 'curve') ||
    (f1.type === 'curve' && f2.type === 'diagonal-up')
  ) {
    typeScore = 0.5;
  } else {
    typeScore = 0.2;
  }
  
  const dx = (f1.centerX - f2.centerX) / bounds.width;
  const dy = (f1.centerY - f2.centerY) / bounds.height;
  const positionDist = Math.sqrt(dx * dx + dy * dy);
  const positionScore = Math.max(0, 1 - positionDist * 2);
  
  const dirDiff = Math.abs(normalizeAngleRad(f1.direction - f2.direction));
  const directionScore = Math.max(0, 1 - dirDiff / Math.PI);
  
  const maxLen = Math.max(f1.length, f2.length, 1);
  const lenDiff = Math.abs(f1.length - f2.length) / maxLen;
  const lengthScore = Math.max(0, 1 - lenDiff);
  
  const totalScore = 
    typeScore * typeWeight +
    positionScore * positionWeight +
    directionScore * directionWeight +
    lengthScore * lengthWeight;
  
  return totalScore;
}

function normalizeAngleRad(angle: number): number {
  while (angle > Math.PI) angle -= 2 * Math.PI;
  while (angle < -Math.PI) angle += 2 * Math.PI;
  return angle;
}

function findMatchingStrokes(
  samples: CharacterStyle[],
  type: string,
  targetIndex: number,
  totalStrokes: number,
  bounds: { width: number; height: number }
): Stroke[] {
  const matches: Stroke[] = [];
  
  const targetCenterY = bounds.height * 0.1 + (bounds.height * 0.8) * (targetIndex + 1) / (totalStrokes + 1);
  const targetCenterX = bounds.width * 0.5;
  const targetFeature: StrokeFeature = {
    centerX: targetCenterX,
    centerY: targetCenterY,
    direction: type === 'vertical' ? Math.PI / 2 : type === 'diagonal-down' ? Math.PI / 4 : type === 'diagonal-up' ? -Math.PI / 4 : 0,
    length: bounds.width * 0.6,
    type,
    boundingBox: { minX: 0, maxX: bounds.width, minY: 0, maxY: bounds.height }
  };
  
  for (const sample of samples) {
    if (sample.strokes.length === 0) continue;
    
    const sampleFeatures = sample.strokes.map(s => extractStrokeFeature(s));
    
    let bestMatchIndex = 0;
    let bestScore = -Infinity;
    
    for (let i = 0; i < sampleFeatures.length; i++) {
      const score = computeStrokeSimilarity(targetFeature, sampleFeatures[i], bounds);
      if (score > bestScore) {
        bestScore = score;
        bestMatchIndex = i;
      }
    }
    
    if (bestScore > 0.5) {
      matches.push(sample.strokes[bestMatchIndex]);
    }
  }
  
  if (matches.length === 0) {
    for (const sample of samples) {
      for (const stroke of sample.strokes) {
        if (stroke.type === type) {
          matches.push(stroke);
          break;
        }
      }
    }
  }
  
  return matches;
}

function interpolateSampleStrokes(
  sampleStrokes: Stroke[],
  targetIndex: number,
  bounds: { width: number; height: number },
  styleFeatures: StyleFeatures
): Stroke {
  if (sampleStrokes.length === 0) {
    return generateStrokeByType('horizontal', targetIndex, 5, bounds, styleFeatures);
  }
  
  let baseStroke = sampleStrokes[0];
  
  if (sampleStrokes.length > 1) {
    let interpolated = baseStroke;
    for (let i = 1; i < sampleStrokes.length; i++) {
      const t = 1 / (i + 1);
      interpolated = interpolateStrokesSimple(interpolated, sampleStrokes[i], t);
    }
    baseStroke = interpolated;
  }
  
  return normalizeStrokeBounds(baseStroke, bounds.width, bounds.height);
}

function interpolateStrokesSimple(strokeA: Stroke, strokeB: Stroke, t: number): Stroke {
  const minLen = Math.min(strokeA.points.length, strokeB.points.length);
  
  const points = [];
  const thickness = [];
  
  for (let i = 0; i < minLen; i++) {
    const pA = strokeA.points[i];
    const pB = strokeB.points[i];
    points.push({
      x: pA.x * (1 - t) + pB.x * t,
      y: pA.y * (1 - t) + pB.y * t,
      speed: (pA.speed ?? 0.8) * (1 - t) + (pB.speed ?? 0.8) * t,
      pressure: (pA.pressure ?? 0.8) * (1 - t) + (pB.pressure ?? 0.8) * t
    });
    thickness.push(strokeA.thickness[i] * (1 - t) + strokeB.thickness[i] * t);
  }
  
  return {
    ...strokeA,
    points,
    thickness
  };
}

export function generateText(
  text: string,
  samples: CharacterStyle[],
  parameters: RenderParameters,
  charSize: { width: number; height: number } = { width: 200, height: 200 }
): GeneratedCharacter[] {
  const characters: GeneratedCharacter[] = [];
  
  for (const char of text) {
    if (char.trim() === '') {
      characters.push({
        character: char,
        strokes: [],
        styleId: 'space',
        svg: ''
      });
      continue;
    }
    
    const generated = generateCharacter(char, samples, parameters, charSize);
    characters.push(generated);
  }
  
  return characters;
}
