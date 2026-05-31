import type { WindParams } from '../types';

export class WindSystem {
  private params: WindParams = {
    strength: 0.3,
    frequency: 1.0,
    direction: [1, 0, 0.5]
  };

  private time: number = 0;

  setParams(params: Partial<WindParams>): void {
    this.params = { ...this.params, ...params };
  }

  getParams(): WindParams {
    return { ...this.params };
  }

  update(deltaTime: number): void {
    this.time += deltaTime * this.params.frequency;
  }

  getWindForceAtPosition(
    position: [number, number, number],
    height: number,
    windResistance: number
  ): [number, number, number] {
    const [dirX, dirY, dirZ] = this.params.direction;
    const len = Math.sqrt(dirX * dirX + dirY * dirY + dirZ * dirZ);
    const normDir = [dirX / len, dirY / len, dirZ / len];

    const turbulence = Math.sin(this.time * 3 + position[0] * 0.5) * 0.3 +
                       Math.sin(this.time * 5 + position[1] * 0.3) * 0.2;

    const heightFactor = 1 + height * 0.5;
    const strength = this.params.strength * (1 - windResistance * 0.5) * heightFactor;
    const gustFactor = 1 + Math.sin(this.time * 0.8) * 0.3 + turbulence * 0.2;

    const force = strength * gustFactor;

    return [
      normDir[0] * force,
      normDir[1] * force * 0.2,
      normDir[2] * force
    ];
  }

  getBranchBending(
    branchStart: [number, number, number],
    branchEnd: [number, number, number],
    depth: number,
    windResistance: number
  ): [number, number, number] {
    const midY = (branchStart[1] + branchEnd[1]) / 2;
    const force = this.getWindForceAtPosition(branchStart, midY, windResistance);
    
    const depthFactor = 1 + depth * 0.2;
    
    return [
      force[0] * depthFactor * 0.1,
      force[1] * depthFactor * 0.05,
      force[2] * depthFactor * 0.1
    ];
  }

  getLeafSway(
    _leafPosition: [number, number, number],
    rotation: number,
    time: number
  ): { rotationOffset: number; positionOffset: [number, number, number] } {
    const swayFreq = 2 + this.params.frequency * 3;
    const baseOffset = Math.sin(time * swayFreq + rotation) * this.params.strength * 0.3;
    
    return {
      rotationOffset: baseOffset * 0.5,
      positionOffset: [
        baseOffset * 0.1,
        Math.sin(time * swayFreq * 1.3 + rotation) * this.params.strength * 0.05,
        baseOffset * 0.1
      ]
    };
  }

  reset(): void {
    this.time = 0;
  }
}
