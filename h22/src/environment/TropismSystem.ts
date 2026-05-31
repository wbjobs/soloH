import type { TropismParams, PlantInstance, TurtleState } from '../types';
import { Vector3 } from '@babylonjs/core/Maths/math.vector';

export class TropismSystem {
  private params: TropismParams = {
    phototropism: 0.6,
    hydrotropism: 0.4,
    strength: 0.3
  };

  private lightDirection: Vector3 = new Vector3(-0.3, -1, -0.3).normalize();
  private waterSource: Vector3 | null = null;

  setParams(params: Partial<TropismParams>): void {
    this.params = { ...this.params, ...params };
  }

  getParams(): TropismParams {
    return { ...this.params };
  }

  setLightDirection(direction: [number, number, number]): void {
    this.lightDirection = new Vector3(direction[0], direction[1], direction[2]).normalize();
  }

  setWaterSource(position: [number, number, number] | null): void {
    this.waterSource = position ? new Vector3(position[0], position[1], position[2]) : null;
  }

  calculateTropismBias(
    plantPosition: [number, number, number],
    turtleState: TurtleState,
    _plants: PlantInstance[]
  ): [number, number, number] {
    const currentDir = new Vector3(
      turtleState.direction[0],
      turtleState.direction[1],
      turtleState.direction[2]
    ).normalize();

    const pos = new Vector3(plantPosition[0], plantPosition[1], plantPosition[2]);

    const photoBias = this.calculatePhototropism(pos, currentDir);
    const hydroBias = this.calculateHydrotropism(pos, currentDir);

    const totalBias = photoBias.scale(this.params.phototropism)
      .add(hydroBias.scale(this.params.hydrotropism))
      .scale(this.params.strength);

    return [totalBias.x, totalBias.y, totalBias.z];
  }

  private calculatePhototropism(_plantPos: Vector3, currentDir: Vector3): Vector3 {
    const lightDir = this.lightDirection.clone().negate();
    
    const skyExposure = Math.max(0, Vector3.Dot(currentDir, new Vector3(0, 1, 0)));
    const lightAlignment = Math.max(0, Vector3.Dot(currentDir, lightDir));
    
    const bias = lightDir.scale(lightAlignment * 0.7)
      .add(new Vector3(0, 1, 0).scale(skyExposure * 0.3));
    
    return bias.normalize();
  }

  private calculateHydrotropism(plantPos: Vector3, currentDir: Vector3): Vector3 {
    if (!this.waterSource) {
      return new Vector3(0, 0, 0);
    }

    const toWater = this.waterSource.subtract(plantPos);
    const distance = toWater.length();
    
    if (distance < 0.1) {
      return new Vector3(0, 0, 0);
    }

    const distanceFactor = Math.max(0, 1 - distance / 20);
    const dirToWater = toWater.normalize();
    
    const horizontalDir = new Vector3(dirToWater.x, 0, dirToWater.z).normalize();
    const heightFactor = Math.max(0, 1 - currentDir.y * 0.5);
    
    return horizontalDir.scale(distanceFactor * heightFactor);
  }

  applyTropismToDirection(
    currentDir: [number, number, number],
    tropismBias: [number, number, number],
    weight: number
  ): [number, number, number] {
    const dir = new Vector3(currentDir[0], currentDir[1], currentDir[2]);
    const bias = new Vector3(tropismBias[0], tropismBias[1], tropismBias[2]);
    
    const result = dir.add(bias.scale(weight)).normalize();
    
    return [result.x, Math.max(0.1, result.y), result.z];
  }

  getGrowthDirectionModifier(
    plantPos: [number, number, number],
    depth: number,
    maxDepth: number
  ): [number, number, number] {
    const depthFactor = 1 - (depth / maxDepth);
    const tropismStrength = this.params.strength * depthFactor;

    const photoBias = this.params.phototropism * tropismStrength;
    const hydroBias = this.params.hydrotropism * tropismStrength * 0.5;

    const lightDir = this.lightDirection.clone().negate();
    let waterDir = new Vector3(0, 0, 0);
    
    if (this.waterSource) {
      waterDir = this.waterSource.subtract(
        new Vector3(plantPos[0], plantPos[1], plantPos[2])
      ).normalize();
    }

    const result = lightDir.scale(photoBias)
      .add(waterDir.scale(hydroBias))
      .add(new Vector3(0, 1, 0).scale(0.3 * tropismStrength));

    const normalized = result.normalize();
    
    return [normalized.x, normalized.y, normalized.z];
  }

  calculateLightExposure(
    position: [number, number, number],
    normal: [number, number, number],
    plants: PlantInstance[]
  ): number {
    const pos = new Vector3(position[0], position[1], position[2]);
    const norm = new Vector3(normal[0], normal[1], normal[2]).normalize();
    
    let shadeFactor = 0;
    const lightDir = this.lightDirection.clone().negate();
    
    for (const plant of plants) {
      if (!plant.isAlive || plant.growthProgress < 0.3) continue;
      
      const plantPos = new Vector3(plant.position[0], plant.position[1], plant.position[2]);
      const toPlant = plantPos.subtract(pos);
      const dist = toPlant.length();
      
      if (dist < 0.5 || dist > 15) continue;
      
      const toPlantDir = toPlant.normalize();
      const alignment = Vector3.Dot(lightDir, toPlantDir);
      
      if (alignment > 0.7) {
        const radiusFactor = plant.crownRadius / Math.max(1, dist);
        shadeFactor += alignment * radiusFactor * plant.growthProgress;
      }
    }
    
    const directLight = Math.max(0, Vector3.Dot(norm, lightDir));
    const ambient = 0.3;
    
    return Math.max(ambient, directLight * (1 - Math.min(0.9, shadeFactor)));
  }
}
