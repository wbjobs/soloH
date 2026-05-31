import { Point, Stroke, GraphNode, NodeType } from '../types';

const DIRECTIONS = [
  [-1, -1], [0, -1], [1, -1],
  [-1, 0],          [1, 0],
  [-1, 1],  [0, 1],  [1, 1]
];

export function buildGraph(
  skeleton: Uint8ClampedArray,
  width: number,
  height: number
): Map<string, GraphNode> {
  const nodes = new Map<string, GraphNode>();
  
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = y * width + x;
      if (skeleton[idx] !== 255) continue;
      
      const key = `${x},${y}`;
      const neighborCount = countNeighbors(skeleton, x, y, width, height);
      
      let type: NodeType;
      if (neighborCount === 1) {
        type = 'endpoint';
      } else if (neighborCount > 2) {
        type = 'junction';
      } else {
        type = 'normal';
      }
      
      nodes.set(key, {
        x,
        y,
        type,
        neighbors: [],
        visited: false
      });
    }
  }
  
  for (const [key, node] of nodes) {
    for (const [dx, dy] of DIRECTIONS) {
      const nx = node.x + dx;
      const ny = node.y + dy;
      const nKey = `${nx},${ny}`;
      const neighbor = nodes.get(nKey);
      if (neighbor) {
        node.neighbors.push(neighbor);
      }
    }
  }
  
  return nodes;
}

function countNeighbors(
  skeleton: Uint8ClampedArray,
  x: number,
  y: number,
  width: number,
  height: number
): number {
  let count = 0;
  for (const [dx, dy] of DIRECTIONS) {
    const nx = x + dx;
    const ny = y + dy;
    if (nx >= 0 && nx < width && ny >= 0 && ny < height) {
      if (skeleton[ny * width + nx] === 255) {
        count++;
      }
    }
  }
  return count;
}

export function extractStrokes(
  nodes: Map<string, GraphNode>,
  distanceMap: Float32Array,
  width: number
): Stroke[] {
  const strokes: Stroke[] = [];
  const nodeArray = Array.from(nodes.values());
  
  const endpoints = nodeArray.filter(n => n.type === 'endpoint');
  const junctions = nodeArray.filter(n => n.type === 'junction');
  
  const processed = new Set<string>();
  let strokeOrder = 0;
  
  for (const endpoint of endpoints) {
    const key = `${endpoint.x},${endpoint.y}`;
    if (processed.has(key)) continue;
    
    const stroke = traceStroke(endpoint, nodes, distanceMap, width, processed);
    if (stroke && stroke.points.length > 2) {
      stroke.order = strokeOrder++;
      strokes.push(stroke);
    }
  }
  
  for (const junction of junctions) {
    const key = `${junction.x},${junction.y}`;
    if (processed.has(key)) continue;
    
    for (const neighbor of junction.neighbors) {
      const nKey = `${neighbor.x},${neighbor.y}`;
      if (processed.has(nKey)) continue;
      
      const stroke = traceStroke(neighbor, nodes, distanceMap, width, processed);
      if (stroke && stroke.points.length > 2) {
        stroke.points.unshift({ x: junction.x, y: junction.y });
        stroke.order = strokeOrder++;
        strokes.push(stroke);
      }
    }
  }
  
  for (const node of nodeArray) {
    const key = `${node.x},${node.y}`;
    if (processed.has(key) || node.type !== 'normal') continue;
    
    const stroke = traceStroke(node, nodes, distanceMap, width, processed);
    if (stroke && stroke.points.length > 2) {
      stroke.order = strokeOrder++;
      strokes.push(stroke);
    }
  }
  
  const mergedStrokes = mergeConnectedStrokes(strokes);
  
  sortStrokesByWritingOrder(mergedStrokes);
  
  return mergedStrokes.map((stroke, index) => ({
    ...stroke,
    order: index,
    type: classifyStrokeType(stroke)
  }));
}

