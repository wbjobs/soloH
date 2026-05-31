import type {
  LSystemConfig,
  EnvironmentParams,
  TurtleState,
  BranchSegment,
  LeafData,
  PlantData,
  GrowthModifier
} from '../types';
import { LSystemParser } from './LSystemParser';

export interface InterpretationOptions {
  tropismBias?: [number, number, number];
  tropismStrength?: number;
  ageFactor?: number;
  maxDepth?: number;
}

export class TurtleInterpreter {
  private toRadians(deg: number): number {
    return deg * (Math.PI / 180);
  }

  normalize(v: [number, number, number]): [number, number, number] {
    const len = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    if (len === 0) return [0, 0, 0];
    return [v[0] / len, v[1] / len, v[2] / len];
  }

  cross(a: [number, number, number], b: [number, number, number]): [number, number, number] {
    return [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0]
    ];
  }

  add(a: [number, number, number], b: [number, number, number]): [number, number, number] {
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  }

  scale(v: [number, number, number], s: number): [number, number, number] {
    return [v[0] * s, v[1] * s, v[2] * s];
  }

  rotateAroundAxis(
    v: [number, number, number],
    axis: [number, number, number],
    angle: number
  ): [number, number, number] {
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    const oneMinusCos = 1 - cos;

    const [ax, ay, az] = axis;
    const [vx, vy, vz] = v;

    const m00 = cos + ax * ax * oneMinusCos;
    const m01 = ax * ay * oneMinusCos - az * sin;
    const m02 = ax * az * oneMinusCos + ay * sin;

    const m10 = ay * ax * oneMinusCos + az * sin;
    const m11 = cos + ay * ay * oneMinusCos;
    const m12 = ay * az * oneMinusCos - ax * sin;

    const m20 = az * ax * oneMinusCos - ay * sin;
    const m21 = az * ay * oneMinusCos + ax * sin;
    const m22 = cos + az * az * oneMinusCos;

    return [
      m00 * vx + m01 * vy + m02 * vz,
      m10 * vx + m11 * vy + m12 * vz,
      m20 * vx + m21 * vy + m22 * vz
    ];
  }

  interpret(
    lstring: string,
    _config: LSystemConfig,
    modifier: GrowthModifier,
    options: InterpretationOptions = {}
  ): PlantData {
    const branches: BranchSegment[] = [];
    const leaves: LeafData[] = [];
    const stack: TurtleState[] = [];

    const {
      tropismBias = [0, 0, 0],
      tropismStrength = 0.3,
      ageFactor = 1,
      maxDepth = 50
    } = options;

    const state: TurtleState = {
      position: [0, 0, 0],
      direction: [0, 1, 0],
      heading: 0,
      up: [0, 0, 1],
      right: [1, 0, 0],
      radius: modifier.trunkRadius,
      depth: 0
    };

    const angleRad = this.toRadians(modifier.branchAngle);

    for (let i = 0; i < lstring.length; i++) {
      const symbol = lstring[i];

      switch (symbol) {
        case 'F':
        case 'A':
        case 'B':
        case 'C': {
          const start = [...state.position] as [number, number, number];
          
          if (state.depth < maxDepth && tropismStrength > 0) {
            state.direction = this.applyTropism(
              state.direction,
              tropismBias,
              tropismStrength,
              state.depth,
              maxDepth
            );
            state.direction = this.normalize(state.direction);
            
            this.updateBasisVectors(state);
          }
          
          const stepLength = modifier.stepLength * ageFactor;
          const step = this.scale(state.direction, stepLength);
          state.position = this.add(state.position, step);

          branches.push({
            start,
            end: [...state.position] as [number, number, number],
            radius: state.radius * ageFactor,
            depth: state.depth
          });

          state.radius *= 0.98;
          state.depth++;
          break;
        }

        case '+':
          state.direction = this.rotateAroundAxis(state.direction, state.up, angleRad);
          state.right = this.rotateAroundAxis(state.right, state.up, angleRad);
          break;

        case '-':
          state.direction = this.rotateAroundAxis(state.direction, state.up, -angleRad);
          state.right = this.rotateAroundAxis(state.right, state.up, -angleRad);
          break;

        case '&':
          state.direction = this.rotateAroundAxis(state.direction, state.right, angleRad);
          state.up = this.rotateAroundAxis(state.up, state.right, angleRad);
          break;

        case '^':
          state.direction = this.rotateAroundAxis(state.direction, state.right, -angleRad);
          state.up = this.rotateAroundAxis(state.up, state.right, -angleRad);
          break;

        case '\\':
          state.direction = this.rotateAroundAxis(state.direction, state.direction, angleRad);
          state.up = this.rotateAroundAxis(state.up, state.direction, angleRad);
          break;

        case '/':
          state.direction = this.rotateAroundAxis(state.direction, state.direction, -angleRad);
          state.up = this.rotateAroundAxis(state.up, state.direction, -angleRad);
          break;

        case '|':
          state.direction = this.rotateAroundAxis(state.direction, state.up, Math.PI);
          state.right = this.rotateAroundAxis(state.right, state.up, Math.PI);
          break;

        case '[':
          stack.push({
            position: [...state.position] as [number, number, number],
            direction: [...state.direction] as [number, number, number],
            heading: state.heading,
            up: [...state.up] as [number, number, number],
            right: [...state.right] as [number, number, number],
            radius: state.radius,
            depth: state.depth
          });
          break;

        case ']': {
          const popped = stack.pop();
          if (popped) {
            leaves.push({
              position: [...state.position] as [number, number, number],
              direction: [...state.direction] as [number, number, number],
              size: modifier.leafSize * (0.7 + Math.random() * 0.6) * ageFactor,
              rotation: Math.random() * Math.PI * 2,
              depth: state.depth
            });
            Object.assign(state, popped);
          }
          break;
        }

        case 'L':
          leaves.push({
            position: [...state.position] as [number, number, number],
            direction: [...state.direction] as [number, number, number],
            size: modifier.leafSize * (0.7 + Math.random() * 0.6) * ageFactor,
            rotation: Math.random() * Math.PI * 2,
            depth: state.depth
          });
          break;
      }
    }

    return { branches, leaves, lstring };
  }

  private applyTropism(
    direction: [number, number, number],
    tropismBias: [number, number, number],
    strength: number,
    depth: number,
    maxDepth: number
  ): [number, number, number] {
    const depthFactor = 1 - (depth / maxDepth);
    const effectiveStrength = strength * depthFactor * depthFactor;
    
    if (effectiveStrength < 0.001) return direction;
    
    const bias: [number, number, number] = [
      tropismBias[0] * effectiveStrength,
      tropismBias[1] * effectiveStrength,
      tropismBias[2] * effectiveStrength
    ];
    
    let result: [number, number, number] = [
      direction[0] + bias[0],
      direction[1] + bias[1],
      direction[2] + bias[2]
    ];
    
    result = this.normalize(result);
    
    result[1] = Math.max(0.05, result[1]);
    
    return this.normalize(result);
  }

  private updateBasisVectors(state: TurtleState): void {
    const dir = state.direction;
    
    const worldUp: [number, number, number] = [0, 1, 0];
    let right = this.cross(worldUp, dir);
    
    if (Math.abs(right[0]) + Math.abs(right[1]) + Math.abs(right[2]) < 0.001) {
      right = [1, 0, 0];
    }
    
    state.right = this.normalize(right);
    state.up = this.normalize(this.cross(dir, state.right));
  }

  generatePlant(
    config: LSystemConfig,
    environment: EnvironmentParams,
    iterations: number,
    onProgress?: (progress: number) => void,
    options: InterpretationOptions = {}
  ): PlantData {
    const modifier = LSystemParser.applyEnvironmentModifiers(config, environment);
    
    const ageFactor = options.ageFactor ?? 1;
    const effectiveIterations = Math.max(1, Math.floor(iterations * modifier.growthRate * ageFactor));
    
    const lstring = LSystemParser.generate(config, effectiveIterations, (p) => {
      if (onProgress) onProgress(p * 0.7);
    });

    if (onProgress) onProgress(0.8);

    const plantData = this.interpret(lstring, config, modifier, options);

    if (onProgress) onProgress(1);

    return plantData;
  }
}