function mergeConnectedStrokes(strokes: Stroke[]): Stroke[] {
  if (strokes.length <= 1) return strokes;
  
  const merged: Stroke[] = [...strokes];
  let changed = true;
  let iterations = 0;
  const maxIterations = 10;
  
  while (changed && iterations < maxIterations) {
    changed = false;
    iterations++;
    
    for (let i = 0; i < merged.length; i++) {
      for (let j = i + 1; j < merged.length; j++) {
        const strokeA = merged[i];
        const strokeB = merged[j];
        
        if (shouldMergeStrokes(strokeA, strokeB)) {
          const mergedStroke = mergeTwoStrokes(strokeA, strokeB);
          merged.splice(j, 1);
          merged[i] = mergedStroke;
          changed = true;
          j--;
        }
      }
    }
  }
  
  return merged;
}

function shouldMergeStrokes(strokeA: Stroke, strokeB: Stroke): boolean {
  const pointsA = strokeA.points;
  const pointsB = strokeB.points;
  
  if (pointsA.length < 2 || pointsB.length < 2) return false;
  
  const aStart = pointsA[0];
  const aEnd = pointsA[pointsA.length - 1];
  const bStart = pointsB[0];
  const bEnd = pointsB[pointsB.length - 1];
  
  const distEndStart = distance(aEnd, bStart);
  const distStartEnd = distance(aStart, bEnd);
  const distEndEnd = distance(aEnd, bEnd);
  const distStartStart = distance(aStart, bStart);
  
  const minDist = Math.min(distEndStart, distStartEnd, distEndEnd, distStartStart);
  const mergeThreshold = 15;
  
  if (minDist > mergeThreshold) return false;
  
  const aDir = getStrokeDirection(strokeA);
  const bDir = getStrokeDirection(strokeB);
  
  let angleDiff = 0;
  if (distEndStart === minDist || distStartEnd === minDist) {
    angleDiff = Math.abs(normalizeAngle(aDir - bDir));
  } else if (distEndEnd === minDist) {
    angleDiff = Math.abs(normalizeAngle(aDir - (bDir + Math.PI)));
  } else {
    angleDiff = Math.abs(normalizeAngle((aDir + Math.PI) - bDir));
  }
  
  const angleThreshold = Math.PI / 3;
  return angleDiff < angleThreshold;
}

function mergeTwoStrokes(strokeA: Stroke, strokeB: Stroke): Stroke {
  const pointsA = strokeA.points;
  const pointsB = strokeB.points;
  const thickA = strokeA.thickness;
  const thickB = strokeB.thickness;
  
  const aStart = pointsA[0];
  const aEnd = pointsA[pointsA.length - 1];
  const bStart = pointsB[0];
  const bEnd = pointsB[pointsB.length - 1];
  
  const distEndStart = distance(aEnd, bStart);
  const distStartEnd = distance(aStart, bEnd);
  const distEndEnd = distance(aEnd, bEnd);
  const distStartStart = distance(aStart, bStart);
  
  const minDist = Math.min(distEndStart, distStartEnd, distEndEnd, distStartStart);
  
  let mergedPoints: Point[];
  let mergedThickness: number[];
  
  if (distEndStart === minDist) {
    mergedPoints = [...pointsA, ...pointsB.slice(1)];
    mergedThickness = [...thickA, ...thickB.slice(1)];
  } else if (distStartEnd === minDist) {
    mergedPoints = [...pointsB, ...pointsA.slice(1)];
    mergedThickness = [...thickB, ...thickA.slice(1)];
  } else if (distEndEnd === minDist) {
    const reversedB = [...pointsB].reverse();
    const reversedBThick = [...thickB].reverse();
    mergedPoints = [...pointsA, ...reversedB.slice(1)];
    mergedThickness = [...thickA, ...reversedBThick.slice(1)];
  } else {
    const reversedA = [...pointsA].reverse();
    const reversedAThick = [...thickA].reverse();
    mergedPoints = [...reversedA, ...pointsB.slice(1)];
    mergedThickness = [...reversedAThick, ...thickB.slice(1)];
  }
  
  const simplified = simplifyStroke(mergedPoints, 1.5);
  
  const simplifiedThickness: number[] = [];
  for (let i = 0; i < simplified.length; i++) {
    const nearestIdx = findNearestPointIndex(simplified[i], mergedPoints);
    simplifiedThickness.push(mergedThickness[nearestIdx]);
  }
  
  return {
    id: `stroke-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    points: simplified,
    thickness: simplifiedThickness,
    order: Math.min(strokeA.order, strokeB.order),
    type: strokeA.type
  };
}

function distance(p1: Point, p2: Point): number {
  return Math.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2);
}

function getStrokeDirection(stroke: Stroke): number {
  const points = stroke.points;
  if (points.length < 2) return 0;
  
  const start = points[0];
  const end = points[points.length - 1];
  return Math.atan2(end.y - start.y, end.x - start.x);
}

function normalizeAngle(angle: number): number {
  while (angle > Math.PI) angle -= 2 * Math.PI;
  while (angle < -Math.PI) angle += 2 * Math.PI;
  return angle;
}

function findNearestPointIndex(target: Point, points: Point[]): number {
  let minDist = Infinity;
  let minIdx = 0;
  
  for (let i = 0; i < points.length; i++) {
    const dist = distance(target, points[i]);
    if (dist < minDist) {
      minDist = dist;
      minIdx = i;
    }
  }
  
  return minIdx;
}

function traceStroke(
  startNode: GraphNode,
  nodes: Map<string, GraphNode>,
  distanceMap: Float32Array,
  width: number,
  processed: Set<string>
): Stroke | null {
  const points: Point[] = [];
  const thickness: number[] = [];
  let current: GraphNode | null = startNode;
  let prev: GraphNode | null = null;
  
  while (current) {
    const key = `${current.x},${current.y}`;
    if (processed.has(key)) break;
    
    processed.add(key);
    points.push({ x: current.x, y: current.y });
    thickness.push(distanceMap[current.y * width + current.x]);
    
    const unvisited = current.neighbors.filter(n => !processed.has(`${n.x},${n.y}`));
    
    if (unvisited.length === 0) {
      break;
    }
    
    let next = unvisited[0];
    if (unvisited.length > 1 && prev) {
      let minAngle = Infinity;
      const prevDir = {
        dx: current.x - prev.x,
        dy: current.y - prev.y
      };
      
      for (const candidate of unvisited) {
        const nextDir = {
          dx: candidate.x - current.x,
          dy: candidate.y - current.y
        };
        
        const angle = angleBetween(prevDir, nextDir);
        if (angle < minAngle) {
          minAngle = angle;
          next = candidate;
        }
      }
    }
    
    prev = current;
    current = next;
  }
  
  if (points.length < 2) return null;
  
  return {
    id: `stroke-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    points,
    thickness,
    order: 0,
    type: 'unknown'
  };
}

function angleBetween(
  v1: { dx: number; dy: number },
  v2: { dx: number; dy: number }
): number {
  const dot = v1.dx * v2.dx + v1.dy * v2.dy;
  const mag1 = Math.sqrt(v1.dx * v1.dx + v1.dy * v1.dy);
  const mag2 = Math.sqrt(v2.dx * v2.dx + v2.dy * v2.dy);
  const cos = Math.max(-1, Math.min(1, dot / (mag1 * mag2)));
  return Math.acos(cos);
}

function sortStrokesByWritingOrder(strokes: Stroke[]): void {
  strokes.sort((a, b) => {
    const aStart = a.points[0];
    const bStart = b.points[0];
    
    if (Math.abs(aStart.y - bStart.y) > 20) {
      return aStart.y - bStart.y;
    }
    
    return aStart.x - bStart.x;
  });
}

function classifyStrokeType(stroke: Stroke): string {
  if (stroke.points.length < 2) return 'dot';
  
  const start = stroke.points[0];
  const end = stroke.points[stroke.points.length - 1];
  
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.sqrt(dx * dx + dy * dy);
  
  if (length < 10) return 'dot';
  
  const angle = Math.atan2(dy, dx) * 180 / Math.PI;
  
  const totalLength = calculatePathLength(stroke.points);
  const straightness = length / totalLength;
  
  if (straightness > 0.9) {
    if (Math.abs(angle) < 15 || Math.abs(angle) > 165) return 'horizontal';
    if (Math.abs(angle - 90) < 15 || Math.abs(angle + 90) < 15) return 'vertical';
    if (angle > 15 && angle < 75) return 'diagonal-down';
    if (angle > -75 && angle < -15) return 'diagonal-up';
    return 'line';
  }
  
  if (hasSharpTurns(stroke.points)) {
    return 'turn';
  }
  
  return 'curve';
}

function calculatePathLength(points: Point[]): number {
  let length = 0;
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x;
    const dy = points[i].y - points[i - 1].y;
    length += Math.sqrt(dx * dx + dy * dy);
  }
  return length;
}

function hasSharpTurns(points: Point[]): boolean {
  for (let i = 2; i < points.length; i++) {
    const v1 = {
      dx: points[i - 1].x - points[i - 2].x,
      dy: points[i - 1].y - points[i - 2].y
    };
    const v2 = {
      dx: points[i].x - points[i - 1].x,
      dy: points[i].y - points[i - 1].y
    };
    
    const angle = angleBetween(v1, v2) * 180 / Math.PI;
    if (angle > 45) return true;
  }
  return false;
}

export function simplifyStroke(points: Point[], tolerance: number = 2): Point[] {
  if (points.length <= 2) return points;
  
  let maxDist = 0;
  let maxIndex = 0;
  const start = points[0];
  const end = points[points.length - 1];
  
  for (let i = 1; i < points.length - 1; i++) {
    const dist = perpendicularDistance(points[i], start, end);
    if (dist > maxDist) {
      maxDist = dist;
      maxIndex = i;
    }
  }
  
  if (maxDist > tolerance) {
    const left = simplifyStroke(points.slice(0, maxIndex + 1), tolerance);
    const right = simplifyStroke(points.slice(maxIndex), tolerance);
    return [...left.slice(0, -1), ...right];
  }
  
  return [start, end];
}

function perpendicularDistance(point: Point, start: Point, end: Point): number {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  
  if (dx === 0 && dy === 0) {
    return Math.sqrt((point.x - start.x) ** 2 + (point.y - start.y) ** 2);
  }
  
  const t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy);
  
  let nearestX, nearestY;
  if (t < 0) {
    nearestX = start.x;
    nearestY = start.y;
  } else if (t > 1) {
    nearestX = end.x;
    nearestY = end.y;
  } else {
    nearestX = start.x + t * dx;
    nearestY = start.y + t * dy;
  }
  
  return Math.sqrt((point.x - nearestX) ** 2 + (point.y - nearestY) ** 2);
}

export function addSpeedAndPressure(stroke: Stroke): Stroke {
  const points = stroke.points;
  const newPoints: Point[] = [];
  
  for (let i = 0; i < points.length; i++) {
    let speed = 1;
    let pressure = 0.8;
    
    if (i > 0 && i < points.length - 1) {
      const prev = points[i - 1];
      const curr = points[i];
      const next = points[i + 1];
      
      const v1 = { dx: curr.x - prev.x, dy: curr.y - prev.y };
      const v2 = { dx: next.x - curr.x, dy: next.y - curr.y };
      const angle = angleBetween(v1, v2);
      
      speed = 1 - (angle / Math.PI) * 0.5;
      pressure = 0.5 + (stroke.thickness[i] / 10) * 0.5;
    } else if (i === 0) {
      pressure = 0.3;
      speed = 0.5;
    } else {
      pressure = 0.4;
      speed = 0.7;
    }
    
    newPoints.push({
      ...points[i],
      speed,
      pressure
    });
  }
  
  return {
    ...stroke,
    points: newPoints
  };
}
